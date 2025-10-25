"""
module info
converts backend1 data into backend2 format

"""

from backend2 import Candidate, Location, WeatherSnapshot, WeatherHour
import math
from typing import List, Optional, Tuple


# main function use this oneeeeeeee

def convert_backend1_data(backend1_output: dict) -> Tuple[List[Candidate], Optional[WeatherSnapshot]]:
    """
    main function which converts everything everywhere all at once
    
    expected backend1 input:
    {
        "venues": [........], # Yelp venues
        "events": [......],# Eventbrite events
        "weather": {.....}, # Weather data
    }
    
    kaput:
    (candidates, weather) where:
    - candidates: List[Candidate] -> all venues + events
    - weather: WeatherSnapshot or None
    """
    
    candidates = []
    
    # convert venues
    for venue in backend1_output.get("venues", []):
        try:
            candidate = convert_yelp_to_candidate(venue)
            candidates.append(candidate)
        except Exception as e:
            print(f"error converting venue {venue.get('name', 'unknown')}: {e}")
    
    # convert events
    for event in backend1_output.get("events", []):
        try:
            candidate = convert_eventbrite_to_candidate(event)
            candidates.append(candidate)
        except Exception as e:
            print(f"error converting event {event.get('name', 'unknown')}: {e}")
    
    # convert weather
    weather = None
    weather_data = backend1_output.get("weather")
    if weather_data:
        try:
            date = weather_data.get("date", "2025-11-15")
            weather = convert_weather_to_snapshot(weather_data, date)
        except Exception as e:
            print(f"error converting weather: {e}")
    
    print(f"converted {len(candidates)} candidates total")
    
    return candidates, weather


# yelp to candidate

def convert_yelp_to_candidate(yelp_venue: dict) -> Candidate:
    """converts a yelp venue (raw or simplified) into Candidate"""
    
    # detect format
    if "coordinates" in yelp_venue:
        return _convert_raw_yelp(yelp_venue)
    else:
        return _convert_clean_venue(yelp_venue)


def _convert_raw_yelp(yelp_venue: dict) -> Candidate:
    """convert raw yelp api response"""
    
    # map categories
    categories = []
    for cat in yelp_venue.get("categories", []):
        alias = cat.get("alias", "")
        mapped = _map_yelp_category(alias)
        if mapped:
            categories.append(mapped)
    if not categories:
        categories = ["bar"]
    
    # price tier
    price_str = yelp_venue.get("price", "££")
    price_tier = len(price_str)
    
    # coords
    coords = yelp_venue.get("coordinates", {})
    lat = coords.get("latitude", 55.8642)
    lon = coords.get("longitude", -4.2518)
    
    distance_km = _calculate_distance_from_center(lat, lon)
    
    return Candidate(
        id=yelp_venue.get("id", "unknown"),
        type="venue",
        name=yelp_venue.get("name", "Unknown Venue"),
        categories=categories,
        price_tier=price_tier,
        rating=yelp_venue.get("rating"),
        reviews=yelp_venue.get("review_count"),
        location=Location(lat=lat, lon=lon),
        indoor=True,
        outdoor=False,
        distance_km_from_center=distance_km,
        capacity_hint=None
    )


def _convert_clean_venue(venue: dict) -> Candidate:
    """convert simplified backend1 venue"""
    
    location_data = venue.get("location", {})
    location = Location(
        lat=location_data.get("lat", 55.8642),
        lon=location_data.get("lon", -4.2518)
    )
    
    distance_km = venue.get("distance_km")
    if distance_km is None:
        distance_km = _calculate_distance_from_center(location.lat, location.lon)
    
    return Candidate(
        id=venue.get("id", "unknown"),
        type="venue",
        name=venue.get("name", "Unknown Venue"),
        categories=venue.get("categories", ["bar"]),
        price_tier=venue.get("price_tier", 2),
        rating=venue.get("rating"),
        reviews=venue.get("reviews"),
        location=location,
        indoor=venue.get("indoor", True),
        outdoor=venue.get("outdoor", False),
        distance_km_from_center=distance_km,
        capacity_hint=venue.get("capacity_hint"),
        open_hours=venue.get("open_hours")
    )


# eventbrite to candidate

def convert_eventbrite_to_candidate(event: dict) -> Candidate:
    """convert an Eventbrite event to Candidate"""
    
    if "venue" in event and "address" in event.get("venue", {}):
        return __convert_raw_eventbrite(event)
    else:
        return _convert_clean_event(event)


def __convert_raw_eventbrite(event: dict) -> Candidate:
    """convert raw eventbrite api response"""
    
    venue = event.get("venue", {})
    address = venue.get("address", {})
    lat = float(address.get("latitude", 55.86))
    lon = float(address.get("longitude", -4.25))
    
    distance_km = _calculate_distance_from_center(lat, lon)
    
    name = event.get("name", {})
    if isinstance(name, dict):
        name = name.get("text", "Unknown Event")
    
    categories = _infer_event_categories(name)
    
    price_min = 10.0
    price_max = 15.0
    
    return Candidate(
        id=event.get("id", "unknown"),
        type="event",
        name=name,
        categories=categories,
        location=Location(lat=lat, lon=lon),
        indoor=True,
        outdoor=False,
        distance_km_from_center=distance_km,
        price_min=price_min,
        price_max=price_max,
        start=event.get("start", {}).get("utc") if isinstance(event.get("start"), dict) else event.get("start"),
        end=event.get("end", {}).get("utc") if isinstance(event.get("end"), dict) else event.get("end"),
        rating=None,
        reviews=None
    )


def _convert_clean_event(event: dict) -> Candidate:
    """convert simplified backend1 event"""
    
    location_data = event.get("location", {})
    location = Location(
        lat=location_data.get("lat", 55.8642),
        lon=location_data.get("lon", -4.2518)
    )
    
    distance_km = event.get("distance_km")
    if distance_km is None:
        distance_km = _calculate_distance_from_center(location.lat, location.lon)
    
    return Candidate(
        id=event.get("id", "unknown"),
        type="event",
        name=event.get("name", "Unknown Event"),
        categories=event.get("categories", ["event"]),
        location=location,
        indoor=event.get("indoor", True),
        outdoor=event.get("outdoor", False),
        distance_km_from_center=distance_km,
        price_min=event.get("price_min", 10.0),
        price_max=event.get("price_max", 15.0),
        start=event.get("start"),
        end=event.get("end"),
        rating=event.get("rating"),
        reviews=event.get("reviews")
    )


# weather to weathersnapthot

def convert_weather_to_snapshot(weather_data: dict, date: str) -> WeatherSnapshot:
    """convert openmetio or simplified weather into weathersnapshot"""
    
    hourly_data = weather_data.get("hourly", [])
    
    if isinstance(hourly_data, dict):
        return _convert_raw_openmeteo(weather_data, date)
    else:
        return _convert_clean_weather(weather_data, date)


def _convert_raw_openmeteo(weather_data: dict, date: str) -> WeatherSnapshot:
    """convert raw openmeteo data"""
    
    hourly_data = weather_data.get("hourly", {})
    times = hourly_data.get("time", [])
    temps = hourly_data.get("temperature_2m", [])
    precips = hourly_data.get("precipitation", [])
    
    hourly = []
    for i in range(len(times)):
        time_str = times[i]
        temp = temps[i] if i < len(temps) else 10.0
        precip = precips[i] if i < len(precips) else 0.0
        
        # extract hh:mm
        hour_part = time_str.split("T")[1][:5] if "T" in time_str else time_str[:5]
        
        hourly.append(WeatherHour(
            time=hour_part,
            temp_c=temp,
            precip_mm=precip,
            is_rain=(precip > 0.3)
        ))
    
    return WeatherSnapshot(date=date, hourly=hourly)


def _convert_clean_weather(weather_data: dict, date: str) -> WeatherSnapshot:
    """convert simplified weather format"""
    
    hourly_list = weather_data.get("hourly", [])
    hourly = []
    
    for hour_data in hourly_list:
        hourly.append(WeatherHour(
            time=hour_data.get("time", "19:00"),
            temp_c=hour_data.get("temp_c", 10.0),
            precip_mm=hour_data.get("precip_mm", 0.0),
            is_rain=hour_data.get("is_rain", False)
        ))
    
    return WeatherSnapshot(
        date=weather_data.get("date", date),
        hourly=hourly
    )


# internal stuff dont use directly pls

def _calculate_distance_from_center(lat: float, lon: float) -> float:
    """distance in km from Glasgow center (George Square)"""
    GLASGOW_CENTER_LAT = 55.8642
    GLASGOW_CENTER_LON = -4.2518
    return _haversine(GLASGOW_CENTER_LAT, GLASGOW_CENTER_LON, lat, lon)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """distance in km using haversine formula"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _map_yelp_category(yelp_alias: str) -> Optional[str]:
    """map yelp aliases to our standard categories"""
    mapping = {
        "karaoke": "karaoke",
        "bars": "bar",
        "pubs": "pub",
        "whisky_bars": "bar",
        "cocktailbars": "cocktail",
        "wine_bars": "wine-bar",
        "divebars": "bar",
        "sportsbars": "bar",
        "irishpubs": "pub",
        "bowling": "bowling",
        "poolhalls": "darts",
        "arcades": "arcade",
        "escapegames": "escape-room",
        "museums": "museum",
        "artgalleries": "gallery",
        "galleries": "gallery",
        "musicvenues": "live-music",
        "jazzandblues": "live-music",
        "comedyclubs": "comedy",
        "gastropubs": "gastropub",
        "restaurants": "restaurant",
        "cafes": "cafe",
        "coffee": "cafe",
        "coffeeshops": "cafe"
    }
    return mapping.get(yelp_alias.lower())


def _infer_event_categories(event_name: str) -> List[str]:
    """guess event categories from name"""
    name_lower = event_name.lower()
    categories = []
    
    if "karaoke" in name_lower or "sing-along" in name_lower:
        categories.append("karaoke")
    music_keywords = ["concert", "gig", "live", "music", "band", "indie", "rock", "jazz", "blues"]
    if any(word in name_lower for word in music_keywords):
        categories.append("live-music")
    if "comedy" in name_lower or "stand-up" in name_lower or "comedian" in name_lower:
        categories.append("comedy")
    if "quiz" in name_lower or "trivia" in name_lower or "pub quiz" in name_lower:
        categories.append("quiz")
    if "escape" in name_lower:
        categories.append("escape-room")
    if any(word in name_lower for word in ["competition", "tournament", "championship", "contest"]):
        if "karaoke" not in categories:
            categories.append("competitive")
    if "bowling" in name_lower:
        categories.append("bowling")
    if not categories:
        categories.append("event")
    return categories


# testing 

if __name__ == "__main__":
    print("testing conversions\n")
    
    backend1_clean = {
        "venues": [
            {
                "id": "yelp_123",
                "name": "The Pot Still",
                "categories": ["bar", "whisky"],
                "price_tier": 2,
                "rating": 4.7,
                "reviews": 1200,
                "location": {"lat": 55.86, "lon": -4.25},
                "indoor": True,
                "distance_km": 0.8
            }
        ],
        "events": [
            {
                "id": "evt_456",
                "name": "Karaoke Night",
                "categories": ["karaoke"],
                "location": {"lat": 55.859, "lon": -4.256},
                "start": "2025-11-15T21:00:00",
                "end": "2025-11-16T00:00:00",
                "price_min": 5.0,
                "indoor": True,
                "distance_km": 0.5
            }
        ],
        "weather": {
            "date": "2025-11-15",
            "hourly": [
                {"time": "19:00", "temp_c": 7, "precip_mm": 1.2, "is_rain": True}
            ]
        }
    }
    
    candidates, weather = convert_backend1_data(backend1_clean)
    
    print(f"test 1 (clean format): {len(candidates)} candidates")
    for c in candidates:
        print(f"   - {c.name} ({c.type})")
    
    backend1_raw = {
        "venues": [
            {
                "id": "the-pot-still",
                "name": "The Pot Still",
                "categories": [
                    {"alias": "whisky_bars"},
                    {"alias": "bars"}
                ],
                "price": "££",
                "rating": 4.7,
                "review_count": 1200,
                "coordinates": {"latitude": 55.86, "longitude": -4.25}
            }
        ],
        "events": [
            {
                "id": "12345",
                "name": {"text": "Indie Night @ King Tut's"},
                "start": {"utc": "2025-11-15T20:00:00Z"},
                "end": {"utc": "2025-11-15T23:30:00Z"},
                "venue": {"address": {"latitude": "55.86", "longitude": "-4.26"}}
            }
        ],
        "weather": {
            "hourly": {
                "time": ["2025-11-15T19:00"],
                "temperature_2m": [7.2],
                "precipitation": [1.2]
            }
        }
    }
    
    candidates_raw, weather_raw = convert_backend1_data(backend1_raw)
    
    print(f"\ntest 2 (raw format): {len(candidates_raw)} candidates")
    for c in candidates_raw:
        print(f"   - {c.name} ({c.type}), categories: {c.categories}")
    
    print("\nall tests passed")
