from database import Database
import os

def test_groups():
    # Use a temporary database file
    db_file = "test_database.json"
    if os.path.exists(db_file):
        os.remove(db_file)
    
    db = Database(db_file)
    
    # Add a page
    db.add_fanpage("https://fb.com/page1")
    db.update_fanpage_name(0, "Page 1")
    
    # Add a group
    g_id = db.add_group("Group A", "gpmlogin_default")
    print(f"Added Group A: {g_id}")
    
    # Assign page to group
    db.update_page_group(0, g_id)
    print("Assigned Page 1 to Group A")
    
    # Verify resolution
    resolved_b = db.resolve_page_browser_id(0)
    print(f"Resolved Browser for Page 1: {resolved_b}")
    assert resolved_b == "gpmlogin_default"
    
    # Update group browser
    db.update_group(g_id, "Group A", "gemlogin_default")
    resolved_b2 = db.resolve_page_browser_id(0)
    print(f"Resolved Browser for Page 1 after group update: {resolved_b2}")
    assert resolved_b2 == "gemlogin_default"
    
    # Remove group
    db.remove_group(g_id)
    pages = db.get_fanpages()
    print(f"Page 1 group_id after removal: '{pages[0]['group_id']}'")
    assert pages[0]['group_id'] == ""
    
    print("Test passed!")
    
    if os.path.exists(db_file):
        os.remove(db_file)

if __name__ == "__main__":
    test_groups()
