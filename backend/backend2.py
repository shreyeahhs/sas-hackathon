# recommendation logic
# Use it f0r the best Glasg0w night 0ut !! -> call recommend()
# -------------------------------------------------------------------------
"""
for backend3
you receive data from backend1, convert them to the ('Candidate') format, call my function recommend() and send the result to fronten

"""

"""
This module handles:
    scoring
    ranking
    itinerary generation logic

    Input
    It receives the preferences of the user (like budget,  number of people in the group,
    mood, date), event or venue candidates (bar, event) and weather

    Output
    Ranked list od the best options and 1 or 2 itineraries with 2-3 stops


    Quick example for da team:
    user says "10 people, £20 each one, karaoke, rainy friday"

    backend 1 will send 50 bars + 20 events + rainy weather

    THIS MODULE RECEIVES IT AND GIVES BACK:
    Top 10: Super trouper bar (score 86), Dancing queen (82), etc
    Itinerary: Bar 19:00 -> Karaoke 20:15 -> Drinks 22:00
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import math
import uuid

# Data models

@dataclass
class Location:
    lat: float
    lon: float


@dataclass
class UserRequest:
    date: str  # year-month-day <- important <- date format
    start_time: str  # hours:minutes
    duration_minutes: int
    group_size: int
    budget_per_person_gbp: float
    moods: List[str]
    center: Optional[Location] = None
    max_walk_minutes_between_stops: int = 15
    max_results: int = 10
    preferred_radius_km: float = 3.0

@dataclass
class Candidate:
    id: str
    type: str  # you have two types "venue" // "event"
    name: str
    categories: List[str]
    location: Location
    distance_km_from_center: float
    indoor: bool
    outdoor: bool = False
    
    # venue case
    price_tier: Optional[int] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    open_hours: Optional[Dict[str, List[List[int]]]] = None
    capacity_hint: Optional[int] = None
    
    # event cse
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    start: Optional[str] = None  # ISO format!!!!
    end: Optional[str] = None


@dataclass
class WeatherHour:
    time: str
    temp_c: float
    precip_mm: float
    is_rain: bool


@dataclass
class WeatherSnapshot:
    date: str
    hourly: List[WeatherHour]


@dataclass
class RankedItem:
    item: Candidate
    score: float
    components: Dict[str, float]
    reasons: List[str]
    eta_minutes_from_center: int
    estimated_cost_pp: float


@dataclass
class ItineraryStop:
    id: str
    name: str
    arrive: str
    depart: str
    walk_minutes_to_next: int
    cost_pp: float


@dataclass
class Itinerary:
    title: str
    stops: List[ItineraryStop]
    total_cost_pp: float
    total_walk_minutes: int
    reasons: List[str]
    plan_b: str


@dataclass
class RecommendationResponse:
    request_id: str
    generated_at: str
    top: List[Dict]
    itineraries: List[Dict]



# next we are going to distribute the weight for the scoring and configure the models
# sum to 100 when multiplied
WEIGHTS = {
    "mood": 30,
    "price": 20,
    "rating": 15,
    "group": 15,
    "distance": 10,
    "weather": 10
}

# price tier mapping for venues
PRICE_TIER_MAP = {
    1: 8,
    2: 12,
    3: 20,
    4: 35
}

# mood to category mapping
MOOD_CATEGORY_MAP = {
    "karaoke": {"karaoke", "bar", "private-rooms", "singing"},
    "fun": {"karaoke", "arcade", "bowling", "darts", "pub-quiz", "bar", "pub"},
    "chill": {"cocktail", "wine-bar", "gastropub", "cafe", "lounge"},
    "competitive": {"bowling", "darts", "escape-room", "quiz", "pool", "games"},
    "live-music": {"live-music", "concert", "gig", "music-venue"},
    "culture": {"museum", "gallery", "theatre", "comedy", "art"}
}

# itinerary templates by mood
ITINERARY_TEMPLATES = {
    "karaoke": ["bar", "karaoke", "bar"],
    "fun": ["bar", "arcade|bowling|darts", "bar"],
    "competitive": ["bar", "bowling|darts|escape-room|quiz", "bar"],
    "chill": ["gastropub|restaurant", "live-music|comedy", "cocktail|dessert"],
    "live-music": ["bar", "live-music|concert", "bar"],
    "culture": ["cafe", "museum|gallery|theatre|comedy", "bar"]
}

DWELL_TIMES = { # to specify how much time the group would be on average per site
    "bar": (60, 75),
    "pub": (60, 75),
    "karaoke": (75, 90),
    "bowling": (60, 90),
    "darts": (60, 90),
    "escape-room": (60, 75),
    "quiz": (90, 120),
    "arcade": (45, 75),
    "restaurant": (75, 90),
    "gastropub": (75, 90),
    "cafe": (45, 60),
    "cocktail": (60, 75),
    "live-music": (90, 120),
    "concert": (90, 150),
    "gig": (90, 120),
    "comedy": (75, 105),
    "museum": (60, 90),
    "gallery": (45, 75),
    "theatre": (120, 180),
    "default": (60, 75)
}



# utility functions

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """km between two lat/lon pts"""
    R = 6371  # earth radius -> km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_time(time_str: str) -> int:
    """convert hours:minutes to minutes since midnight"""
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def minutes_to_time(minutes: int) -> str:
    """convert minutes since midnight to hours:minutes"""
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def get_weekday(date_str: str) -> str:
    """get weekday name from yyyy-mm-dd (year-month-day)"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%a")  # Mon, Tue, etc.


def time_overlaps(start1: int, end1: int, start2: int, end2: int) -> bool:
    """check if two time ranges overlap in minss"""
    return start1 < end2 and start2 < end1


# filtering functions

def is_time_compatible(candidate: Candidate, date: str, start_min: int, end_min: int) -> bool:
    """is candidate event available during requested time?"""
    if candidate.type == "event":
        if not candidate.start or not candidate.end:
            return False
        event_start = datetime.fromisoformat(candidate.start.replace('Z', '+00:00'))
        event_end = datetime.fromisoformat(candidate.end.replace('Z', '+00:00'))
        
        req_date = datetime.strptime(date, "%Y-%m-%d")
        req_start = req_date.replace(hour=start_min//60, minute=start_min%60)
        req_end = req_date.replace(hour=end_min//60, minute=end_min%60)
        
        return event_start < req_end and event_end > req_start
    
    # venue check open_hours
    if candidate.open_hours:
        weekday = get_weekday(date)
        if weekday in candidate.open_hours:
            for open_block in candidate.open_hours[weekday]:
                block_start, block_end = open_block
                if block_end < block_start: # handle overnight
                    block_end += 24 * 60
                if time_overlaps(start_min, end_min, block_start, block_end):
                    return True
            return False
    return True  #no hours info -> we ll assume open


def soft_radius_filter(candidates: List[Candidate], preferred_km: float) -> List[Candidate]:
    """keep items within radius but allow up to 1.5x with penalty"""
    return [c for c in candidates if c.distance_km_from_center <= preferred_km * 1.5]


# scoring

def mood_match(user_moods: List[str], categories: List[str]) -> float:
    """calculate mood category overlap  0-1 """
    if not user_moods:
        return 0.6
    
    max_match = 0.0
    for mood in user_moods:
        mood_lower = mood.lower()
        if mood_lower in MOOD_CATEGORY_MAP:
            desired = MOOD_CATEGORY_MAP[mood_lower]
            hits = len(set(categories) & desired)
            match = min(1.0, hits / max(len(desired), 1))
            max_match = max(max_match, match)
    
    return max_match if max_match > 0 else 0.3


def estimate_cost_pp(candidate: Candidate) -> float:
    """estimate cost/person"""
    if candidate.type == "venue":
        if candidate.price_tier:
            return PRICE_TIER_MAP.get(candidate.price_tier, 12)
        return 12
    else:  #event
        if candidate.price_min is not None:
            if candidate.price_max is not None:
                return (candidate.price_min + candidate.price_max) / 2
            return candidate.price_min
        return 15


def price_fit(cost_pp: float, budget_pp: float) -> float:
    """score how well price fits budget -> 0-1"""
    if cost_pp <= budget_pp:
        return 1.0
    overage = cost_pp - budget_pp
    penalty = overage / (budget_pp + 10)
    return max(0.0, 1.0 - penalty)


def rating_norm(rating: Optional[float], reviews: Optional[int]) -> float:
    """normalize rating to 0-1 with review confidence"""
    if rating is None:
        return 0.6
    
    norm = rating / 5.0
    
    if reviews and reviews < 30:  # penalize low review count
        norm *= 0.85
    
    return min(1.0, norm)


def group_fit(group_size: int, capacity_hint: Optional[int]) -> float:
    """score venue capacity fit 0-1"""
    if capacity_hint:
        ratio = capacity_hint / (group_size * 1.2)
        return min(1.0, ratio)

    if group_size <= 12:
        return 0.75
    elif group_size <= 20:
        return 0.5
    else:
        return 0.3


def distance_norm(distance_km: float, preferred_km: float) -> float:
    """normalize distance -> 0-1 -> the closer the better"""
    return max(0.0, 1.0 - min(distance_km / preferred_km, 1.0))


def weather_fit(weather: Optional[WeatherSnapshot], date: str, start_time: str, 
                candidate: Candidate) -> float:
    """Score weather compatibility """
    if not weather:
        return 0.8
    
    # relevant hour finder
    hour_str = start_time.split(":")[0] + ":00"
    is_rain = False
    temp = 10.0
    
    for h in weather.hourly:
        if h.time.startswith(hour_str):
            is_rain = h.is_rain
            temp = h.temp_c
            break
    
    if is_rain and candidate.outdoor:
        return 0.2
    if is_rain and candidate.indoor:
        return 1.0
    if not is_rain and candidate.outdoor and temp > 10:
        return 1.0
    return 0.8


def build_reasons(components: Dict[str, float], candidate: Candidate, 
                 user: UserRequest) -> List[str]:
    """generate human readable reasons for the score (for mood price rating etc)"""
    reasons = []
    
    if components["mood"] > 0.7:
        mood_str = ", ".join(user.moods)
        reasons.append(f"fits mood: {mood_str}")
    
    cost = estimate_cost_pp(candidate)
    if cost < user.budget_per_person_gbp:
        diff = user.budget_per_person_gbp - cost
        reasons.append(f"under budget by £{diff:.0f}")
    elif cost <= user.budget_per_person_gbp * 1.2:
        reasons.append("within budget")
    
    if candidate.rating and candidate.rating >= 4.5:
        review_str = f" from {candidate.reviews} reviews" if candidate.reviews else ""
        reasons.append(f"high rating ({candidate.rating:.1f}/5{review_str})")
    
    if components["weather"] == 1.0 and candidate.indoor:
        reasons.append("indoor during rain")
    
    if candidate.distance_km_from_center < 1.0:
        walk_min = int(candidate.distance_km_from_center * 12)
        reasons.append(f"{walk_min} minutes walk from center")
    
    return reasons[:4]  


# ranking

def rank_activities(
    user: UserRequest,
    candidates: List[Candidate],
    weather: Optional[WeatherSnapshot]
) -> List[RankedItem]:
    """rank and score all candidates:
    parse time window, filter by time and ratius, put a hard budget filter and 
    apply distance penalties for overflow radius"""
    
    start_min = parse_time(user.start_time)
    end_min = start_min + user.duration_minutes
    
    compatible = [c for c in candidates 
                  if is_time_compatible(c, user.date, start_min, end_min)]
    compatible = soft_radius_filter(compatible, user.preferred_radius_km)
    
    compatible = [c for c in compatible 
                  if estimate_cost_pp(c) <= user.budget_per_person_gbp * 2]
    
    ranked = []
    
    for c in compatible:
        components = {
            "mood": mood_match(user.moods, c.categories),
            "price": price_fit(estimate_cost_pp(c), user.budget_per_person_gbp),
            "rating": rating_norm(c.rating, c.reviews),
            "group": group_fit(user.group_size, c.capacity_hint),
            "distance": distance_norm(c.distance_km_from_center, user.preferred_radius_km),
            "weather": weather_fit(weather, user.date, user.start_time, c)
        }
        
        if c.distance_km_from_center > user.preferred_radius_km:
            components["distance"] = max(0.0, components["distance"] - 0.2)
        
        # weighted score
        score = sum(WEIGHTS[k] * components[k] for k in WEIGHTS)
        
        reasons = build_reasons(components, c, user)
        
        eta = int(c.distance_km_from_center * 12)
        cost_pp = estimate_cost_pp(c)
        
        ranked.append(RankedItem(c, score, components, reasons, eta, cost_pp))
    
    # tie breakers for the sorting
    ranked.sort(key=lambda r: (
        -r.score,
        -(r.item.reviews or 0),
        r.item.distance_km_from_center,
        r.item.name
    ))
    
    # diversity penalty
    ranked = apply_diversity_penalty(ranked)
    
    return ranked[:user.max_results]


def apply_diversity_penalty(ranked: List[RankedItem]) -> List[RankedItem]:
    """penalize duplicate categories in top results"""
    category_count = {}
    
    for r in ranked:
        main_cat = r.item.categories[0] if r.item.categories else "other"
        category_count[main_cat] = category_count.get(main_cat, 0) + 1
        
        if category_count[main_cat] > 2:
            r.score *= 0.9  # penalty 10%
    
    #srot again
    ranked.sort(key=lambda r: (
        -r.score,
        -(r.item.reviews or 0),
        r.item.distance_km_from_center
    ))
    
    return ranked


# itinerary

def get_dwell_time(categories: List[str]) -> Tuple[int, int]:
    """Get min/max dwell time for a category."""
    for cat in categories:
        if cat in DWELL_TIMES:
            return DWELL_TIMES[cat]
    return DWELL_TIMES["default"]


def build_itineraries(
    user: UserRequest,
    ranked: List[RankedItem]
) -> List[Itinerary]:
    """build 1 up to 2 itineraries from ranked items"""
    
    templates = pick_templates(user.moods)
    itineraries = []
    
    for template in templates[:2]:  # no more > 2 itineraries
        itin = try_build_template(user, ranked, template)
        if itin:
            itineraries.append(itin)
    
    return itineraries


def pick_templates(moods: List[str]) -> List[List[str]]:
    """select itinerary templates based on moods"""
    templates = []
    
    for mood in moods:
        mood_lower = mood.lower()
        if mood_lower in ITINERARY_TEMPLATES:
            templates.append(ITINERARY_TEMPLATES[mood_lower])
    
    if not templates:
        templates.append(["bar", "bar|karaoke|bowling", "bar"])
    
    return templates


def try_build_template(
    user: UserRequest,
    ranked: List[RankedItem],
    template: List[str]
) -> Optional[Itinerary]:
    """try to build an itinerary following a template"""
    
    stops = []
    current_time = parse_time(user.start_time)
    total_cost = 0.0
    total_walk = 0
    last_location = user.center or Location(55.858, -4.259)
    used_ids = set()
    
    for i, slot in enumerate(template):
        categories = slot.split("|")
        
        # best match for this slot
        candidate = None
        for r in ranked:
            if r.item.id in used_ids:
                continue
            if any(cat in r.item.categories for cat in categories):
                dist_km = haversine_distance(  # walk time from last location
                    last_location.lat, last_location.lon,
                    r.item.location.lat, r.item.location.lon
                )
                walk_min = int(dist_km * 12)
                
                if walk_min <= user.max_walk_minutes_between_stops:
                    candidate = r
                    break
        
        if not candidate:
            continue
        
        # times calculation
        if i > 0:
            walk_min = int(haversine_distance(
                last_location.lat, last_location.lon,
                candidate.item.location.lat, candidate.item.location.lon
            ) * 12)
            current_time += walk_min
            total_walk += walk_min
        else:
            walk_min = 0
        
        # dwell time
        dwell_min, dwell_max = get_dwell_time(candidate.item.categories)
        dwell = (dwell_min + dwell_max) // 2
        
        # for events respect actual times
        if candidate.item.type == "event" and candidate.item.start:
            event_start = datetime.fromisoformat(candidate.item.start.replace('Z', '+00:00'))
            current_time = event_start.hour * 60 + event_start.minute
            if candidate.item.end:
                event_end = datetime.fromisoformat(candidate.item.end.replace('Z', '+00:00'))
                dwell = (event_end.hour * 60 + event_end.minute) - current_time
        
        arrive = minutes_to_time(current_time)
        depart = minutes_to_time(current_time + dwell)
        
        walk_to_next = 0
        if i < len(template) - 1:
            # estimate walk to next (im using average)
            walk_to_next = 7
        
        stops.append(ItineraryStop(
            id=candidate.item.id,
            name=candidate.item.name,
            arrive=arrive,
            depart=depart,
            walk_minutes_to_next=walk_to_next,
            cost_pp=candidate.estimated_cost_pp
        ))
        
        total_cost += candidate.estimated_cost_pp
        current_time += dwell
        last_location = candidate.item.location
        used_ids.add(candidate.item.id)
    
    if len(stops) < 2:
        return None
    
    # budget constraint
    if total_cost > user.budget_per_person_gbp * 1.2:
        return None
    # title
    title = generate_itinerary_title(stops, user.moods)
    # reasons to party hard
    reasons = []
    if total_cost <= user.budget_per_person_gbp:
        reasons.append("within budget")
    elif total_cost <= user.budget_per_person_gbp * 1.1:
        reasons.append("slightly above budget")
    
    if total_walk <= user.max_walk_minutes_between_stops * len(stops):
        reasons.append("short transfers")
    
    #checking for indoor dominance
    indoor_count = sum(1 for s in stops if any(
        r.item.id == s.id and r.item.indoor for r in ranked
    ))
    if indoor_count >= len(stops) * 0.7:
        reasons.append("mostly indoor")
    
    plan_b = f"Alternative venues available within {user.preferred_radius_km}km"
    
    return Itinerary(
        title=title,
        stops=stops,
        total_cost_pp=round(total_cost, 2),
        total_walk_minutes=total_walk,
        reasons=reasons[:3],
        plan_b=plan_b
    )


def generate_itinerary_title(stops: List[ItineraryStop], moods: List[str]) -> str:
    """ title for the itinerar"""
    if "karaoke" in [m.lower() for m in moods]:
        return "Karaoke night folks"
    if "competitive" in [m.lower() for m in moods]:
        return "Game on challenge!"
    if "chill" in [m.lower() for m in moods]:
        return "Relaxed evening out so just chill guys"
    if "culture" in [m.lower() for m in moods]:
        return "Cultural journey"
    
    return "Glasgow Night Out"


# api

def recommend(
    user: UserRequest,
    candidates: List[Candidate],
    weather: Optional[WeatherSnapshot]
) -> RecommendationResponse:
    """recommendation function with ranking and itineraries"""
    
    ranked = rank_activities(user, candidates, weather)
    itineraries = build_itineraries(user, ranked)
    
    # to json
    top_items = []
    for r in ranked:
        top_items.append({
            "id": r.item.id,
            "name": r.item.name,
            "type": r.item.type,
            "score": round(r.score, 1),
            "reasons": r.reasons,
            "components": {k: round(v, 2) for k, v in r.components.items()},
            "eta_minutes_from_center": r.eta_minutes_from_center,
            "estimated_cost_pp": round(r.estimated_cost_pp, 2)
        })
    
    itinerary_dicts = []
    for itin in itineraries:
        itinerary_dicts.append({
            "title": itin.title,
            "stops": [asdict(s) for s in itin.stops],
            "total_cost_pp": itin.total_cost_pp,
            "total_walk_minutes": itin.total_walk_minutes,
            "reasons": itin.reasons,
            "plan_b": itin.plan_b
        })
    
    return RecommendationResponse(
        request_id=str(uuid.uuid4()),
        generated_at=datetime.utcnow().isoformat() + "Z",
        top=top_items,
        itineraries=itinerary_dicts
    )

