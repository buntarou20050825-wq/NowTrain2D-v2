#!/usr/bin/env python
"""MS3-2 の動作確認テストスクリプト"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from data_cache import DataCache
from train_state import debug_dump_trains_at, get_service_date, to_effective_seconds, determine_service_type

JST = ZoneInfo("Asia/Tokyo")

def main():
    print("=" * 70)
    print("MS3-2 動作確認テスト")
    print("=" * 70)

    # DataCache の初期化とロード
    data_dir = Path(__file__).parent / "data"
    cache = DataCache(data_dir)

    print(f"\nDataCache を初期化中... (data_dir: {data_dir})")
    cache.load_all()

    print(f"\n読み込み結果:")
    print(f"  - 路線数: {len(cache.railways)}")
    print(f"  - 駅数: {len(cache.stations)}")
    print(f"  - 山手線時刻表: {len(cache.yamanote_trains)} 件")
    print(f"  - 山手線セグメント: {len(cache.yamanote_segments)} 件")

    if cache.yamanote_trains:
        service_types = {t.service_type for t in cache.yamanote_trains}
        print(f"  - サービスタイプ: {sorted(service_types)}")

    # テスト1: 平日朝 8:00 (月曜日想定)
    print("\n" + "=" * 70)
    print("テスト1: 平日朝 8:00 (2025-01-20 月曜日)")
    print("=" * 70)
    dt1 = datetime(2025, 1, 20, 8, 0, tzinfo=JST)
    debug_dump_trains_at(dt1, cache, limit=15)

    # テスト2: 深夜 1:00
    print("\n" + "=" * 70)
    print("テスト2: 深夜 1:00 (2025-01-20)")
    print("=" * 70)
    dt2 = datetime(2025, 1, 20, 1, 0, tzinfo=JST)
    debug_dump_trains_at(dt2, cache, limit=15)

    # テスト3: 土曜朝 8:00
    print("\n" + "=" * 70)
    print("テスト3: 土曜朝 8:00 (2025-01-25 土曜日)")
    print("=" * 70)
    dt3 = datetime(2025, 1, 25, 8, 0, tzinfo=JST)
    debug_dump_trains_at(dt3, cache, limit=15)

    # テスト4: 時間系ユーティリティのテスト
    print("\n" + "=" * 70)
    print("テスト4: 時間系ユーティリティ関数")
    print("=" * 70)

    test_times = [
        datetime(2025, 1, 20, 4, 0, tzinfo=JST),   # サービス日の開始
        datetime(2025, 1, 20, 12, 0, tzinfo=JST),  # 昼間
        datetime(2025, 1, 20, 23, 0, tzinfo=JST),  # 深夜前
        datetime(2025, 1, 21, 2, 0, tzinfo=JST),   # 深夜 (前日のサービス日)
    ]

    for dt in test_times:
        service_date = get_service_date(dt)
        effective_sec = to_effective_seconds(dt)
        service_type = determine_service_type(dt)
        print(f"{dt.isoformat()}")
        print(f"  → サービス日: {service_date}, 秒数: {effective_sec}, タイプ: {service_type}")

    print("\n" + "=" * 70)
    print("テスト完了")
    print("=" * 70)

if __name__ == "__main__":
    main()
