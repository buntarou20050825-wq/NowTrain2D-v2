"""
GTFS-RT VehiclePosition から山手線の列車位置を取得
"""
import os
import re
import httpx
import asyncio
from google.transit import gtfs_realtime_pb2
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class YamanoteTrainPosition:
    """山手線の列車位置"""
    trip_id: str           # 例: "4201301G"
    train_number: str      # 例: "301G"
    direction: str         # "OuterLoop" or "InnerLoop"
    latitude: float
    longitude: float
    stop_sequence: int
    status: int            # 1=STOPPED_AT, 2=IN_TRANSIT_TO
    timestamp: int


@dataclass
class YamanoteTrainPositionWithSchedule:
    """山手線の列車位置（出発時刻付き）"""
    trip_id: str
    train_number: str
    direction: str
    latitude: float
    longitude: float
    stop_sequence: int
    status: int
    timestamp: int
    # 新規追加
    departure_time: Optional[int] = None  # 現在駅の出発時刻（UNIXタイムスタンプ）
    next_arrival_time: Optional[int] = None  # 次駅の到着時刻


def is_yamanote(trip_id: str) -> bool:
    """山手線かどうか判定"""
    return trip_id.endswith('G')


def get_direction(trip_id: str) -> str:
    """方向を取得"""
    if trip_id.startswith('4201'):
        return 'OuterLoop'
    elif trip_id.startswith('4211'):
        return 'InnerLoop'
    
    # Fallback: 列車番号の偶奇で判定
    # 山手線: 外回り=奇数, 内回り=偶数
    try:
        # trip_id の後半部分から数字を抽出 (例: "4200461G" -> "461")
        # プレフィックス4桁を除いた部分を使用
        suffix = trip_id[4:]
        num_part = ''.join(filter(str.isdigit, suffix))
        if num_part:
            num = int(num_part)
            if num % 2 == 1:
                return 'OuterLoop'
            else:
                return 'InnerLoop'
    except Exception:
        pass
        
    return 'Unknown'


def get_train_number(trip_id: str) -> str:
    """
    Trip ID から列車番号を抽出する（4桁プレフィックススキップ + ゼロ埋め除去）
    
    山手線のtrip_idは「4桁プレフィックス + 列車番号」の形式。
    例: "4201301G" → "301G", "42020906G" → "906G"
    
    Args:
        trip_id: GTFS Trip ID (例: "4201301G", "42020906G")
    
    Returns:
        抽出・正規化された列車番号 (例: "301G", "906G")
    """
    # 4桁のプレフィックスをスキップ
    if len(trip_id) <= 4:
        return trip_id
    
    suffix = trip_id[4:]  # 例: "0906G" or "301G"
    
    # 末尾の "数字 + 英字" パターンをマッチ
    match = re.match(r'^(\d+)([A-Z])$', suffix)
    if match:
        number_part = match.group(1)
        letter = match.group(2)
        
        # 数値化して先頭の0を削除 (例: "0906" -> 906 -> "906")
        normalized_number = str(int(number_part))
        
        return f"{normalized_number}{letter}"
    
    # マッチしない場合はそのまま返す
    return suffix


async def fetch_yamanote_positions(api_key: str) -> list[YamanoteTrainPosition]:
    """
    GTFS-RT VehiclePosition から山手線の列車位置を取得
    
    Args:
        api_key: ODPT APIキー
    
    Returns:
        山手線列車位置のリスト
    """
    url = "https://api-challenge.odpt.org/api/v4/gtfs/realtime/jreast_odpt_train_vehicle"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={"acl:consumerKey": api_key},
            timeout=30.0
        )
        response.raise_for_status()
    
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    
    positions = []
    
    for entity in feed.entity:
        if not entity.HasField('vehicle'):
            continue
        
        vp = entity.vehicle
        trip_id = vp.trip.trip_id
        
        # 山手線フィルタ
        if not is_yamanote(trip_id):
            continue
        
        positions.append(YamanoteTrainPosition(
            trip_id=trip_id,
            train_number=get_train_number(trip_id),
            direction=get_direction(trip_id),
            latitude=vp.position.latitude,
            longitude=vp.position.longitude,
            stop_sequence=vp.current_stop_sequence,
            status=vp.current_status,
            timestamp=vp.timestamp
        ))
    
    return positions


# 同期版（テスト用）
def fetch_yamanote_positions_sync(api_key: str) -> list[YamanoteTrainPosition]:
    """同期版の位置取得"""
    import requests
    
    url = "https://api-challenge.odpt.org/api/v4/gtfs/realtime/jreast_odpt_train_vehicle"
    
    response = requests.get(
        url,
        params={"acl:consumerKey": api_key},
        timeout=30.0
    )
    response.raise_for_status()
    
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    
    positions = []
    
    for entity in feed.entity:
        if not entity.HasField('vehicle'):
            continue
        
        vp = entity.vehicle
        trip_id = vp.trip.trip_id
        
        if not is_yamanote(trip_id):
            continue
        
        positions.append(YamanoteTrainPosition(
            trip_id=trip_id,
            train_number=get_train_number(trip_id),
            direction=get_direction(trip_id),
            latitude=vp.position.latitude,
            longitude=vp.position.longitude,
            stop_sequence=vp.current_stop_sequence,
            status=vp.current_status,
            timestamp=vp.timestamp
        ))
    
    return positions


async def fetch_yamanote_positions_with_schedule(api_key: str) -> list[YamanoteTrainPositionWithSchedule]:
    """
    VehiclePosition と TripUpdate を統合して、出発時刻付きの位置情報を返す
    """
    # 1. VehiclePosition を取得
    vehicle_url = "https://api-challenge.odpt.org/api/v4/gtfs/realtime/jreast_odpt_train_vehicle"
    
    # 2. TripUpdate を取得
    trip_update_url = "https://api-challenge.odpt.org/api/v4/gtfs/realtime/jreast_odpt_train_trip_update"
    
    async with httpx.AsyncClient() as client:
        vehicle_resp, trip_resp = await asyncio.gather(
            client.get(vehicle_url, params={"acl:consumerKey": api_key}, timeout=30.0),
            client.get(trip_update_url, params={"acl:consumerKey": api_key}, timeout=30.0),
        )
    
    # VehiclePosition をパース
    vehicle_feed = gtfs_realtime_pb2.FeedMessage()
    vehicle_feed.ParseFromString(vehicle_resp.content)
    
    # TripUpdate をパースしてマップ化
    trip_feed = gtfs_realtime_pb2.FeedMessage()
    trip_feed.ParseFromString(trip_resp.content)
    
    # trip_id → {stop_sequence: {arrival, departure}} のマップ
    trip_schedules = {}
    for entity in trip_feed.entity:
        if not entity.HasField('trip_update'):
            continue
        tu = entity.trip_update
        trip_id = tu.trip.trip_id
        if not is_yamanote(trip_id):
            continue
        
        schedules = {}
        for stu in tu.stop_time_update:
            schedules[stu.stop_sequence] = {
                'arrival': stu.arrival.time if stu.HasField('arrival') else None,
                'departure': stu.departure.time if stu.HasField('departure') else None,
            }
        trip_schedules[trip_id] = schedules
    
    # VehiclePosition と TripUpdate を統合
    positions = []
    for entity in vehicle_feed.entity:
        if not entity.HasField('vehicle'):
            continue
        
        vp = entity.vehicle
        trip_id = vp.trip.trip_id
        
        if not is_yamanote(trip_id):
            continue
        
        # TripUpdate から出発時刻を取得
        departure_time = None
        next_arrival_time = None
        if trip_id in trip_schedules:
            current_seq = vp.current_stop_sequence
            if current_seq in trip_schedules[trip_id]:
                departure_time = trip_schedules[trip_id][current_seq].get('departure')
            next_seq = current_seq + 1
            if next_seq in trip_schedules[trip_id]:
                next_arrival_time = trip_schedules[trip_id][next_seq].get('arrival')
        
        positions.append(YamanoteTrainPositionWithSchedule(
            trip_id=trip_id,
            train_number=get_train_number(trip_id),
            direction=get_direction(trip_id),
            latitude=vp.position.latitude,
            longitude=vp.position.longitude,
            stop_sequence=vp.current_stop_sequence,
            status=vp.current_status,
            timestamp=vp.timestamp,
            departure_time=departure_time,
            next_arrival_time=next_arrival_time,
        ))
    
    return positions
