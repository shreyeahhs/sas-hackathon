# BACKEND 3 - API and Chatbot
# FastAPI endpoints with OpenAI chatbot integration
# -------------------------------------------------------------------------

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from datetime import datetime, timedelta
import uuid
import json
import re
import httpx
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import asyncio
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from event_scraper import GlasgowEventScraper

try:
    import h2  # type: ignore
    HTTP2_AVAILABLE = True
except Exception:
    HTTP2_AVAILABLE = False

# Load environment variables from possible locations (.env in root or backend)
def _load_envs() -> bool:
    loaded_any = False
    candidates = [
        Path.cwd() / ".env",  # when running from repo root
        Path(__file__).resolve().parent / ".env",  # backend/.env
        Path(__file__).resolve().parent.parent / ".env",  # repo root from file location
    ]
    for p in candidates:
        try:
            if p.exists():
                load_dotenv(dotenv_path=p, override=False)
                loaded_any = True
        except Exception:
            pass
    return loaded_any

_load_envs()

app = FastAPI(title="NightOut Planner API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize event scraper
event_scraper = GlasgowEventScraper()


# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
FOURSQUARE_API_KEY = os.getenv("FOURSQUARE_API_KEY", "")
# Comma-separated order of providers to use. Allowed values: gptgoogle, google, foursquare, osm
PROVIDERS_ORDER = os.getenv("PROVIDERS_ORDER", "gptgoogle,google,osm")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Session storage (in production, use Redis or database)
chat_sessions = {}

# Simple circuit breaker for flaky providers
provider_failures: Dict[str, Dict[str, Any]] = {
    "foursquare": {"count": 0, "skip_until": None}
}

def _should_skip_provider(name: str) -> bool:
    entry = provider_failures.get(name)
    if not entry:
        return False
    skip_until = entry.get("skip_until")
    if not skip_until:
        return False
    try:
        return datetime.utcnow() < skip_until
    except Exception:
        return False

def _record_provider_failure(name: str, threshold: int = 3, cooldown_sec: int = 600) -> None:
    entry = provider_failures.setdefault(name, {"count": 0, "skip_until": None})
    entry["count"] = int(entry.get("count", 0)) + 1
    if entry["count"] >= threshold:
        entry["skip_until"] = datetime.utcnow() + timedelta(seconds=cooldown_sec)
        # reset count to avoid ever-increasing values
        entry["count"] = 0
        print(f"Provider '{name}' temporarily disabled for {cooldown_sec}s due to repeated failures.")
    provider_failures[name] = entry

def _record_provider_success(name: str) -> None:
    entry = provider_failures.setdefault(name, {"count": 0, "skip_until": None})
    entry["count"] = 0
    entry["skip_until"] = None
    provider_failures[name] = entry

# ==================== GPT-GUIDED GOOGLE SEARCH ====================
async def generate_gpt_place_queries(state: "ConversationState", limit: int = 5) -> List[Dict[str, Any]]:
    """Ask GPT to suggest specific venue queries based on state (mood, budget, group size, preferences).
    Returns a list of {query, reason, type?} dicts.
    """
    if not client:
        return []
    sys = (
        "You are a nightlife and dining recommender for Glasgow. "
        "Return ONLY valid JSON, no code fences, no prose. "
        "Respond with a JSON object of the shape {\"items\": [ {\"query\": string, \"reason\": string, \"type\": string?}, ... ] }. "
        "Do not include trailing commas."
    )
    prefs = state.preferences or {}
    prompt = {
        "role": "user",
        "content": (
            "Suggest up to " + str(limit) + " specific place NAMES in Glasgow that match: "
            f"mood={state.mood}, group_size={state.group_size}, budget_per_person=£{state.budget_per_person}, "
            f"preferences={prefs}. "
            "Focus on real venues likely to exist. For each item include {query, reason, type}. "
            "Respond ONLY with a JSON object {items:[...]}."
        ),
    }
    # Log what we're sending to GPT
    try:
        print("GPT request messages:")
        print({"system": sys, "user": prompt.get("content")})
    except Exception:
        pass
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys}, prompt],
            temperature=0.6,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        # Log raw GPT response (truncated)
        try:
            print(f"GPT raw response (truncated 2000):\n{str(raw)[:2000]}")
        except Exception:
            pass
        # Extract JSON
        # First try strict JSON object with items[] as instructed
        try:
            obj = json.loads(raw)
            print(f"GPT parsed JSON object: {obj}")
            if isinstance(obj, dict) and isinstance(obj.get("items"), list):
                data = obj.get("items")
                print(f"GPT extracted items array: {data}")
            else:
                print(f"GPT object missing 'items' list; obj keys: {obj.keys() if isinstance(obj, dict) else 'not a dict'}")
                data = None
        except Exception as e:
            print(f"GPT JSON parse error: {e}")
            data = None

        if isinstance(data, list) and data:
            out = []
            for it in data[:limit]:
                if isinstance(it, dict) and it.get("query"):
                    out.append({
                        "query": str(it.get("query")),
                        "reason": str(it.get("reason", "")),
                        "type": it.get("type"),
                    })
            if out:
                try:
                    print(f"GPT parsed suggestions: {out}")
                except Exception:
                    pass
                return out
        # Fallback: parse any JSON array response variants
        data = _parse_gpt_json_array(raw)
        if isinstance(data, list) and data:
            out = []
            for it in data[:limit]:
                if isinstance(it, dict) and it.get("query"):
                    out.append({
                        "query": str(it.get("query")),
                        "reason": str(it.get("reason", "")),
                        "type": it.get("type"),
                    })
            if out:
                print(f"GPT parsed suggestions (array fallback): {out}")
                return out
        # Fallback: extract "query": "..." pairs via regex if JSON was malformed/truncated
        try:
            fallback_qs = []
            for m in re.finditer(r'"query"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw):
                q = m.group(1)
                # unescape common sequences
                q = q.replace('\\"', '"').strip()
                if q and q not in fallback_qs:
                    fallback_qs.append(q)
                if len(fallback_qs) >= limit:
                    break
            if fallback_qs:
                out = [{"query": q, "reason": "", "type": None} for q in fallback_qs]
                print(f"GPT fallback-extracted suggestions: {out}")
                return out
        except Exception as ex:
            print(f"GPT fallback extract error: {ex}")
    except Exception as e:
        print(f"GPT suggestions error: {e}")
    return []

async def search_google_textsearch(query: str, *, lat: Optional[float], lon: Optional[float], prefs: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params: Dict[str, Any] = {"query": query, "key": GOOGLE_PLACES_API_KEY}
    if lat is not None and lon is not None:
        params["location"] = f"{lat},{lon}"
        params["radius"] = (prefs or {}).get("max_distance_m", 5000)
    if prefs and prefs.get("open_now"):
        params["opennow"] = "true"
    price_max = (prefs or {}).get("price_tier_max")
    if price_max is not None:
        try:
            params["maxprice"] = int(price_max)
        except Exception:
            pass
    try:
        # Log request with masked key
        safe = dict(params)
        if "key" in safe:
            safe["key"] = "***"
        print(f"Google TextSearch request: {safe}")
        async with httpx.AsyncClient() as http_client:
            r = await http_client.get(url, params=params, timeout=10.0)
            try:
                print(f"Google TextSearch raw response (truncated 1500):\n{r.text[:1500]}")
            except Exception:
                pass
            data = r.json()
            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                return []
            venues: List[Dict[str, Any]] = []
            for place in data.get("results", []):
                price_level = place.get("price_level")
                venue = {
                    "name": place.get("name", ""),
                    "rating": place.get("rating"),
                    "price": ("£" * int(price_level)) if isinstance(price_level, int) and price_level > 0 else "££",
                    "price_level": price_level,
                    "categories": [{"title": (place.get("types", ["bar"])[0] or "bar").replace("_", " ").title()}],
                    "location": {"display_address": [place.get("formatted_address") or place.get("vicinity", "")]},
                    "url": f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id','')}",
                    "phone": "",
                    "image_url": "",
                    "open_now": place.get("opening_hours", {}).get("open_now") if place.get("opening_hours") else None,
                    "rating_count": place.get("user_ratings_total"),
                    "coordinates": {
                        "latitude": place.get("geometry", {}).get("location", {}).get("lat"),
                        "longitude": place.get("geometry", {}).get("location", {}).get("lng"),
                    },
                }
                venues.append(venue)
            return venues
    except Exception as e:
        print(f"Google TextSearch error: {e}")
        return []

def _normalize_name(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip().lower()

async def search_google_find_place(query: str, *, lat: Optional[float], lon: Optional[float]) -> Optional[Dict[str, Any]]:
    """Use Google Find Place From Text to get a place_id and basic info for an exact name query."""
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params: Dict[str, Any] = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,name,formatted_address,geometry,price_level,rating,user_ratings_total,opening_hours",
        "key": GOOGLE_PLACES_API_KEY,
    }
    if lat is not None and lon is not None:
        # Bias results near user’s location
        params["locationbias"] = f"point:{lat},{lon}"
    try:
        safe = dict(params)
        if "key" in safe:
            safe["key"] = "***"
        print(f"Google FindPlace request: {safe}")
        async with httpx.AsyncClient() as http_client:
            r = await http_client.get(url, params=params, timeout=10.0)
            try:
                print(f"Google FindPlace raw response (truncated 1500):\n{r.text[:1500]}")
            except Exception:
                pass
            data = r.json()
            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                return None
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            # Return top candidate
            return candidates[0]
    except Exception as e:
        print(f"Google FindPlace error: {e}")
        return None

async def search_google_place_details(place_id: str) -> Optional[Dict[str, Any]]:
    """Fetch detailed info for a place_id."""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "place_id,name,formatted_address,geometry,price_level,rating,user_ratings_total,opening_hours,website,formatted_phone_number,url",
        "key": GOOGLE_PLACES_API_KEY,
    }
    try:
        safe = dict(params)
        if "key" in safe:
            safe["key"] = "***"
        print(f"Google Place Details request: {safe}")
        async with httpx.AsyncClient() as http_client:
            r = await http_client.get(url, params=params, timeout=10.0)
            try:
                print(f"Google Place Details raw response (truncated 2000):\n{r.text[:2000]}")
            except Exception:
                pass
            data = r.json()
            if data.get("status") != "OK":
                return None
            return data.get("result")
    except Exception as e:
        print(f"Google Place Details error: {e}")
        return None

async def search_gpt_google(state: "ConversationState", *, limit: int = 10, lat: Optional[float] = None, lon: Optional[float] = None) -> List[Dict[str, Any]]:
    # Ensure coords
    if lat is None or lon is None:
        try:
            lat, lon = await _nominatim_geocode(state.location)
        except Exception:
            lat, lon = None, None
    # Ask GPT for queries
    suggestions = await generate_gpt_place_queries(state, limit=6)
    try:
        print(f"GPT suggestions used for Google TextSearch: {suggestions}")
    except Exception:
        pass
    if not suggestions:
        return []
    # For each suggestion, prefer exact FindPlace then Details; fallback to TextSearch
    aggregated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for s in suggestions:
        q = s.get("query")
        if not q:
            continue
        # Try exact find place
        candidate = await search_google_find_place(q, lat=lat, lon=lon)
        if candidate and candidate.get("place_id"):
            details = await search_google_place_details(candidate["place_id"])
            if details:
                price_level = details.get("price_level")
                v = {
                    "name": details.get("name", ""),
                    "rating": details.get("rating"),
                    "price": ("£" * int(price_level)) if isinstance(price_level, int) and price_level > 0 else "££",
                    "price_level": price_level,
                    "categories": [{"title": ""}],
                    "location": {"display_address": [details.get("formatted_address", "")]},
                    "url": details.get("url") or f"https://www.google.com/maps/place/?q=place_id:{candidate.get('place_id','')}",
                    "phone": details.get("formatted_phone_number", ""),
                    "image_url": "",
                    "open_now": details.get("opening_hours", {}).get("open_now") if details.get("opening_hours") else None,
                    "rating_count": details.get("user_ratings_total"),
                    "coordinates": {
                        "latitude": details.get("geometry", {}).get("location", {}).get("lat"),
                        "longitude": details.get("geometry", {}).get("location", {}).get("lng"),
                    },
                }
                key = f"{v.get('name','')}|{', '.join(v.get('location',{}).get('display_address',[]))}"
                if key not in seen:
                    aggregated.append(v)
                    seen.add(key)
                if len(aggregated) >= limit:
                    break
                continue  # next suggestion

        # Fallback to TextSearch if exact find failed
        results = await search_google_textsearch(q, lat=lat, lon=lon, prefs=state.preferences)
        for v in results:
            key = f"{v.get('name','')}|{', '.join(v.get('location',{}).get('display_address',[]))}"
            if key not in seen:
                aggregated.append(v)
                seen.add(key)
            if len(aggregated) >= limit:
                break
        if len(aggregated) >= limit:
            break
    return aggregated

# Pydantic models for requests
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    timestamp: str
    context: Dict[str, Any]
    suggestions: Optional[List[str]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    session_id: str

# Conversation state management
class ConversationState:
    def __init__(self):
        self.stage = "greeting"  # greeting, mood, group_size, budget, location, time, searching, complete
        self.mood = None
        self.group_size = None
        self.budget_per_person = None
        self.location = "Glasgow"
        self.start_time = "19:00"
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.preferences = {}
        self.history = []
        # Track which venues we've already shown (dedupe across "show more")
        self.seen_venue_keys: List[str] = []
        # Track which events we've already shown (dedupe across "show alternatives")
        self.seen_event_titles: List[str] = []
        # Cached geocoded coordinates for location
        self.location_lat: Optional[float] = None
        self.location_lng: Optional[float] = None

def _parse_distance_m(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*(km|kilometer|kilometers|m|meter|meters)", text, re.I)
    if not m:
        return None
    val = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("km"):
        return val * 1000
    return val

def extract_preferences_from_message(message: str) -> Dict[str, Any]:
    """Extract lightweight preferences from free text.
    Returns keys: open_now (bool), max_distance_m (int), min_rating (float), price_tier_max (int).
    """
    prefs: Dict[str, Any] = {}
    msg = message.lower()
    # open now
    if any(k in msg for k in ["open now", "currently open", "open right now", "open rn"]):
        prefs["open_now"] = True
    # min rating like 4+, 4.5, at least 4
    m = re.search(r"(\d(?:\.\d)?)\s*\+|at\s*least\s*(\d(?:\.\d)?)|rating\s*(\d(?:\.\d)?)", msg)
    if m:
        for g in m.groups():
            if g:
                try:
                    prefs["min_rating"] = float(g)
                    break
                except Exception:
                    pass
    # distance
    dist = _parse_distance_m(message)
    if dist:
        prefs["max_distance_m"] = dist
    # price tier via repeated £ symbols like "£££" (avoid treating "£50" as a tier)
    try:
        runs = re.findall(r"£{2,4}", message)
        # Only apply if we actually see repeated symbols; ignore single '£' which usually precedes a number
        if runs:
            # take the longest run length as tier
            tier = max(len(r) for r in runs)
            prefs["price_tier_max"] = min(4, max(1, tier))
    except Exception:
        pass
    return prefs

def _price_level_from_budget(budget: Optional[float]) -> Optional[int]:
    if budget is None:
        return None
    try:
        b = float(budget)
    except Exception:
        return None
    if b <= 20:
        return 2
    if b <= 30:
        return 3
    if b <= 50:
        return 4
    return 4

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, asin, sqrt
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def _normalize_price_level(v: Dict[str, Any]) -> Optional[int]:
    if v.get("price_level") is not None:
        try:
            return int(v.get("price_level"))
        except Exception:
            pass
    price = v.get("price")
    if isinstance(price, str) and price:
        return min(4, max(1, price.count("£")))
    return None

def ensure_location_coords(state: ConversationState) -> None:
    if state.location_lat is not None and state.location_lng is not None:
        return
    try:
        # try nominatim sync via async helper by running loop logic
        # We'll reuse existing _nominatim_geocode within event loop later; here keep as placeholder
        pass
    except Exception:
        pass

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # remove first fence line
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl+1:]
        # remove trailing fence if present
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()

def _parse_gpt_json_array(raw: str) -> Optional[List[Any]]:
    # Attempt direct parse
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    # Strip code fences and retry
    try:
        cleaned = _strip_code_fences(raw)
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    # Extract bracketed array substring
    try:
        start = raw.find('[')
        end = raw.rfind(']')
        if start != -1 and end != -1 and end > start:
            sub = raw[start:end+1]
            data = json.loads(sub)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return None

def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, ConversationState]:
    """Get existing session or create new one"""
    if session_id and session_id in chat_sessions:
        return session_id, chat_sessions[session_id]
    
    new_session_id = str(uuid.uuid4())
    chat_sessions[new_session_id] = ConversationState()
    return new_session_id, chat_sessions[new_session_id]

def extract_mood_from_message(message: str) -> Optional[List[str]]:
    """Extract mood keywords from user message"""
    message_lower = message.lower()
    moods = []
    
    mood_keywords = {
        "chill": ["chill", "relax", "calm", "quiet", "laid back", "easy", "casual"],
        "party": ["party", "dance", "club", "wild", "energetic", "crazy", "fun", "exciting"],
        "romantic": ["romantic", "date", "couple", "intimate", "cozy", "special"],
        "adventurous": ["adventure", "explore", "try something new", "different", "unique", "karaoke", "bowling"]
    }
    
    for mood, keywords in mood_keywords.items():
        if any(keyword in message_lower for keyword in keywords):
            moods.append(mood)
    
    return moods if moods else None

def extract_number_from_message(message: str) -> Optional[int]:
    """Extract numbers from message"""
    numbers = re.findall(r'\b(\d+)\b', message)
    return int(numbers[0]) if numbers else None

def extract_budget_from_message(message: str) -> Optional[float]:
    """Extract budget from message"""
    # Look for £ or $ followed by number
    budget_match = re.search(r'[£$]\s*(\d+)', message)
    if budget_match:
        return float(budget_match.group(1))
    
    # Look for standalone number when discussing budget
    number = extract_number_from_message(message)
    if number and 10 <= number <= 200:  # Reasonable budget range
        return float(number)
    
    return None

async def search_venues(location: str, categories: str, limit: int = 10, *, prefs: Optional[Dict[str, Any]] = None, lat: Optional[float] = None, lon: Optional[float] = None, state: Optional["ConversationState"] = None) -> List[Dict]:
    """Search using providers in configured order with graceful fallback. Accepts optional prefs/coords and optional state."""
    # Parse providers order
    order = [p.strip().lower() for p in PROVIDERS_ORDER.split(",") if p.strip()]
    try:
        print(f"Provider order: {order}")
    except Exception:
        pass
    # Build list, enforcing API key availability
    for provider in order:
        if provider == "gptgoogle":
            # Requires both OpenAI and Google
            if not (client and GOOGLE_PLACES_API_KEY):
                print("Skipping GPT-guided search: missing OpenAI or Google key")
                continue
            if state is None:
                print("Skipping GPT-guided search: no conversation state provided")
                continue
            print("Trying provider: gptgoogle")
            venues = await search_gpt_google(state, limit=limit, lat=lat, lon=lon)
            if venues:
                print(f"Provider gptgoogle returned {len(venues)} venues")
                return venues
            else:
                print("Provider gptgoogle returned no venues")
        elif provider == "foursquare":
            if not FOURSQUARE_API_KEY:
                print("Skipping Foursquare: missing FOURSQUARE_API_KEY")
                continue
            if _should_skip_provider("foursquare"):
                print("Skipping Foursquare due to temporary disable after repeated failures.")
                continue
            print("Trying provider: foursquare")
            venues = await search_foursquare_venues(location, categories, limit, lat=lat, lon=lon, prefs=prefs)
            if venues:
                _record_provider_success("foursquare")
                print(f"Provider foursquare returned {len(venues)} venues")
                return venues
            else:
                _record_provider_failure("foursquare")
                print("Provider foursquare returned no venues")
        elif provider == "google":
            if not GOOGLE_PLACES_API_KEY:
                print("Skipping Google Places: missing GOOGLE_PLACES_API_KEY")
                continue
            print("Trying provider: google")
            venues = await search_google_places(location, categories, limit, lat=lat, lon=lon, prefs=prefs)
            if venues:
                print(f"Provider google returned {len(venues)} venues")
                return venues
            else:
                print("Provider google returned no venues")
        elif provider == "osm":
            print("Using OpenStreetMap Overpass fallback")
            venues = await search_overpass_venues(location, categories, limit, lat=lat, lon=lon, prefs=prefs)
            if venues:
                print(f"Provider osm returned {len(venues)} venues")
                return venues
            else:
                print("Provider osm returned no venues")
        else:
            # Unknown provider keyword; skip
            continue
    return []

async def _http_get_with_retries(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
    retries: int = 2,
    backoff: float = 0.5,
    use_http2: Optional[bool] = None,
):
    """HTTP GET with limited retries and backoff for transient errors like RemoteProtocolError.

    Retries on: RemoteProtocolError, Read/Connect timeouts, ConnectError, and 5xx responses.
    Adds 'Connection: close' on retry attempts to avoid keep-alive issues.
    Enables HTTP/2 for improved stability when supported by the server.
    """
    last_exc: Optional[BaseException] = None
    hdrs = dict(headers or {})
    http2_flag = HTTP2_AVAILABLE if use_http2 is None else bool(use_http2)
    for attempt in range(retries + 1):
        try:
            # Attempt with current HTTP/2 flag; if ImportError due to missing h2, fallback to HTTP/1.1
            try:
                async with httpx.AsyncClient(http2=http2_flag, timeout=timeout, headers=hdrs) as http_client:
                    resp = await http_client.get(url, params=params)
                    resp.raise_for_status()
                    return resp
            except ImportError as e:
                # Missing h2 support; fallback to HTTP/1.1 once and retry immediately
                if http2_flag:
                    http2_flag = False
                    continue
                raise
        except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as e:
            last_exc = e
            # Prepare next attempt
            if attempt < retries:
                hdrs = {**hdrs, "Connection": "close"}
                await asyncio.sleep(backoff * (2 ** attempt))
                continue
            break
        except httpx.HTTPStatusError as e:
            # Retry only on 5xx
            status = e.response.status_code if e.response is not None else 0
            if 500 <= status < 600 and attempt < retries:
                last_exc = e
                await asyncio.sleep(backoff * (2 ** attempt))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("_http_get_with_retries: exhausted without exception but no response")

async def search_foursquare_venues(location: str, categories: str, limit: int = 10, *, lat: Optional[float] = None, lon: Optional[float] = None, prefs: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """Search Foursquare API for venues (FREE tier: 950 calls/day). Adds categories, fields, and robust error logging."""
    url = "https://api.foursquare.com/v3/places/search"
    headers = {
        "Authorization": FOURSQUARE_API_KEY,
        "Accept": "application/json",
        "User-Agent": "NightOutPlanner/1.0 (contact: example@example.com)",
    }
    
    # Map our categories to Foursquare categories
    category_map = {
        "cafes": "13035",
        "lounges": "13003",
        "wine_bars": "13003",
        "nightlife": "10000",
        "bars": "13003",
        "danceclubs": "10032",
        "restaurants": "13065",
        "cocktailbars": "13003",
        "karaoke": "10001",
        "arcades": "12059",
        "bowling": "18021"
    }
    
    # Build params; prefer precise coordinates via Nominatim to reduce API errors
    if lat is None or lon is None:
        lat, lon = await _nominatim_geocode(location)
    if lat is not None and lon is not None:
        params = {
            "ll": f"{lat},{lon}",
            "radius": (prefs or {}).get("max_distance_m", 5000),
            "limit": limit,
            "fields": "fsq_id,name,location,categories,rating,website,geocodes"
        }
    else:
        params = {
            "near": location,
            "limit": limit,
            "fields": "fsq_id,name,location,categories,rating,website,geocodes"
        }

    # Map requested categories to Foursquare category IDs
    requested = [c.strip() for c in categories.split(",") if c.strip()]
    cat_ids = []
    for c in requested:
        if c in category_map:
            cat_ids.append(category_map[c])
    if cat_ids:
        # comma-separated IDs per API spec
        params["categories"] = ",".join(sorted(set(cat_ids)))
    
    try:
        # Log request params for debugging (no secrets included)
        try:
            print(f"Foursquare request params: {params}")
        except Exception:
            pass

        response = await _http_get_with_retries(url, headers=headers, params=params, timeout=15.0, retries=2, backoff=0.6)

        # Log raw response (truncated) for debugging
        try:
            preview = response.text[:2000]
            print(f"Foursquare raw response (truncated to 2000 chars):\n{preview}")
        except Exception:
            pass

        places = response.json().get("results", [])
        print(f"Foursquare parsed results count: {len(places)}")

        # Convert to our format
        venues = []
        for place in places:
            # rating may be absent; when present it's 0-10 scale
            fsq_rating = place.get("rating")
            rating_value = (fsq_rating / 2) if isinstance(fsq_rating, (int, float)) else None

            loc_obj = place.get("location", {})
            display_addr = []
            if loc_obj.get("formatted_address"):
                display_addr.append(loc_obj.get("formatted_address"))
            else:
                if loc_obj.get("address"):
                    display_addr.append(loc_obj.get("address"))
                if loc_obj.get("locality"):
                    display_addr.append(loc_obj.get("locality"))

            venue = {
                "name": place.get("name", ""),
                "rating": rating_value,
                "price": "££",
                "categories": [{"title": cat.get("name", "")} for cat in place.get("categories", [])],
                "location": {
                    "display_address": display_addr
                },
                "url": place.get("website") or f"https://foursquare.com/v/{place.get('fsq_id', '')}",
                "phone": "",
                "image_url": "",
                # extra fields for ranking
                "price_level": None,
                "open_now": None,
                "rating_count": None,
                "coordinates": {
                    "latitude": (place.get("geocodes", {}).get("main", {}).get("latitude")),
                    "longitude": (place.get("geocodes", {}).get("main", {}).get("longitude"))
                }
            }
            venues.append(venue)

        return venues
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else "?"
        body = e.response.text if e.response is not None else ""
        print(f"Foursquare API HTTP error: {status} {body}")
        return []
    except Exception as e:
        # Print repr for more detail when message is empty
        print(f"Foursquare API error: {repr(e)}")
        return []

async def search_google_places(location: str, categories: str, limit: int = 10, *, lat: Optional[float] = None, lon: Optional[float] = None, prefs: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """Search Google Places API (FREE tier: 5000 requests/month). Supports prefs: radius, open_now, price limits."""

    # Prefer provided coordinates; else geocode
    if lat is None or lon is None:
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        geocode_params = {"address": location, "key": GOOGLE_PLACES_API_KEY}
        try:
            # Log geocode request (mask API key)
            try:
                safe_geo = dict(geocode_params)
                if "key" in safe_geo:
                    safe_geo["key"] = "***"
                print(f"Google Geocode request params: {safe_geo}")
            except Exception:
                pass

            async with httpx.AsyncClient() as http_client:
                geo_response = await http_client.get(geocode_url, params=geocode_params, timeout=10.0)
                # Log truncated response
                try:
                    print(f"Google Geocode raw response (truncated 1500):\n{geo_response.text[:1500]}")
                except Exception:
                    pass
                geo_data = geo_response.json()
                if geo_data.get("status") != "OK" or not geo_data.get("results"):
                    return []
                loc = geo_data["results"][0]["geometry"]["location"]
                lat, lon = loc["lat"], loc["lng"]
        except Exception as e:
            print(f"Google Geocode error: {e}")
            return []

    # Map categories to Google Places types
    type_map = {
        "cafes": "cafe",
        "lounges": "bar",
        "wine_bars": "bar",
        "nightlife": "night_club",
        "bars": "bar",
        "danceclubs": "night_club",
        "restaurants": "restaurant",
        "cocktailbars": "bar",
        "karaoke": "night_club",
        "arcades": "amusement_center",
        "bowling": "bowling_alley"
    }
    place_type = "bar"
    for cat in categories.split(","):
        if cat in type_map:
            place_type = type_map[cat]
            break

    # Build nearby search
    places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    radius = (prefs or {}).get("max_distance_m", 5000)
    params: Dict[str, Any] = {
        "location": f"{lat},{lon}",
        "radius": radius,
        "type": place_type,
        "key": GOOGLE_PLACES_API_KEY,
    }
    if prefs and prefs.get("open_now"):
        params["opennow"] = "true"
    # Price levels are 0-4; use maxprice to cap
    price_max = (prefs or {}).get("price_tier_max")
    if price_max is not None:
        try:
            params["maxprice"] = int(price_max)
        except Exception:
            pass

    try:
        # Log places request (mask API key)
        try:
            safe_params = dict(params)
            if "key" in safe_params:
                safe_params["key"] = "***"
            print(f"Google Places request params: {safe_params}")
        except Exception:
            pass

        async with httpx.AsyncClient() as http_client:
            places_response = await http_client.get(places_url, params=params, timeout=10.0)
            # Log truncated response
            try:
                print(f"Google Places raw response (truncated 2000):\n{places_response.text[:2000]}")
            except Exception:
                pass

            places_data = places_response.json()
            if places_data.get("status") != "OK":
                return []
            venues: List[Dict[str, Any]] = []
            results = places_data.get("results", [])
            print(f"Google Places parsed results count: {len(results)}")
            for place in results[:limit]:
                price_level = place.get("price_level")
                price_str = None
                if price_level is not None:
                    try:
                        price_str = "£" * max(1, int(price_level))
                    except Exception:
                        price_str = None
                venue = {
                    "name": place.get("name", ""),
                    "rating": place.get("rating"),
                    "price": price_str or "££",
                    "price_level": price_level,
                    "categories": [{"title": place.get("types", ["bar"])[0].replace("_", " ").title()}],
                    "location": {"display_address": [place.get("vicinity", "")]},
                    "url": f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id', '')}",
                    "phone": "",
                    "image_url": "",
                    "open_now": place.get("opening_hours", {}).get("open_now") if place.get("opening_hours") else None,
                    "rating_count": place.get("user_ratings_total"),
                    "coordinates": {
                        "latitude": place.get("geometry", {}).get("location", {}).get("lat"),
                        "longitude": place.get("geometry", {}).get("location", {}).get("lng"),
                    },
                }
                venues.append(venue)
            return venues
    except Exception as e:
        print(f"Google Places API error: {e}")
        return []


async def search_overpass_venues(location: str, categories: str, limit: int = 10, *, lat: Optional[float] = None, lon: Optional[float] = None, prefs: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """Search OpenStreetMap Overpass API for venues around a location (no API key)."""
    # Geocode with Nominatim if needed
    if lat is None or lon is None:
        lat, lon = await _nominatim_geocode(location)
    if lat is None or lon is None:
        return []

    # Map categories to OSM tags
    tag_map = {
        "cafes": ("amenity", "cafe"),
        "lounges": ("amenity", "bar"),
        "wine_bars": ("amenity", "bar"),
        "nightlife": ("amenity", "nightclub"),
        "bars": ("amenity", "bar"),
        "danceclubs": ("amenity", "nightclub"),
        "restaurants": ("amenity", "restaurant"),
        "cocktailbars": ("amenity", "bar"),
        "karaoke": ("amenity", "bar"),  # no direct karaoke tag
        "arcades": ("leisure", "amusement_arcade"),
        "bowling": ("leisure", "bowling_alley"),
    }

    key, value = tag_map.get(categories.split(",")[0], ("amenity", "bar"))
    radius = (prefs or {}).get("max_distance_m", 5000)  # meters

    overpass_query = f"""
    [out:json][timeout:15];
    (
      node["{key}"="{value}"](around:{radius},{lat},{lon});
      way["{key}"="{value}"](around:{radius},{lat},{lon});
      relation["{key}"="{value}"](around:{radius},{lat},{lon});
    );
    out center {limit};
    """

    headers = {"User-Agent": "NightOutPlanner/1.0 (contact: example@example.com)"}
    url = "https://overpass-api.de/api/interpreter"

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20.0) as http_client:
            resp = await http_client.post(url, data={"data": overpass_query})
            resp.raise_for_status()
            data = resp.json()
            elements = data.get("elements", [])

            venues: List[Dict[str, Any]] = []
            for el in elements[:limit]:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue
                addr_parts = []
                if tags.get("addr:street"):
                    addr_parts.append(tags.get("addr:street"))
                if tags.get("addr:city"):
                    addr_parts.append(tags.get("addr:city"))
                address = ", ".join(addr_parts)
                lat_c = el.get("lat") or el.get("center", {}).get("lat")
                lon_c = el.get("lon") or el.get("center", {}).get("lon")
                gmaps_url = (
                    f"https://www.google.com/maps/search/?api=1&query="
                    f"{httpx.QueryParams.encode_component(name)}%20{lat_c}%2C{lon_c}"
                    if lat_c and lon_c else ""
                )

                venue = {
                    "name": name,
                    "rating": None,
                    "price": "££",
                    "categories": [{"title": value.replace("_", " ").title()}],
                    "location": {"display_address": [address] if address else []},
                    "url": gmaps_url,
                    "phone": "",
                    "image_url": "",
                    # normalized fields for ranking
                    "price_level": None,
                    "open_now": None,
                    "rating_count": None,
                    "coordinates": {"latitude": lat_c, "longitude": lon_c},
                }
                venues.append(venue)

            return venues
    except Exception as e:
        print(f"Overpass API error: {e}")
        return []

async def _nominatim_geocode(query: str) -> tuple[Optional[float], Optional[float]]:
    """Geocode a query to (lat, lon) using Nominatim (no API key)."""
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "NightOutPlanner/1.0 (contact: example@example.com)"}
    params = {"q": query, "format": "json", "limit": 1}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as http_client:
            resp = await http_client.get(url, params=params)
            resp.raise_for_status()
            results = resp.json()
            if not results:
                return None, None
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"Nominatim error: {e}")
        return None, None

def get_fallback_venues(categories: str, limit: int = 10) -> List[Dict]:
    """Deprecated: hardcoded venues removed. Kept for backward compatibility if referenced elsewhere."""
    return []

def format_venue_for_chat(venue: Dict) -> Dict[str, Any]:
    """Normalize a venue object from any provider to the chat-friendly shape."""
    # Prefer computed price_level to format a price string
    price_level = venue.get("price_level")
    price_str = venue.get("price", "££")
    if price_level is not None:
        try:
            lvl = int(price_level)
            price_str = "£" * max(1, lvl)
        except Exception:
            pass
    return {
        "name": venue.get("name", ""),
        "rating": venue.get("rating"),
        "price": price_str,
        "categories": [cat["title"] for cat in venue.get("categories", [])],
        "address": ", ".join(venue.get("location", {}).get("display_address", [])),
        "url": venue.get("url", ""),
        "phone": venue.get("phone", ""),
        "image": venue.get("image_url", "")
    }

def _venue_key(venue: Dict[str, Any]) -> str:
    """Build a stable dedupe key from provider-agnostic fields (name + first address line if present)."""
    name = (venue.get("name") or "").strip().lower()
    addr_list = venue.get("location", {}).get("display_address", []) or []
    addr0 = (addr_list[0] if addr_list else "").strip().lower()
    return f"{name}|{addr0}"

def _select_new_venues(state: ConversationState, venues: List[Dict[str, Any]], desired: int) -> List[Dict[str, Any]]:
    """Filter out venues already shown in this session and pick up to 'desired'. Also updates state.seen_venue_keys."""
    fresh: List[Dict[str, Any]] = []
    for v in venues:
        key = _venue_key(v)
        if key and key not in state.seen_venue_keys:
            fresh.append(v)
    picked = fresh[:desired]
    # update seen keys
    for v in picked:
        key = _venue_key(v)
        if key:
            state.seen_venue_keys.append(key)
    return picked

def get_events_summary_for_gpt(max_events: int = 50) -> str:
    """Get a concise summary of events from cache for GPT context"""
    try:
        events = event_scraper.get_events_cached(force_refresh=False)
        if not events:
            return "No events available."
        
        # Limit events to avoid token overflow
        events_subset = events[:max_events]
        
        # Format as concise text
        lines = ["Available Events in Glasgow Today:"]
        for e in events_subset:
            cats = ", ".join(e.get('categories', [e.get('category', 'general')]))
            lines.append(f"- {e.get('title')}: {cats} at {e.get('venue')} ({e.get('date')})")
        
        if len(events) > max_events:
            lines.append(f"...and {len(events) - max_events} more events")
        
        return "\n".join(lines)
    except Exception as e:
        print(f"Error loading events for GPT: {e}")
        return "Events data temporarily unavailable."

async def get_combined_recommendations_with_gpt(state: ConversationState, user_query: str) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Use GPT to recommend both events and venues based on user preferences
    Returns: (text_response, formatted_events, formatted_venues)
    """
    if not client:
        return "AI recommendations unavailable.", [], []
    
    # Get all events data
    try:
        all_events = event_scraper.get_events_cached(force_refresh=False)
    except Exception as e:
        print(f"Error loading events: {e}")
        all_events = []
    
    events_summary = get_events_summary_for_gpt(max_events=50)
    
    # Build comprehensive context
    already_shown = ""
    if state.seen_event_titles:
        already_shown = f"\n\nEvents ALREADY SHOWN (do NOT recommend these again):\n" + "\n".join(f"- {title}" for title in state.seen_event_titles[-10:])  # Show last 10
    
    system_prompt = f"""You are a Glasgow nightlife and events expert. You have access to:
1. Live events happening today in Glasgow
2. Venue search capabilities via Google Places API

User preferences:
- Mood: {state.mood or 'not specified'}
- Group size: {state.group_size or 'not specified'}
- Budget per person: £{state.budget_per_person or 'not specified'}
- Location: {state.location}
- Time: {state.start_time}

{events_summary}{already_shown}

Based on the user's query and preferences, recommend a mix of:
1. Relevant events from the list above (use EXACT event titles as they appear)
2. Venue types to search for (e.g., "cocktail bars", "karaoke", "restaurants")

IMPORTANT: Do NOT recommend any events from the "ALREADY SHOWN" list above.

Format your response as JSON:
{{
  "text_response": "Friendly explanation of recommendations",
  "recommended_events": ["Exact Event Title 1", "Exact Event Title 2"],
  "venue_search_queries": ["venue type 1", "venue type 2"]
}}

Keep recommendations relevant to their mood, budget, and group size. Recommend 2-4 events maximum."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.7,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        text_response = result.get("text_response", "Here are some suggestions!")
        recommended_event_titles = result.get("recommended_events", [])
        venue_queries = result.get("venue_search_queries", [])
        
        print(f"GPT recommended {len(recommended_event_titles)} events and {len(venue_queries)} venue types")
        print(f"Event titles: {recommended_event_titles}")
        print(f"Venue queries: {venue_queries}")
        
        # Find the actual event details for recommended events
        # Filter out events we've already shown
        formatted_events = []
        if all_events and recommended_event_titles:
            for event_title in recommended_event_titles[:10]:  # Check more titles since some may be filtered
                # Find event by title (case-insensitive partial match)
                for event in all_events:
                    event_actual_title = event.get('title', '')
                    
                    # Skip if already shown
                    if event_actual_title in state.seen_event_titles:
                        continue
                    
                    # Check for title match
                    if event_title.lower() in event_actual_title.lower() or event_actual_title.lower() in event_title.lower():
                        # Format like events.html
                        categories = event.get('categories', [event.get('category', 'general')])
                        category_str = categories[0] if isinstance(categories, list) else categories
                        
                        # Generate Google Maps link from venue name
                        venue_name = event.get('venue', '')
                        maps_url = ""
                        if venue_name and venue_name != "Venue TBA":
                            # Create Google Maps search URL for the venue in Glasgow
                            import urllib.parse
                            search_query = urllib.parse.quote(f"{venue_name}, Glasgow")
                            maps_url = f"https://www.google.com/maps/search/?api=1&query={search_query}"
                        
                        formatted_event = {
                            'title': event_actual_title,
                            'category': category_str,
                            'categories': categories if isinstance(categories, list) else [categories],
                            'date': event.get('date'),
                            'venue': event.get('venue'),
                            'description': event.get('description', '')[:200] + '...' if event.get('description') else '',
                            'link': event.get('url'),  # Event details link
                            'maps_url': maps_url,  # Google Maps link for venue location
                            'image_url': event.get('image_url', '')  # Event image
                        }
                        formatted_events.append(formatted_event)
                        
                        # Track this event as shown
                        state.seen_event_titles.append(event_actual_title)
                        
                        # Stop after finding 4 unique events
                        if len(formatted_events) >= 4:
                            break
                
                if len(formatted_events) >= 4:
                    break
        
        # Search for venues based on GPT's recommendations
        # Use direct Google search to avoid redundant GPT calls
        all_venues = []
        seen_place_ids = set()
        
        for query in venue_queries[:3]:  # Limit to 3 searches
            try:
                # Use search_google_places directly instead of search_venues
                # to avoid the "gptgoogle" provider making another GPT call
                venues = await search_google_places(
                    state.location,
                    query,
                    limit=5,
                    lat=state.location_lat,
                    lon=state.location_lng,
                    prefs=state.preferences
                )
                # Dedupe by place_id
                for v in venues:
                    place_id = v.get('place_id')
                    if place_id and place_id not in seen_place_ids:
                        seen_place_ids.add(place_id)
                        all_venues.append(v)
            except Exception as e:
                print(f"Error searching venues for '{query}': {e}")
        
        # Rank and select venues
        formatted_venues = []
        if all_venues:
            print(f"Found {len(all_venues)} total venues before ranking")
            ranked = rank_and_filter_venues(state, all_venues)
            print(f"After ranking: {len(ranked)} venues")
            selected = _select_new_venues(state, ranked, desired=5)
            print(f"Selected {len(selected)} venues after deduplication")
            formatted_venues = [format_venue_for_chat(v) for v in selected]
            print(f"Formatted {len(formatted_venues)} venues for display")
        else:
            print("No venues found from Google Places")
        
        print(f"Returning: {len(formatted_events)} events, {len(formatted_venues)} venues")
        return text_response, formatted_events, formatted_venues
        
    except Exception as e:
        print(f"GPT combined recommendations error: {e}")
        import traceback
        traceback.print_exc()
        return "Let me find some great options for you!", [], []

async def generate_ai_response(state: ConversationState, user_message: str) -> tuple[str, Optional[List[str]], Optional[List[Dict]]]:
    """Generate AI response using OpenAI with short-term memory from session history"""

    if not client:
        return "Sorry, the chatbot is not configured. Please set OPENAI_API_KEY.", None, None

    # Build a concise system prompt capturing known facts
    system_prompt = (
        "You are a friendly nightlife assistant for Glasgow. "
        f"Current stage: {state.stage}. "
        f"Known facts -> Mood: {state.mood or 'n/a'}, Group size: {state.group_size or 'n/a'}, "
        f"Budget/pp: £{state.budget_per_person or 'n/a'}, Location: {state.location}, Time: {state.start_time}. "
        "Be concise, proactive, and ask ONE question at a time when you need more info."
    )

    # Use recent conversation turns for memory (avoid sending unbounded history)
    # History already includes the latest user message (added before this call)
    recent_history = state.history[-12:] if state.history else []

    # Compose messages list with system + recent history
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in recent_history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if content:
            messages.append({"role": role, "content": content})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=220
        )
        return response.choices[0].message.content, None, None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return (
            "I'm having trouble connecting. Let's continue: what's your vibe for tonight (chill, party, romantic, adventurous)?",
            None,
            None,
        )

def _score_venue(state: ConversationState, v: Dict[str, Any]) -> float:
    # rating (0-5)
    rating = v.get("rating") or 0.0
    try:
        rating = float(rating)
    except Exception:
        rating = 0.0
    rating_weight = 1.0

    # reviews count
    rc = v.get("rating_count") or 0
    try:
        rc = float(rc)
    except Exception:
        rc = 0.0
    reviews_boost = min(1.0, (rc / 200.0))  # cap

    # price fit
    desired_price = state.preferences.get("price_tier_max")
    if desired_price is None:
        desired_price = _price_level_from_budget(state.budget_per_person) or 4
    venue_price = _normalize_price_level(v) or desired_price
    price_fit = 0.2 if venue_price <= desired_price else -0.2

    # distance penalty
    dist_pen = 0.0
    if state.location_lat is not None and state.location_lng is not None:
        c = v.get("coordinates") or {}
        if c.get("latitude") is not None and c.get("longitude") is not None:
            try:
                d_m = _haversine_m(state.location_lat, state.location_lng, float(c["latitude"]), float(c["longitude"]))
                # 0.02 penalty per km
                dist_pen = -0.02 * (d_m / 1000.0)
            except Exception:
                dist_pen = 0.0

    # open_now small boost
    on = v.get("open_now")
    open_boost = 0.1 if (state.preferences.get("open_now") and on) else 0.0

    score = rating_weight * rating + reviews_boost + price_fit + open_boost + dist_pen
    return score

def rank_and_filter_venues(state: ConversationState, venues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Filters
    filtered: List[Dict[str, Any]] = []
    min_rating = state.preferences.get("min_rating")
    price_cap = state.preferences.get("price_tier_max")
    max_dist = state.preferences.get("max_distance_m")
    for v in venues:
        # rating filter
        if min_rating is not None:
            try:
                if (v.get("rating") or 0) < float(min_rating):
                    continue
            except Exception:
                pass
        # price filter
        if price_cap is not None:
            lvl = _normalize_price_level(v)
            if lvl is not None and int(lvl) > int(price_cap):
                continue
        # distance filter
        if max_dist and state.location_lat is not None and state.location_lng is not None:
            c = v.get("coordinates") or {}
            if c.get("latitude") is not None and c.get("longitude") is not None:
                try:
                    d_m = _haversine_m(state.location_lat, state.location_lng, float(c["latitude"]), float(c["longitude"]))
                    if d_m > max_dist:
                        continue
                except Exception:
                    pass
        filtered.append(v)

    # Rank
    ranked = sorted(filtered, key=lambda x: _score_venue(state, x), reverse=True)
    return ranked

# ==================== ENDPOINTS ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    fs_entry = provider_failures.get("foursquare", {})
    skip_until = fs_entry.get("skip_until")
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "openai_configured": bool(OPENAI_API_KEY),
        "foursquare_configured": bool(FOURSQUARE_API_KEY),
        "google_places_configured": bool(GOOGLE_PLACES_API_KEY),
        "overpass_available": True,
        "providers_order": PROVIDERS_ORDER,
        "foursquare_skipped": _should_skip_provider("foursquare"),
        "foursquare_failures": fs_entry.get("count", 0),
        "foursquare_skip_until": skip_until.isoformat() if skip_until else None,
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Enhanced conversational chatbot endpoint"""
    
    # Get or create session
    session_id, state = get_or_create_session(request.session_id)
    user_message = request.message.strip()
    
    # Add to history
    state.history.append({"role": "user", "content": user_message})
    # Update preferences from user message (lightweight extraction)
    try:
        extracted = extract_preferences_from_message(user_message)
        if extracted:
            state.preferences.update(extracted)
    except Exception:
        pass
    
    suggestions = None
    recommendations = None
    reply = ""
    
    # STATE MACHINE: Process based on conversation stage
    
    if state.stage == "greeting":
        # Initial greeting
        reply = "Hey! 🌃 I'm here to help you plan an amazing night out in Glasgow. What's your vibe tonight? Are you feeling chill, ready to party, romantic, or adventurous?"
        suggestions = ["Chill", "Party", "Romantic", "Adventurous"]
        state.stage = "mood"
    
    elif state.stage == "mood":
        # Extract mood
        moods = extract_mood_from_message(user_message)
        if moods:
            state.mood = moods
            reply = f"Nice! {', '.join(moods).title()} vibes it is! 🎉 How many people are in your group?"
            suggestions = ["Just me", "2 people", "3-5 people", "5+ people"]
            state.stage = "group_size"
        else:
            reply = "I didn't quite catch that! Are you looking for something chill, a party atmosphere, romantic, or adventurous?"
            suggestions = ["Chill", "Party", "Romantic", "Adventurous"]
    
    elif state.stage == "group_size":
        # Extract group size
        group_size = extract_number_from_message(user_message)
        if group_size:
            state.group_size = group_size
            reply = f"Perfect, {group_size} {'person' if group_size == 1 else 'people'}! What's your budget per person? (e.g., £20, £30, £50)"
            suggestions = ["£20", "£30", "£50", "£100"]
            state.stage = "budget"
        elif "just me" in user_message.lower() or "solo" in user_message.lower():
            state.group_size = 1
            reply = "Flying solo tonight! What's your budget? (e.g., £20, £30, £50)"
            suggestions = ["£20", "£30", "£50", "£100"]
            state.stage = "budget"
        else:
            reply = "How many people will be going out? Just give me a number!"
            suggestions = ["1", "2", "4", "6"]
    
    elif state.stage == "budget":
        # Extract budget
        budget = extract_budget_from_message(user_message)
        if budget:
            state.budget_per_person = budget
            # Derive a default price tier from budget if not set
            if state.preferences.get("price_tier_max") is None:
                tier = _price_level_from_budget(budget)
                if tier is not None:
                    state.preferences["price_tier_max"] = tier
            
            # Ensure coords for ranking
            try:
                if state.location_lat is None or state.location_lng is None:
                    state.location_lat, state.location_lng = await _nominatim_geocode(state.location)
            except Exception:
                pass
            
            # Use GPT to recommend both events and venues
            reply = f"Great! £{budget} per person. Let me find the perfect mix of events and venues for you... 🔍"
            
            # Generate query for GPT based on preferences
            query = f"I'm looking for a {', '.join(state.mood or ['fun'])} night out with {state.group_size} {'person' if state.group_size == 1 else 'people'}, budget £{budget} per person"
            
            gpt_response, events, venues = await get_combined_recommendations_with_gpt(state, query)
            
            # Combine events and venues into recommendations
            recommendations = []
            
            # Add formatted events first
            if events:
                recommendations.extend(events)
            
            # Then add venues
            if venues:
                recommendations.extend(venues)
            
            if recommendations:
                reply += f"\n\n{gpt_response}\n\n"
                if events:
                    reply += f"📅 I found {len(events)} great event{'s' if len(events) != 1 else ''}:\n"
                if venues:
                    reply += f"🏢 And {len(venues)} perfect venue{'s' if len(venues) != 1 else ''}:"
                suggestions = ["Tell me more", "Show me alternatives", "Something different"]
            else:
                reply += f"\n\n{gpt_response}"
                suggestions = ["Show me venues", "What events are on?", "Try different mood"]
            
            state.stage = "complete"
        else:
            reply = "What's your budget per person? Just give me a number like 20, 30, or 50 (in pounds)."
            suggestions = ["£20", "£30", "£50"]
    
    elif state.stage == "complete":
        # User wants refinement or more options
        if any(word in user_message.lower() for word in ["more", "alternative", "other", "different"]):
            reply = "Let me find some different options for you..."
            
            # Use GPT again for alternative recommendations
            query = f"Show me different options for a {', '.join(state.mood or ['fun'])} night out with {state.group_size} {'person' if state.group_size == 1 else 'people'}, budget £{state.budget_per_person} per person. I've already seen some places, show me alternatives."
            
            gpt_response, events, venues = await get_combined_recommendations_with_gpt(state, query)
            
            # Combine events and venues
            recommendations = []
            if events:
                recommendations.extend(events)
            if venues:
                recommendations.extend(venues)
            
            if recommendations:
                reply += f"\n\n{gpt_response}\n\n"
                if events:
                    reply += f"📅 Here are {len(events)} more event{'s' if len(events) != 1 else ''}:\n"
                if venues:
                    reply += f"🏢 And {len(venues)} different venue{'s' if len(venues) != 1 else ''}:"
                suggestions = ["Perfect!", "Show me more", "Start over"]
            else:
                reply += "\n\nSorry, couldn't find more options right now. Try again?"
                suggestions = ["Try again", "Start over"]
        
        elif any(word in user_message.lower() for word in ["restart", "start over", "reset", "new search"]):
            # Reset session
            state.stage = "greeting"
            state.mood = None
            state.group_size = None
            state.budget_per_person = None
            reply = "Sure! Let's start fresh. What's your vibe for tonight?"
            suggestions = ["Chill", "Party", "Romantic", "Adventurous"]
        
        else:
            # Use AI for general questions
            reply, _, _ = await generate_ai_response(state, user_message)
            suggestions = ["Show me more options", "Start over"]
    
    else:
        # Fallback to AI
        reply, _, _ = await generate_ai_response(state, user_message)
    
    # Add to history and trim to avoid unbounded growth
    state.history.append({"role": "assistant", "content": reply})
    if len(state.history) > 100:
        state.history = state.history[-100:]

    # Build context for response
    context = {
        "stage": state.stage,
        "mood": state.mood,
        "group_size": state.group_size,
        "budget_per_person": state.budget_per_person,
        "location": state.location
    }
    
    return ChatResponse(
        reply=reply,
        timestamp=datetime.utcnow().isoformat(),
        context=context,
        suggestions=suggestions,
        recommendations=recommendations,
        session_id=session_id
    )

# -------------------------------------------------------------------------
# LIVE EVENTS ENDPOINT
# -------------------------------------------------------------------------

class EventsRequest(BaseModel):
    category: Optional[str] = None
    venue: Optional[str] = None
    today_only: bool = True

class EventResponse(BaseModel):
    title: str
    date: str
    venue: str
    description: str
    category: str  # primary category for backward compatibility
    categories: List[str]  # all categories
    url: str
    image_url: Optional[str] = None

class EventsListResponse(BaseModel):
    events: List[EventResponse]
    total_count: int
    categories: List[str]

@app.post("/api/events/live", response_model=EventsListResponse)
async def get_live_events(request: EventsRequest):
    """
    Get live events in Glasgow from cached CSV data (parsed once daily)
    """
    try:
        # Use cached data instead of parsing every time
        all_events = event_scraper.get_events_cached(force_refresh=False)
        
        # Apply filters
        filtered_events = all_events
        
        if request.today_only:
            filtered_events = event_scraper.filter_events_today(filtered_events)
        
        if request.category:
            filtered_events = event_scraper.filter_events_by_category(
                filtered_events, request.category
            )
        
        if request.venue:
            filtered_events = event_scraper.filter_events_by_venue(
                filtered_events, request.venue
            )
        
        # Get unique categories (use all categories if available)
        categories_set = set()
        for e in filtered_events:
            multi = e.get('categories')
            if isinstance(multi, list) and multi:
                for c in multi:
                    if isinstance(c, str) and c:
                        categories_set.add(c)
            else:
                categories_set.add(e.get('category', 'General'))
        categories = sorted(list(categories_set))
        
        # Convert to response format
        event_responses = []
        for e in filtered_events:
            event_responses.append(
                EventResponse(
                    title=e['title'],
                    date=e['date'],
                    venue=e['venue'],
                    description=e['description'],
                    category=e.get('category', 'general'),
                    categories=e.get('categories', [e.get('category', 'general')]),
                    url=e['url'],
                    image_url=e.get('image_url')
                )
            )
        
        return EventsListResponse(
            events=event_responses,
            total_count=len(event_responses),
            categories=categories
        )
    
    except Exception as e:
        print(f"Error fetching live events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")

@app.get("/api/events/categories")
async def get_event_categories():
    """Get available event categories from cached data"""
    try:
        all_events = event_scraper.get_events_cached(force_refresh=False)
        categories_set = set()
        for e in all_events:
            multi = e.get('categories')
            if isinstance(multi, list) and multi:
                for c in multi:
                    if isinstance(c, str) and c:
                        categories_set.add(c)
            else:
                categories_set.add(e.get('category', 'General'))
        categories = sorted(list(categories_set))
        return {"categories": categories}
    except Exception as e:
        print(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

@app.get("/api/events/refresh")
@app.post("/api/events/refresh")
async def refresh_events_cache():
    """Manually trigger a fresh parse and cache update"""
    try:
        print("Manual cache refresh requested")
        events = event_scraper.get_events_cached(force_refresh=True)
        return {
            "status": "success",
            "message": f"Cache refreshed with {len(events)} events",
            "event_count": len(events),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"Error refreshing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh cache: {str(e)}")

# -------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

