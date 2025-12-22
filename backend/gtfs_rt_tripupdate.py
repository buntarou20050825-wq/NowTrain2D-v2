# backend/gtfs_rt_tripupdate.py
"""
GTFS-RT TripUpdate fetching and normalization for Yamanote Line.

MS1: リアルタイム駅時刻テーブルへの正規化を行う。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

import httpx
from google.transit import gtfs_realtime_pb2
from zoneinfo import ZoneInfo

from constants import (
    TRIP_UPDATE_URL,
    YAMANOTE_ROUTE_ID,
    HTTP_TIMEOUT,
)
from gtfs_rt_vehicle import is_yamanote, get_direction, get_train_number
from train_state import determine_service_type

if TYPE_CHECKING:
    from data_cache import DataCache

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class RealtimeStationSchedule:
    """1駅分のリアルタイム到着・発車時刻情報"""
    stop_sequence: int
    station_id: Optional[str]        # 静的データから解決された駅ID
    arrival_time: Optional[int]      # unix timestamp (seconds)
    departure_time: Optional[int]    # unix timestamp (seconds)
    resolved: bool                   # station_id が静的/stop_idから解決できたか
    raw_stop_id: Optional[str]       # TripUpdate側の stop_id（あれば）
    delay: int = 0                   # MS6: 遅延秒数 (デフォルト0)


@dataclass
class TrainSchedule:
    """1本の列車のリアルタイム時刻テーブル"""
    trip_id: str                     # 主キー
    train_number: Optional[str]
    start_date: Optional[str]
    direction: Optional[str]         # "InnerLoop" / "OuterLoop"
    feed_timestamp: Optional[int]    # feed.header.timestamp
    schedules_by_seq: Dict[int, RealtimeStationSchedule] = field(default_factory=dict)
    ordered_sequences: List[int] = field(default_factory=list)


# ============================================================================
# Fetch Function
# ============================================================================

async def fetch_trip_updates(
    client: httpx.AsyncClient,
    api_key: str,
    data_cache: "DataCache",
) -> Dict[str, TrainSchedule]:
    """
    GTFS-RT TripUpdate を取得し、列車ごとのリアルタイム駅時刻テーブルに正規化する。
    
    Args:
        client: httpx.AsyncClient インスタンス
        api_key: ODPT API key
        data_cache: 静的データキャッシュ
        
    Returns:
        {trip_id: TrainSchedule} の辞書
    """
    results: Dict[str, TrainSchedule] = {}
    
    # 1. APIリクエスト
    try:
        url = f"{TRIP_UPDATE_URL}?acl:consumerKey={api_key}"
        response = await client.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        content = response.content
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch TripUpdate: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error fetching TripUpdate: {e}")
        return {}
    
    # 2. Protobuf解析
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(content)
    except Exception as e:
        logger.error(f"Failed to parse TripUpdate protobuf: {e}")
        return {}
    
    feed_timestamp = feed.header.timestamp if feed.header.HasField("timestamp") else None
    logger.info(f"TripUpdate feed: {len(feed.entity)} entities, timestamp={feed_timestamp}")
    
    # 現在時刻からサービスタイプを推定
    now_jst = datetime.now(JST)
    current_service_type = determine_service_type(now_jst)
    
    # デバッグ用: route_id のサンプルを収集
    route_id_samples: List[str] = []
    
    # 3. エンティティを処理
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        
        trip_update = entity.trip_update
        trip = trip_update.trip
        trip_id = trip.trip_id
        
        # route_id サンプル収集 (最初の5件)
        if len(route_id_samples) < 5 and trip.route_id:
            route_id_samples.append(trip.route_id)
        
        # 4. 山手線フィルタ
        is_yamanote_train = False
        
        # route_id が取得でき、かつ YAMANOTE_ROUTE_ID と一致する場合
        if trip.route_id:
            is_yamanote_train = (trip.route_id == YAMANOTE_ROUTE_ID)
        
        # route_id が空/未設定/一致しない場合は trip_id でフォールバック判定
        if not is_yamanote_train:
            is_yamanote_train = is_yamanote(trip_id)
        
        if not is_yamanote_train:
            continue
        
        # 5. キャンセル除外
        if trip.HasField("schedule_relationship"):
            if trip.schedule_relationship == gtfs_realtime_pb2.TripDescriptor.CANCELED:
                logger.debug(f"Skipping canceled trip: {trip_id}")
                continue
        
        # 6. 列車情報の抽出
        train_number = get_train_number(trip_id)
        start_date = trip.start_date if trip.start_date else None
        
        # 7. 静的データ紐付けと direction 決定
        static_train = data_cache.get_static_train(train_number, current_service_type)
        
        if static_train:
            direction = static_train.direction
        else:
            # フォールバック: trip_id から推定
            direction = get_direction(trip_id)
        
        # 8. stop_sequence -> station_id マップを取得
        seq_to_station = data_cache.get_seq_to_station_map(train_number, current_service_type)
        
        # 9. stop_time_update の展開
        schedules_by_seq: Dict[int, RealtimeStationSchedule] = {}
        
        for stu in trip_update.stop_time_update:
            stop_seq = stu.stop_sequence
            raw_stop_id = stu.stop_id if stu.stop_id else None
            
            # 駅ID解決
            station_id: Optional[str] = None
            resolved = False
            
            # 優先順位1: raw_stop_id が静的データの station_id 体系と一致するか確認
            if raw_stop_id:
                # 静的データの駅IDは "JR-East.XXX" 形式
                # TripUpdate の stop_id が同形式なら採用
                if raw_stop_id.startswith("JR-East."):
                    station_id = raw_stop_id
                    resolved = True
            
            # 優先順位2: seq_to_station マップから解決
            if not resolved and seq_to_station:
                mapped_station = seq_to_station.get(stop_seq)
                if mapped_station:
                    station_id = mapped_station
                    resolved = True
            
            # 到着・発車時刻の抽出
            arrival_time: Optional[int] = None
            departure_time: Optional[int] = None
            
            if stu.HasField("arrival") and stu.arrival.HasField("time"):
                arrival_time = stu.arrival.time
            
            if stu.HasField("departure") and stu.departure.HasField("time"):
                departure_time = stu.departure.time
            
            # MS6: 遅延情報の抽出
            delay = 0
            if stu.HasField("arrival") and stu.arrival.HasField("delay"):
                delay = stu.arrival.delay
            elif stu.HasField("departure") and stu.departure.HasField("delay"):
                delay = stu.departure.delay
            
            # 到着も発車も無いレコードはスキップ
            if arrival_time is None and departure_time is None:
                continue
            
            # SKIPPED 駅は除外
            if stu.HasField("schedule_relationship"):
                if stu.schedule_relationship == gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.SKIPPED:
                    continue
            
            schedules_by_seq[stop_seq] = RealtimeStationSchedule(
                stop_sequence=stop_seq,
                station_id=station_id,
                arrival_time=arrival_time,
                departure_time=departure_time,
                resolved=resolved,
                raw_stop_id=raw_stop_id,
                delay=delay,
            )
        
        # 10. ordered_sequences を作成（昇順ソート）
        ordered_sequences = sorted(schedules_by_seq.keys())
        
        # 要素数が2未満の列車は無効として除外
        if len(ordered_sequences) < 2:
            continue
        
        # 11. 結果に追加
        results[trip_id] = TrainSchedule(
            trip_id=trip_id,
            train_number=train_number,
            start_date=start_date,
            direction=direction,
            feed_timestamp=feed_timestamp,
            schedules_by_seq=schedules_by_seq,
            ordered_sequences=ordered_sequences,
        )
    
    # デバッグ: route_id サンプル出力
    if route_id_samples:
        logger.debug(f"TripUpdate route_id samples: {route_id_samples}")
    
    logger.info(
        f"Parsed {len(results)} Yamanote TripUpdates "
        f"(feed had {len(feed.entity)} entities)"
    )
    
    return results
