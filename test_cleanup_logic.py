import psutil
import subprocess
import time
import os
import sys

def test_cleanup_logic():
    # 1. Start a dummy "page_worker" script
    worker_content = "import time\nwhile True: time.sleep(1)"
    with open("dummy_worker.py", "w") as f:
        f.write(worker_content)
    
    # Start it
    proc = subprocess.Popen([sys.executable, "dummy_worker.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
    print(f"Started dummy worker PID: {proc.pid}")
    
    # Give it a second to start
    time.sleep(2)
    
    # Verify it exists
    assert psutil.pid_exists(proc.pid)
    print("Verified worker exists.")
    
    # 2. Simulate cleanup
    print("Running cleanup logic simulation...")
    found = False
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = p.info.get('cmdline') or []
            cmdline_str = " ".join(cmdline).lower()
            if "dummy_worker.py" in cmdline_str:
                print(f"Found target process: {p.pid}. Terminating...")
                p.terminate()
                found = True
        except: continue
    
    assert found
    
    # Wait for completion
    time.sleep(2)
    assert not psutil.pid_exists(proc.pid)
    print("Verified worker terminated successfully.")
    
    # Cleanup dummy file
    if os.path.exists("dummy_worker.py"):
        os.remove("dummy_worker.py")
    
    print("Test passed!")

if __name__ == "__main__":
    test_cleanup_logic()
