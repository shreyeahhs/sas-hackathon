# BACKEND 2 - DATA and API's
# -------------------------------------------------------------------------

"""
This module handles connection to API's
Yelp for venues
Skiddle for events
Open Meteo for weather

cleans and will normalise all the external data into a single JSON format

prepares a fallback local dataset (seed.json) with around 50 venues/events in Glasgow, as a precautionary measure incase API fails

adds caching so repeated queries do not trigger repeated API calls
"""

from fastapi import FASTAPI
from functools import lru_cache
import requests
import pandas as pd

app = FASTAPI()

# Keys
GOOGLE_API_KEY = "AIzaSyBxs2jnmgryVX46-H3kKf7PJEk6rfu825Y"

# Fallback Dataset
def load_fallback():
    try:
        df = pd.read_csv("glasgow_fallback_seed.csv")
        seed= []
        for _, row in df.iterrows():
            seed.append({
                "name": row["name"],
                "type": "venue",
                "location": row.get("vibe", "Unknown"),
                "coordinates": {"lat": 55.8642, 'lng': -4.2518},
                "date": None,
                "price": row.get("pricing", "££"),
                "mood": row.get("mood", ""),
                "cuisine": row.get("cuisine", ""),
                "weather": None
            })
        return seed
    except Exception as e:
        print("Error loading fallback CSV:", e)
        return []
SEED_DATA = load_fallback()

# Google places API 
def get_google_places(location="Glasgow", term="bars"):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{term} in {location}",
        "key": GOOGLE_API_KEY,
        "region": "uk"
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return normalise_google_places(response.json())

def normalise_google_places(data):
    results = []
    for place in data.get("results", []):
        results.append({
            "name": place.get("name"),
            "type": "venue",
            "location": place.get("formatted_address", "Unknown"),
            "coordinates": {
                "lat": place["geometry"]["location"]["lat"],
                "lng": place["geometry"]["location"]["lng"]
            },
            "date": None,
            "price": str(place.get("price_level", "££")),
            "mood": None,
            "cuisine": None,
            "weather": None
        })
    return results

# open meteo API
def get_weather(lat=55.8642, lon=-4.2518):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "current_weather": True}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data.get("current_weather", {}).get("weathercode", "Clear")

# Routes for endpoints
@app.get("/")
def home ():
    return {"message": "Back end running"}
    
@app.get("/recommendations")
def get_recommendations(location: str = "Glasgow", term: str = "bars"):
    try:
        venues = (location, term)
        events = (location)