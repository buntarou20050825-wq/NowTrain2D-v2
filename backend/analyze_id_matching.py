"""
MS4-2: Train ID Matching Analysis Script
Compare GTFS-RT trip_id with static timetable train numbers
"""
import json
from pathlib import Path
from gtfs_client import GtfsClient

def main():
    # Load static timetable
    static_path = Path("../data/mini-tokyo-3d/train-timetables/jreast-yamanote.json")
    with open(static_path, 'r', encoding='utf-8') as f:
        static_trains = json.load(f)
    
    # Extract unique train numbers from static data
    static_numbers = set()
    for train in static_trains:
        number = train.get('n', '')
        if number:
            static_numbers.add(number)
    
    print(f"Static timetable: {len(static_trains)} trains")
    print(f"Unique train numbers: {len(static_numbers)}")
    print(f"Sample static numbers: {sorted(list(static_numbers))[:10]}")
    print()
    
    # Fetch GTFS-RT data
    client = GtfsClient()
    entities = client.fetch_vehicle_positions()
    
    print(f"GTFS-RT: {len(entities)} entities")
    print()
    
    # Analyze trip_id patterns
    trip_ids = []
    for entity in entities[:20]:  # First 20 for analysis
        if entity.HasField('trip_update'):
            trip = entity.trip_update.trip
            trip_id = trip.trip_id if trip.HasField('trip_id') else ""
            route_id = trip.route_id if trip.HasField('route_id') else ""
            direction_id = trip.direction_id if trip.HasField('direction_id') else None
            
            trip_ids.append({
                'trip_id': trip_id,
                'route_id': route_id,
                'direction_id': direction_id
            })
    
    print("Sample GTFS-RT trip_ids:")
    for i, t in enumerate(trip_ids[:10], 1):
        print(f"  {i}. trip_id='{t['trip_id']}', route_id='{t['route_id']}', direction={t['direction_id']}")
    print()
    
    # Try to find patterns
    print("=" * 60)
    print("PATTERN ANALYSIS")
    print("=" * 60)
    
    # Check if trip_id contains train number
    print("\nChecking if GTFS trip_id contains static train numbers...")
    matches = []
    for t in trip_ids:
        trip_id = t['trip_id']
        for static_num in list(static_numbers)[:50]:  # Check first 50
            if static_num in trip_id:
                matches.append((trip_id, static_num))
    
    if matches:
        print(f"Found {len(matches)} potential matches:")
        for trip_id, static_num in matches[:5]:
            print(f"  trip_id '{trip_id}' contains '{static_num}'")
    else:
        print("No direct substring matches found.")
    
    print()
    print("=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("1. Analyze trip_id format (e.g., does it encode train number?)")
    print("2. Check if stop_time_update stop_ids match Yamanote stations")
    print("3. Consider using departure times for matching")
    print("4. May need to consult ODPT documentation or static GTFS")

if __name__ == "__main__":
    main()
