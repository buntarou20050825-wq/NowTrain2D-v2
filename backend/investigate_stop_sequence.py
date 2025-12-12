"""
stop_sequence → 駅ID マッピングの詳細調査
"""
import os
import requests
from google.transit import gtfs_realtime_pb2
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('ODPT_API_KEY', '').strip()

print("=" * 70)
print("stop_sequence → 駅ID マッピング調査")
print("=" * 70)

# TripUpdate から stop_sequence → stop_id のマッピングを取得
url = 'https://api-challenge.odpt.org/api/v4/gtfs/realtime/jreast_odpt_train_trip_update'
response = requests.get(url, params={'acl:consumerKey': api_key}, timeout=30)
feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(response.content)

outer_loop_mapping = {}  # 外回り
inner_loop_mapping = {}  # 内回り

for entity in feed.entity:
    if not entity.HasField('trip_update'):
        continue
    
    tu = entity.trip_update
    trip_id = tu.trip.trip_id
    
    if not trip_id.endswith('G'):
        continue
    
    # 外回り判定
    is_outer = trip_id.startswith('4201') or trip_id.startswith('4200')
    is_inner = trip_id.startswith('4211') or trip_id.startswith('4210')
    
    for stu in tu.stop_time_update:
        seq = stu.stop_sequence
        stop_id = stu.stop_id
        
        if is_outer and seq not in outer_loop_mapping:
            outer_loop_mapping[seq] = stop_id
        elif is_inner and seq not in inner_loop_mapping:
            inner_loop_mapping[seq] = stop_id

print("\n【外回り】stop_sequence → stop_id")
print("-" * 50)
for seq in sorted(outer_loop_mapping.keys()):
    print(f"  seq={seq:2d} → {outer_loop_mapping[seq]}")

print("\n【内回り】stop_sequence → stop_id")
print("-" * 50)
for seq in sorted(inner_loop_mapping.keys()):
    print(f"  seq={seq:2d} → {inner_loop_mapping[seq]}")

# 外回りと内回りの駅順序を確認
print("\n【比較】同じ seq でも駅が違うか？")
print("-" * 50)
all_seqs = set(outer_loop_mapping.keys()) | set(inner_loop_mapping.keys())
for seq in sorted(all_seqs):
    outer = outer_loop_mapping.get(seq, "N/A")
    inner = inner_loop_mapping.get(seq, "N/A")
    match = "✅" if outer == inner else "❌"
    print(f"  seq={seq:2d}: 外回り={outer:45s} 内回り={inner} {match}")

print("\n" + "=" * 70)
print("結論:")
print("=" * 70)

if outer_loop_mapping and inner_loop_mapping:
    # 最初と最後の駅を確認
    print(f"\n外回り: seq=1 → {outer_loop_mapping.get(1, 'N/A')}")
    print(f"内回り: seq=1 → {inner_loop_mapping.get(1, 'N/A')}")
    
    # 同じseqで駅が違うものがあるか
    diff_count = 0
    for seq in all_seqs:
        if outer_loop_mapping.get(seq) != inner_loop_mapping.get(seq):
            diff_count += 1
    
    if diff_count > 0:
        print(f"\n⚠️ 外回りと内回りで同じseqでも駅が異なるケースが {diff_count} 件あり")
        print("   → direction も考慮した変換が必要")
    else:
        print("\n✅ 外回りと内回りで stop_sequence → stop_id は同一")
