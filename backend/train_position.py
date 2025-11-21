from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import TYPE_CHECKING, Optional
import logging

from pydantic import BaseModel

if TYPE_CHECKING:
    from train_state import TrainSectionState
    from data_cache import DataCache

logger = logging.getLogger(__name__)


@dataclass
class TrainPosition:
    """
    列車の「地図上の位置」と付随情報（内部用）

    - JSON 化しやすいように、プリミティブ型のみを持つ
    """
    # 列車ID関連
    train_id: str         # 例: "JR-East.Yamanote.400G.Weekday"
    base_id: str          # 例: "JR-East.Yamanote.400G"
    number: str           # 例: "400G"
    service_type: str     # 例: "Weekday", "SaturdayHoliday", "Unknown"

    # 路線・方向
    line_id: str          # 例: "JR-East.Yamanote"
    direction: str        # 例: "InnerLoop", "OuterLoop"

    # 状態
    is_stopped: bool
    station_id: Optional[str]        # 停車中の駅ID（is_stopped=True のとき）
    from_station_id: Optional[str]   # 走行中セグメントの起点駅
    to_station_id: Optional[str]     # 走行中セグメントの終点駅
    progress: float               # 0.0〜1.0（停車中は0.0）

    # 座標（必須）
    lon: float
    lat: float

    # 時間情報（サービス日内秒数）
    current_time_sec: int

    # 将来の GTFS-RT 統合用フィールド（今はデフォルト値）
    is_scheduled: bool = True     # 時刻表ベースの位置なら True
    delay_seconds: int = 0        # 遅延秒数（GTFS-RT統合時に使用）


class TrainPositionResponse(BaseModel):
    train_id: str
    base_id: str
    number: str
    service_type: str
    line_id: str
    direction: str

    is_stopped: bool
    station_id: Optional[str]
    from_station_id: Optional[str]
    to_station_id: Optional[str]
    progress: float

    lon: float
    lat: float

    current_time_sec: int

    is_scheduled: bool
    delay_seconds: int

    @classmethod
    def from_dataclass(cls, pos: TrainPosition) -> "TrainPositionResponse":
        """
        内部の dataclass を API レスポンスに変換するヘルパー
        """
        return cls(**asdict(pos))


class YamanotePositionsResponse(BaseModel):
    """
    /api/yamanote/positions のレスポンスラッパー

    - 今後フィールドを足しても互換性を保ちやすくするためにオブジェクトで返す
    """
    positions: list[TrainPositionResponse]
    count: int
    timestamp: str  # リクエスト時刻（JST, ISO8601文字列）


def _get_station_coord(
    station_id: Optional[str],
    cache: DataCache,
) -> Optional[tuple[float, float]]:
    """
    station_id から (lon, lat) を取得するヘルパー。
    見つからない場合は警告ログを出し None を返す。
    """
    if not station_id:
        return None

    coord = cache.station_positions.get(station_id)
    if coord is None:
        logger.warning(
            "No coordinates for station_id=%s; skipping related train state",
            station_id,
        )
        return None

    return coord


def _interpolate_coords(
    from_station_id: Optional[str],
    to_station_id: Optional[str],
    progress: float,
    cache: DataCache,
) -> Optional[tuple[float, float]]:
    """
    駅 A → 駅 B 間の進捗 progress (0.0〜1.0) に応じて、
    線形補間した座標を返す。

    - どちらかの駅座標が無い場合は None を返す。
    - progress は [0.0, 1.0] にクランプする。
    """
    if from_station_id is None or to_station_id is None:
        return None

    start = _get_station_coord(from_station_id, cache)
    end = _get_station_coord(to_station_id, cache)

    if start is None or end is None:
        logger.warning(
            "Missing coordinates for segment %s → %s; skipping",
            from_station_id,
            to_station_id,
        )
        return None

    lon1, lat1 = start
    lon2, lat2 = end

    # クランプ
    if progress < 0.0:
        progress = 0.0
    elif progress > 1.0:
        progress = 1.0

    lon = lon1 + (lon2 - lon1) * progress
    lat = lat1 + (lat2 - lat1) * progress

    return lon, lat


def train_state_to_position(
    state: TrainSectionState,
    cache: DataCache,
) -> Optional[TrainPosition]:
    """
    1本の列車状態を地図座標付きの TrainPosition に変換する。

    - 座標が取得できない場合は None を返す。
    - 停車中: 駅座標そのものを使う
    - 走行中: from/to 駅間を直線補間
    """
    train = state.train

    # train_id は base_id + service_type で再構成しておく
    train_id = (
        f"{train.base_id}.{train.service_type}"
        if train.service_type and train.service_type != "Unknown"
        else train.base_id
    )

    # ★ 停車中
    if state.is_stopped:
        # 明示的な stopped_at_station_id を優先し、無ければ from_station_id を使う
        station_id = state.stopped_at_station_id or state.from_station_id

        coord = _get_station_coord(station_id, cache)
        if coord is None:
            return None

        lon, lat = coord

        return TrainPosition(
            train_id=train_id,
            base_id=train.base_id,
            number=train.number,
            service_type=train.service_type,
            line_id=train.line_id,
            direction=train.direction,
            is_stopped=True,
            station_id=station_id,
            from_station_id=None,
            to_station_id=None,
            progress=0.0,
            lon=lon,
            lat=lat,
            current_time_sec=state.current_time_sec,
            is_scheduled=True,
            delay_seconds=0,
        )

    # ★ 走行中
    from_id = state.from_station_id
    to_id = state.to_station_id

    coords = _interpolate_coords(from_id, to_id, state.progress, cache)
    if coords is None:
        return None

    lon, lat = coords

    return TrainPosition(
        train_id=train_id,
        base_id=train.base_id,
        number=train.number,
        service_type=train.service_type,
        line_id=train.line_id,
        direction=train.direction,
        is_stopped=False,
        station_id=None,
        from_station_id=from_id,
        to_station_id=to_id,
        progress=state.progress,
        lon=lon,
        lat=lat,
        current_time_sec=state.current_time_sec,
        is_scheduled=True,
        delay_seconds=0,
    )


def get_yamanote_train_positions(
    dt_jst: datetime,
    cache: DataCache,
) -> list[TrainPosition]:
    """
    指定した JST 時刻における山手線の全列車位置を返す。

    - MS3-2 の get_yamanote_trains_at() を利用
    - 座標が取得できない列車はスキップ
    """
    from train_state import get_yamanote_trains_at

    states = get_yamanote_trains_at(dt_jst, cache)
    result: list[TrainPosition] = []
    skipped = 0

    for state in states:
        try:
            pos = train_state_to_position(state, cache)
            if pos is None:
                skipped += 1
                continue
            result.append(pos)
        except Exception as e:
            logger.warning(
                "Failed to convert train state to position for train %s: %s",
                state.train.base_id,
                e,
            )
            skipped += 1
            continue

    logger.info(
        "Converted %d Yamanote train states to positions (skipped %d states)",
        len(result),
        skipped,
    )

    return result


def debug_dump_positions_at(
    dt_jst: datetime,
    cache: DataCache,
    limit: int = 10,
) -> None:
    """
    指定時刻における山手線列車の位置を、コンソールにダンプする。
    """
    from train_state import (
        get_service_date,
        to_effective_seconds,
        determine_service_type,
    )

    positions = get_yamanote_train_positions(dt_jst, cache)

    service_date = get_service_date(dt_jst)
    service_sec = to_effective_seconds(dt_jst)
    service_type = determine_service_type(dt_jst)

    print("\n" + "=" * 60)
    print(f"時刻 (JST): {dt_jst.isoformat()}")
    print(f"サービス日: {service_date}")
    print(f"サービス秒: {service_sec}")
    print(f"service_type: {service_type}")
    print(f"列車数: {len(positions)}")
    print("=" * 60 + "\n")

    for i, pos in enumerate(positions[:limit], start=1):
        if pos.is_stopped:
            print(
                f"{i:2d}. {pos.number:>6s} {pos.direction:>10s} "
                f"[停車] {pos.station_id}  "
                f"({pos.lon:.5f}, {pos.lat:.5f})"
            )
        else:
            print(
                f"{i:2d}. {pos.number:>6s} {pos.direction:>10s} "
                f"{pos.from_station_id} → {pos.to_station_id} "
                f"({pos.progress*100:5.1f}%) "
                f"({pos.lon:.5f}, {pos.lat:.5f})"
            )

    if len(positions) > limit:
        print(f"\n... 他 {len(positions) - limit} 本\n")
