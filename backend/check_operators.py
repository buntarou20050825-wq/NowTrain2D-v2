# backend/check_operators.py
"""
ODPT Challenge API でサポートされている事業者（鉄道会社）を確認
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ODPT_API_KEY", "").strip()

# odpt:Train で取得できる全データを確認
url = "https://api-challenge.odpt.org/api/v4/odpt:Train"
print(f"Fetching all trains from Challenge API...")
resp = requests.get(url, params={"acl:consumerKey": api_key}, timeout=60)

if resp.status_code == 200:
    trains = resp.json()
    print(f"Total trains: {len(trains)}")
    
    # 事業者別に集計
    operators = {}
    for train in trains:
        op = train.get('odpt:operator', 'Unknown')
        if op not in operators:
            operators[op] = {'count': 0, 'railways': set()}
        operators[op]['count'] += 1
        operators[op]['railways'].add(train.get('odpt:railway', 'Unknown'))
    
    print(f"\n=== サポートされている事業者 ({len(operators)}) ===\n")
    for op, data in sorted(operators.items(), key=lambda x: -x[1]['count']):
        op_name = op.split(':')[-1] if ':' in op else op
        print(f"{op_name}: {data['count']}本")
        for railway in sorted(data['railways']):
            line_name = railway.split(':')[-1] if ':' in railway else railway
            print(f"  - {line_name}")
        print()
else:
    print(f"Error: {resp.status_code}")
    print(resp.text[:500])