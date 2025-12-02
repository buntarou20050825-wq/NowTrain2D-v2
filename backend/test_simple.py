"""簡易テストスクリプト - タイムスタンプと列車数のみ表示"""
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
    
    if not positions:
        print("No trains found")
        return
    
    # タイムスタンプ
    print(f"\nTimestamp: {positions[0].timestamp}")
    
    # 統計
    outer = [p for p in positions if p.direction == 'OuterLoop']
    inner = [p for p in positions if p.direction == 'InnerLoop']
    unknown = [p for p in positions if p.direction == 'Unknown']
    
    print(f"\n=== 山手線列車: 合計 {len(positions)}本 ===")
    print(f"外回り (OuterLoop): {len(outer)}本")
    print(f"内回り (InnerLoop): {len(inner)}本")
    if unknown:
        print(f"不明 (Unknown): {len(unknown)}本")
    
    # サンプル表示（最初の3本）
    print(f"\n=== サンプル（最初の3本）===")
    for i, pos in enumerate(positions[:3], 1):
        print(f"{i}. trip_id={pos.trip_id}, 番号={pos.train_number}, "
              f"方向={pos.direction}, 座標=({pos.latitude:.4f}, {pos.longitude:.4f})")

if __name__ == "__main__":
    main()
