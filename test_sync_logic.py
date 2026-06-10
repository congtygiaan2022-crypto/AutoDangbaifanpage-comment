from database import Database
import os

def test_sync():
    db_file = "test_sync_database.json"
    if os.path.exists(db_file): os.remove(db_file)
    db = Database(db_file)
    
    # 1. Setup pages and group
    db.add_fanpage("page1")
    db.add_fanpage("page2")
    g_id = db.add_group("Group A", "browser_1")
    
    # 2. Assign pages to group (should sync browser_1)
    db.update_pages_group_bulk([0, 1], g_id)
    
    pages = db.get_fanpages()
    assert pages[0]['browser_id'] == "browser_1"
    assert pages[1]['browser_id'] == "browser_1"
    print("Initial sync passed.")
    
    # 3. Update group browser (should sync pages)
    db.update_group(g_id, "Group A", "browser_2")
    pages = db.get_fanpages()
    assert pages[0]['browser_id'] == "browser_2"
    assert pages[1]['browser_id'] == "browser_2"
    print("Group browser update sync passed.")
    
    # 4. Assign single page to group
    db.add_fanpage("page3")
    db.update_page_group(2, g_id)
    pages = db.get_fanpages()
    assert pages[2]['browser_id'] == "browser_2"
    print("Single page assignment sync passed.")
    
    print("All sync tests passed!")
    if os.path.exists(db_file): os.remove(db_file)

if __name__ == "__main__":
    test_sync()
