"""Test get_train_number with new regex pattern"""
import re

def get_train_number(trip_id: str) -> str:
    """Regex-based extraction"""
    match = re.search(r'(\d{3,4})([A-Z])$', trip_id)
    
    if match:
        number_part = match.group(1)
        suffix = match.group(2)
        normalized_number = str(int(number_part))
        return f"{normalized_number}{suffix}"
    
    return trip_id

# Test cases based on user's requirements
test_cases = [
    ("4201103G", "1103G"),   # 4桁の列車番号
    ("4200906G", "906G"),    # ゼロ埋め4桁→3桁に正規化
    ("4201301G", "1301G"),   # 4桁
    ("42001103G", "1103G"),  # プレフィックス5桁でも動作
]

print("Testing get_train_number (regex pattern \\d{3,4}):")
all_passed = True
for trip_id, expected in test_cases:
    result = get_train_number(trip_id)
    status = "OK" if result == expected else "FAIL"
    if result != expected:
        all_passed = False
    print(f"  {trip_id:<12} -> {result:<8} (expected: {expected:<8}) [{status}]")

print(f"\n{'All tests passed!' if all_passed else 'Some tests failed!'}")
