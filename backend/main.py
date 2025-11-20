# backend/main.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import os
import logging
from typing import Any, Dict, List, Optional

from data_cache import DataCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
_raw_origins = os.getenv("FRONTEND_URL", "http://localhost:5173")
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
