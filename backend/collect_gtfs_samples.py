import time
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

# .env から APIキーを読み込む
load_dotenv()
API_KEY = os.getenv("ODPT_API_KEY")

if not API_KEY:
    print("Error: ODPT_API_KEY not found in .env file.")
    exit(1)

URL = "https://api-challenge.odpt.org/api/v4/gtfs/realtime/jreast_odpt_train_vehicle"
COUNT = 5        # 取得回数
INTERVAL = 30    # 間隔（秒）

print(f"Starting GTFS-RT collection: {COUNT} files, every {INTERVAL} seconds...")

for i in range(COUNT):
    try:
        # APIリクエスト
        print(f"[{i+1}/{COUNT}] Fetching data at {datetime.now().strftime('%H:%M:%S')}...")
        response = requests.get(URL, params={"acl:consumerKey": API_KEY}, timeout=10)
        response.raise_for_status()
        
        # バイナリとして保存
        filename = f"gtfs_sample_{i}.bin"
        with open(filename, "wb") as f:
            f.write(response.content)
        
        print(f"  -> Saved to {filename} ({len(response.content)} bytes)")
        
    except Exception as e:
        print(f"  -> Error: {e}")
    
    # 最後の回以外は待機
    if i < COUNT - 1:
        time.sleep(INTERVAL)

print("Done! Please upload the generated .bin files.")