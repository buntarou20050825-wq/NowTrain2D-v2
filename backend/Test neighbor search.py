#!/usr/bin/env python3
"""
Neighbor Search テストスクリプト

前後区間サーチ機能のユニットテスト
"""

import sys
sys.path.insert(0, '.')

from train_position import (
    YAMANOTE_STATION_ORDER,
    YAMANOTE_STATION_INDEX,
    NUM_YAMANOTE_STATIONS,
    get_adjacent_segments,
    estimate_segment_progress_extended,
    haversine_distance,
)


def test_station_order():
    """駅順序データの検証"""
    print("\n=== Test: Station Order ===")
    
    # 30駅あることを確認
    assert len(YAMANOTE_STATION_ORDER) == 30, f"Expected 30 stations, got {len(YAMANOTE_STATION_ORDER)}"
    print(f"✓ Station count: {len(YAMANOTE_STATION_ORDER)}")
    
    # インデックスマッピングの整合性
    assert len(YAMANOTE_STATION_INDEX) == 30
    for idx, station in enumerate(YAMANOTE_STATION_ORDER):
        assert YAMANOTE_STATION_INDEX[station] == idx
    print("✓ Station index mapping is consistent")
    
    # 大崎が0、品川が29
    assert YAMANOTE_STATION_INDEX["JR-East.Yamanote.Osaki"] == 0
    assert YAMANOTE_STATION_INDEX["JR-East.Yamanote.Shinagawa"] == 29
    print("✓ Osaki=0, Shinagawa=29")
    
    print("All station order tests passed!")


def test_adjacent_segments_outer_loop():
    """外回りの隣接区間取得テスト"""
    print("\n=== Test: Adjacent Segments (OuterLoop) ===")
    
    # 通常ケース: 渋谷→原宿 (外回り)
    # 期待: [(渋谷→原宿), (恵比寿→渋谷), (原宿→代々木)]
    segments = get_adjacent_segments(
        "JR-East.Yamanote.Shibuya",
        "JR-East.Yamanote.Harajuku",
        "OuterLoop"
    )
    
    print(f"Shibuya→Harajuku (OuterLoop):")
    for i, (f, t) in enumerate(segments):
        label = ["Expected", "Previous", "Next"][i]
        print(f"  {label}: {f.split('.')[-1]}→{t.split('.')[-1]}")
    
    assert len(segments) == 3
    assert segments[0] == ("JR-East.Yamanote.Shibuya", "JR-East.Yamanote.Harajuku")
    assert segments[1] == ("JR-East.Yamanote.Ebisu", "JR-East.Yamanote.Shibuya")
    assert segments[2] == ("JR-East.Yamanote.Harajuku", "JR-East.Yamanote.Yoyogi")
    print("✓ OuterLoop normal case passed")
    
    # 環状線境界ケース: 品川→大崎 (外回り、29→0をまたぐ)
    segments = get_adjacent_segments(
        "JR-East.Yamanote.Shinagawa",
        "JR-East.Yamanote.Osaki",
        "OuterLoop"
    )
    
    print(f"\nShinagawa→Osaki (OuterLoop, wrapping 29→0):")
    for i, (f, t) in enumerate(segments):
        label = ["Expected", "Previous", "Next"][i]
        print(f"  {label}: {f.split('.')[-1]}→{t.split('.')[-1]}")
    
    assert segments[0] == ("JR-East.Yamanote.Shinagawa", "JR-East.Yamanote.Osaki")
    # 前の区間: 高輪ゲートウェイ(28)→品川(29)
    assert segments[1] == ("JR-East.Yamanote.TakanawaGateway", "JR-East.Yamanote.Shinagawa")
    # 次の区間: 大崎(0)→五反田(1)
    assert segments[2] == ("JR-East.Yamanote.Osaki", "JR-East.Yamanote.Gotanda")
    print("✓ OuterLoop boundary case passed")
    
    print("All OuterLoop tests passed!")


def test_adjacent_segments_inner_loop():
    """内回りの隣接区間取得テスト"""
    print("\n=== Test: Adjacent Segments (InnerLoop) ===")
    
    # 通常ケース: 原宿→渋谷 (内回り)
    # インデックス: 原宿=5, 渋谷=4 (減少方向)
    # 期待: [(原宿→渋谷), (代々木(6)→原宿), (渋谷→恵比寿(3))]
    segments = get_adjacent_segments(
        "JR-East.Yamanote.Harajuku",
        "JR-East.Yamanote.Shibuya",
        "InnerLoop"
    )
    
    print(f"Harajuku→Shibuya (InnerLoop):")
    for i, (f, t) in enumerate(segments):
        label = ["Expected", "Previous", "Next"][i]
        print(f"  {label}: {f.split('.')[-1]}→{t.split('.')[-1]}")
    
    assert len(segments) == 3
    assert segments[0] == ("JR-East.Yamanote.Harajuku", "JR-East.Yamanote.Shibuya")
    # 前の区間: 代々木(6)→原宿(5)
    assert segments[1] == ("JR-East.Yamanote.Yoyogi", "JR-East.Yamanote.Harajuku")
    # 次の区間: 渋谷(4)→恵比寿(3)
    assert segments[2] == ("JR-East.Yamanote.Shibuya", "JR-East.Yamanote.Ebisu")
    print("✓ InnerLoop normal case passed")
    
    # 環状線境界ケース: 大崎→品川 (内回り、0→29をまたぐ)
    segments = get_adjacent_segments(
        "JR-East.Yamanote.Osaki",
        "JR-East.Yamanote.Shinagawa",
        "InnerLoop"
    )
    
    print(f"\nOsaki→Shinagawa (InnerLoop, wrapping 0→29):")
    for i, (f, t) in enumerate(segments):
        label = ["Expected", "Previous", "Next"][i]
        print(f"  {label}: {f.split('.')[-1]}→{t.split('.')[-1]}")
    
    assert segments[0] == ("JR-East.Yamanote.Osaki", "JR-East.Yamanote.Shinagawa")
    # 前の区間: 五反田(1)→大崎(0)
    assert segments[1] == ("JR-East.Yamanote.Gotanda", "JR-East.Yamanote.Osaki")
    # 次の区間: 品川(29)→高輪ゲートウェイ(28)
    assert segments[2] == ("JR-East.Yamanote.Shinagawa", "JR-East.Yamanote.TakanawaGateway")
    print("✓ InnerLoop boundary case passed")
    
    print("All InnerLoop tests passed!")


def test_haversine_distance():
    """Haversine距離計算のテスト"""
    print("\n=== Test: Haversine Distance ===")
    
    # 渋谷駅〜原宿駅間（約1.4km）
    shibuya_lat, shibuya_lon = 35.6580, 139.7016
    harajuku_lat, harajuku_lon = 35.6702, 139.7027
    
    dist = haversine_distance(shibuya_lat, shibuya_lon, harajuku_lat, harajuku_lon)
    print(f"Shibuya to Harajuku: {dist:.0f}m")
    assert 1200 < dist < 1500, f"Expected ~1360m, got {dist}"
    print("✓ Distance calculation reasonable")
    
    # 同一点
    dist_zero = haversine_distance(35.0, 139.0, 35.0, 139.0)
    assert dist_zero < 1, f"Expected ~0, got {dist_zero}"
    print("✓ Same point = 0 distance")
    
    print("Haversine tests passed!")


def test_estimate_segment_progress_extended():
    """拡張進捗推定のテスト"""
    print("\n=== Test: Extended Segment Progress ===")
    
    # 簡単な直線区間
    # 渋谷(35.6580, 139.7016) → 原宿(35.6702, 139.7027)
    segment_coords = [
        [139.7016, 35.6580],  # Shibuya
        [139.7027, 35.6702],  # Harajuku
    ]
    
    # 始点付近（渋谷駅から少し北）
    result = estimate_segment_progress_extended(
        segment_coords,
        35.6590,  # 少し北（原宿方向）
        139.7017,
        max_distance_m=500.0
    )
    
    print(f"Near Shibuya station:")
    print(f"  Progress: {result['progress']:.3f}")
    print(f"  Distance: {result['distance_m']:.1f}m")
    
    assert result is not None
    assert result['progress'] < 0.15, "Should be near start"
    assert result['distance_m'] < 150
    print("✓ Start point detection OK")
    
    # 中間点付近
    mid_lat = (35.6580 + 35.6702) / 2
    mid_lon = (139.7016 + 139.7027) / 2
    
    result = estimate_segment_progress_extended(
        segment_coords,
        mid_lat,
        mid_lon,
        max_distance_m=500.0
    )
    
    print(f"\nMidpoint:")
    print(f"  Progress: {result['progress']:.3f}")
    print(f"  Distance: {result['distance_m']:.1f}m")
    
    assert result is not None
    assert 0.4 < result['progress'] < 0.6, "Should be near middle"
    print("✓ Midpoint detection OK")
    
    # 距離超過（線路から遠い点）
    result = estimate_segment_progress_extended(
        segment_coords,
        35.70,  # かなり北
        139.71,
        max_distance_m=500.0
    )
    
    print(f"\nFar point (should be None): {result}")
    assert result is None, "Should reject points > 500m"
    print("✓ Distance rejection OK")
    
    print("Extended progress estimation tests passed!")


def test_unknown_station():
    """未知の駅IDのハンドリング"""
    print("\n=== Test: Unknown Station Handling ===")
    
    segments = get_adjacent_segments(
        "Unknown.Station.A",
        "Unknown.Station.B",
        "OuterLoop"
    )
    
    print(f"Unknown stations result: {segments}")
    assert len(segments) == 1
    assert segments[0] == ("Unknown.Station.A", "Unknown.Station.B")
    print("✓ Unknown stations return original segment only")
    
    print("Unknown station handling passed!")


def run_all_tests():
    """全テストを実行"""
    print("=" * 60)
    print("Neighbor Search Unit Tests")
    print("=" * 60)
    
    test_station_order()
    test_adjacent_segments_outer_loop()
    test_adjacent_segments_inner_loop()
    test_haversine_distance()
    test_estimate_segment_progress_extended()
    test_unknown_station()
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()