# backend/analyze_trip_ids.py
import os
from collections import Counter
from dotenv import load_dotenv
from gtfs_client import GtfsClient

load_dotenv()

client = GtfsClient()
entities = client.fetch_vehicle_positions()

# trip_id のプレフィックス（最初の3桁）を集計
prefixes = Counter()
suffixes = Counter()  # 末尾のアルファベット

for entity in entities:
    if not entity.HasField('trip_update'):
        continue
    
    trip_id = getattr(entity.trip_update.trip, 'trip_id', '')
    if trip_id:
        # プレフィックス（最初の3桁）
        prefix = trip_id[:3] if len(trip_id) >= 3 else trip_id
        prefixes[prefix] += 1
        
        # サフィックス（末尾1文字）
        suffix = trip_id[-1] if trip_id else ''
        suffixes[suffix] += 1

print("=== Trip ID Prefix Analysis ===")
for prefix, count in prefixes.most_common(20):
    print(f"  {prefix}XXXX: {count} trains")

print("\n=== Trip ID Suffix Analysis ===")
for suffix, count in suffixes.most_common():
    print(f"  XXXXXX{suffix}: {count} trains")

print(f"\nTotal entities: {len(entities)}")