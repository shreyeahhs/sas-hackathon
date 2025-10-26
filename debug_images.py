import sys
sys.path.insert(0, '.')
from event_scraper import GlasgowEventScraper
import json

scraper = GlasgowEventScraper()

print('Refreshing events cache with better images...')
events = scraper.get_events_cached(force_refresh=True)

print(f'\nTotal events: {len(events)}')
events_with_images = [e for e in events if e.get('image_url')]
real_images = [e for e in events if e.get('image_url') and 'placeholder' not in e['image_url']]

print(f'Events with any image_url: {len(events_with_images)}')
print(f'Events with real (non-placeholder) images: {len(real_images)}')

if real_images:
    print('\n=== Sample Event with Real Image ===')
    print(json.dumps(real_images[0], indent=2))

