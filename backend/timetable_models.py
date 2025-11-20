# backend/timetable_models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class StopTime:
    """1駅分の到着・発車時刻情報（秒に正規化済み）"""

    station_id: str
    # 日跨ぎを含めた秒数（例: 0〜86399 が1日目、86400〜が2日目…）
    arrival_sec: int | None
    departure_sec: int | None


@dataclass
class TimetableTrain:
    """1本の列車の時刻表（MS3-1 時点では山手線専用で使う）"""

    # 例: "JR-East.Yamanote.400G"
    base_id: str

    # 例: "Weekday" / "Holiday" / "Unknown" など
    # NOTE:
    #   - id の末尾から "Weekday" / "Holiday" などを推定
    #   - 当てはまらない場合は "Unknown" としてログに警告を出す
    service_type: str

    # 例: "JR-East.Yamanote"
    line_id: str
    # 例: "400G"
    number: str
    # 例: "JR-East.Local"
    train_type: str
    # 例: "InnerLoop" / "OuterLoop"
    direction: str

    # 始発駅・終着駅（駅IDの配列）
    # NOTE:
    #   - destination_stations は ds が複数の場合、そのまま複数保持する
    origin_stations: List[str]
    destination_stations: List[str]

    # 停車駅のリスト（順番通り）
    stops: List[StopTime]
