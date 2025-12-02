# backend/check_odpt_json_api.py
"""
ODPT JSON API を調査して、列車の路線情報が取得できるか確認
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ODPT_API_KEY", "").strip()

if not api_key:
    print("Error: ODPT_API_KEY not set")
    exit(1)

# ODPT JSON API エンドポイント
endpoints = [
    # JR東日本の列車ロケーション（リアルタイム）
    ("JR-East Trains", "https://api-challenge.odpt.org/api/v4/odpt:Train?odpt:operator=odpt.Operator:JR-East"),
    # 山手線の列車のみ
    ("Yamanote Trains", "https://api-challenge.odpt.org/api/v4/odpt:Train?odpt:railway=odpt.Railway:JR-East.Yamanote"),
    # 路線一覧
    ("JR-East Railways", "https://api-challenge.odpt.org/api/v4/odpt:Railway?odpt:operator=odpt.Operator:JR-East"),
]

for name, url in endpoints:
    print(f"\n{'='*60}")
    print(f"[{name}]")
    print(f"URL: {url[:70]}...")
    
    try:
        resp = requests.get(url, params={"acl:consumerKey": api_key}, timeout=30)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            if isinstance(data, list):
                print(f"Result count: {len(data)}")
                
                if data:
                    print(f"\nFirst item keys: {list(data[0].keys())}")
                    print(f"\nFirst item (formatted):")
                    print(json.dumps(data[0], ensure_ascii=False, indent=2))
                    
                    # 2件目もあれば表示
                    if len(data) > 1:
                        print(f"\nSecond item (formatted):")
                        print(json.dumps(data[1], ensure_ascii=False, indent=2))
            else:
                print(f"Result type: {type(data)}")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
        else:
            print(f"Error: {resp.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("Error: Request timed out")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

print(f"\n{'='*60}")
print("Done.")