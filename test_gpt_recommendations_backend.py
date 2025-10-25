"""
Test script for GPT recommendations with events CSV integration
"""
import asyncio
import sys
import os

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.backend3 import get_events_summary_for_gpt, ConversationState, get_combined_recommendations_with_gpt


async def test_events_summary():
    """Test events summary generation for GPT"""
    print("=" * 60)
    print("TEST 1: Events Summary for GPT")
    print("=" * 60)
    
    summary = get_events_summary_for_gpt(max_events=10)
    print(summary)
    print(f"\nLength: {len(summary)} characters")
    print()


async def test_gpt_recommendations():
    """Test full GPT recommendation flow"""
    print("=" * 60)
    print("TEST 2: GPT Recommendations with Events + Venues")
    print("=" * 60)
    
    # Create mock conversation state
    state = ConversationState(
        session_id="test",
        location="Glasgow",
        location_lat=55.8642,
        location_lng=-4.2518,
        group_size=4,
        mood=["party", "chill"],
        budget_per_person=30,
        start_time="evening",
        preferences={"price_tier_max": 2},
        stage="budget"
    )
    
    query = "I'm looking for a fun night out with 4 people, budget £30 per person"
    
    print(f"User Query: {query}")
    print(f"State: location={state.location}, group={state.group_size}, mood={state.mood}, budget=£{state.budget_per_person}")
    print("\nCalling GPT recommendations...\n")
    
    try:
        text_response, venues = await get_combined_recommendations_with_gpt(state, query)
        
        print("=" * 60)
        print("GPT RESPONSE:")
        print("=" * 60)
        print(text_response)
        print()
        
        print("=" * 60)
        print(f"VENUES FOUND: {len(venues)}")
        print("=" * 60)
        for i, venue in enumerate(venues, 1):
            print(f"\n{i}. {venue}")
        
        if not venues:
            print("(No venues returned)")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n🧪 Testing GPT Recommendations Backend\n")
    
    await test_events_summary()
    await test_gpt_recommendations()
    
    print("\n✅ Tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
