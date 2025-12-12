from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import TYPE_CHECKING, Optional
import logging
import math

from pydantic import BaseModel

if TYPE_CHECKING:
    from train_state import TrainSectionState
    from data_cache import DataCache
    from gtfs_rt_vehicle import YamanoteTrainPosition

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
    departure_time: Optional[int] = None # 発車予定時刻（秒）
    data_quality: str = "timetable_only"  # "good", "stale", "rejected", "timetable_only", "error"


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
    departure_time: Optional[int]
    data_quality: str

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
            departure_time=state.segment_end_sec,  # 停車セグメントの終了時刻＝発車時刻
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
        departure_time=None,  # 走行中は次駅到着時刻などが該当するが、ここではNoneまたは次セグメント情報が必要
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


# ============================================================================
# Phase 1: Geometry Helper Functions for Hybrid Position Estimation
# ============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    2点間の距離をメートルで返す（Haversine公式）
    """
    R = 6371000  # 地球の半径（メートル）
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def point_to_segment_distance(
    px: float, py: float,  # ターゲット点 (lon, lat)
    ax: float, ay: float,  # 線分始点 (lon, lat)
    bx: float, by: float   # 線分終点 (lon, lat)
) -> tuple[float, float, float, float]:
    """
    点から線分への最短距離と、最近接点の位置を返す。
    
    Returns:
        (distance_m, nearest_lon, nearest_lat, t)
        - distance_m: 最短距離（メートル）
        - nearest_lon, nearest_lat: 最近接点の座標
        - t: 線分上の位置パラメータ（0.0〜1.0）
    """
    dx = bx - ax
    dy = by - ay
    
    if dx == 0 and dy == 0:
        # 線分が点の場合
        return haversine_distance(py, px, ay, ax), ax, ay, 0.0
    
    # 線分上のパラメータ t を計算
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))  # 0〜1にクランプ
    
    # 最近接点
    nearest_lon = ax + t * dx
    nearest_lat = ay + t * dy
    
    # 距離
    dist = haversine_distance(py, px, nearest_lat, nearest_lon)
    
    return dist, nearest_lon, nearest_lat, t


def get_segment_coords(
    from_station_id: str,
    to_station_id: str,
    direction: str,
    cache: "DataCache"
) -> list[list[float]] | None:
    """
    駅間の座標列を取得する（環状線・方向対応版）。
    
    Args:
        from_station_id: 出発駅ID（例: "JR-East.Yamanote.Shibuya"）
        to_station_id: 到着駅ID（例: "JR-East.Yamanote.Ebisu"）
        direction: 列車の進行方向（"OuterLoop" or "InnerLoop"）
        cache: データキャッシュ
    
    Returns:
        座標列 [[lon, lat], ...] または None（取得失敗時）
        ※ 座標は from → to の順番で並ぶ（列車の進行方向）
    """
    from_idx = cache.station_track_indices.get(from_station_id)
    to_idx = cache.station_track_indices.get(to_station_id)
    
    if from_idx is None or to_idx is None:
        return None
    
    if not cache.track_points:
        return None
    
    total_points = len(cache.track_points)
    
    if direction == "OuterLoop":
        # 外回り: track_points のインデックス増加方向に進む
        if from_idx <= to_idx:
            coords = cache.track_points[from_idx:to_idx + 1]
        else:
            # 0をまたぐ場合（例: 品川 → 大崎 → 五反田）
            coords = cache.track_points[from_idx:] + cache.track_points[:to_idx + 1]
    else:
        # 内回り: track_points のインデックス減少方向に進む
        # → 座標を逆順で取得する
        if from_idx >= to_idx:
            coords = cache.track_points[to_idx:from_idx + 1]
            coords = coords[::-1]  # 逆順にして from → to の順にする
        else:
            # 0をまたぐ場合（例: 五反田 → 大崎 → 品川）
            coords = cache.track_points[to_idx:] + cache.track_points[:from_idx + 1]
            coords = coords[::-1]
    
    # tuple を list に変換
    return [[c[0], c[1]] for c in coords]


def estimate_segment_progress(
    segment_coords: list[list[float]],  # [[lon, lat], [lon, lat], ...]
    target_lat: float,
    target_lon: float,
    max_distance_m: float = 200.0
) -> float | None:
    """
    GTFS-RT座標から区間内の進捗率を推定する。
    
    Args:
        segment_coords: 区間の座標列 [[lon, lat], ...]（from → to の順）
        target_lat: GTFS-RTの緯度
        target_lon: GTFS-RTの経度
        max_distance_m: 線路からの最大許容距離（メートル）
    
    Returns:
        進捗率 (0.0〜1.0) または None（計算不能・異常時）
    """
    # 1. 入力検証
    if not segment_coords or len(segment_coords) < 2:
        return None
    
    # 2. 累積距離の計算
    cumulative_distances = [0.0]
    for i in range(1, len(segment_coords)):
        prev = segment_coords[i - 1]
        curr = segment_coords[i]
        dist = haversine_distance(prev[1], prev[0], curr[1], curr[0])
        cumulative_distances.append(cumulative_distances[-1] + dist)
    
    total_length = cumulative_distances[-1]
    if total_length < 1.0:  # 1m未満はゼロ除算防止
        return None
    
    # 3. 最近接点の探索
    min_dist = float('inf')
    best_segment_idx = 0
    best_t = 0.0
    best_nearest_lon = segment_coords[0][0]
    best_nearest_lat = segment_coords[0][1]
    
    for i in range(len(segment_coords) - 1):
        ax, ay = segment_coords[i]
        bx, by = segment_coords[i + 1]
        
        dist, nearest_lon, nearest_lat, t = point_to_segment_distance(
            target_lon, target_lat, ax, ay, bx, by
        )
        
        if dist < min_dist:
            min_dist = dist
            best_segment_idx = i
            best_t = t
            best_nearest_lon = nearest_lon
            best_nearest_lat = nearest_lat
    
    # 4. 距離チェック
    if min_dist > max_distance_m:
        return None
    
    # 5. 進捗率の計算
    # セグメント始点から最近接点までの距離を計算
    segment_start_dist = cumulative_distances[best_segment_idx]
    segment_length = (cumulative_distances[best_segment_idx + 1] - 
                     cumulative_distances[best_segment_idx])
    
    progress_distance = segment_start_dist + best_t * segment_length
    progress = progress_distance / total_length
    
    # 6. クランプして返す
    return max(0.0, min(1.0, progress))


# ============================================================================
# Phase 1: Main Blending Logic
# ============================================================================

def train_state_to_position_with_override(
    state: "TrainSectionState",
    cache: "DataCache",
    override_progress: float | None = None,
    data_quality: str = "timetable_only"
) -> Optional[TrainPosition]:
    """
    TrainSectionState を TrainPosition（座標）に変換する。
    override_progress が指定された場合、state.progress の代わりにその値を使用する。
    """
    train = state.train

    train_id = (
        f"{train.base_id}.{train.service_type}"
        if train.service_type and train.service_type != "Unknown"
        else train.base_id
    )

    # 停車中
    if state.is_stopped:
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
            departure_time=state.segment_end_sec,
            data_quality=data_quality,
        )

    # 走行中
    from_id = state.from_station_id
    to_id = state.to_station_id
    
    progress = override_progress if override_progress is not None else state.progress

    coords = _interpolate_coords(from_id, to_id, progress, train.direction, cache)
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
        progress=progress,
        lon=lon,
        lat=lat,
        current_time_sec=state.current_time_sec,
        is_scheduled=True,
        delay_seconds=0,
        departure_time=None,
        data_quality=data_quality,
    )


def get_blended_train_positions(
    current_time: datetime,
    cache: "DataCache",
    gtfs_data: dict[str, "YamanoteTrainPosition"] | None = None
) -> list[TrainPosition]:
    """
    時刻表ベースの位置にGTFS-RTの補正を適用した列車位置を返す。
    
    Args:
        current_time: 現在時刻
        cache: データキャッシュ
        gtfs_data: GTFS-RTデータ（train_numberをキーとする辞書）
    
    Returns:
        補正済みの列車位置リスト
    """
    from train_state import get_yamanote_trains_at, blend_progress
    
    # 1. 時刻表から現在の列車状態を取得（既存ロジック）
    states = get_yamanote_trains_at(current_time, cache)
    
    results = []
    blend_stats = {"good": 0, "stale": 0, "rejected": 0, "timetable_only": 0, "error": 0}
    
    for state in states:
        # 2. マッチするGTFS-RTデータを探す
        gtfs_position = None
        if gtfs_data and state.train.number in gtfs_data:
            gtfs_position = gtfs_data[state.train.number]
        
        # 3. 走行中の場合のみブレンド処理を試みる
        blended_progress = state.progress
        data_quality = "timetable_only"
        
        if not state.is_stopped and gtfs_position is not None:
            try:
                # 3a. 区間の座標列を取得（方向を考慮）
                segment_coords = get_segment_coords(
                    state.from_station_id,
                    state.to_station_id,
                    state.train.direction,
                    cache
                )
                
                if segment_coords and len(segment_coords) >= 2:
                    # 3b. GTFS-RT座標から進捗率を推定
                    rt_progress = estimate_segment_progress(
                        segment_coords,
                        gtfs_position.latitude,
                        gtfs_position.longitude
                    )
                    
                    if rt_progress is not None:
                        # 3c. staleness を計算
                        staleness_sec = current_time.timestamp() - gtfs_position.timestamp
                        
                        # 3d. ブレンド
                        blended_progress, data_quality = blend_progress(
                            state.progress,
                            rt_progress,
                            staleness_sec
                        )
            except Exception as e:
                # エラー時は時刻表の値をそのまま使用
                logger.warning(f"Blend failed for {state.train.number}: {e}")
                blended_progress = state.progress
                data_quality = "error"
        
        # 4. 進捗率を座標に変換
        position = train_state_to_position_with_override(
            state, 
            cache, 
            override_progress=blended_progress,
            data_quality=data_quality
        )
        
        if position:
            blend_stats[data_quality] = blend_stats.get(data_quality, 0) + 1
            results.append(position)
    
    logger.info(
        f"Blended {len(results)} trains: good={blend_stats['good']}, "
        f"stale={blend_stats['stale']}, rejected={blend_stats['rejected']}, "
        f"timetable_only={blend_stats['timetable_only']}, error={blend_stats['error']}"
    )
    
    return results

