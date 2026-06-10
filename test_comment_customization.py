import os
import sys
import random
from database import Database

# Reconfigure stdout for UTF-8 compatibility
sys.stdout.reconfigure(encoding='utf-8')

def test_comment_settings_simulation():
    print("==================================================================")
    print("STARTING FANPAGE COMMENT CUSTOMIZATION SIMULATION TEST")
    print("==================================================================")
    
    db_file = "test_custom_comment_database.json"
    if os.path.exists(db_file):
        os.remove(db_file)
        
    print("\n1. Initializing Database with mock file...")
    db = Database(db_file)
    
    # Verify migration logic
    print("✓ Database initialized.")
    assert db.get_comment_all_fanpages() is True, "Default comment_all_fanpages mode should be True"
    assert db.get_comment_template() == "", "Default global template should be empty string"
    
    print("\n2. Setting up test Fanpages...")
    db.add_fanpage("https://facebook.com/page1")
    db.add_fanpage("https://facebook.com/page2")
    
    fanpages = db.get_fanpages()
    assert len(fanpages) == 2, "Should have 2 fanpages added"
    assert fanpages[0]['comment_template'] == "", "Default fanpage template should be empty string"
    print(f"✓ Added {len(fanpages)} pages. Default individual templates are empty.")

    print("\n3. Setting Global and Per-page templates...")
    global_template = "Mẫu chung: {Xin chào|Hello} các bạn nhé!"
    page1_template = "Mẫu Trang 1: {Chào Page 1|Hi Page 1} chúc {ngày mới tốt lành|buổi chiều vui vẻ}."
    page2_template = "Mẫu Trang 2: {Chúc mừng|Tuyệt vời} {quá|ghê}."
    
    db.set_comment_template(global_template)
    db.update_page_comment_template(0, page1_template)
    db.update_page_comment_template(1, page2_template)
    
    print(f"  - Global template: {db.get_comment_template()}")
    print(f"  - Page 1 template: {db.get_fanpages()[0]['comment_template']}")
    print(f"  - Page 2 template: {db.get_fanpages()[1]['comment_template']}")
    print("✓ Templates set successfully.")

    print("\n4. Testing EFFECTIVE comment template resolving...")
    
    # Case A: Global mode is ACTIVE (comment_all_fanpages = True)
    db.set_comment_all_fanpages(True)
    print(f"  [Mode: Global (All pages)]")
    eff1_global = db.get_effective_comment_template(0)
    eff2_global = db.get_effective_comment_template("https://facebook.com/page2")
    
    print(f"    - Effective Page 1: {eff1_global}")
    print(f"    - Effective Page 2: {eff2_global}")
    
    assert eff1_global == global_template, "Should return global template in global mode"
    assert eff2_global == global_template, "Should return global template in global mode"
    print("  ✓ Correctly resolved to global template.")

    # Case B: Local mode is ACTIVE (comment_all_fanpages = False)
    db.set_comment_all_fanpages(False)
    print(f"  [Mode: Per-page (Local)]")
    eff1_local = db.get_effective_comment_template(0)
    eff2_local = db.get_effective_comment_template("https://facebook.com/page2")
    
    print(f"    - Effective Page 1: {eff1_local}")
    print(f"    - Effective Page 2: {eff2_local}")
    
    assert eff1_local == page1_template, "Should return page1 specific template in local mode"
    assert eff2_local == page2_template, "Should return page2 specific template in local mode"
    print("  ✓ Correctly resolved to page-specific templates.")

    print("\n5. Simulating Spin Syntax Rendering...")
    
    def simulate_spin_text(text):
        import re
        while True:
            match = re.search(r'\{([^{}]+)\}', text)
            if not match:
                break
            options = match.group(1).split('|')
            text = text.replace(match.group(0), random.choice(options), 1)
        return text

    print("  - Spinning global template multiple times:")
    for _ in range(3):
        print(f"    * {simulate_spin_text(global_template)}")
        
    print("  - Spinning Page 1 template multiple times:")
    for _ in range(3):
        print(f"    * {simulate_spin_text(page1_template)}")
        
    print("  - Spinning Page 2 template multiple times:")
    for _ in range(3):
        print(f"    * {simulate_spin_text(page2_template)}")
    print("✓ Spin syntax parsing simulated successfully.")

    print("\n6. Simulating execution loop for worker/GUI runner...")
    # Simulate processing loops in page_worker.py or gui.py
    for idx, page in enumerate(db.get_fanpages()):
        link = page['link']
        # Fetch template for current page
        template = db.get_effective_comment_template(link)
        spun = simulate_spin_text(template)
        print(f"  Processing page {idx+1} ({link}):")
        print(f"    Resolved template -> {template}")
        print(f"    Spun comment string -> {spun}")
    
    # Cleanup
    if os.path.exists(db_file):
        os.remove(db_file)
    print("\n✓ Cleaned up test database files.")
    
    print("==================================================================")
    print("ALL SIMULATION AND UNIT TESTS PASSED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    test_comment_settings_simulation()
