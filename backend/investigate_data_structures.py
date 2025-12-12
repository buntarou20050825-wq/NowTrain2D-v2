"""
調査スクリプト: GTFS-RTとDataCacheのデータ構造を調査
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# データディレクトリのパス（修正済み）
base_dir = Path("C:/Users/bunta/NowTrain2D-v2")
data_dir = base_dir / "data"

output_lines = []

def log(msg):
    print(msg)
    output_lines.append(msg)

# 1. GTFS-RT VehiclePosition の実際のデータ
log("=" * 60)
log("1. GTFS-RT VehiclePosition データ構造")
log("=" * 60)

from gtfs_rt_vehicle import fetch_yamanote_positions_sync

api_key = os.getenv("ODPT_API_KEY", "").strip()
positions = fetch_yamanote_positions_sync(api_key)

log(f"\n取得した列車数: {len(positions)}")
if positions:
    sample = positions[0]
    log(f"\nサンプルデータ (1件目):")
    log(f"  trip_id:       {sample.trip_id}")
    log(f"  train_number:  {sample.train_number}")
    log(f"  direction:     {sample.direction}")
    log(f"  latitude:      {sample.latitude}")
    log(f"  longitude:     {sample.longitude}")
    log(f"  stop_sequence: {sample.stop_sequence}")
    log(f"  status:        {sample.status}")
    log(f"  timestamp:     {sample.timestamp}")
    
    log(f"\n全列車のtrain_number一覧 (最初の10件):")
    for p in positions[:10]:
        log(f"  {p.train_number} (trip_id: {p.trip_id})")

# 2. 時刻表のID形式
log("\n" + "=" * 60)
log("2. 時刻表のID形式")
log("=" * 60)

timetable_path = data_dir / "mini-tokyo-3d/train-timetables/jreast-yamanote.json"

if timetable_path.exists():
    with open(timetable_path, "r", encoding="utf-8") as f:
        timetables = json.load(f)
    
    log(f"\n時刻表の列車数: {len(timetables)}")
    
    if timetables:
        sample = timetables[0]
        log(f"\nサンプルデータ (1件目):")
        log(f"  id:     {sample.get('id', 'N/A')}")
        log(f"  t:      {sample.get('t', 'N/A')}")  # base_id
        log(f"  r:      {sample.get('r', 'N/A')}")  # line_id
        log(f"  n:      {sample.get('n', 'N/A')}")  # number (列車番号)
        log(f"  y:      {sample.get('y', 'N/A')}")  # train_type
        log(f"  d:      {sample.get('d', 'N/A')}")  # direction
        log(f"  os:     {sample.get('os', 'N/A')}")  # origin_stations
        log(f"  ds:     {sample.get('ds', 'N/A')}")  # destination_stations
        
        tt = sample.get('tt', [])
        if tt:
            log(f"\n  時刻表の最初の停車駅:")
            for stop in tt[:3]:
                log(f"    s: {stop.get('s', 'N/A')}, a: {stop.get('a', 'N/A')}, d: {stop.get('d', 'N/A')}")
        
        log(f"\n時刻表の全number一覧 (最初の10件):")
        for t in timetables[:10]:
            log(f"  n={t.get('n', 'N/A')}, id={t.get('id', 'N/A')}")
else:
    log(f"\n時刻表ファイルが見つかりません: {timetable_path}")

# 3. 駅IDの形式比較
log("\n" + "=" * 60)
log("3. 駅IDの形式")
log("=" * 60)

# stations.json から駅ID形式を確認
stations_path = data_dir / "mini-tokyo-3d/stations.json"
if stations_path.exists():
    with open(stations_path, "r", encoding="utf-8") as f:
        stations = json.load(f)
    
    # 山手線の駅だけ抽出
    yamanote_stations = [s for s in stations if "JR-East.Yamanote" in s.get("railway", "")]
    
    log(f"\n山手線の駅数: {len(yamanote_stations)}")
    log(f"\nサンプル駅ID (最初の5件):")
    for s in yamanote_stations[:5]:
        log(f"  id: {s.get('id', 'N/A')}")
        log(f"    railway: {s.get('railway', 'N/A')}")
        coord = s.get('coord', 'N/A')
        log(f"    coord: {coord}")
        log("")
else:
    log(f"stations.jsonが見つかりません: {stations_path}")

# 4. 区間座標（coordinates.json）の構造
log("\n" + "=" * 60)
log("4. 区間座標（coordinates.json）の構造")
log("=" * 60)

coords_path = data_dir / "mini-tokyo-3d/coordinates.json"
if coords_path.exists():
    with open(coords_path, "r", encoding="utf-8") as f:
        coordinates = json.load(f)
    
    railways_coords = coordinates.get("railways", [])
    
    yamanote_coords = None
    for r in railways_coords:
        if r.get("id") == "JR-East.Yamanote":
            yamanote_coords = r
            break
    
    if yamanote_coords:
        sublines = yamanote_coords.get("sublines", [])
        log(f"\n山手線のsubline数: {len(sublines)}")
        
        if sublines:
            first_subline = sublines[0]
            log(f"\n最初のsublineの構造:")
            log(f"  キー: {list(first_subline.keys())}")
            
            coords = first_subline.get("coords", [])
            log(f"  座標点数: {len(coords)}")
            if coords:
                log(f"  最初の座標: {coords[0]}")
                log(f"  2番目の座標: {coords[1] if len(coords) > 1 else 'N/A'}")
            
            # subline にセクションIDや駅IDはあるか？
            log(f"\n全sublineのキー/データサンプル:")
            for i, sub in enumerate(sublines[:3]):
                log(f"  [{i}] キー: {list(sub.keys())}, 座標数: {len(sub.get('coords', []))}")
    else:
        log("山手線の座標データが見つかりません")
else:
    log(f"coordinates.jsonが見つかりません: {coords_path}")

# 5. DataCacheの station_track_indices の確認
log("\n" + "=" * 60)
log("5. DataCacheのstation_track_indices")
log("=" * 60)

import sys
sys.path.insert(0, str(base_dir / "backend"))
from data_cache import DataCache

cache = DataCache(data_dir)
cache.load_all()

log(f"\ntrack_points数: {len(cache.track_points)}")
log(f"station_track_indices数: {len(cache.station_track_indices)}")

if cache.station_track_indices:
    log(f"\nサンプル駅インデックス (最初の5件):")
    for station_id, idx in list(cache.station_track_indices.items())[:5]:
        log(f"  {station_id}: インデックス {idx}")
        if cache.track_points and 0 <= idx < len(cache.track_points):
            coord = cache.track_points[idx]
            log(f"    座標: ({coord[0]}, {coord[1]})")

# 6. マッチングキーの比較
log("\n" + "=" * 60)
log("6. train_id マッチング分析")
log("=" * 60)

# GTFS-RT の train_number と 時刻表の n (number) を比較
gtfs_train_numbers = set(p.train_number for p in positions)
timetable_numbers = set()

if timetable_path.exists():
    with open(timetable_path, "r", encoding="utf-8") as f:
        timetables = json.load(f)
    timetable_numbers = set(t.get('n', '') for t in timetables if t.get('n'))

log(f"\nGTFS-RT train_numbers: {len(gtfs_train_numbers)} 件")
log(f"時刻表 numbers: {len(timetable_numbers)} 件")

# 一致するものを検出
matching = gtfs_train_numbers.intersection(timetable_numbers)
log(f"一致: {len(matching)} 件")

if matching:
    log(f"\n一致例 (最初の5件): {list(matching)[:5]}")

# 一致しないもの
gtfs_only = gtfs_train_numbers - timetable_numbers
if gtfs_only:
    log(f"\nGTFS-RTにのみ存在 (時刻表になし): {list(gtfs_only)[:10]}")

log("\n" + "=" * 60)
log("調査完了")
log("=" * 60)

# 結果をファイルに保存
with open("investigation_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

print("\n結果を investigation_results.txt に保存しました")
