import json

def main():
    path = "../data/mini-tokyo-3d/train-timetables/jreast-yamanote.json"
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    outer_even = 0
    outer_odd = 0
    inner_even = 0
    inner_odd = 0
    
    for train in data:
        num_str = train.get('n', '')
        direction = train.get('d', '')
        
        # Extract number part
        num_part = ''.join(filter(str.isdigit, num_str))
        if not num_part:
            continue
            
        num = int(num_part)
        is_even = (num % 2 == 0)
        
        if direction == 'OuterLoop':
            if is_even:
                outer_even += 1
            else:
                outer_odd += 1
        elif direction == 'InnerLoop':
            if is_even:
                inner_even += 1
            else:
                inner_odd += 1
                
    print(f"OuterLoop (Even): {outer_even}")
    print(f"OuterLoop (Odd): {outer_odd}")
    print(f"InnerLoop (Even): {inner_even}")
    print(f"InnerLoop (Odd): {inner_odd}")

if __name__ == "__main__":
    main()
