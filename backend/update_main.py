"""Update main.py to add v3 endpoint"""
import re

# Read with proper encoding
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
old_import = '''from train_position import (
    get_yamanote_train_positions,
    TrainPositionResponse,
    YamanotePositionsResponse,
)'''

new_import = '''from train_position import (
    get_yamanote_train_positions,
    get_blended_train_positions,
    TrainPositionResponse,
    YamanotePositionsResponse,
)'''

content = content.replace(old_import, new_import)

# 2. Add v3 endpoint at the end
v3_endpoint = '''

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
                }
                for pos in positions
            ]
        }
    
    except Exception as e:
        logger.error(f"Error in v3 endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
'''

# Check if v3 already exists
if '/api/trains/yamanote/positions/v3' not in content:
    content = content.rstrip() + v3_endpoint + '\n'
    print("Added v3 endpoint")
else:
    print("v3 endpoint already exists")

# Write back
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("main.py updated successfully")
