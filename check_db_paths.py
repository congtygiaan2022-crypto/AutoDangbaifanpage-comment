
import json
import os

path = "database.json"
print(f"Current Working Directory: {os.getcwd()}")
print(f"Path to database.json: {os.path.abspath(path)}")

if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for page in data.get('fanpages', []):
            if page.get('name') == 'Xóm Nhiều Chuyện':
                print(f"Folders for Xóm Nhiều Chuyện: {page.get('folders')}")
            if page.get('name') == 'Tee Cloudy':
                print(f"Folders for Tee Cloudy: {page.get('folders')}")
else:
    print("database.json NOT FOUND in CWD!")
