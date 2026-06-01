import requests
import time

class GPMLoginAPI:
    def __init__(self, base_url="http://localhost:5555"):
        import re
        match = re.match(r"(https?://[^/:]+:\d+)", base_url)
        if match:
            self.base_url = match.group(1)
        else:
            self.base_url = base_url.rstrip('/')

    def get_profiles(self):
        # Default GPM API for profiles
        # Trying various common endpoints for GPM Login V2 and V3
        endpoints = ["/api/v3/profiles", "/api/v2/profiles", "/api/v1/profiles", "/profiles"]
        success = False
        all_profiles = []
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    success = True
                    print(f"DEBUG: GPM Profiles loaded successfully via {endpoint}")
                    
                    if isinstance(data, list):
                        all_profiles = data
                    elif isinstance(data, dict):
                        # Try common fields
                        found = False
                        for field in ['data', 'profiles', 'results', 'data_list', 'list']:
                            res = data.get(field)
                            if isinstance(res, list):
                                all_profiles = res
                                found = True
                                break
                            if isinstance(res, dict) and 'data' in res and isinstance(res['data'], list):
                                all_profiles = res['data']
                                found = True
                                break
                        
                        if not found and ('id' in data or 'profile_id' in data) and ('name' in data or 'title' in data):
                            all_profiles = [data]
                    break
            except: continue
            
        return all_profiles if success else None

    def _wait_and_get_debug_address_from_list(self, profile_id, attempts=10):
        print(f"[GPM] Polling profiles list for profile {profile_id} debug port...")
        for attempt in range(attempts):
            time.sleep(2)
            all_p = self.get_profiles()
            if all_p:
                for p in all_p:
                    p_id = p.get('id', p.get('profile_id', p.get('_id')))
                    if p_id == profile_id:
                        debug = (p.get('selenium_remote_debug_address') or 
                                 p.get('remote_debugging_address') or 
                                 p.get('remote_debug_address') or 
                                 p.get('selenium_debug_address') or
                                 p.get('debug_address'))
                        
                        port = p.get('port') or p.get('selenium_port') or p.get('debug_port')
                        if not debug and port:
                            debug = f"127.0.0.1:{port}"
                            
                        if debug:
                            print(f"[GPM] Found debug address via list: {debug}")
                            return {
                                "selenium_remote_debug_address": debug, 
                                "remote_debugging_address": debug,
                                "debugger_address": debug,
                                "driver_path": p.get('driver_path') or p.get('browser_path', '')
                            }
                        else:
                            print(f"[GPM] Profile found ({profile_id}) but no debug info yet. Status: {p.get('status', p.get('state', 'unknown'))} (Attempt {attempt+1}/{attempts})")
                            break
        return None

    def start_profile(self, profile_id):
        # Force close any existing running instance of the profile first to ensure clean state
        print(f"[GPM] Ensuring profile {profile_id} is closed before starting...")
        try:
            self.stop_profile(profile_id)
            self.kill_chrome_process(profile_id)
            time.sleep(1) # brief pause to let it close
        except Exception as e:
            print(f"Error checking/stopping profile {profile_id}: {e}")

        """
        Starts a profile. Handles cases where API returns non-JSON 'GPM-Login' string.
        """
        endpoints = [
            f"/api/v3/profiles/start/{profile_id}",
            f"/api/v2/profiles/start/{profile_id}",
            f"/api/v1/profiles/start/{profile_id}", 
            f"/profiles/start/{profile_id}"
        ]
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to start profile via: {url}")
                response = requests.get(url, timeout=35)
                body = response.text
                print(f"Start profile status: {response.status_code}, body: {body}")
                
                if response.status_code == 200:
                    # 1. Try JSON decode first
                    try:
                        res_data = response.json()
                        if isinstance(res_data, dict):
                            is_success = res_data.get('success')
                            msg = str(res_data.get('message', '')).upper()
                            
                            # Handle ALREADY_OPEN
                            if is_success is False or "ALREADY_OPEN" in msg:
                                if "ALREADY_OPEN" in msg:
                                    print(f"[GPM] Profile {profile_id} is already open. Stopping profile to reset session...")
                                    self.stop_profile(profile_id)
                                    self.kill_chrome_process(profile_id)
                                    time.sleep(3)
                                    
                                    # Retry starting the profile via the same url
                                    print(f"Retrying start profile via: {url}")
                                    response = requests.get(url, timeout=35)
                                    body = response.text
                                    print(f"Retry start profile status: {response.status_code}, body: {body}")
                                    if response.status_code == 200:
                                        try:
                                            res_data = response.json()
                                            if not isinstance(res_data, dict):
                                                raise Exception("Retry did not return JSON dictionary")
                                            is_success = res_data.get('success')
                                        except Exception as parse_e:
                                            # Fallback to string success checking if retry response is not JSON
                                            if "GPM-Login" in body or (len(body) < 50):
                                                debug_info = self._wait_and_get_debug_address_from_list(profile_id)
                                                if debug_info:
                                                    return {"success": True, "data": debug_info}
                                            raise parse_e
                                    else:
                                        raise Exception(f"Retry returned status {response.status_code}")
                                else:
                                    print(f"[GPM] API returned failure response: {res_data}")
                            
                            # Extract debug address from JSON response
                            data_block = res_data.get('data')
                            if not isinstance(data_block, dict):
                                data_block = res_data
                                
                            debug = (data_block.get('selenium_remote_debug_address') or 
                                     data_block.get('remote_debugging_address') or 
                                     data_block.get('remote_debug_address') or
                                     data_block.get('selenium_debug_address') or
                                     data_block.get('debug_address'))
                            
                            if debug:
                                return {
                                    "success": True, 
                                    "data": {
                                        "selenium_remote_debug_address": debug, 
                                        "remote_debugging_address": debug,
                                        "debugger_address": debug,
                                        "driver_path": data_block.get('driver_path') or data_block.get('browser_path', '')
                                    }
                                }
                            
                            # If API response returned success but no debug info, try polling the list
                            if is_success is True or is_success is None:
                                debug_info = self._wait_and_get_debug_address_from_list(profile_id)
                                if debug_info:
                                    return {"success": True, "data": debug_info}
                                    
                        return {"success": True, "data": res_data}
                    except Exception as json_e:
                        print(f"[GPM] JSON parsing or retry failed: {json_e}")
                        
                        # 2. JSON failed. Check for 'GPM-Login' or other success strings
                        if "GPM-Login" in body or (len(body) < 50 and response.status_code == 200):
                            print(f"[GPM] API returned string success. Waiting for profile metadata...")
                            debug_info = self._wait_and_get_debug_address_from_list(profile_id)
                            if debug_info:
                                return {"success": True, "data": debug_info}
                        
                        print(f"JSON decode failed for {endpoint}, and fallback search failed.")
                        continue
            except requests.exceptions.ReadTimeout as e:
                print(f"ReadTimeout starting GPM profile via {endpoint}: {e}")
                print(f"[GPM] Timeout hit. Force closing profile {profile_id} to clean up...")
                self.stop_profile(profile_id)
                self.kill_chrome_process(profile_id)
                return None
            except Exception as e:
                print(f"Error starting profile via {endpoint}: {e}")
        return None


    def stop_profile(self, profile_id):
        endpoints = [
            f"/api/v3/profiles/close/{profile_id}",
            f"/api/v2/profiles/close/{profile_id}",
            f"/profiles/stop/{profile_id}"
        ]
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to stop profile via: {url}")
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('success') is True:
                            return {"success": True, "message": "Profile stopped"}
                        elif data.get('success') is False:
                            msg = str(data.get('message', '')).lower()
                            if 'not running' in msg or 'not open' in msg or 'already' in msg:
                                return {"success": True, "message": "Profile already stopped"}
                            print(f"Endpoint {endpoint} returned false: {data}")
                            continue
                    except:
                        if "GPM" in response.text or len(response.text) < 50:
                            return {"success": True, "message": "Profile stopped (non-JSON)"}
            except Exception as e:
                print(f"Error on {endpoint}: {e}")
        return {"success": False, "message": "All stop endpoints failed"}

    def find_profile_by_name(self, name):
        profiles = self.get_profiles()
        for profile in profiles:
            p_name = profile.get('name', profile.get('title', '')).strip()
            if p_name.lower() == name.lower().strip():
                return profile
        return None

    def kill_chrome_process(self, profile_id):
        import psutil
        print(f"[GPM]: Checking and killing active Chrome process for profile {profile_id}...")
        
        profile_path = None
        try:
            profiles = self.get_profiles()
            if profiles:
                for p in profiles:
                    p_id = p.get('id') or p.get('profile_id') or p.get('_id')
                    if str(p_id) == str(profile_id):
                        profile_path = p.get('profile_path') or p.get('path')
                        break
        except Exception as e:
            print(f"Could not retrieve profile path via API: {e}")

        # Fallback GPM profile directory pattern
        if not profile_path:
            profile_path = f"gpm_{profile_id}"

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
                            # Strict match: must contain "gpm" to prevent killing GemLogin or personal browsers
                            if "gpm" in user_data_dir:
                                # 1. Strict match of the full path
                                if norm_profile_path in user_data_dir or user_data_dir in norm_profile_path:
                                    match = True
                                # 2. Strict boundary check for relative path fallback
                                elif user_data_dir.endswith(f"/profiles/{profile_id}") or user_data_dir.endswith(f"\\profiles\\{profile_id}") or user_data_dir.endswith(f"/gpm_{profile_id}") or user_data_dir.endswith(f"\\gpm_{profile_id}"):
                                    match = True
                                    
                        if match:
                            pid = proc.info['pid']
                            print(f"[GPM]: Killing Chrome process (PID: {pid}) for profile {profile_id}...")
                            proc.kill()
                            killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        if not killed:
            print(f"[GPM]: No running Chrome process found for profile {profile_id}.")
        return killed
