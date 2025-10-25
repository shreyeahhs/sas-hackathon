# BACKEND 2 - Recommendation logic
# Use it f0r the best Glasg0w night 0ut !!
# -------------------------------------------------------------------------

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
    Top 10: Super Trouper bar (score 86), Dancing Queen (82), etc
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
    date: str  # year - month - day <- important <- date format
    start_time: str  # "HH:MM" (hours:minutes)
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
    
    # venue parameters
    price_tier: Optional[int] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    open_hours: Optional[Dict[str, List[List[int]]]] = None
    capacity_hint: Optional[int] = None
    
    # event parametes
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
    
