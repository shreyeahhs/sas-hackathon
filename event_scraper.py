"""scraper"""

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
    """scraper"""
    
    BASE_URL = "https://www.whatsonglasgow.co.uk"
    EVENTS_URL = f"{BASE_URL}/events/"
    CACHE_FILE = "events_cache.csv"
    CACHE_MAX_AGE_HOURS = 24
    MAX_PAGES = 5  # Try up to 5 pages of listings
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
        """fetch"""
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
        """date"""
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
        """clean"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def _extract_image_src(self, img) -> Optional[str]:
        """image"""
        if not img:
            return None
        # Prefer lazy-loading attributes first
        for attr in [
            'data-src', 'data-original', 'data-lazy-src', 'data-large_image', 'data-image',
        ]:
            src = img.get(attr)
            if src:
                return src
        # Try srcset (pick a candidate containing 800x600 if available, else first URL)
        srcset = img.get('srcset')
        if srcset:
            # split by comma, take URL part before size descriptor
            candidates = [s.strip().split(' ')[0] for s in srcset.split(',') if s.strip()]
            # Prefer an 800x600 upload
            for c in candidates:
                if '/uploads/800x600/' in c:
                    return c
            if candidates:
                return candidates[0]
        # Fallback to standard src
        return img.get('src')

    def _is_good_image_url(self, src: str) -> bool:
        """image"""
        if not src:
            return False
        s = src.lower()
        if 'placeholder' in s or 'logo' in s:
            return False
        return '/uploads/' in s
    
    def extract_event_category(self, text: str) -> Optional[str]:
        """category"""
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
        """detail"""
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
        """categories"""
        if not html:
            return []
        
        cats: Set[str] = set()
        
        # Find where navigation menu starts (to avoid extracting all categories)
        nav_markers = [
            'all-events-in-glasgow',
            'btn btn-sm mb-1',
            'class="btn btn-sm'
        ]
        
        nav_start_idx = len(html)
        for marker in nav_markers:
            idx = html.find(marker)
            if idx > 0 and idx < nav_start_idx:
                nav_start_idx = idx
        
        # Extract categories only from the part before navigation
        pre_nav_html = html[:nav_start_idx]
        
        # Find /events/<category>/ links
        for match in re.finditer(r'href="([^"]*?/events/([^/?"#]+)/[^"]*)"', pre_nav_html):
            full_href, cat_token = match.group(1), match.group(2)
            # Map to canonical form
            cat_token_clean = cat_token.strip().lower().replace('_', '-').replace(' ', '-')
            canon = self.CATEGORY_MAP.get(cat_token_clean)
            if canon and len(cats) < 5:  # limit to first 5 category links
                cats.add(canon)
        
        return list(cats)
    
    def parse_image_from_detail(self, html: str) -> Optional[str]:
        """image"""
        if not html:
            return None
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Strategy 1: Look for main event image (common patterns)
            # Try hero/featured image first
            for selector in [
                'img.event-image',
                'img.hero-image', 
                '.event-details img',
                '.event-header img',
                'article img',
                '.main-image img'
            ]:
                img = soup.select_one(selector)
                if img:
                    src = self._extract_image_src(img)
                    if src and self._is_good_image_url(src):
                        # Prefer explicit 800x600 if available in URL
                        return self._make_absolute_url(src)
            
            # Strategy 2: Find any large image (not placeholder)
            all_imgs = soup.find_all('img')
            for img in all_imgs:
                src = self._extract_image_src(img)
                if src and self._is_good_image_url(src) and ('/uploads/800x600/' in src or '800x600' in src or '/uploads/' in src):
                    return self._make_absolute_url(src)
            
            # Strategy 3: Any non-placeholder image
            for img in all_imgs:
                src = self._extract_image_src(img)
                if src and self._is_good_image_url(src):
                    return self._make_absolute_url(src)
                    
        except Exception as e:
            if self.debug:
                print(f"Error parsing image from detail: {e}")
        
        return None
    
    def _make_absolute_url(self, url: str) -> str:
        """url"""
        if url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return self.BASE_URL + url
        elif url.startswith('http'):
            return url
        return url

    def parse_events_from_html(self, html: str) -> List[Dict]:
        """parse"""
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')

        # Find all event links on the page. Many cards wrap the whole tile in an <a>,
        # and additional nested anchors (like category badges) may also point to the
        # same event URL. We'll start broad, then filter aggressively.
        event_links = soup.find_all('a', href=re.compile(r'/event/\d+'))

        events = []
        print(f"Found {len(event_links)} event links")

        # Known category labels we should ignore if they appear as standalone link text
        known_category_labels = set(self.CATEGORY_MAP.values())
        # Include also human-readable forms (spaces instead of dashes)
        known_category_labels.update({c.replace('-', ' ') for c in self.CATEGORY_MAP.values()})
        # Site-specific section badges we observed that are not actual event titles
        known_category_labels.update({
            'weddings', 'charity and fundraiser', 'halloween', 'christmas',
            'quiz night', 'pet', 'gardening', 'glasgow 850', 'days out', 'nights out'
        })

        for link in event_links:
            try:
                # Extract URL
                event_url = link.get('href', '')
                if not event_url.startswith('http'):
                    event_url = self.BASE_URL + event_url
        
                # Extract title ONLY from nested h3/h4 within the card title area.
                # Fallback to link text as a last resort, but ignore plain category labels.
                title_elem = link.find(['h4', 'h3'])
                if not title_elem:
                    # Try to get the title from the parent card instead of the badge link
                    maybe_parent = link.find_parent(['div', 'article', 'section'])
                    if maybe_parent:
                        title_elem = maybe_parent.find(['h4', 'h3'])
                if title_elem:
                    title = self.clean_text(title_elem.get_text())
                else:
                    title = self.clean_text(link.get_text())
                    # If fallback title matches a category label like "Music" or similar, skip it.
                    norm_title = title.strip().lower()
                    if norm_title in known_category_labels:
                        continue
                
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
                        img_src = self._extract_image_src(img_elem)
                        if img_src and self._is_good_image_url(img_src):
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
                
                # Heuristic guard: if we didn't find any typical metadata from the card
                # and the link didn't contain a proper title element, it's likely a badge.
                # Skip such entries to avoid rows like "Music/Comedy" with TBA fields.
                if (not title_elem) and (not date) and (not venue) and (not description) and (not image_url):
                    continue

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
                    
                    # Also extract better image from detail page if listing image is invalid or low quality
                    if detail_html and (not image_url or 'placeholder' in (image_url or '').lower() or 'logo' in (image_url or '').lower() or '/uploads/800x600/' not in (image_url or '')):
                        better_image = self.parse_image_from_detail(detail_html)
                        if better_image:
                            image_url = better_image
                            event['image_url'] = image_url
                    
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
        """dedupe"""
        def score(e: Dict) -> int:
            s = 0
            title = (e.get('title') or '').strip()
            desc = (e.get('description') or '').strip()
            date = (e.get('date') or '').strip()
            venue = (e.get('venue') or '').strip()
            img = (e.get('image_url') or '').lower()
            # Title richness
            if len(title) >= 12:
                s += 3
            elif len(title) >= 6:
                s += 1
            # Non-placeholder description
            if desc and desc.lower() != 'no description available':
                s += 2
            # Concrete date/venue
            if date and date.lower() != 'date tba':
                s += 1
            if venue and venue.lower() != 'venue tba':
                s += 1
            # Prefer 800x600 uploads
            if '/uploads/800x600/' in img:
                s += 1
            # Prefer titles with multiple words
            if ' ' in title.strip():
                s += 1
            return s

        by_url: Dict[str, Dict] = {}
        for e in events:
            url = e.get('url') or ''
            if not url:
                continue
            if url not in by_url:
                by_url[url] = e
            else:
                if score(e) > score(by_url[url]):
                    by_url[url] = e

        return list(by_url.values())
    
    def get_todays_events(self) -> List[Dict]:
        """events"""
        print("Fetching today's events from What's On Glasgow...")

        all_events: List[Dict] = []
        seen_urls: Set[str] = set()
        for page in range(1, self.MAX_PAGES + 1):
            url = self.EVENTS_URL if page == 1 else f"{self.EVENTS_URL}?page={page}"
            html = self.fetch_events_page(url)
            if not html:
                if self.debug:
                    print(f"[Scraper] No HTML for page {page}, stopping pagination")
                break
            page_events = self.parse_events_from_html(html)
            # Stop if page produced nothing new
            new_count = 0
            for e in page_events:
                u = e.get('url')
                if not u or u in seen_urls:
                    continue
                seen_urls.add(u)
                all_events.append(e)
                new_count += 1
            print(f"[Scraper] Page {page}: {len(page_events)} parsed, {new_count} new")
            if new_count == 0:
                break
        
        events = all_events
        events = self.deduplicate_events(events)
        
        print(f"Successfully parsed {len(events)} unique events")
        return events
    
    def filter_events_by_category(self, events: List[Dict], category: str) -> List[Dict]:
        """filter"""
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
        """filter"""
        return [e for e in events if venue.lower() in e.get('venue', '').lower()]
    
    def filter_events_today(self, events: List[Dict]) -> List[Dict]:
        """today"""
        today = datetime.now().date()

        def _strip_ordinal(d: str) -> str:
            return re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", d)

        def _parse_date(d: str) -> Optional[datetime]:
            try:
                return datetime.strptime(_strip_ordinal(d.strip()), "%d %B %Y")
            except Exception:
                return None

        filtered: List[Dict] = []
        for e in events:
            ds = (e.get('date') or '').strip()
            if not ds:
                continue
            # Normalize leading 'Selected dates between'
            ds_norm = re.sub(r"^Selected dates between\s+", "", ds, flags=re.I)
            # Split possible ranges
            if ' - ' in ds_norm:
                parts = [p.strip() for p in ds_norm.split(' - ', 1)]
                start = _parse_date(parts[0])
                end = _parse_date(parts[1]) if len(parts) > 1 else None
                if start and end:
                    if start.date() <= today <= end.date():
                        filtered.append(e)
                    continue
                # Fallback: if parsing failed but month/year match, do lenient contains
                if str(today.year) in ds_norm and today.strftime('%B') in ds_norm:
                    filtered.append(e)
                continue
            else:
                single = _parse_date(ds_norm)
                if single and single.date() == today:
                    filtered.append(e)
                continue

        return filtered
    
    def _is_cache_valid(self) -> bool:
        """cache"""
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
        """save"""
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
        """load"""
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
        """cache"""
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
        """format"""
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
        """close"""
        self.http_client.close()


def main():
    """main"""
    scraper = GlasgowEventScraper()
    
    try:
        # Build/refresh cache first so results are written to disk
        print("\n[Scraper] Building cache...")
        all_events = scraper.get_events_cached(force_refresh=True)
        cache_path = str(Path(scraper.CACHE_FILE).resolve())
        print(f"[Scraper] Cache written to: {cache_path}")
        
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
