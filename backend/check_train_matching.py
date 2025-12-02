# backend/check_train_matching.py
"""
ODPT JSON API と静的時刻表の trainNumber マッチング確認
対象: 横浜線、京王相模原線
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

def fetch_trains(railway_filter):
    """指定路線の列車を取得"""
    url = f"https://api-challenge.odpt.org/api/v4/odpt:Train?odpt:railway={railway_filter}"
    resp = requests.get(url, params={"acl:consumerKey": api_key}, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return []

def fetch_all_jreast():
    """JR東日本の全列車を取得"""
    url = "https://api-challenge.odpt.org/api/v4/odpt:Train?odpt:operator=odpt.Operator:JR-East"
    resp = requests.get(url, params={"acl:consumerKey": api_key}, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return []

def fetch_keio():
    """京王の全列車を取得"""
    url = "https://api-challenge.odpt.org/api/v4/odpt:Train?odpt:operator=odpt.Operator:Keio"
    resp = requests.get(url, params={"acl:consumerKey": api_key}, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return []

print("=" * 60)
print("ODPT JSON API - Train Number Matching Test")
print("=" * 60)

# === 1. JR東日本 横浜線 ===
print("\n[1] JR東日本 横浜線")
print("-" * 40)

# 横浜線を直接取得
yokohama_trains = fetch_trains("odpt.Railway:JR-East.Yokohama")
print(f"横浜線列車数: {len(yokohama_trains)}")

if yokohama_trains:
    print("\n横浜線の列車番号サンプル:")
    for train in yokohama_trains[:10]:
        print(f"  trainNumber: {train.get('odpt:trainNumber'):<10} "
              f"direction: {train.get('odpt:railDirection', '').split(':')[-1]:<10} "
              f"from: {train.get('odpt:fromStation', '').split('.')[-1]}")
else:
    # 横浜線がない場合、全JR東日本から探す
    print("横浜線が見つからない。JR東日本全体から検索...")
    all_jreast = fetch_all_jreast()
    
    # 路線別に集計
    railways = {}
    for train in all_jreast:
        railway = train.get('odpt:railway', 'Unknown')
        if railway not in railways:
            railways[railway] = []
        railways[railway].append(train)
    
    print(f"\nJR東日本の路線一覧 ({len(railways)}路線):")
    for railway, trains in sorted(railways.items()):
        line_name = railway.split(':')[-1] if ':' in railway else railway
        sample_nums = [t.get('odpt:trainNumber', '?') for t in trains[:3]]
        print(f"  {line_name:<25} {len(trains):>3}本  例: {sample_nums}")

# === 2. 京王電鉄 ===
print("\n" + "=" * 60)
print("[2] 京王電鉄")
print("-" * 40)

keio_trains = fetch_keio()
print(f"京王列車数: {len(keio_trains)}")

if keio_trains:
    # 路線別に集計
    keio_railways = {}
    for train in keio_trains:
        railway = train.get('odpt:railway', 'Unknown')
        if railway not in keio_railways:
            keio_railways[railway] = []
        keio_railways[railway].append(train)
    
    print(f"\n京王の路線一覧 ({len(keio_railways)}路線):")
    for railway, trains in sorted(keio_railways.items()):
        line_name = railway.split(':')[-1] if ':' in railway else railway
        print(f"\n  {line_name} ({len(trains)}本):")
        for train in trains[:5]:
            print(f"    trainNumber: {train.get('odpt:trainNumber'):<10} "
                  f"type: {train.get('odpt:trainType', '').split('.')[-1]:<15} "
                  f"from: {train.get('odpt:fromStation', '').split('.')[-1]}")
else:
    print("京王の列車が見つからない")

# === 3. 静的時刻表との比較 ===
print("\n" + "=" * 60)
print("[3] 静的時刻表との比較")
print("-" * 40)

# 静的時刻表のサンプル（ユーザー提供）
static_yokohama = ["447K", "525K", "507K", "503K"]
static_keio = ["7731", "7733", "7735", "7737", "7739"]

print("\n横浜線 - 静的時刻表の列車番号:")
print(f"  {static_yokohama}")

if yokohama_trains:
    odpt_yokohama = [t.get('odpt:trainNumber') for t in yokohama_trains]
    matched = [n for n in static_yokohama if n in odpt_yokohama]
    print(f"  ODPT API の列車番号: {odpt_yokohama[:10]}...")
    print(f"  マッチ: {matched if matched else 'なし（時刻が異なる可能性）'}")

print("\n京王相模原線 - 静的時刻表の列車番号:")
print(f"  {static_keio}")

if keio_trains:
    # 相模原線のみ抽出
    sagamihara_trains = [t for t in keio_trains 
                         if 'Sagamihara' in t.get('odpt:railway', '')]
    if sagamihara_trains:
        odpt_keio = [t.get('odpt:trainNumber') for t in sagamihara_trains]
        matched = [n for n in static_keio if n in odpt_keio]
        print(f"  ODPT API の列車番号: {odpt_keio[:10]}...")
        print(f"  マッチ: {matched if matched else 'なし（時刻が異なる可能性）'}")
    else:
        print("  相模原線の列車が見つからない")

print("\n" + "=" * 60)
print("Done.")