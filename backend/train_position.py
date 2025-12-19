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
    
    # GTFS-RT 生情報
    gtfs_stop_sequence: Optional[int] = None
    gtfs_status: Optional[int] = None
    
    # 比較表示用座標（Phase 1 追加）
    timetable_lat: Optional[float] = None  # 純粋な時刻表ベースの位置
    timetable_lon: Optional[float] = None
    gtfs_lat: Optional[float] = None       # 純粋なGTFS-RTの位置
    gtfs_lon: Optional[float] = None


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
    
    # GTFS-RT 生情報
    gtfs_stop_sequence: Optional[int] = None
    gtfs_status: Optional[int] = None
    
    # 比較表示用座標（Phase 1 追加）
    timetable_lat: Optional[float] = None
    timetable_lon: Optional[float] = None
    gtfs_lat: Optional[float] = None
    gtfs_lon: Optional[float] = None

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


# ============================================================================
# 山手線の駅順序データ（Neighbor Search用）
# ============================================================================

YAMANOTE_STATION_ORDER = [
    "JR-East.Yamanote.Osaki",           # 0
    "JR-East.Yamanote.Gotanda",         # 1
    "JR-East.Yamanote.Meguro",          # 2
    "JR-East.Yamanote.Ebisu",           # 3
    "JR-East.Yamanote.Shibuya",         # 4
    "JR-East.Yamanote.Harajuku",        # 5
    "JR-East.Yamanote.Yoyogi",          # 6
    "JR-East.Yamanote.Shinjuku",        # 7
    "JR-East.Yamanote.ShinOkubo",       # 8
    "JR-East.Yamanote.Takadanobaba",    # 9
    "JR-East.Yamanote.Mejiro",          # 10
    "JR-East.Yamanote.Ikebukuro",       # 11
    "JR-East.Yamanote.Otsuka",          # 12
    "JR-East.Yamanote.Sugamo",          # 13
    "JR-East.Yamanote.Komagome",        # 14
    "JR-East.Yamanote.Tabata",          # 15
    "JR-East.Yamanote.NishiNippori",    # 16
    "JR-East.Yamanote.Nippori",         # 17
    "JR-East.Yamanote.Uguisudani",      # 18
    "JR-East.Yamanote.Ueno",            # 19
    "JR-East.Yamanote.Okachimachi",     # 20
    "JR-East.Yamanote.Akihabara",       # 21
    "JR-East.Yamanote.Kanda",           # 22
    "JR-East.Yamanote.Tokyo",           # 23
    "JR-East.Yamanote.Yurakucho",       # 24
    "JR-East.Yamanote.Shimbashi",       # 25
    "JR-East.Yamanote.Hamamatsucho",    # 26
    "JR-East.Yamanote.Tamachi",         # 27
    "JR-East.Yamanote.TakanawaGateway", # 28
    "JR-East.Yamanote.Shinagawa",       # 29
]

YAMANOTE_STATION_INDEX = {
    station_id: idx for idx, station_id in enumerate(YAMANOTE_STATION_ORDER)
}

NUM_YAMANOTE_STATIONS = len(YAMANOTE_STATION_ORDER)


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
    """
    if direction == "OuterLoop":
        if start_idx <= end_idx:
            return track_points[start_idx : end_idx + 1]
        else:
            return track_points[start_idx:] + track_points[: end_idx + 1]
    else:
        if start_idx >= end_idx:
            if end_idx == 0:
                return track_points[start_idx::-1]
            else:
                return track_points[start_idx : end_idx - 1 : -1]
        else:
            p1 = track_points[start_idx::-1]
            p2 = track_points[: end_idx - 1 : -1] if end_idx > 0 else track_points[::-1]
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

    distances = []
    total_distance = 0.0
    for i in range(len(path) - 1):
        d = _euclidean_distance(path[i], path[i + 1])
        distances.append(d)
        total_distance += d

    if total_distance == 0:
        return path[0]

    target_distance = progress * total_distance

    cumulative = 0.0
    for i, d in enumerate(distances):
        if cumulative + d >= target_distance:
            if d == 0:
                return path[i]
            local_progress = (target_distance - cumulative) / d
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
    """
    if from_station_id is None or to_station_id is None:
        return None

    if (
        not cache.track_points
        or from_station_id not in cache.station_track_indices
        or to_station_id not in cache.station_track_indices
    ):
        start = _get_station_coord(from_station_id, cache)
        end = _get_station_coord(to_station_id, cache)

        if start is None or end is None:
            return None

        lon1, lat1 = start
        lon2, lat2 = end
        
        progress = max(0.0, min(1.0, progress))

        lon = lon1 + (lon2 - lon1) * progress
        lat = lat1 + (lat2 - lat1) * progress
        return lon, lat

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
    """
    train = state.train

    train_id = (
        f"{train.base_id}.{train.service_type}"
        if train.service_type and train.service_type != "Unknown"
        else train.base_id
    )

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
        )

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
        departure_time=None,
    )


def get_yamanote_train_positions(
    dt_jst: datetime,
    cache: DataCache,
) -> list[TrainPosition]:
    """
    指定した JST 時刻における山手線の全列車位置を返す。
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
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def point_to_segment_distance(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float
) -> tuple[float, float, float, float]:
    """
    点から線分への最短距離と、最近接点の位置を返す。
    
    Returns:
        (distance_m, nearest_lon, nearest_lat, t)
    """
    dx = bx - ax
    dy = by - ay
    
    if dx == 0 and dy == 0:
        return haversine_distance(py, px, ay, ax), ax, ay, 0.0
    
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    
    nearest_lon = ax + t * dx
    nearest_lat = ay + t * dy
    
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
    """
    from_idx = cache.station_track_indices.get(from_station_id)
    to_idx = cache.station_track_indices.get(to_station_id)
    
    if from_idx is None or to_idx is None:
        return None
    
    if not cache.track_points:
        return None
    
    total_points = len(cache.track_points)
    
    if direction == "OuterLoop":
        if from_idx <= to_idx:
            coords = cache.track_points[from_idx:to_idx + 1]
        else:
            coords = cache.track_points[from_idx:] + cache.track_points[:to_idx + 1]
    else:
        if from_idx >= to_idx:
            coords = cache.track_points[to_idx:from_idx + 1]
            coords = coords[::-1]
        else:
            coords = cache.track_points[to_idx:] + cache.track_points[:from_idx + 1]
            coords = coords[::-1]
    
    return [[c[0], c[1]] for c in coords]


def estimate_segment_progress(
    segment_coords: list[list[float]],
    target_lat: float,
    target_lon: float,
    max_distance_m: float = 500.0
) -> float | None:
    """
    GTFS-RT座標から区間内の進捗率を推定する。
    """
    if not segment_coords or len(segment_coords) < 2:
        return None
    
    cumulative_distances = [0.0]
    for i in range(1, len(segment_coords)):
        prev = segment_coords[i - 1]
        curr = segment_coords[i]
        dist = haversine_distance(prev[1], prev[0], curr[1], curr[0])
        cumulative_distances.append(cumulative_distances[-1] + dist)
    
    total_length = cumulative_distances[-1]
    if total_length < 1.0:
        return None
    
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
    
    if min_dist > max_distance_m:
        return None
    
    segment_start_dist = cumulative_distances[best_segment_idx]
    segment_length = (cumulative_distances[best_segment_idx + 1] - 
                     cumulative_distances[best_segment_idx])
    
    progress_distance = segment_start_dist + best_t * segment_length
    progress = progress_distance / total_length
    
    return max(0.0, min(1.0, progress))


# ============================================================================
# Neighbor Search: 隣接区間取得
# ============================================================================

def get_adjacent_segments(
    from_station_id: str,
    to_station_id: str,
    direction: str
) -> list[tuple[str, str]]:
    """
    時刻表の想定区間に加え、前後の隣接区間を返す。
    
    Args:
        from_station_id: 時刻表が示す出発駅
        to_station_id: 時刻表が示す到着駅
        direction: "OuterLoop" or "InnerLoop"
    
    Returns:
        探索すべき区間のリスト [(from, to), ...]
        順序: [想定区間, 前の区間, 次の区間]
    """
    from_idx = YAMANOTE_STATION_INDEX.get(from_station_id)
    to_idx = YAMANOTE_STATION_INDEX.get(to_station_id)
    
    if from_idx is None or to_idx is None:
        return [(from_station_id, to_station_id)]
    
    segments = []
    
    # 1. 想定区間（時刻表通り）
    segments.append((from_station_id, to_station_id))
    
    if direction == "OuterLoop":
        # 外回り: インデックス増加方向に進む
        prev_from_idx = (from_idx - 1) % NUM_YAMANOTE_STATIONS
        prev_from = YAMANOTE_STATION_ORDER[prev_from_idx]
        prev_to = from_station_id
        segments.append((prev_from, prev_to))
        
        next_from = to_station_id
        next_to_idx = (to_idx + 1) % NUM_YAMANOTE_STATIONS
        next_to = YAMANOTE_STATION_ORDER[next_to_idx]
        segments.append((next_from, next_to))
        
    else:  # InnerLoop
        # 内回り: インデックス減少方向に進む
        prev_from_idx = (from_idx + 1) % NUM_YAMANOTE_STATIONS
        prev_from = YAMANOTE_STATION_ORDER[prev_from_idx]
        prev_to = from_station_id
        segments.append((prev_from, prev_to))
        
        next_from = to_station_id
        next_to_idx = (to_idx - 1) % NUM_YAMANOTE_STATIONS
        next_to = YAMANOTE_STATION_ORDER[next_to_idx]
        segments.append((next_from, next_to))
    
    return segments


# ============================================================================
# Neighbor Search: 拡張された進捗推定
# ============================================================================

def estimate_segment_progress_extended(
    segment_coords: list[list[float]],
    target_lat: float,
    target_lon: float,
    max_distance_m: float = 500.0
) -> dict | None:
    """
    GTFS-RT座標から区間内の進捗率を推定する（拡張版）。
    
    Returns:
        {
            'progress': float,
            'distance_m': float,
            'lon': float,
            'lat': float
        }
        または None
    """
    if not segment_coords or len(segment_coords) < 2:
        return None
    
    cumulative_distances = [0.0]
    for i in range(1, len(segment_coords)):
        prev = segment_coords[i - 1]
        curr = segment_coords[i]
        dist = haversine_distance(prev[1], prev[0], curr[1], curr[0])
        cumulative_distances.append(cumulative_distances[-1] + dist)
    
    total_length = cumulative_distances[-1]
    if total_length < 1.0:
        return None
    
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
    
    if min_dist > max_distance_m:
        return None
    
    segment_start_dist = cumulative_distances[best_segment_idx]
    segment_length = (cumulative_distances[best_segment_idx + 1] - 
                     cumulative_distances[best_segment_idx])
    
    progress_distance = segment_start_dist + best_t * segment_length
    progress = progress_distance / total_length
    progress = max(0.0, min(1.0, progress))
    
    return {
        'progress': progress,
        'distance_m': min_dist,
        'lon': best_nearest_lon,
        'lat': best_nearest_lat
    }


# ============================================================================
# Neighbor Search: 前後区間サーチ関数
# ============================================================================

def find_train_on_segments(
    gtfs_lat: float,
    gtfs_lon: float,
    from_station_id: str,
    to_station_id: str,
    direction: str,
    cache: "DataCache",
    max_distance_m: float = 500.0
) -> dict | None:
    """
    GTFS-RT座標を使って、想定区間および隣接区間から列車位置を探す。
    
    Args:
        gtfs_lat: GTFS-RTの緯度
        gtfs_lon: GTFS-RTの経度
        from_station_id: 時刻表が示す出発駅
        to_station_id: 時刻表が示す到着駅
        direction: "OuterLoop" or "InnerLoop"
        cache: データキャッシュ
        max_distance_m: 線路からの最大許容距離
    
    Returns:
        {
            'segment': (from_station, to_station),
            'progress': float,
            'distance_m': float,
            'lon': float,
            'lat': float,
            'is_neighbor': bool
        }
        または None
    """
    segments_to_search = get_adjacent_segments(from_station_id, to_station_id, direction)
    
    best_result = None
    best_distance = float('inf')
    
    for idx, (seg_from, seg_to) in enumerate(segments_to_search):
        segment_coords = get_segment_coords(seg_from, seg_to, direction, cache)
        
        if not segment_coords or len(segment_coords) < 2:
            continue
        
        result = estimate_segment_progress_extended(
            segment_coords,
            gtfs_lat,
            gtfs_lon,
            max_distance_m
        )
        
        if result is not None and result['distance_m'] < best_distance:
            best_distance = result['distance_m']
            best_result = {
                'segment': (seg_from, seg_to),
                'progress': result['progress'],
                'distance_m': result['distance_m'],
                'lon': result['lon'],
                'lat': result['lat'],
                'is_neighbor': (idx > 0)
            }
    
    return best_result


# ============================================================================
# Phase 1: Override function for position conversion
# ============================================================================

def train_state_to_position_with_override(
    state: "TrainSectionState",
    cache: "DataCache",
    override_progress: float | None = None,
    data_quality: str = "timetable_only",
    gtfs_info: dict | None = None,
    override_from_station: str | None = None,
    override_to_station: str | None = None,
    # 比較表示用座標
    timetable_coords: tuple[float, float] | None = None,  # (lat, lon)
    gtfs_coords: tuple[float, float] | None = None,       # (lat, lon)
) -> Optional[TrainPosition]:
    """
    TrainSectionState を TrainPosition（座標）に変換する。
    override_progress/override_from_station/override_to_station が指定された場合、
    state の値の代わりにその値を使用する。
    
    timetable_coords / gtfs_coords が指定された場合、比較表示用に保存する。
    """
    train = state.train

    train_id = (
        f"{train.base_id}.{train.service_type}"
        if train.service_type and train.service_type != "Unknown"
        else train.base_id
    )

    stop_seq = gtfs_info.get("stop_sequence") if gtfs_info else None
    status = gtfs_info.get("status") if gtfs_info else None

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
            gtfs_stop_sequence=stop_seq,
            gtfs_status=status,
            # 比較表示用座標
            timetable_lat=timetable_coords[0] if timetable_coords else None,
            timetable_lon=timetable_coords[1] if timetable_coords else None,
            gtfs_lat=gtfs_coords[0] if gtfs_coords else None,
            gtfs_lon=gtfs_coords[1] if gtfs_coords else None,
        )

    # 走行中
    from_id = override_from_station if override_from_station else state.from_station_id
    to_id = override_to_station if override_to_station else state.to_station_id
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
        gtfs_stop_sequence=stop_seq,
        gtfs_status=status,
        # 比較表示用座標
        timetable_lat=timetable_coords[0] if timetable_coords else None,
        timetable_lon=timetable_coords[1] if timetable_coords else None,
        gtfs_lat=gtfs_coords[0] if gtfs_coords else None,
        gtfs_lon=gtfs_coords[1] if gtfs_coords else None,
    )


# ============================================================================
# Phase 1: Main Blending Logic with Neighbor Search
# ============================================================================

def get_blended_train_positions(
    current_time: datetime,
    cache: "DataCache",
    gtfs_data: dict[str, "YamanoteTrainPosition"] | None = None
) -> list[TrainPosition]:
    """
    時刻表ベースの位置にGTFS-RTの補正を適用した列車位置を返す。
    前後区間サーチ（Neighbor Search）対応版。
    
    Args:
        current_time: 現在時刻
        cache: データキャッシュ
        gtfs_data: GTFS-RTデータ（train_numberをキーとする辞書）
    
    Returns:
        補正済みの列車位置リスト
    """
    from train_state import get_yamanote_trains_at, blend_progress
    
    # 1. 時刻表から現在の列車状態を取得
    states = get_yamanote_trains_at(current_time, cache)
    
    results = []
    blend_stats = {"good": 0, "stale": 0, "rejected": 0, "timetable_only": 0, "error": 0}
    neighbor_found_count = 0
    
    for state in states:
        # 2. マッチするGTFS-RTデータを探す
        gtfs_position = None
        if gtfs_data and state.train.number in gtfs_data:
            gtfs_position = gtfs_data[state.train.number]
        
        # デバッグログ
        if gtfs_data:
            sample_numbers = list(gtfs_data.keys())[:5]
            if state.train.number in sample_numbers or state.train.number == "906G":
                logger.info(
                    f"[DEBUG] Train {state.train.number}: "
                    f"GTFS match={'YES' if gtfs_position else 'NO'}, "
                    f"is_stopped={state.is_stopped}, "
                    f"from={state.from_station_id}, to={state.to_station_id}"
                )
        
        # 3. 走行中の場合のみブレンド処理
        blended_progress = state.progress
        data_quality = "timetable_only"
        final_from_station = state.from_station_id
        final_to_station = state.to_station_id
        
        gtfs_info = None
        if gtfs_position:
            gtfs_info = {
                "stop_sequence": gtfs_position.stop_sequence,
                "status": gtfs_position.status
            }
        
        if not state.is_stopped and gtfs_position is not None:
            try:
                # ★ 前後区間サーチを使用
                search_result = find_train_on_segments(
                    gtfs_position.latitude,
                    gtfs_position.longitude,
                    state.from_station_id,
                    state.to_station_id,
                    state.train.direction,
                    cache,
                    max_distance_m=500.0
                )
                
                if search_result is not None:
                    # 隣接区間で見つかった場合はログ出力
                    if search_result['is_neighbor']:
                        neighbor_found_count += 1
                        found_from = search_result['segment'][0].split('.')[-1]
                        found_to = search_result['segment'][1].split('.')[-1]
                        expected_from = state.from_station_id.split('.')[-1] if state.from_station_id else "?"
                        expected_to = state.to_station_id.split('.')[-1] if state.to_station_id else "?"
                        logger.info(
                            f"Train {state.train.number}: Neighbor search found in "
                            f"{found_from}→{found_to} "
                            f"(expected {expected_from}→{expected_to})"
                        )
                        # 区間を更新
                        final_from_station, final_to_station = search_result['segment']
                    
                    rt_progress = search_result['progress']
                    
                    # staleness計算
                    staleness_sec = current_time.timestamp() - gtfs_position.timestamp
                    
                    # ブレンド
                    blended_progress, data_quality = blend_progress(
                        state.progress,
                        rt_progress,
                        staleness_sec
                    )
                else:
                    # どの区間でも見つからない → rejected
                    data_quality = "rejected"
                    
            except Exception as e:
                logger.warning(f"Neighbor search failed for {state.train.number}: {e}")
                data_quality = "error"
        
        # 4. 比較表示用の座標を計算
        # (A) 純粋な時刻表位置（override なし）
        timetable_coords = None
        if not state.is_stopped:
            tt_coords = _interpolate_coords(
                state.from_station_id, 
                state.to_station_id, 
                state.progress, 
                state.train.direction, 
                cache
            )
            if tt_coords:
                timetable_coords = (tt_coords[1], tt_coords[0])  # (lat, lon)
        else:
            # 停車中は駅座標を使用
            station_id = state.stopped_at_station_id or state.from_station_id
            coord = _get_station_coord(station_id, cache)
            if coord:
                timetable_coords = (coord[1], coord[0])  # (lat, lon)
        
        # (B) 純粋なGTFS-RT位置
        gtfs_coords = None
        if gtfs_position:
            gtfs_coords = (gtfs_position.latitude, gtfs_position.longitude)
        
        # 5. 進捗率を座標に変換
        position = train_state_to_position_with_override(
            state, 
            cache, 
            override_progress=blended_progress,
            data_quality=data_quality,
            gtfs_info=gtfs_info,
            override_from_station=final_from_station,
            override_to_station=final_to_station,
            timetable_coords=timetable_coords,
            gtfs_coords=gtfs_coords,
        )
        
        if position:
            blend_stats[data_quality] = blend_stats.get(data_quality, 0) + 1
            results.append(position)
    
    logger.info(
        f"Blended {len(results)} trains: good={blend_stats['good']}, "
        f"stale={blend_stats['stale']}, rejected={blend_stats['rejected']}, "
        f"timetable_only={blend_stats['timetable_only']}, error={blend_stats['error']}, "
        f"neighbor_found={neighbor_found_count}"
    )
    
    return results