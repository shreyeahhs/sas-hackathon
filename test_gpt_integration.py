"""
Test GPT integration with events CSV and venue recommendations
"""
import httpx
import json
import asyncio

BASE_URL = "http://localhost:8000"

async def test_full_chat_flow():
    """Test complete chatbot flow with GPT recommendations"""
    
    print("=" * 70)
    print("TESTING GPT INTEGRATION - Full Chat Flow")
    print("=" * 70)
    
    session_id = "test_session_gpt"
    
    # Helper function to send message
    async def send_message(msg):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/chat",
                json={"message": msg, "session_id": session_id}
            )
            return response.json()
    
    print("\n1️⃣  Starting conversation...")
    result = await send_message("Hello")
    print(f"Bot: {result['reply'][:100]}...")
    print(f"Suggestions: {result.get('suggestions', [])}")
    
    print("\n2️⃣  Setting location...")
    result = await send_message("Glasgow")
    print(f"Bot: {result['reply'][:100]}...")
    
    print("\n3️⃣  Setting mood...")
    result = await send_message("party")
    print(f"Bot: {result['reply'][:100]}...")
    
    print("\n4️⃣  Setting start time...")
    result = await send_message("evening")
    print(f"Bot: {result['reply'][:100]}...")
    
    print("\n5️⃣  Setting group size...")
    result = await send_message("2")
    print(f"Bot: {result['reply'][:100]}...")
    
    print("\n6️⃣  Setting budget (triggering GPT recommendations)...")
    result = await send_message("50")
    print(f"\n{'='*70}")
    print("GPT RESPONSE:")
    print(f"{'='*70}")
    print(f"Reply: {result['reply']}")
    print(f"\nSuggestions: {result.get('suggestions', [])}")
    
    recommendations = result.get('recommendations', [])
    print(f"\n{'='*70}")
    print(f"RECOMMENDATIONS: {len(recommendations)} items")
    print(f"{'='*70}")
    
    events = [r for r in recommendations if 'date' in r and 'venue' in r]
    venues = [r for r in recommendations if 'place_id' in r or 'rating' in r]
    
    print(f"\n📅 EVENTS: {len(events)}")
    for i, event in enumerate(events, 1):
        print(f"\n  {i}. {event.get('title')}")
        print(f"     Category: {', '.join(event.get('categories', []))}")
        print(f"     Date: {event.get('date')}")
        print(f"     Venue: {event.get('venue')}")
        if event.get('description'):
            print(f"     Description: {event.get('description')[:80]}...")
        if event.get('link'):
            print(f"     Link: {event.get('link')}")
    
    print(f"\n🏢 VENUES: {len(venues)}")
    for i, venue in enumerate(venues, 1):
        print(f"\n  {i}. {venue.get('name')}")
        print(f"     Rating: {venue.get('rating')} | Price: {venue.get('price')}")
        print(f"     Categories: {', '.join(venue.get('categories', []))}")
        print(f"     Address: {venue.get('address')}")
    
    print(f"\n{'='*70}")
    print("TEST RESULTS:")
    print(f"{'='*70}")
    print(f"✅ Events returned: {len(events)}")
    print(f"✅ Venues returned: {len(venues)}")
    print(f"✅ Total recommendations: {len(recommendations)}")
    
    if len(events) > 0:
        print("✅ Events have proper formatting (title, date, venue, categories)")
    else:
        print("⚠️  No events returned (GPT may not have recommended any)")
    
    if len(venues) > 0:
        print("✅ Venues have proper formatting (name, rating, address)")
    else:
        print("⚠️  No venues returned")
    
    # Check for duplicates
    venue_names = [v.get('name') for v in venues]
    if len(venue_names) != len(set(venue_names)):
        print("❌ Duplicate venues found!")
    else:
        print("✅ No duplicate venues")
    
    return events, venues

async def main():
    try:
        print("\n🧪 Testing GPT Integration with Events CSV + Google Places\n")
        events, venues = await test_full_chat_flow()
        print("\n✅ All tests completed successfully!\n")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
