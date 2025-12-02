# backend/check_stop_details.py
import os
from dotenv import load_dotenv
from gtfs_client import GtfsClient

load_dotenv()

client = GtfsClient()
entities = client.fetch_vehicle_positions()

print(f"Total entities: {len(entities)}\n")

# 最初の5件を詳細に確認
for entity in entities[:5]:
    if not entity.HasField('trip_update'):
        continue
    
    trip = entity.trip_update.trip
    trip_id = getattr(trip, 'trip_id', '')
    stop_updates = entity.trip_update.stop_time_update
    
    print(f"=== Trip ID: {trip_id} ===")
    print(f"Stop count: {len(stop_updates)}")
    
    # 最初の3つの stop_time_update を詳細表示
    for i, stu in enumerate(stop_updates[:3]):
        print(f"\n  Stop [{i}]:")
        print(f"    stop_id: '{getattr(stu, 'stop_id', 'N/A')}'")
        print(f"    stop_sequence: {getattr(stu, 'stop_sequence', 'N/A')}")
        
        # arrival
        if stu.HasField('arrival'):
            arr = stu.arrival
            print(f"    arrival.time: {getattr(arr, 'time', 'N/A')}")
            print(f"    arrival.delay: {getattr(arr, 'delay', 'N/A')}")
        else:
            print(f"    arrival: None")
        
        # departure
        if stu.HasField('departure'):
            dep = stu.departure
            print(f"    departure.time: {getattr(dep, 'time', 'N/A')}")
            print(f"    departure.delay: {getattr(dep, 'delay', 'N/A')}")
        else:
            print(f"    departure: None")
    
    print("\n" + "="*50 + "\n")