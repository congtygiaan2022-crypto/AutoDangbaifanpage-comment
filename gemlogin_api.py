import requests
import time

class GemLoginAPI:
    def __init__(self, base_url="http://localhost:1010"):
        import re
        match = re.match(r"(https?://[^/:]+:\d+)", base_url)
        if match:
            self.base_url = match.group(1)
        else:
            self.base_url = base_url.rstrip('/')

    def get_profiles(self):
        # GemLogin / GenLogin standard endpoints
        endpoints = ["/profiles", "/api/profiles", "/api/v1/profiles", "/api/v2/profiles", "/api/v3/profiles"]
        success = False
        all_profiles = []
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    success = True
                    if isinstance(data, list):
                        all_profiles = data
                    elif isinstance(data, dict):
                        all_profiles = data.get('data', [])
                    break
            except: continue
            
        return all_profiles if success else None

    def start_profile(self, profile_id):
        # Force close any existing running instance of the profile first to ensure clean state
        print(f"GemLogin: Ensuring profile {profile_id} is closed before starting...")
        try:
            self.stop_profile(profile_id)
            self.kill_chrome_process(profile_id)
            time.sleep(1) # brief pause to let it close
        except Exception as e:
            print(f"Error checking/stopping profile {profile_id}: {e}")

        # Prioritize known working /api/profiles/start/ endpoint first
        endpoints = [
            f"/api/profiles/start/{profile_id}",
            f"/api/v1/profiles/start/{profile_id}",
            f"/api/profile/start/{profile_id}",
            f"/profiles/start/{profile_id}"
        ]
        
        for attempt in range(3):
            for endpoint in endpoints:
                url = f"{self.base_url}{endpoint}"
                try:
                    print(f"Trying to start profile (Attempt {attempt+1}) via: {url}")
                    # Use 35s timeout to give slow proxies/connections enough time
                    response = requests.get(url, timeout=35)
                    if response.status_code == 200:
                        res_data = response.json()
                        if isinstance(res_data, dict):
                            # Special case: success is False but status is 200 (Not Ready)
                            if res_data.get('success') is False:
                                msg = res_data.get('message', '').lower()
                                if 'not ready' in msg or 'running' in msg:
                                    print(f"GemLogin: Profile {profile_id} is {msg}. Attempt {attempt+1}/3...")
                                    if attempt == 0:
                                        print(f"GemLogin: Force closing profile {profile_id} before retry...")
                                        self.stop_profile(profile_id)
                                        self.kill_chrome_process(profile_id)
                                    time.sleep(5)
                                    break # Try next attempt
                                
                                print(f"GemLogin API Error: {res_data.get('message')}")
                                continue # Try next endpoint
                                
                            if res_data.get('success') or res_data.get('status') == 'success' or 'data' in res_data:
                                if 'success' not in res_data: res_data['success'] = True
                                if 'data' not in res_data: res_data['data'] = res_data
                                return res_data
                        return {"success": True, "data": res_data}
                except requests.exceptions.ReadTimeout as e:
                    print(f"ReadTimeout starting profile via {endpoint}: {e}")
                    if "/api/profiles/start/" in endpoint:
                        # Clean up any stuck background browser processes to prevent "a bunch of open tabs"
                        print(f"GemLogin: Timeout hit. Force closing profile {profile_id} to clean up...")
                        self.stop_profile(profile_id)
                        self.kill_chrome_process(profile_id)
                        return None # Exit immediately, do not retry!
                except Exception as e:
                    print(f"Error starting profile via {endpoint}: {e}")
            
            if attempt < 2:
                time.sleep(2) # Gap between full endpoint cycles
                
        return None

    def stop_profile(self, profile_id):
        endpoints = [
            f"/api/profiles/close/{profile_id}",
            f"/api/v1/profiles/close/{profile_id}",
            f"/profiles/stop/{profile_id}"
        ]
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to stop profile via: {url}")
                response = requests.get(url, timeout=3)
                print(f"Stop profile status: {response.status_code}")
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('success') is True or data.get('status') == 'success':
                            return {"success": True, "message": "Profile stopped"}
                        elif data.get('success') is False:
                            msg = str(data.get('message', '')).lower()
                            if 'not running' in msg or 'not open' in msg or 'already' in msg:
                                return {"success": True, "message": "Profile already stopped"}
                            print(f"Endpoint {endpoint} returned false: {data}")
                            continue
                        return data
                    except:
                        return {"success": True, "message": "Profile stopped"}
            except Exception as e:
                print(f"Error on {endpoint}: {e}")
        return {"success": False, "message": "All stop endpoints failed"}

    def find_profile_by_name(self, name):
        profiles = self.get_profiles()
        print(f"Debugging: Looking for profile '{name}'")
        print(f"Total profiles found: {len(profiles)}")
        for profile in profiles:
            p_name = profile.get('name', '').strip()
            print(f"Checking candidate: '{p_name}'")
            if p_name.lower() == name.lower().strip():
                return profile
        return None

    def kill_chrome_process(self, profile_id):
        import psutil
        print(f"GemLogin: Checking and killing active Chrome process for profile {profile_id}...")
        
        profile_path = None
        try:
            profiles = self.get_profiles()
            if profiles:
                for p in profiles:
                    p_id = p.get('id')
                    if str(p_id) == str(profile_id):
                        profile_path = p.get('profile_path')
                        break
        except Exception as e:
            print(f"Could not retrieve profile path via API: {e}")

        # Fallback path if API failed
        if not profile_path:
            profile_path = f".gemlogin/profile/profiles/{profile_id}"

        norm_profile_path = profile_path.replace("\\", "/").rstrip("/").lower()

        killed = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name']
                if name and 'chrome' in name.lower():
                    cmdline = proc.info['cmdline']
                    if cmdline:
                        user_data_dir = None
                        for arg in cmdline:
                            if arg.startswith('--user-data-dir='):
                                user_data_dir = arg.split('=', 1)[1].strip('"\'').replace("\\", "/").rstrip("/").lower()
                                break
                        
                        match = False
                        if user_data_dir:
                            # Strict match: must contain ".gemlogin" to prevent killing GPM or personal browsers
                            if ".gemlogin" in user_data_dir:
                                # 1. Strict match of the full path
                                if norm_profile_path in user_data_dir or user_data_dir in norm_profile_path:
                                    match = True
                                # 2. Strict boundary check for relative path fallback
                                elif user_data_dir.endswith(f"/profiles/{profile_id}") or user_data_dir.endswith(f"\\profiles\\{profile_id}"):
                                    match = True
                                    
                        if match:
                            pid = proc.info['pid']
                            print(f"GemLogin: Killing Chrome process (PID: {pid}) for profile {profile_id}...")
                            proc.kill()
                            killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        if not killed:
            print(f"GemLogin: No running Chrome process found for profile {profile_id}.")
        return killed
