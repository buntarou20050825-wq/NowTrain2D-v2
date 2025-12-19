"""
MS2 Integration Test - Verify position calculation with real TripUpdate data
"""
import asyncio
import os
from dotenv import load_dotenv
import httpx
from pathlib import Path

load_dotenv()

# Import modules
import sys
sys.path.insert(0, str(Path(__file__).parent))

from data_cache import DataCache
from gtfs_rt_tripupdate import fetch_trip_updates
from train_position_v4 import compute_all_progress, debug_progress_stats


async def main():
    # Load data cache
    data_dir = Path(__file__).parent.parent / "data"
    data_cache = DataCache(data_dir)
    data_cache.load_all()
    
    # Get API key
    api_key = os.getenv("ODPT_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ODPT_API_KEY not set")
        return
    
    # Fetch TripUpdates (MS1)
    print("Fetching TripUpdates (MS1)...")
    async with httpx.AsyncClient() as client:
        schedules = await fetch_trip_updates(client, api_key, data_cache)
    
    print(f"Fetched {len(schedules)} Yamanote trains")
    
    # Compute progress (MS2)
    print("\nComputing progress (MS2)...")
    results = compute_all_progress(schedules)
    
    # Stats
    stats = debug_progress_stats(results)
    print(f"\n=== MS2 Statistics ===")
    print(f"Total: {stats['total']}")
    print(f"Running: {stats['running']}")
    print(f"Stopped: {stats['stopped']}")
    print(f"Unknown: {stats['unknown']}")
    print(f"Invalid: {stats['invalid']}")
    
    # Verify progress values are in range
    progress_errors = []
    for r in results:
        if r.progress is not None:
            if r.progress < 0.0 or r.progress > 1.0:
                progress_errors.append(f"{r.train_number}: progress={r.progress}")
    
    if progress_errors:
        print(f"\n⚠️ Progress out of range: {progress_errors}")
    else:
        print(f"\n✅ All progress values in 0.0-1.0 range")
    
    # Show some examples
    print("\n=== Sample Results ===")
    for r in results[:3]:
        print(f"\nTrain {r.train_number} ({r.direction}):")
        print(f"  Status: {r.status}")
        print(f"  Progress: {r.progress}")
        print(f"  Segment: {r.prev_station_id} -> {r.next_station_id}")
        print(f"  Seq: {r.prev_seq} -> {r.next_seq}")
    
    # Validate no 31->1 segments (loop closure)
    loop_errors = []
    for r in results:
        if r.prev_seq == 31 and r.next_seq == 1:
            loop_errors.append(r.train_number)
    
    if loop_errors:
        print(f"\n⚠️ Loop closure detected (31->1): {loop_errors}")
    else:
        print(f"\n✅ No 31->1 loop closure (correct)")
    
    # Write results to file
    with open("ms2_test_output.txt", "w") as f:
        f.write(f"=== MS2 Test Results ===\n")
        f.write(f"Total: {stats['total']}\n")
        f.write(f"Running: {stats['running']}\n")
        f.write(f"Stopped: {stats['stopped']}\n")
        f.write(f"Unknown: {stats['unknown']}\n")
        f.write(f"Invalid: {stats['invalid']}\n")
        f.write(f"\nProgress in range: {'Yes' if not progress_errors else 'No'}\n")
        f.write(f"No 31->1 loop: {'Yes' if not loop_errors else 'No'}\n")
        
        f.write(f"\n=== All Results ===\n")
        for r in results:
            f.write(f"{r.train_number}: status={r.status}, progress={r.progress}, "
                   f"seg={r.prev_seq}->{r.next_seq}\n")
    
    print("\nOutput written to ms2_test_output.txt")


if __name__ == "__main__":
    asyncio.run(main())
