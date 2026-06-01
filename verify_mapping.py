import sys
import os

# Set output encoding to utf-8 for Windows CMD
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from database import Database

db = Database()
print("Checking for unmapped pages...")
unmapped = [p.get('name') for p in db.get_fanpages() if not p.get('folders')]
print(f"Unmapped pages: {unmapped}")

print("\nRunning auto_map_folders...")
count, details = db.auto_map_folders()
print(f"Mapped {count} pages.")
for detail in details:
    print(f" - {detail}")

print("\nUpdated status for unmapped pages:")
for p in db.get_fanpages():
    if p.get('name') in unmapped:
        print(f"Page: {p.get('name')}, Folders: {p.get('folders')}")
