"""Print specific sections from debug result"""
with open('debug_result.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== FILE CONTENTS ===")
for i, line in enumerate(lines):
    print(f"{i:03d}: {line.rstrip()}")
