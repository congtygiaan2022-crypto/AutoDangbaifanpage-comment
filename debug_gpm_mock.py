
import http.server
import socketserver
import json
import time

PORT = 29995
PROFILE_ID = "42577b72-3eb6-40d7-940f-e9c932e4d4e5"

class GPMMockHandler(http.server.BaseHTTPRequestHandler):
    start_attempts = 0

    def do_GET(self):
        # 1. Mock 'start profile' endpoint (returns string)
        if "profiles/start" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"GPM-Login")
            GPMMockHandler.start_attempts = 0 # Reset counter when a start is called
            print(f"[Mock] Called START for {PROFILE_ID}. Returning 'GPM-Login'")

        # 2. Mock 'get profiles' endpoint (returns list)
        elif "profiles" in self.path:
            GPMMockHandler.start_attempts += 1
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Simulate slow port population: only provide port on 4th attempt
            debug_addr = ""
            if GPMMockHandler.start_attempts >= 4:
                debug_addr = "127.0.0.1:12345"
            
            p_list = [
                {
                    "id": PROFILE_ID,
                    "name": "Akiho Yoshizawa",
                    "status": "starting" if debug_addr == "" else "ready",
                    "selenium_remote_debug_address": debug_addr
                }
            ]
            self.wfile.write(json.dumps(p_list).encode())
            print(f"[Mock] Called LIST. Attempt {GPMMockHandler.start_attempts}. Port: {debug_addr}")
        else:
            self.send_response(404)
            self.end_headers()

def run_mock():
    with socketserver.TCPServer(("", PORT), GPMMockHandler) as httpd:
        print(f"Mock GPM API serving at port {PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_mock()
