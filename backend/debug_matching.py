"""
Debug script to compare GTFS-RT and timetable train numbers - Text output version
"""
import os
import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

JST = ZoneInfo("Asia/Tokyo")
BASE_DIR = Path(__file__).resolve().parent.parent  # NowTrain-v2/
DATA_DIR = BASE_DIR / "data"

async def main():
    from data_cache import DataCache
    from train_state import get_yamanote_trains_at
    from gtfs_rt_vehicle import fetch_yamanote_positions, get_train_number
    
    api_key = os.getenv("ODPT_API_KEY", "").strip()
    current_time = datetime.now(JST)
    
    output = []
    output.append("=" * 60)
    output.append(f"Debug: Train ID Comparison")
    output.append(f"Time: {current_time.isoformat()}")
    output.append("=" * 60)
    
    cache = DataCache(DATA_DIR)
    cache.load_all()
    output.append(f"\n[Cache] Loaded {len(cache.yamanote_segments)} segments")
    
    states = get_yamanote_trains_at(current_time, cache)
    timetable_numbers = sorted(set(s.train.number for s in states))
    output.append(f"\n[Timetable] {len(states)} trains active")
    output.append(f"[Timetable] Sample: {timetable_numbers[:10]}")
    
    try:
        gtfs_positions = await fetch_yamanote_positions(api_key)
        output.append(f"\n[GTFS-RT] {len(gtfs_positions)} positions fetched")
        
        output.append("\n[GTFS-RT] Raw data sample (first 10):")
        for p in gtfs_positions[:10]:
            extracted = get_train_number(p.trip_id)
            output.append(f"  trip_id={p.trip_id} -> train_number={p.train_number}")
        
        gtfs_numbers = sorted(set(p.train_number for p in gtfs_positions))
        
    except Exception as e:
        output.append(f"\n[GTFS-RT] Error: {e}")
        gtfs_numbers = []
        gtfs_positions = []
    
    timetable_set = set(timetable_numbers)
    gtfs_set = set(gtfs_numbers)
    
    matched = timetable_set & gtfs_set
    only_timetable = timetable_set - gtfs_set
    only_gtfs = gtfs_set - timetable_set
    
    output.append("\n" + "=" * 60)
    output.append("COMPARISON RESULTS")
    output.append("=" * 60)
    output.append(f"Matched: {len(matched)}")
    output.append(f"Only in Timetable: {len(only_timetable)}")
    output.append(f"Only in GTFS-RT: {len(only_gtfs)}")
    
    output.append(f"\n[Matched sample]: {sorted(matched)[:10]}")
    output.append(f"[Only Timetable sample]: {sorted(only_timetable)[:10]}")
    output.append(f"[Only GTFS-RT sample]: {sorted(only_gtfs)[:10]}")
    
    output.append("\n" + "=" * 60)
    output.append("UNMATCHED GTFS DETAIL (All)")
    output.append("=" * 60)
    
    for num in sorted(only_gtfs):
        orig = next((p for p in gtfs_positions if p.train_number == num), None)
        if orig:
            output.append(f"  {num}: trip_id={orig.trip_id}")
    
    # Write to file with UTF-8
    with open("debug_result.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    
    print("Results saved to debug_result.txt")

if __name__ == "__main__":
    asyncio.run(main())
