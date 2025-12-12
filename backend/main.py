# backend/main.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import os
import logging
from typing import Any, Dict, List, Optional

from datetime import datetime
from zoneinfo import ZoneInfo

from data_cache import DataCache
from train_position import (
    get_yamanote_train_positions,
    get_blended_train_positions,
    TrainPositionResponse,
    YamanotePositionsResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")

load_dotenv()

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent  # NowTrain-v2/
DATA_DIR = BASE_DIR / "data"

data_cache = DataCache(DATA_DIR)


@app.on_event("startup")
async def startup_event():
    data_cache.load_all()
    logger.info(
        "Data loaded: %d railways, %d stations",
        len(data_cache.railways),
        len(data_cache.stations),
    )
    # TODO (MS6): FastAPI 0.109+ では lifespan を使う書き方も検討


# CORS 設定
_default_origins = "http://localhost:5173,http://localhost:5174"  # 5174を追加
_raw_origins = os.getenv("FRONTEND_URL", _default_origins)
frontend_urls = [
    origin.strip()
    for origin in _raw_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_urls,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/lines")
async def get_lines(operator: Optional[str] = None):
    logger.info("GET /api/lines called with operator=%s", operator)

    lines = data_cache.railways

    if operator:
        prefix = operator + "."
        lines = [l for l in lines if l.get("id", "").startswith(prefix)]
        # TODO (MS6): operators.json を使った厳密な事業者フィルタを検討

    def to_line_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
        title = raw.get("title", {})
        station_ids = raw.get("stations", [])
        line_id = raw.get("id", "")
        operator_id = line_id.split(".")[0] if "." in line_id else ""
        return {
            "id": line_id,
            "name_ja": title.get("ja", ""),
            "name_en": title.get("en", ""),
            "color": raw.get("color", "#000000"),
            "operator": operator_id,
            "station_count": len(station_ids),
        }

    return {"lines": [to_line_summary(l) for l in lines]}


@app.get("/api/lines/{line_id}")
async def get_line(line_id: str):
    logger.info("GET /api/lines/%s", line_id)

    raw = next((l for l in data_cache.railways if l.get("id") == line_id), None)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Line not found: {line_id}")

    title = raw.get("title", {})
    operator_id = line_id.split(".")[0] if "." in line_id else ""

    return {
        "id": raw.get("id"),
        "name_ja": title.get("ja", ""),
        "name_en": title.get("en", ""),
        "color": raw.get("color", "#000000"),
        "operator": operator_id,
        "stations": raw.get("stations", []),
        "ascending": raw.get("ascending"),
        "descending": raw.get("descending"),
        "car_composition": raw.get("carComposition"),  # 元データ camelCase → API では snake_case に揃え済み
    }


@app.get("/api/stations")
async def get_stations(lineId: Optional[str] = None):
    logger.info("GET /api/stations called with lineId=%s", lineId)

    if lineId is None:
        raise HTTPException(status_code=400, detail="lineId query parameter is required")

    exists = any(l.get("id") == lineId for l in data_cache.railways)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Line not found: {lineId}")

    stations = [st for st in data_cache.stations if st.get("railway") == lineId]

    def to_station(raw: Dict[str, Any]) -> Dict[str, Any]:
        title = raw.get("title", {})
        coord_raw = raw.get("coord")
        lon, lat = None, None
        if isinstance(coord_raw, (list, tuple)) and len(coord_raw) >= 2:
            lon, lat = coord_raw[0], coord_raw[1]

        return {
            "id": raw.get("id"),
            "line_id": raw.get("railway"),
            "name_ja": title.get("ja", ""),
            "name_en": title.get("en", ""),
            "coord": {"lon": lon, "lat": lat},
        }

    return {"stations": [to_station(st) for st in stations]}


@app.get("/api/shapes")
async def get_shapes(lineId: Optional[str] = None):
    logger.info("GET /api/shapes called with lineId=%s", lineId)

    if lineId is None:
        raise HTTPException(status_code=400, detail="lineId query parameter is required")

    exists = any(l.get("id") == lineId for l in data_cache.railways)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Line not found: {lineId}")

    railway_coords = data_cache.coordinates.get("railways", [])
    entry = next((c for c in railway_coords if c.get("id") == lineId), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Shape not found for line: {lineId}")

    merged_coords: List[List[float]] = []
    previous_end: Optional[List[float]] = None

    for sub in entry.get("sublines", []):
        coords = sub.get("coords") or []
        if not coords:
            continue

        if previous_end is not None:
            first = coords[0]
            last = coords[-1]

            dist_to_first = (first[0] - previous_end[0]) ** 2 + (first[1] - previous_end[1]) ** 2
            dist_to_last = (last[0] - previous_end[0]) ** 2 + (last[1] - previous_end[1]) ** 2

            if dist_to_last < dist_to_first:
                coords = list(reversed(coords))

        merged_coords.extend(coords)
        previous_end = coords[-1]

    if not merged_coords:
        raise HTTPException(status_code=404, detail=f"Shape not found for line: {lineId}")

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": merged_coords,
        },
        "properties": {
            "line_id": lineId,
            "color": entry.get("color", "#000000"),
            "segment_type": "main",
        },
    }

    return {
        "type": "FeatureCollection",
        "features": [feature],
    }


@app.get(
    "/api/yamanote/positions",
    response_model=YamanotePositionsResponse,
    tags=["yamanote"],
)
async def api_yamanote_positions(
    now: Optional[str] = Query(
        default=None,
        description=(
            "JST の日時 (ISO8601)。"
            "未指定の場合はサーバー現在時刻(JST)を使用。"
            "例: 2025-01-20T08:00:00+09:00"
        ),
    ),
):
    """
    山手線の「時刻表ベースの列車位置」を返す API。

    - MS3-3 では、駅間を直線補間した簡易位置
    - 将来、GTFS-RT 統合でリアルタイム位置に差し替え予定
    """
    try:
        if now is None:
            dt_jst = datetime.now(JST)
        else:
            dt = datetime.fromisoformat(now)
            if dt.tzinfo is None:
                # タイムゾーン無しの場合は JST とみなす
                dt_jst = dt.replace(tzinfo=JST)
            else:
                dt_jst = dt.astimezone(JST)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid 'now' datetime: {e}")

    positions = get_yamanote_train_positions(dt_jst, data_cache)

    return YamanotePositionsResponse(
        positions=[TrainPositionResponse.from_dataclass(p) for p in positions],
        count=len(positions),
        timestamp=dt_jst.isoformat(),
    )


from gtfs_rt_vehicle import fetch_yamanote_positions, YamanoteTrainPosition

@app.get("/api/trains/yamanote/positions")
async def get_yamanote_positions():
    """
    山手線のリアルタイム列車位置を取得
    
    Returns:
        {
            "timestamp": 1760072237,
            "trains": [
                {
                    "tripId": "4201301G",
                    "trainNumber": "301G",
                    "direction": "OuterLoop",
                    "latitude": 35.7204,
                    "longitude": 139.7063,
                    "stopSequence": 11,
                    "status": 1
                },
                ...
            ]
        }
    """
    api_key = os.getenv("ODPT_API_KEY", "").strip()
    
    try:
        positions = await fetch_yamanote_positions(api_key)
        
        return {
            "timestamp": positions[0].timestamp if positions else 0,
            "count": len(positions),
            "trains": [
                {
                    "tripId": p.trip_id,
                    "trainNumber": p.train_number,
                    "direction": p.direction,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "stopSequence": p.stop_sequence,
                    "status": p.status
                }
                for p in positions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/trains/yamanote/positions/v2")
async def get_yamanote_positions_v2():
    """
    山手線のリアルタイム列車位置を取得（出発時刻付き）
    """
    api_key = os.getenv("ODPT_API_KEY", "").strip()
    
    try:
        from gtfs_rt_vehicle import fetch_yamanote_positions_with_schedule
        positions = await fetch_yamanote_positions_with_schedule(api_key)
        
        return {
            "timestamp": positions[0].timestamp if positions else 0,
            "count": len(positions),
            "trains": [
                {
                    "tripId": p.trip_id,
                    "trainNumber": p.train_number,
                    "direction": p.direction,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "stopSequence": p.stop_sequence,
                    "status": p.status,
                    # 新規追加
                    "departureTime": p.departure_time,
                    "nextArrivalTime": p.next_arrival_time,
                    "timestamp": p.timestamp,  # GTFS-RT更新時刻
                }
                for p in positions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trains/yamanote/positions/v3")
async def get_yamanote_positions_v3():
    """
    時刻表 + GTFS-RT ハイブリッドの列車位置を返す (Phase 1)
    """
    api_key = os.getenv("ODPT_API_KEY", "").strip()
    
    # 1. GTFS-RTを非同期で取得（失敗してもNoneで続行）
    gtfs_data = None
    try:
        gtfs_list = await fetch_yamanote_positions(api_key)
        # train_number をキーとする辞書に変換
        gtfs_data = {pos.train_number: pos for pos in gtfs_list}
        logger.info(f"GTFS-RT: {len(gtfs_data)} trains fetched")
    except Exception as e:
        logger.warning(f"GTFS-RT fetch failed, using timetable only: {e}")
    
    try:
        # 2. 現在時刻を取得
        current_time = datetime.now(JST)
        
        # 3. ブレンド処理を呼び出し
        positions = get_blended_train_positions(
            current_time,
            data_cache,
            gtfs_data
        )
        
        # ★ デバッグ用: マッチングしなかったGTFSキーのサンプルを出力
        if gtfs_data:
            gtfs_keys = set(gtfs_data.keys())
            # マッチ成功したキー（timetable_only 以外）
            matched_keys = {p.number for p in positions if p.data_quality != "timetable_only"}
            
            # マッチしなかったキー
            unmatched_gtfs = list(gtfs_keys - matched_keys)
            
            if unmatched_gtfs:
                logger.warning(f"Unmatched GTFS keys (sample 5): {unmatched_gtfs[:5]}")
            else:
                logger.info("All GTFS data matched successfully!")
        
        # 4. レスポンスを構築
        return {
            "timestamp": current_time.isoformat(),
            "gtfsAvailable": gtfs_data is not None,
            "trainCount": len(positions),
            "trains": [
                {
                    "trainNumber": pos.number,
                    "latitude": pos.lat,
                    "longitude": pos.lon,
                    "fromStation": pos.from_station_id,
                    "toStation": pos.to_station_id,
                    "progress": pos.progress,
                    "direction": pos.direction,
                    "isStopped": pos.is_stopped,
                    "stationId": pos.station_id,
                    "dataQuality": pos.data_quality,
                    # ★ 新規追加: フロントエンドが期待しているフィールド
                    "stopSequence": pos.gtfs_stop_sequence,
                    "gtfsStatus": pos.gtfs_status,
                }
                for pos in positions
            ]
        }
    
    except Exception as e:
        logger.error(f"Error in v3 endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

