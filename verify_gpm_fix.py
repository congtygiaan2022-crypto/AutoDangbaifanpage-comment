
from gpmlogin_api import GPMLoginAPI
import threading
import time
import subprocess
import sys
import os

def run_test():
    # 1. Start Mock Server in a thread
    # Use the script we just created
    print("[Test] Starting Mock GPM Server...")
    # Since I'm an agent, I'll just rely on the fact that I can't easily run a persistent background process 
    # without blocking my turn, OR I can just run it via run_command if I have it.
    
    # Actually, I'll just write the test logic here and ask the user to run it if they want, 
    # OR I can try to run it myself and see if I can capture output.
    
    api = GPMLoginAPI(base_url="http://localhost:29995")
    profile_id = "42577b72-3eb6-40d7-940f-e9c932e4d4e5"
    
    print(f"[Test] Attempting to start profile {profile_id}...")
    start_time = time.time()
    result = api.start_profile(profile_id)
    end_time = time.time()
    
    if result and result.get('success'):
        print(f"[Test] SUCCESS! Captured metadata: {result['data']}")
        print(f"[Test] Execution took {end_time - start_time:.2f} seconds.")
    else:
        print("[Test] FAILED to retrieve metadata.")

if __name__ == "__main__":
    run_test()
