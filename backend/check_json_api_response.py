"""
ODPT JSON API レスポンス確認
どんなフィールドが含まれてるか調べる
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ODPT_API_KEY", "").strip()
YAMANOTE_API_URL = "https://api-challenge.odpt.org/api/v4/odpt:Train"

def main():
    params = {
        "odpt:railway": "odpt.Railway:JR-East.Yamanote",
        "acl:consumerKey": API_KEY
    }
    
    resp = requests.get(YAMANOTE_API_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    print("=" * 60)
    print(f"取得した列車数: {len(data)}")
    print("=" * 60)
    
    if data:
        print("\n【サンプル（1件目）の全フィールド】")
        print(json.dumps(data[0], indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 60)
        print("【全列車の概要】")
        print("=" * 60)
        for train in data[:10]:  # 最初の10件
            train_num = train.get("odpt:trainNumber", "?")
            from_st = train.get("odpt:fromStation", "").split(".")[-1] if train.get("odpt:fromStation") else "?"
            to_st = train.get("odpt:toStation", "").split(".")[-1] if train.get("odpt:toStation") else "?"
            delay = train.get("odpt:delay", 0)
            
            # 時刻関連のフィールドを探す
            time_fields = [k for k in train.keys() if "time" in k.lower() or "date" in k.lower()]
            
            print(f"{train_num}: {from_st} → {to_st} (delay: {delay}秒)")
            if time_fields:
                print(f"  時刻フィールド: {time_fields}")
                for tf in time_fields:
                    print(f"    {tf}: {train.get(tf)}")

if __name__ == "__main__":
    main()