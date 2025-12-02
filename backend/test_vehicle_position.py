"""
VehiclePosition 取得のテストスクリプト
"""
import os
from dotenv import load_dotenv
from gtfs_rt_vehicle import fetch_yamanote_positions_sync

load_dotenv()

def main():
    api_key = os.getenv("ODPT_API_KEY", "").strip()
    if not api_key:
        print("Error: ODPT_API_KEY not set")
        return
    
    print("Fetching Yamanote line positions...")
    positions = fetch_yamanote_positions_sync(api_key)
    
    print(f"\n=== 山手線列車: {len(positions)}本 ===\n")
    print(f"{'trip_id':<12} {'番号':<6} {'方向':<10} {'緯度':<10} {'経度':<12} {'seq':<4} {'ts':<12} {'status'}")
    print("-" * 85)
    
    # 方向別にソート
    for pos in sorted(positions, key=lambda p: (p.direction, p.train_number)):
        print(f"TIMESTAMP: {pos.timestamp}")
        print(f"{pos.trip_id:<12} {pos.train_number:<6} {pos.direction:<10} "
              f"{pos.latitude:<10.4f} {pos.longitude:<12.4f} {pos.stop_sequence:<4} {pos.timestamp:<12} {pos.status}")
    
    # 統計
    outer = [p for p in positions if p.direction == 'OuterLoop']
    inner = [p for p in positions if p.direction == 'InnerLoop']
    print(f"\n外回り: {len(outer)}本")
    print(f"内回り: {len(inner)}本")

if __name__ == "__main__":
    main()
