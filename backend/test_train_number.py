"""Test get_train_number function with 4-digit prefix skip"""
import re

def get_train_number(trip_id: str) -> str:
    """4桁プレフィックススキップ + ゼロ埋め除去"""
    if len(trip_id) <= 4:
        return trip_id
    
    suffix = trip_id[4:]
    
    match = re.match(r'^(\d+)([A-Z])$', suffix)
    if match:
        number_part = match.group(1)
        letter = match.group(2)
        normalized_number = str(int(number_part))
        return f"{normalized_number}{letter}"
    
    return suffix

# Test cases
test_cases = [
    ("4201301G", "301G"),
    ("42020906G", "906G"),
    ("42010461G", "461G"),
    ("4211904G", "904G"),
    ("42110002G", "2G"),
]

print("Testing get_train_number (4-digit prefix skip + normalize):")
all_passed = True
for trip_id, expected in test_cases:
    result = get_train_number(trip_id)
    status = "OK" if result == expected else "FAIL"
    if result != expected:
        all_passed = False
    print(f"  {trip_id} -> {result} (expected: {expected}) [{status}]")

print(f"\n{'All tests passed!' if all_passed else 'Some tests failed!'}")
