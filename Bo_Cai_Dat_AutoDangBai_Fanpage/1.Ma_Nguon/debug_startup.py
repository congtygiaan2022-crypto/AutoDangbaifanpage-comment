import sys
import traceback

try:
    print("Importing database...")
    from database import Database
    
    print("Initializing Database...")
    db = Database()
    print("Database loaded successfully.")
    
    fanpages = db.get_fanpages()
    print(f"Loaded {len(fanpages)} fanpages.")
    
    for i, page in enumerate(fanpages):
        print(f"Page {i}: STT={page.get('stt')}, Link={page.get('link')}")
        
    print("Startup check passed.")
    
except Exception:
    print("Startup failed!")
    traceback.print_exc()
