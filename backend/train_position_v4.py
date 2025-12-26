# backend/train_position_v4.py
"""
MS2: TripUpdate-only 列車位置計算エンジン

TrainSchedule（MS1の成果物）から現在区間と進捗率を計算する。
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from station_ranks import get_station_dwell_time

from gtfs_rt_tripupdate import TrainSchedule, RealtimeStationSchedule

logger = logging.getLogger(__name__)

# Mini Tokyo 3D方式: arrival == departure の場合のデフォルト停車時間（秒）
# 参考: https://internet.watch.impress.co.jp/docs/interview/1434086.html
# 「最も誤差が少ないと思われる"毎分25秒"を基準にしました」
DEFAULT_STOP_DURATION = 25


# ============================================================================
# MS8: 物理演算ベースの台形速度制御 (E235系)
# ============================================================================

def calculate_physics_progress(elapsed_time: float, total_duration: float) -> float:
    """
    山手線E235系の性能に基づく台形速度制御で進捗率(0.0-1.0)を計算する。
    """
    if total_duration <= 0: return 1.0
    if elapsed_time <= 0: return 0.0
    if elapsed_time >= total_duration: return 1.0
    
    T_ACC = 30.0  # 加速時間 (0->90km/h)
    T_DEC = 25.0  # 減速時間 (90km/h->0)
    
    if total_duration < (T_ACC + T_DEC):
        factor = total_duration / (T_ACC + T_DEC)
        t_acc, t_dec = T_ACC * factor, T_DEC * factor
    else:
        t_acc, t_dec = T_ACC, T_DEC
    
    t_const = total_duration - t_acc - t_dec
    v_peak = 1.0 / (0.5 * t_acc + t_const + 0.5 * t_dec)
    
    if elapsed_time < t_acc:
        return 0.5 * (v_peak / t_acc) * (elapsed_time ** 2)
    elif elapsed_time < (t_acc + t_const):
        dist_acc = 0.5 * v_peak * t_acc
        return dist_acc + v_peak * (elapsed_time - t_acc)
    else:
        time_left = total_duration - elapsed_time
        return 1.0 - 0.5 * (v_peak / t_dec) * (time_left ** 2)



# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SegmentProgress:
    """列車の現在位置・進捗情報"""
    trip_id: str
    train_number: Optional[str]
    direction: Optional[str]
    
    # 現在区間（前駅→次駅）
    prev_station_id: Optional[str]
    next_station_id: Optional[str]
    prev_seq: Optional[int]
    next_seq: Optional[int]
    
    # 時刻と進捗
    now_ts: int
    t0_departure: Optional[int]    # 前駅の発車時刻
    t1_arrival: Optional[int]      # 次駅の到着時刻
    progress: Optional[float]      # 0.0〜1.0（計算不能なら None）
    status: str                    # "running" / "stopped" / "unknown" / "invalid"
    
    # デバッグ用
    feed_timestamp: Optional[int] = None
    segment_count: int = 0         # 全区間数
    delay: int = 0                 # MS6: 遅延秒数


# ============================================================================
# Helper Functions
# ============================================================================

def _get_departure_time(schedule: RealtimeStationSchedule) -> Optional[int]:
    """
    発車時刻を取得する。
    arrival == departure の場合（GTFS時刻表の仕様）は、
    ランクごとの停車時間（station_ranks.py）を加算して返す。
    """
    arr = schedule.arrival_time
    dep = schedule.departure_time

    # 両方ある場合
    if arr is not None and dep is not None:
        # 時刻表上で到着=発車となっている場合、停車時間を足して「実質発車時刻」を作る
        if arr == dep:
            dwell = get_station_dwell_time(schedule.station_id)
            return arr + dwell
        return dep
        
    # departureだけある
    if dep is not None:
        return dep
        
    # arrivalだけある（稀なケース）
    if arr is not None:
        dwell = get_station_dwell_time(schedule.station_id)
        return arr + dwell

    return None

def _is_stopped_at_station(
    schedule: RealtimeStationSchedule,
    now_ts: int,
) -> bool:
    """
    現在時刻がこの駅の到着〜発車の間にあるか判定。
    """
    arr = schedule.arrival_time
    
    # 統一ロジックを使って発車時刻を取得
    effective_dep = _get_departure_time(schedule)
    
    if arr is not None and effective_dep is not None:
        return arr <= now_ts <= effective_dep
    
    return False

def _get_arrival_time(schedule: RealtimeStationSchedule) -> Optional[int]:
    """
    到着時刻を取得する。無ければ発車時刻で代替。
    """
    if schedule.arrival_time is not None:
        return schedule.arrival_time
    return schedule.departure_time


def _is_stopped_at_station(
    schedule: RealtimeStationSchedule,
    now_ts: int,
) -> bool:
    """
    現在時刻がこの駅の到着〜発車の間にあるか判定。
    
    arrival == departure の場合は、Mini Tokyo 3D方式で
    DEFAULT_STOP_DURATION（25秒）の停車時間を仮定する。
    """
    arr = schedule.arrival_time
    dep = schedule.departure_time
    
    # 両方ある場合
    if arr is not None and dep is not None:
        # ★ arrival == departure の場合は 25秒の停車時間を仮定
        effective_dep = dep if arr != dep else arr + DEFAULT_STOP_DURATION
        return arr <= now_ts <= effective_dep
    
    return False


# ============================================================================
# Main Calculation Functions
# ============================================================================

def compute_progress_for_train(
    schedule: TrainSchedule,
    now_ts: Optional[int] = None,
) -> SegmentProgress:
    """
    単一列車の現在位置・進捗を計算する。
    
    Args:
        schedule: TrainSchedule（MS1の出力）
        now_ts: 現在時刻（unix seconds）。None なら time.time() を使用。
    
    Returns:
        SegmentProgress（計算結果）
    """
    # 1. now_ts の決定
    if now_ts is None:
        now_ts = int(time.time())
    
    # feed_timestamp との補正（過去に戻る防止）
    if schedule.feed_timestamp is not None and now_ts < schedule.feed_timestamp:
        now_ts = schedule.feed_timestamp
    
    # 基本情報
    trip_id = schedule.trip_id
    train_number = schedule.train_number
    direction = schedule.direction
    seqs = schedule.ordered_sequences
    schedules_by_seq = schedule.schedules_by_seq
    
    # 2. 無効チェック（区間数が2未満）
    if len(seqs) < 2:
        return SegmentProgress(
            trip_id=trip_id,
            train_number=train_number,
            direction=direction,
            prev_station_id=None,
            next_station_id=None,
            prev_seq=None,
            next_seq=None,
            now_ts=now_ts,
            t0_departure=None,
            t1_arrival=None,
            progress=None,
            status="invalid",
            feed_timestamp=schedule.feed_timestamp,
            segment_count=0,
            delay=0,
        )
    
    # 3. 停車判定（各駅の arrival <= now <= departure をチェック）
    for seq in seqs:
        stu = schedules_by_seq.get(seq)
        if stu and _is_stopped_at_station(stu, now_ts):
            return SegmentProgress(
                trip_id=trip_id,
                train_number=train_number,
                direction=direction,
                prev_station_id=stu.station_id,
                next_station_id=stu.station_id,
                prev_seq=seq,
                next_seq=seq,
                now_ts=now_ts,
                t0_departure=stu.departure_time,
                t1_arrival=stu.arrival_time,
                progress=0.0,  # 停車中は 0.0
                status="stopped",
                feed_timestamp=schedule.feed_timestamp,
                segment_count=len(seqs) - 1,
                delay=stu.delay,  # MS6: 停車中はその駅の遅延
            )
    
    # 4. 区間判定（走行中）
    # ordered_sequences を i=0..len-2 で走査
    for i in range(len(seqs) - 1):
        prev_seq = seqs[i]
        next_seq = seqs[i + 1]
        
        prev_stu = schedules_by_seq.get(prev_seq)
        next_stu = schedules_by_seq.get(next_seq)
        
        if prev_stu is None or next_stu is None:
            continue
        
        # t0 = 前駅の発車時刻、t1 = 次駅の到着時刻
        t0 = _get_departure_time(prev_stu)
        t1 = _get_arrival_time(next_stu)
        
        # 両方存在チェック
        if t0 is None or t1 is None:
            continue
        
        # 無効区間（t1 <= t0）はスキップ
        if t1 <= t0:
            continue
        
        # 現在時刻がこの区間内か判定
        if t0 <= now_ts <= t1:
            # MS8: 物理演算ベースの台形速度制御
            elapsed = now_ts - t0
            duration = t1 - t0
            eased_progress = calculate_physics_progress(elapsed, duration)
            
            return SegmentProgress(
                trip_id=trip_id,
                train_number=train_number,
                direction=direction,
                prev_station_id=prev_stu.station_id,
                next_station_id=next_stu.station_id,
                prev_seq=prev_seq,
                next_seq=next_seq,
                now_ts=now_ts,
                t0_departure=t0,
                t1_arrival=t1,
                progress=eased_progress,  # MS8: 物理演算適用済み
                status="running",
                feed_timestamp=schedule.feed_timestamp,
                segment_count=len(seqs) - 1,
                delay=next_stu.delay,  # MS6: 走行中は次駅到着遅延
            )
    
    # 5. 区間も停車も見つからない → unknown
    # デバッグ用：最初と最後の時刻を記録
    first_stu = schedules_by_seq.get(seqs[0])
    last_stu = schedules_by_seq.get(seqs[-1])
    
    first_time = None
    last_time = None
    
    if first_stu:
        first_time = first_stu.arrival_time or first_stu.departure_time
    if last_stu:
        last_time = last_stu.departure_time or last_stu.arrival_time
    
    return SegmentProgress(
        trip_id=trip_id,
        train_number=train_number,
        direction=direction,
        prev_station_id=first_stu.station_id if first_stu else None,
        next_station_id=last_stu.station_id if last_stu else None,
        prev_seq=seqs[0],
        next_seq=seqs[-1],
        now_ts=now_ts,
        t0_departure=first_time,
        t1_arrival=last_time,
        progress=None,
        status="unknown",
        feed_timestamp=schedule.feed_timestamp,
        segment_count=len(seqs) - 1,
        delay=0,
    )


def compute_all_progress(
    schedules: Dict[str, TrainSchedule],
    now_ts: Optional[int] = None,
) -> List[SegmentProgress]:
    """
    複数列車の現在位置・進捗をまとめて計算する。
    
    Args:
        schedules: {trip_id: TrainSchedule} の辞書（MS1の出力）
        now_ts: 現在時刻（unix seconds）。None なら time.time() を使用。
    
    Returns:
        SegmentProgress のリスト
    """
    # now_ts を統一（全列車で同じ時刻を使う）
    if now_ts is None:
        now_ts = int(time.time())
    
    results: List[SegmentProgress] = []
    
    for trip_id, schedule in schedules.items():
        try:
            progress = compute_progress_for_train(schedule, now_ts)
            results.append(progress)
        except Exception as e:
            logger.error(f"Failed to compute progress for {trip_id}: {e}")
            # エラーでも結果を返す
            results.append(SegmentProgress(
                trip_id=trip_id,
                train_number=schedule.train_number,
                direction=schedule.direction,
                prev_station_id=None,
                next_station_id=None,
                prev_seq=None,
                next_seq=None,
                now_ts=now_ts,
                t0_departure=None,
                t1_arrival=None,
                progress=None,
                status="invalid",
                feed_timestamp=schedule.feed_timestamp,
                segment_count=0,
            ))
    
    return results


# ============================================================================
# Debug/Test Function
# ============================================================================

def debug_progress_stats(results: List[SegmentProgress]) -> Dict[str, int]:
    """
    計算結果の統計を返す（デバッグ用）。
    """
    stats = {
        "running": 0,
        "stopped": 0,
        "unknown": 0,
        "invalid": 0,
        "total": len(results),
    }
    
    for r in results:
        if r.status in stats:
            stats[r.status] += 1
    
    return stats


# ============================================================================
# MS5: Track-Following Coordinate Calculation
# ============================================================================

def calculate_coordinates(
    progress_data: SegmentProgress,
    cache: "DataCache",
) -> tuple[float, float] | None:
    """
    MS5: SegmentProgress から座標を計算する（線路形状追従）。
    
    既存の _interpolate_coords を使用し、線路に沿った座標を返す。
    
    Args:
        progress_data: SegmentProgress（MS2の出力）
        cache: DataCache インスタンス
        
    Returns:
        (latitude, longitude) のタプル。計算不能なら None。
        ※ v4 API の location.latitude/longitude に対応するため (lat, lon) 順。
    """
    from train_position import _interpolate_coords, _get_station_coord
    
    status = progress_data.status
    
    # 1) stopped: 停車駅の座標を返す
    if status == "stopped":
        station_id = progress_data.prev_station_id
        if not station_id:
            station_id = progress_data.next_station_id
        
        if station_id:
            coord = _get_station_coord(station_id, cache)
            if coord:
                # _get_station_coord は (lon, lat) を返す
                lon, lat = coord
                return (lat, lon)  # v4 API用に (lat, lon) に変換
        
        return None
    
    # 2) running: 線路形状に沿った補間
    if status == "running":
        progress = progress_data.progress
        if progress is None:
            return None
        
        prev_station_id = progress_data.prev_station_id
        next_station_id = progress_data.next_station_id
        direction = progress_data.direction
        
        if not prev_station_id or not next_station_id:
            return None
        
        try:
            # _interpolate_coords は (lon, lat) を返す
            result = _interpolate_coords(
                from_station_id=prev_station_id,
                to_station_id=next_station_id,
                progress=progress,
                direction=direction or "OuterLoop",  # デフォルト
                cache=cache,
            )
            
            if result:
                lon, lat = result
                return (lat, lon)  # v4 API用に (lat, lon) に変換
            
            return None
            
        except Exception as e:
            logger.warning(f"Track interpolation failed for {progress_data.train_number}: {e}")
            
            # フォールバック: 駅座標の直線補間
            try:
                prev_coord = _get_station_coord(prev_station_id, cache)
                next_coord = _get_station_coord(next_station_id, cache)
                
                if prev_coord and next_coord:
                    lon0, lat0 = prev_coord
                    lon1, lat1 = next_coord
                    
                    lat = lat0 + (lat1 - lat0) * progress
                    lon = lon0 + (lon1 - lon0) * progress
                    
                    return (lat, lon)
            except Exception:
                pass
            
            return None
    
    # 3) unknown / invalid: None を返す
    return None