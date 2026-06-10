import json

try:
    with open(r"h:\Tool_tucode\AutoDangbaifanpage+comment\database.json", "r", encoding="utf-8") as f:
        json.load(f)
    print("JSON is valid.")
except Exception as e:
    print(f"JSON Error: {e}")
