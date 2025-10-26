import httpx
import asyncio

GOOGLE_PLACES_API_KEY = "AIzaSyBxs2jnmgryVX46-H3kKf7PJEk6rfu825Y"

async def test_google_places():
    async with httpx.AsyncClient() as client:
        # Geocode Glasgow
        geo_response = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": "Glasgow", "key": GOOGLE_PLACES_API_KEY}
        )
        geo_data = geo_response.json()
        
        print("=== GEOCODING ===")
        print(f"Status: {geo_data.get('status')}")
        
        if geo_data.get("status") == "OK" and geo_data.get("results"):
            loc = geo_data["results"][0]["geometry"]["location"]
            lat, lng = loc["lat"], loc["lng"]
            print(f"Glasgow: {lat}, {lng}\n")
            
            # Search for bars
            places_response = await client.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params={
                    "location": f"{lat},{lng}",
                    "radius": 5000,
                    "type": "bar",
                    "key": GOOGLE_PLACES_API_KEY
                }
            )
            places_data = places_response.json()
            
            print("=== PLACES SEARCH ===")
            print(f"Status: {places_data.get('status')}")
            print(f"Found: {len(places_data.get('results', []))} venues\n")
            
            print("=== TOP 5 BARS IN GLASGOW ===")
            for i, place in enumerate(places_data.get("results", [])[:5], 1):
                name = place.get("name", "")
                rating = place.get("rating", "N/A")
                address = place.get("vicinity", "")
                price_level = place.get("price_level", 2)
                price = "£" * max(1, price_level) if price_level else "££"
                
                print(f"{i}. {name}")
                print(f"   ⭐ {rating} | {price}")
                print(f"   📍 {address}\n")
        else:
            print(f"Error: {geo_data}")

asyncio.run(test_google_places())
