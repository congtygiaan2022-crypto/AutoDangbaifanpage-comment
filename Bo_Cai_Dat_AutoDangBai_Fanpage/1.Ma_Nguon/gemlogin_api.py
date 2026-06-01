import requests
import time

class GemLoginAPI:
    def __init__(self, base_url="http://localhost:1010"):
        self.base_url = base_url

    def get_profiles(self):
        endpoints = ["/profiles", "/api/profiles", "/api/v1/profiles"]
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying endpoint: {url}")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    # GenLogin/GemLogin often return profiles in a list directly or under 'data'
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        return data.get('data', [])
                print(f"Endpoint {url} returned {response.status_code}")
            except Exception as e:
                print(f"Error on {endpoint}: {e}")
        return []

    def start_profile(self, profile_id):
        # Possible patterns: /profiles/start/{id}, /api/profiles/start/{id}, /api/v1/profiles/start/{id}
        endpoints = [f"/profiles/start/{profile_id}", f"/api/profiles/start/{profile_id}", f"/api/v1/profiles/start/{profile_id}"]
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to start profile via: {url}")
                # Increase timeout since starting a profile can take a long time on some systems
                response = requests.get(url, timeout=60)
                print(f"Start profile status: {response.status_code}, body: {response.text}")
                if response.status_code == 200:
                    return response.json() 
            except Exception as e:
                print(f"Error starting profile via {endpoint}: {e}")
        return None

    def stop_profile(self, profile_id):
        endpoints = [f"/profiles/stop/{profile_id}", f"/api/profiles/close/{profile_id}", f"/api/profiles/stop/{profile_id}"]
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to stop profile via: {url}")
                response = requests.get(url, timeout=10)
                print(f"Stop profile status: {response.status_code}")
                if response.status_code == 200:
                    try:
                        return response.json()
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
