"""
GTFS-RT VehiclePosition から山手線の列車位置を取得
"""
import os
import httpx
from google.transit import gtfs_realtime_pb2
from dataclasses import dataclass
from typing import Optional


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
    """列車番号を抽出（静的時刻表との照合用）"""
    # "4201301G" → "301G"
    return trip_id[4:]


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
