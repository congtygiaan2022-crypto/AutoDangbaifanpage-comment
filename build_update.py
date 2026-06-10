# -*- coding: utf-8 -*-
"""
build_update.py - Công cụ đóng gói và phát hành bản cập nhật trên Máy Gốc (Source Machine)
========================================================================================
Chạy script này trên máy gốc để:
1. Tự động gom các file code cần thiết (.py, .pyw, .bat) và nén thành `update.zip`
2. Tự động tạo/cập nhật `version.json` với số phiên bản mới.
3. Chạy một HTTP Server nội bộ trên Port 8000 để các máy khác tải về trực tiếp qua LAN/Internet.
"""

import os
import json
import zipfile
import http.server
import socketserver
import socket

# Cấu hình các file cần đóng gói (KHÔNG đưa các file database.json, system.db, hay video vào zip)
REQUIRED_FILES = [
    "gui.py",
    "page_worker.py",
    "database.py",
    "db_helper.py",
    "facebook_automator.py",
    "gemlogin_api.py",
    "gpmlogin_api.py",
    "requirements.txt",
    "Chay_Chuong_Trinh.bat",
    "Chay_Khong_CMD.pyw"
]

VERSION_FILE = "current_version.json"
SERVER_PORT = 8000  # Port phát hành link update

def get_local_ip():
    """Lấy IP mạng LAN của máy hiện tại để làm link download cho máy con"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def build_package():
    print("=========================================")
    print(" BẮT ĐẦU ĐÓNG GÓI BẢN CẬP NHẬT ")
    print("=========================================")
    
    # 1. Đọc version hiện tại và tăng phiên bản
    local_version = "2.1"
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                local_version = json.load(f).get("version", "2.1")
        except: pass
        
    try:
        new_version = str(round(float(local_version) + 0.1, 2))
    except:
        new_version = "2.2"
        
    print(f"-> Phiên bản cũ: {local_version}")
    user_input = input(f"-> Nhập phiên bản mới (Nhấn Enter để chọn {new_version}): ").strip()
    if user_input:
        new_version = user_input
        
    changelog = input("-> Nhập nội dung cập nhật (changelog): ").strip()
    if not changelog:
        changelog = f"Bản cập nhật tối ưu hệ thống phiên bản {new_version}"

    # 2. Tạo file nén update.zip
    zip_filename = "update.zip"
    print(f"\n[1/3] Đang nén file vào {zip_filename}...")
    
    count = 0
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
        for file in REQUIRED_FILES:
            if os.path.exists(file):
                zip_ref.write(file)
                print(f"  + Đã nén: {file}")
                count += 1
            else:
                print(f"  - Cảnh báo: Không tìm thấy file {file} (Bỏ qua)")
                
    if count == 0:
        print("❌ Lỗi: Không nén được file nào. Đóng gói thất bại.")
        return None, None
        
    print(f"✓ Đóng gói xong {count} tệp vào {zip_filename}.")

    # 3. Tạo file version.json
    local_ip = get_local_ip()
    download_url = f"http://{local_ip}:{SERVER_PORT}/{zip_filename}"
    
    version_data = {
        "version": new_version,
        "download_url": download_url,
        "changelog": changelog
    }
    
    print(f"\n[2/3] Đang tạo file version.json...")
    print(f"  - Đường dẫn tải bản cập nhật: {download_url}")
    
    with open("version.json", "w", encoding="utf-8") as f:
        json.dump(version_data, f, indent=4, ensure_ascii=False)
    
    # Cập nhật cả file current_version của máy gốc
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": new_version}, f, indent=4)
        
    print("✓ Đã tạo thành công file version.json.")
    return new_version, local_ip

def start_server(local_ip):
    print(f"\n[3/3] Đang khởi chạy Server phát hành cập nhật...")
    
    handler = http.server.SimpleHTTPRequestHandler
    # Tắt log in ra terminal khi client truy cập để đỡ rối
    handler.log_message = lambda *args: None 
    
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", SERVER_PORT), handler) as httpd:
            print("=========================================")
            print(f" SERVER UPDATE ĐANG HOẠT ĐỘNG")
            print(f" - Địa chỉ IP máy gốc: {local_ip}")
            print(f" - Port: {SERVER_PORT}")
            print(f" - Link file version: http://{local_ip}:{SERVER_PORT}/version.json")
            print(f" - Link file zip:     http://{local_ip}:{SERVER_PORT}/update.zip")
            print("=========================================")
            print("Để các máy khác cập nhật được:")
            print(f" 1. Giữ cửa sổ terminal này chạy liên tục.")
            print(f" 2. Trên các máy con, cấu hình SERVER_JSON_URL thành:")
            print(f"    'http://{local_ip}:{SERVER_PORT}/version.json'")
            print(" 3. Đảm bảo các máy con chung mạng LAN (Wifi) với máy gốc.")
            print("    (Nếu khác mạng LAN, bạn cần cấu hình NAT Port Forwarding hoặc dùng Ngrok)")
            print("=========================================")
            print("Nhấn Ctrl+C để tắt Server.")
            httpd.serve_forever()
    except Exception as e:
        print(f"❌ Lỗi khởi chạy Server: {e}")

if __name__ == "__main__":
    version, local_ip = build_package()
    if version:
        try:
            start_server(local_ip)
        except KeyboardInterrupt:
            print("\n❌ Đã dừng Server update.")
