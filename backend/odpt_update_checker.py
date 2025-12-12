"""
ODPT JSON API 更新頻度チェッカー
山手線の列車情報がどれくらいの頻度で更新されるか計測する
"""

import os
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ODPT_API_KEY", "").strip()
YAMANOTE_API_URL = "https://api-challenge.odpt.org/api/v4/odpt:Train"

def fetch_yamanote_trains():
    """山手線の列車情報を取得"""
    params = {
        "odpt:railway": "odpt.Railway:JR-East.Yamanote",
        "acl:consumerKey": API_KEY
    }
    
    try:
        resp = requests.get(YAMANOTE_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] API取得失敗: {e}")
        return None

def extract_train_state(train):
    """列車の状態を抽出（変化検知用）"""
    return {
        "trainNumber": train.get("odpt:trainNumber"),
        "fromStation": train.get("odpt:fromStation"),
        "toStation": train.get("odpt:toStation"),
        "delay": train.get("odpt:delay", 0),
    }

def main():
    if not API_KEY:
        print("[ERROR] ODPT_API_KEY が設定されていません")
        print("  export ODPT_API_KEY='your-api-key'")
        return
    
    print("=" * 60)
    print("ODPT JSON API 更新頻度チェッカー")
    print("=" * 60)
    print(f"開始時刻: {datetime.now().strftime('%H:%M:%S')}")
    print("5秒ごとにAPIを叩いて、データの変化を検知します")
    print("Ctrl+C で終了")
    print("=" * 60)
    print()
    
    # 前回の状態を保持
    prev_states = {}  # { trainNumber: state }
    update_times = []  # 更新検知時刻のリスト
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            now = datetime.now()
            now_str = now.strftime('%H:%M:%S')
            
            trains = fetch_yamanote_trains()
            if not trains:
                time.sleep(5)
                continue
            
            # 変化を検知
            changes = []
            for train in trains:
                train_num = train.get("odpt:trainNumber")
                if not train_num:
                    continue
                
                current_state = extract_train_state(train)
                prev_state = prev_states.get(train_num)
                
                if prev_state:
                    # fromStation または toStation が変わったか
                    if (prev_state["fromStation"] != current_state["fromStation"] or
                        prev_state["toStation"] != current_state["toStation"]):
                        changes.append({
                            "trainNumber": train_num,
                            "before": f"{prev_state['fromStation']} → {prev_state['toStation']}",
                            "after": f"{current_state['fromStation']} → {current_state['toStation']}",
                        })
                
                prev_states[train_num] = current_state
            
            # 結果表示
            if changes:
                update_times.append(now)
                print(f"\n[{now_str}] 🔄 {len(changes)}件の更新を検知!")
                for c in changes[:5]:  # 最大5件表示
                    print(f"  {c['trainNumber']}: {c['before']} → {c['after']}")
                if len(changes) > 5:
                    print(f"  ... 他{len(changes) - 5}件")
                
                # 更新間隔を計算
                if len(update_times) >= 2:
                    interval = (update_times[-1] - update_times[-2]).total_seconds()
                    print(f"  📊 前回更新からの間隔: {interval:.0f}秒")
            else:
                # 変化なし（ドットで進捗表示）
                print(f"[{now_str}] . (列車数: {len(trains)}, チェック#{check_count})", end="\r")
            
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("計測終了")
        print("=" * 60)
        
        if len(update_times) >= 2:
            intervals = []
            for i in range(1, len(update_times)):
                intervals.append((update_times[i] - update_times[i-1]).total_seconds())
            
            print(f"検知した更新回数: {len(update_times)}")
            print(f"更新間隔:")
            print(f"  最小: {min(intervals):.0f}秒")
            print(f"  最大: {max(intervals):.0f}秒")
            print(f"  平均: {sum(intervals)/len(intervals):.0f}秒")
        else:
            print("十分なデータが集まりませんでした")
        
        print("=" * 60)

if __name__ == "__main__":
    main()