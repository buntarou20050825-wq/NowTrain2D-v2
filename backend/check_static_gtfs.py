import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ODPT_API_KEY", "").strip()

# 静的GTFSデータのエンドポイント候補
endpoints = [
    "https://api-challenge.odpt.org/api/v4/gtfs/jreast",
    "https://api-challenge.odpt.org/api/v4/files/JR-East/data/JR-East-GTFS.zip",
]

for url in endpoints:
    print(f"\nTrying: {url}")
    try:
        resp = requests.get(url, params={"acl:consumerKey": api_key}, timeout=30, stream=True)
        print(f"  Status: {resp.status_code}")
        print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
        print(f"  Content-Length: {resp.headers.get('content-length', 'N/A')}")
        
        if resp.status_code == 200:
            # 最初の100バイトを確認
            content_start = resp.content[:100]
            print(f"  Content start: {content_start[:50]}...")
            
            # ZIPファイルかどうか確認
            if content_start[:2] == b'PK':
                print(f"  >>> ZIP file detected! <<<")
    except Exception as e:
        print(f"  Error: {e}")

print("\nDone.")