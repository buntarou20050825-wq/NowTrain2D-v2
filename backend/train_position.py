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


def _get_path_points(
    start_idx: int,
    end_idx: int,
    direction: str,
    track_points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """
    開始インデックスから終了インデックスまでの座標リストを取得する。
    山手線は環状線なので、インデックスのラップアラウンドを考慮する。
    
    Args:
        start_idx: 出発駅のtrack_pointsインデックス
        end_idx: 到着駅のtrack_pointsインデックス
        direction: "InnerLoop" or "OuterLoop"
        track_points: 線路座標リスト（外回り順）
    
    Returns:
        出発駅から到着駅までの座標リスト
    """
    if direction == "OuterLoop":
        # 外回り: インデックス増加方向
        if start_idx <= end_idx:
            return track_points[start_idx : end_idx + 1]
        else:
            # ラップアラウンド（例: 品川→大崎→五反田）
            return track_points[start_idx:] + track_points[: end_idx + 1]
    else:
        # 内回り: インデックス減少方向
        if start_idx >= end_idx:
            # Pythonのスライス [start:end:-1] は endを含まないので注意
            # end_idx を含めるために end_idx-1 までとするが、end_idxが0の場合は特別扱いが必要
            if end_idx == 0:
                return track_points[start_idx::-1]
            else:
                return track_points[start_idx : end_idx - 1 : -1]
        else:
            # ラップアラウンド（例: 五反田→大崎→品川）
            # 前半: start_idx -> 0
            part1 = track_points[start_idx::-1]
            # 後半: last -> end_idx
            part2 = track_points[: end_idx - 1 : -1] if end_idx > 0 else track_points[::-1]
            # 正確には track_points[end:] の逆順
            part2 = track_points[: end_idx - 1 : -1] if end_idx > 0 else track_points[::-1]
            
            # シンプルに実装し直す: 全体を逆順にしたリストから抽出する方が安全かもしれないが、
            # ここではインデックス操作で頑張る
            
            # part1: start_idx から 0 まで逆順
            p1 = track_points[start_idx::-1]
            # part2: 末尾 から end_idx まで逆順
            p2 = track_points[: end_idx - 1 : -1] if end_idx > 0 else track_points[::-1]
            # wait, track_points[: end_idx - 1 : -1] means from end (implicit) down to end_idx
            # slice(None, end_idx-1, -1) -> start at last element, go down to end_idx
            
            return p1 + p2


def _euclidean_distance(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """2点間のユークリッド距離"""
    return ((coord1[0] - coord2[0]) ** 2 + (coord1[1] - coord2[1]) ** 2) ** 0.5


def _get_point_on_path(
    path: list[tuple[float, float]], progress: float
) -> tuple[float, float]:
    """
    パス上の総距離に基づき、進捗 progress (0.0~1.0) に対応する座標を計算する。
    """
    if not path:
        return (0.0, 0.0)
    if len(path) < 2:
        return path[0]

    if progress <= 0.0:
        return path[0]
    if progress >= 1.0:
        return path[-1]

    # 各セグメントの距離を計算
    distances = []
    total_distance = 0.0
    for i in range(len(path) - 1):
        d = _euclidean_distance(path[i], path[i + 1])
        distances.append(d)
        total_distance += d

    if total_distance == 0:
        return path[0]

    # 目標距離
    target_distance = progress * total_distance

    # 目標距離に対応する点を探索
    cumulative = 0.0
    for i, d in enumerate(distances):
        if cumulative + d >= target_distance:
            # この区間内にある
            if d == 0:
                return path[i]
            local_progress = (target_distance - cumulative) / d
            # 線形補間
            lon = path[i][0] + local_progress * (path[i + 1][0] - path[i][0])
            lat = path[i][1] + local_progress * (path[i + 1][1] - path[i][1])
            return (lon, lat)
        cumulative += d

    return path[-1]


def _interpolate_coords(
    from_station_id: Optional[str],
    to_station_id: Optional[str],
    progress: float,
    direction: str,
    cache: DataCache,
) -> Optional[tuple[float, float]]:
    """
    駅 A → 駅 B 間の進捗 progress (0.0〜1.0) に応じて座標を返す。
    MS3-5: 線路形状に沿ったパス補間を行う。
    """
    if from_station_id is None or to_station_id is None:
        return None

    # フォールバック条件のチェック
    # 1. 線路データがない
    # 2. 駅がマッピングされていない
    if (
        not cache.track_points
        or from_station_id not in cache.station_track_indices
        or to_station_id not in cache.station_track_indices
    ):
        # 従来の直線補間（フォールバック）
        start = _get_station_coord(from_station_id, cache)
        end = _get_station_coord(to_station_id, cache)

        if start is None or end is None:
            return None

        lon1, lat1 = start
        lon2, lat2 = end
        
        # クランプ
        progress = max(0.0, min(1.0, progress))

        lon = lon1 + (lon2 - lon1) * progress
        lat = lat1 + (lat2 - lat1) * progress
        return lon, lat

    # Polyline補間
    start_idx = cache.station_track_indices[from_station_id]
    end_idx = cache.station_track_indices[to_station_id]

    path = _get_path_points(start_idx, end_idx, direction, cache.track_points)
    return _get_point_on_path(path, progress)


def _linear_interpolate(
    from_coord: tuple[float, float],
    to_coord: tuple[float, float],
    progress: float,
) -> tuple[float, float]:
    """従来の直線補間（フォールバック用）"""
    lon = from_coord[0] + progress * (to_coord[0] - from_coord[0])
    lat = from_coord[1] + progress * (to_coord[1] - from_coord[1])
    return (lon, lat)


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

    coords = _interpolate_coords(from_id, to_id, state.progress, train.direction, cache)
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
