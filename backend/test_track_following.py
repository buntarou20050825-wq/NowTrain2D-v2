"""
MS3-5 線路形状追従の検証スクリプト
"""
from data_cache import DataCache
from train_position import _interpolate_coords, _linear_interpolate
import logging
from pathlib import Path

# ログ設定
logging.basicConfig(level=logging.INFO)

def test_track_following():
    print("Initializing DataCache...")
    cache = DataCache(Path("../data"))
    cache.load_all()
    
    print(f"Track points loaded: {len(cache.track_points)}")
    print(f"Station indices mapped: {len(cache.station_track_indices)}")
    
    if not cache.track_points:
        print("ERROR: No track points loaded!")
        return

    # テストケース1: 渋谷→新宿（外回り）
    # カーブが多い区間なので差が出るはず
    test_interpolation(
        cache,
        from_id="JR-East.Yamanote.Shibuya",
        to_id="JR-East.Yamanote.Shinjuku",
        direction="OuterLoop",
        progress=0.5
    )
    
    # テストケース2: 品川→五反田（外回り、大崎をまたぐ）
    # 品川(29) -> 大崎(0) -> 五反田(1) のようなラップアラウンド
    test_interpolation(
        cache,
        from_id="JR-East.Yamanote.Shinagawa",
        to_id="JR-East.Yamanote.Gotanda",
        direction="OuterLoop",
        progress=0.5
    )
    
    # テストケース3: 新宿→渋谷（内回り）
    # 逆方向
    test_interpolation(
        cache,
        from_id="JR-East.Yamanote.Shinjuku",
        to_id="JR-East.Yamanote.Shibuya",
        direction="InnerLoop",
        progress=0.5
    )

def test_interpolation(cache, from_id, to_id, direction, progress):
    from_station = cache.station_positions.get(from_id)
    to_station = cache.station_positions.get(to_id)
    
    if not from_station or not to_station:
        print(f"Station not found: {from_id} or {to_id}")
        return

    # 直線補間
    linear = _linear_interpolate(from_station, to_station, progress)
    
    # Polyline補間
    polyline = _interpolate_coords(from_id, to_id, progress, direction, cache)
    
    print(f"\n{from_id.split('.')[-1]} → {to_id.split('.')[-1]} ({direction})")
    print(f"  直線補間:   ({linear[0]:.6f}, {linear[1]:.6f})")
    print(f"  Polyline補間: ({polyline[0]:.6f}, {polyline[1]:.6f})")
    
    diff_lon = abs(linear[0]-polyline[0])
    diff_lat = abs(linear[1]-polyline[1])
    print(f"  差分: ({diff_lon:.6f}, {diff_lat:.6f})")
    
    if diff_lon > 0.0001 or diff_lat > 0.0001:
        print("  ✅ Significant difference detected (Track following active)")
    else:
        print("  ⚠️ Little difference (Straight track or fallback?)")

if __name__ == "__main__":
    test_track_following()
