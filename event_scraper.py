"""
Event Scraper for What's On Glasgow
Parses live events from https://www.whatsonglasgow.co.uk/events/
"""

import re
import os
import json
import csv
from typing import List, Dict, Optional, Set
from pathlib import Path
from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup


class GlasgowEventScraper:
    """Scrapes and parses events from What's On Glasgow website"""
    
    BASE_URL = "https://www.whatsonglasgow.co.uk"
    EVENTS_URL = f"{BASE_URL}/events/"
    CACHE_FILE = "events_cache.csv"
    CACHE_MAX_AGE_HOURS = 24
    # Canonical top-level categories (lowercase) - match site structure
    CATEGORY_MAP = {
        # Direct mappings for site's actual categories
        "music": "music",
        "theatre": "theatre",
        "film": "film",
        "comedy": "comedy",
        "tour": "tour",
        "tours": "tour",
        "exhibitions": "exhibitions",
        "sport": "sport",
        "sports": "sport",
        "food-and-drink": "food-and-drink",
        "family-and-kids": "family-and-kids",
        "family-&-kids": "family-and-kids",
        "family": "family-and-kids",
        "kids": "family-and-kids",
        "workshops": "workshops",
        "gaming": "gaming",
        "arts-and-crafts": "arts-and-crafts",
        "active": "active",
        "nature": "nature",
        "nights-out": "nights-out",
        "nightlife": "nights-out",
        "days-out": "days-out",
        "outdoor": "outdoor",
        "talks-and-lectures": "talks-and-lectures",
        "health-and-wellbeing": "health-and-wellbeing",
        "community": "community",
        "festivals": "festivals",
        "shopping": "shopping",
        "history": "history",
        "learning": "learning",
        # Common synonyms
        "theater": "theatre",
        "cinema": "film",
        "gigs": "music",
        "concerts": "music",
        "food": "food-and-drink",
        "drink": "food-and-drink",
    }
    
    def __init__(self):
        self.http_client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        # Simple in-memory cache for event detail pages to avoid refetching
        self._detail_cache = {}
        # Debug logging toggle (env-driven)
        self.debug = str(os.getenv("EVENT_SCRAPER_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}
    
    def fetch_events_page(self, url: Optional[str] = None) -> str:
        """Fetch the events page HTML"""
        target_url = url or self.EVENTS_URL
        print(f"Fetching: {target_url}")
        
        try:
            response = self.http_client.get(target_url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching page: {e}")
            return ""
    
    def parse_event_date(self, date_str: str) -> Optional[str]:
        """Parse and normalize event date strings"""
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Handle "Selected dates between X - Y" format
        if "Selected dates between" in date_str:
            match = re.search(r'between\s+(.+?)\s+-\s+(.+?)$', date_str)
            if match:
                return f"{match.group(1)} - {match.group(2)}"
        
        # Handle "X - Y" date range format
        if ' - ' in date_str:
            return date_str
        
        # Handle single date
        return date_str
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text
    
    def extract_event_category(self, text: str) -> Optional[str]:
        """Extract category from event title or description"""
        # Categories typically appear as uppercase tags
        category_pattern = r'\b([A-Z\s&]+)$'
        match = re.search(category_pattern, text)
        if match:
            category = match.group(1).strip()
            # Filter out common non-category text
            if len(category) > 2 and category not in ["READ MORE", "CLICK HERE"]:
                return category
        return None

    def fetch_event_detail(self, event_url: str) -> str:
        """Fetch and cache individual event detail page HTML."""
        if not event_url:
            return ""
        if event_url in self._detail_cache:
            return self._detail_cache[event_url]
        try:
            r = self.http_client.get(event_url)
            r.raise_for_status()
            html = r.text
            # cache only if reasonable length
            if html and len(html) > 200:
                self._detail_cache[event_url] = html
            return html
        except Exception as e:
            print(f"Error fetching event detail: {e} -> {event_url}")
            return ""

    def _normalize_category(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        s = self.clean_text(raw)
        # Remove trailing words like 'Events', 'in Glasgow' if present
        s = re.sub(r"\b(events?|in glasgow)\b", "", s, flags=re.I)
        s = re.sub(r"\s+/\s+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        if not s:
            return None
        # Title case common categories
        return s[:1].upper() + s[1:]

    def parse_categories_from_detail(self, html: str) -> List[str]:
        """Parse categories from an event detail page.

        Strategy: Look for the FIRST few /events/<cat>/ links that appear
        BEFORE the main navigation menu. These are typically breadcrumb or
        category badge links specific to this event.
        
        The main nav menu will have ALL categories, but event-specific category
        links appear earlier in the DOM, near the event title/metadata.
        """
        if not html:
            return []
        
        cats: Set[str] = set()
        
        # Find where navigation menu starts (to avoid extracting all categories)
        nav_markers = [
            'all-events-in-glasgow',
            'btn btn-sm mb-1',
            'class="btn btn-sm'
        ]
        nav_start_pos = len(html)
        for marker in nav_markers:
            pos = html.find(marker)
            if pos != -1 and pos < nav_start_pos:
                nav_start_pos = pos
        
        # Only search HTML before navigation menu
        search_html = html[:nav_start_pos]
        
        # Extract category tokens from event-specific section
        import re
        seen_tokens = []
        skip_tokens = ('all-events', 'this-weekend', 'burns-night', 'february-half-term', 
                       'valentines', 'easter-holiday', 'summer-holiday', 'october-half-term',
                       'halloween', 'bonfire-night', 'christmas', 'hogmanay', 
                       "what's-on", "what's-on-today", 'today')
        
        for match in re.finditer(r'href=["\']?[^"\']*?/events/([^/?#"\'>]+)/?["\']?', search_html, re.IGNORECASE):
            token = match.group(1).strip().lower().replace('_', '-').replace(' ', '-')
            # Skip generic/nav tokens
            if token in skip_tokens:
                continue
            if token not in seen_tokens:
                seen_tokens.append(token)
            # Take first few unique tokens (event-specific)
            if len(seen_tokens) >= 5:
                break
        
        if self.debug:
            try:
                print(f"    [detail parse] Navigation menu starts at position: {nav_start_pos}")
                print(f"    [detail parse] Input HTML length: {len(html)} bytes")
                print(f"    [detail parse] seen_tokens: {seen_tokens}")
            except Exception:
                pass
        
        # Map tokens to canonical categories
        mapped_count = 0
        for token in seen_tokens:
            canon = self.CATEGORY_MAP.get(token)
            if canon:
                cats.add(canon)
                mapped_count += 1
        
        if self.debug:
            try:
                print(f"    [detail parse] mapped {mapped_count} tokens to categories: {sorted(cats)}")
            except Exception:
                pass
        
        # Meta section fallback
        try:
            soup = BeautifulSoup(html, 'html.parser')
            meta = soup.find('meta', attrs={'property': 'article:section'})
            if meta and meta.get('content'):
                token = self._normalize_category(meta['content'])
                if token:
                    t = token.lower().replace(' & ', ' and ').replace(' ', '-')
                    canon = self.CATEGORY_MAP.get(t)
                    if canon:
                        cats.add(canon)
        except Exception:
            pass
        
        # Return up to 3 sorted categories
        if cats:
            return sorted(cats)[:3]
        return []
    
    def parse_events_from_html(self, html: str) -> List[Dict]:
        """Parse events from the events listing page HTML"""
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all event links on the page
        event_links = soup.find_all('a', href=re.compile(r'/event/\d+'))
        
        events = []
        print(f"Found {len(event_links)} event links")
        
        for link in event_links:
            try:
                # Extract URL
                event_url = link.get('href', '')
                if not event_url.startswith('http'):
                    event_url = self.BASE_URL + event_url
        
                # Extract title from the link text or nested h4/h3
                title_elem = link.find(['h4', 'h3'])
                if title_elem:
                    title = self.clean_text(title_elem.get_text())
                else:
                    title = self.clean_text(link.get_text())
                
                # Skip if title is empty or just "READ MORE"
                if not title or title == "READ MORE":
                    continue
                
                # Find parent container to get more details
                parent = link.find_parent(['div', 'article', 'section'])
                
                # Extract date (look for date patterns in parent)
                date = None
                venue = None
                description = None
                image_url = None
                categories: Set[str] = set()
                listing_raw_tokens: List[str] = []
                
                if parent:
                    # Look for event image
                    img_elem = parent.find('img')
                    if img_elem:
                        img_src = img_elem.get('src') or img_elem.get('data-src')
                        if img_src:
                            # Make absolute URL if relative
                            if img_src.startswith('//'):
                                image_url = 'https:' + img_src
                            elif img_src.startswith('/'):
                                image_url = self.BASE_URL + img_src
                            elif img_src.startswith('http'):
                                image_url = img_src
                    
                    # Look for date text (typically before venue)
                    text_content = parent.get_text()
                    
                    # Try to find date patterns
                    date_patterns = [
                        r'(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}(?:\s+-\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})?)',
                        r'Selected dates between.+?\d{4}',
                        r'\d{1,2}/\d{1,2}/\d{4}'
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, text_content)
                        if match:
                            date = self.parse_event_date(match.group(0))
                            break
                    
                    # Look for venue (typically in a link with /listings/)
                    venue_link = parent.find('a', href=re.compile(r'/listings/'))
                    if venue_link:
                        venue = self.clean_text(venue_link.get_text())
                    
                    # Get description (usually in a <p> tag or after the title)
                    desc_elem = parent.find('p')
                    if desc_elem:
                        description = self.clean_text(desc_elem.get_text())
                    
                    # Try to extract categories from listing card via /events/<category>/ links
                    try:
                        for a in parent.find_all('a', href=True):
                            href = a['href']
                            href_path = href.split(self.BASE_URL)[-1] if href.startswith('http') else href
                            m = re.search(r"/events/([^/?#]+)/", href_path)
                            if m:
                                token = m.group(1).strip().lower()
                                token = token.replace('_', '-').replace(' ', '-')
                                listing_raw_tokens.append(token)
                                canon = self.CATEGORY_MAP.get(token)
                                if canon:
                                    categories.add(canon)
                    except Exception:
                        pass
                
                # Create event object
                event = {
                    'title': title,
                    'date': date or "Date TBA",
                    'venue': venue or "Venue TBA",
                    'description': description or "No description available",
                    'url': event_url,
                    'image_url': image_url or ""
                }
                
                detail_raw_tokens: List[str] = []
                # If no categories found in listing, fetch detail page for accurate category
                if not categories:
                    detail_html = self.fetch_event_detail(event_url)
                    detail_cats = self.parse_categories_from_detail(detail_html)
                    for c in detail_cats:
                        categories.add(c)
                    # Debug: also collect raw tokens from detail anchors
                    if self.debug and detail_html:
                        try:
                            for m in re.finditer(r"/events/([^/?#]+)/", detail_html):
                                tok = m.group(1).strip().lower().replace('_', '-').replace(' ', '-')
                                if tok not in detail_raw_tokens:
                                    detail_raw_tokens.append(tok)
                        except Exception:
                            pass

                # Finalize categories
                if categories:
                    ordered = sorted(categories)
                    event['category'] = ordered[0]
                    event['categories'] = ordered
                else:
                    event['category'] = 'general'
                    event['categories'] = ['general']

                # Emit raw debug line if enabled
                if self.debug:
                    try:
                        debug_line = {
                            "title": event.get("title"),
                            "url": event.get("url"),
                            "listing_raw_tokens": listing_raw_tokens,
                            "detail_raw_tokens": detail_raw_tokens,
                            "final_categories": event.get("categories"),
                        }
                        print(json.dumps({"event_debug": debug_line}, ensure_ascii=False))
                    except Exception:
                        pass

                events.append(event)
                
            except Exception as e:
                print(f"Error parsing event: {e}")
                continue
        
        return events
    
    def deduplicate_events(self, events: List[Dict]) -> List[Dict]:
        """Remove duplicate events based on title and URL"""
        seen = set()
        unique_events = []
        
        for event in events:
            # Create a unique key from title and URL
            key = (event['title'], event['url'])
            
            if key not in seen:
                seen.add(key)
                unique_events.append(event)
        
        return unique_events
    
    def get_todays_events(self) -> List[Dict]:
        """Fetch and parse today's events from the website"""
        print("Fetching today's events from What's On Glasgow...")
        
        html = self.fetch_events_page()
        if not html:
            print("Failed to fetch events page")
            return []
        
        events = self.parse_events_from_html(html)
        events = self.deduplicate_events(events)
        
        print(f"Successfully parsed {len(events)} unique events")
        return events
    
    def filter_events_by_category(self, events: List[Dict], category: str) -> List[Dict]:
        """Filter events by top-level category (supports both 'category' and 'categories')."""
        key = (category or "").strip().lower()
        if not key:
            return events
        out: List[Dict] = []
        for e in events:
            primary = (e.get('category') or '').strip().lower()
            if primary == key:
                out.append(e)
                continue
            multi = e.get('categories') or []
            if any(isinstance(x, str) and x.strip().lower() == key for x in multi):
                out.append(e)
        return out
    
    def filter_events_by_venue(self, events: List[Dict], venue: str) -> List[Dict]:
        """Filter events by venue"""
        return [e for e in events if venue.lower() in e.get('venue', '').lower()]
    
    def filter_events_today(self, events: List[Dict]) -> List[Dict]:
        """Filter events happening today (October 25, 2025)"""
        today_str = "25th October 2025"
        today_variations = ["25th October 2025", "25 October 2025", "October 25 2025"]
        
        filtered = []
        for event in events:
            date_str = event.get('date', '')
            
            # Check if today's date is in the date string
            if any(today in date_str for today in today_variations):
                filtered.append(event)
            # Check for date ranges that include today
            elif ' - ' in date_str:
                # This is a simplified check - could be enhanced
                if "October 2025" in date_str or "25" in date_str:
                    filtered.append(event)
        
        return filtered
    
    def _is_cache_valid(self) -> bool:
        """Check if cache file exists and is less than CACHE_MAX_AGE_HOURS old"""
        cache_path = Path(self.CACHE_FILE)
        if not cache_path.exists():
            return False
        
        try:
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            age = datetime.now() - mtime
            return age < timedelta(hours=self.CACHE_MAX_AGE_HOURS)
        except Exception as e:
            print(f"Error checking cache age: {e}")
            return False
    
    def save_events_to_csv(self, events: List[Dict]) -> None:
        """Save events to CSV cache file"""
        try:
            with open(self.CACHE_FILE, 'w', newline='', encoding='utf-8') as f:
                if not events:
                    return
                
                # Write header and data
                fieldnames = ['title', 'date', 'venue', 'description', 'category', 'categories', 'url', 'image_url']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for event in events:
                    # Convert categories list to pipe-separated string
                    row = {
                        'title': event.get('title', ''),
                        'date': event.get('date', ''),
                        'venue': event.get('venue', ''),
                        'description': event.get('description', ''),
                        'category': event.get('category', 'general'),
                        'categories': '|'.join(event.get('categories', [])),
                        'url': event.get('url', ''),
                        'image_url': event.get('image_url', '')
                    }
                    writer.writerow(row)
                
            print(f"✓ Cached {len(events)} events to {self.CACHE_FILE}")
        except Exception as e:
            print(f"Error saving events to CSV: {e}")
    
    def load_events_from_csv(self) -> List[Dict]:
        """Load events from CSV cache file"""
        try:
            events = []
            with open(self.CACHE_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert pipe-separated categories string back to list
                    categories_str = row.get('categories', '')
                    categories = [c.strip() for c in categories_str.split('|') if c.strip()]
                    
                    event = {
                        'title': row.get('title', ''),
                        'date': row.get('date', ''),
                        'venue': row.get('venue', ''),
                        'description': row.get('description', ''),
                        'category': row.get('category', 'general'),
                        'categories': categories or [row.get('category', 'general')],
                        'url': row.get('url', ''),
                        'image_url': row.get('image_url', '')
                    }
                    events.append(event)
            
            print(f"✓ Loaded {len(events)} events from cache")
            return events
        except FileNotFoundError:
            print(f"Cache file {self.CACHE_FILE} not found")
            return []
        except Exception as e:
            print(f"Error loading events from CSV: {e}")
            return []
    
    def get_events_cached(self, force_refresh: bool = False) -> List[Dict]:
        """Get events using CSV cache (parse only if cache invalid or force_refresh=True)"""
        # Check cache validity
        if not force_refresh and self._is_cache_valid():
            print(f"Using cached events (age < {self.CACHE_MAX_AGE_HOURS}h)")
            events = self.load_events_from_csv()
            if events:
                return events
            print("Cache was empty, falling back to fresh parse")
        
        # Cache invalid or empty - parse fresh
        print("Parsing events from website...")
        events = self.get_todays_events()
        
        # Save to cache
        if events:
            self.save_events_to_csv(events)
        
        return events
    
    def format_event_for_display(self, event: Dict) -> str:
        """Format event as a readable string"""
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {event['title']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📆 Date: {event['date']}
📍 Venue: {event['venue']}
🏷️  Category: {event['category']}
📝 {event['description'][:200]}{'...' if len(event['description']) > 200 else ''}
🔗 {event['url']}
"""
    
    def close(self):
        """Close HTTP client"""
        self.http_client.close()


def main():
    """Main function to demonstrate scraper usage"""
    scraper = GlasgowEventScraper()
    
    try:
        # Get all events
        all_events = scraper.get_todays_events()
        
        # Filter for today's events
        todays_events = scraper.filter_events_today(all_events)
        
        print(f"\n{'='*60}")
        print(f"LIVE EVENTS IN GLASGOW - TODAY (October 25, 2025)")
        print(f"{'='*60}")
        print(f"Found {len(todays_events)} events happening today\n")
        
        # Display events by category
        categories = {}
        for event in todays_events:
            cat = event['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(event)
        
        # Show events grouped by category
        for category, events in sorted(categories.items()):
            print(f"\n{'='*60}")
            print(f"📂 {category.upper()} ({len(events)} events)")
            print(f"{'='*60}")
            
            for event in events[:5]:  # Show first 5 per category
                print(scraper.format_event_for_display(event))
        
        # Show summary
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Total events today: {len(todays_events)}")
        print(f"Categories: {', '.join(sorted(categories.keys()))}")
        
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
