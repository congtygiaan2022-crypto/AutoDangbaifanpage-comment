import sys
import json
import os

# Set output encoding to utf-8 for Windows CMD
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open('database.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"{'STT':<4} {'Name':<35} {'Folders Status'}")
print("-" * 75)

for page in data.get('fanpages', []):
    stt = page.get('stt', '?')
    name = page.get('name', 'Page_Khong_Ten').strip()
    folders = page.get('folders', [])
    
    if not folders:
        print(f"{stt:<4} {name:<35} EMPTY FOLDERS")
        continue
    
    status = []
    for folder in folders:
        if os.path.exists(folder):
            try:
                files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))]
                status.append(f"EXISTS ({len(files)} videos)")
            except Exception as e:
                status.append(f"ERROR ({e})")
        else:
            status.append("MISSING")
    
    print(f"{stt:<4} {name:<35} {', '.join(status)}")
