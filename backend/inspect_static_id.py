import json
import os

def main():
    path = "../data/mini-tokyo-3d/train-timetables/jreast-yamanote.json"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Total trains: {len(data)}")
    print("First 5 trains:")
    for i, train in enumerate(data[:5]):
        print(f"  ID: {train.get('id')}")
        print(f"  Number: {train.get('n')}")
        print(f"  Type: {train.get('y')}")
        print(f"  Direction: {train.get('d')}")
        print("-" * 20)

if __name__ == "__main__":
    main()
