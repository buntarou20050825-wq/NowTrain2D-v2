# backend/check_stop_ids.py
import os
from dotenv import load_dotenv
from gtfs_client import GtfsClient

load_dotenv()

client = GtfsClient()
entities = client.fetch_vehicle_positions()

print(f"Total entities: {len(entities)}\n")

# 各列車の stop_id を確認
for entity in entities[:20]:
    if not entity.HasField('trip_update'):
        continue
    
    trip = entity.trip_update.trip
    trip_id = getattr(trip, 'trip_id', '')
    stop_updates = entity.trip_update.stop_time_update
    
    print(f"Trip ID: {trip_id}")
    print(f"  Stop count: {len(stop_updates)}")
    
    # 最初の3つの stop_id を表示
    for i, stu in enumerate(stop_updates[:3]):
        stop_id = getattr(stu, 'stop_id', 'N/A')
        print(f"    [{i}] stop_id: {stop_id}")
    
    # 山手線っぽいか判定
    if len(stop_updates) >= 28:
        print(f"  >>> Possible Yamanote (30 stations) <<<")
    
    print()