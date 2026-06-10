# -*- coding: utf-8 -*-
"""
launcher.py - Trình khởi chạy & Cập nhật tự động cho các Máy Con (Client Machines)
=============================================================================
Hướng dẫn cài đặt trên máy con:
1. Đặt file này vào thư mục chứa code Tool trên máy con.
2. Sửa lại biến `SERVER_IP` ở dưới thành địa chỉ IP của Máy Gốc (máy nguồn).
3. Đổi file chạy `.bat` để gọi `python launcher.py` thay vì chạy trực tiếp GUI.
"""

import os
import sys
import json
import requests
import zipfile
import subprocess

# CẤU HÌNH ĐỊA CHỈ MÁY GỐC (Thay đổi địa chỉ IP này bằng IP hiển thị khi chạy build_update.py trên máy gốc)
SERVER_IP = "127.0.0.1"  # Ví dụ: "192.168.1.15"
SERVER_PORT = 8000

SERVER_JSON_URL = f"http://{SERVER_IP}:{SERVER_PORT}/version.json"
VERSION_FILE = "current_version.json"
DEFAULT_VERSION = "2.1"

def get_current_local_version():
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("version", DEFAULT_VERSION)
        except:
            pass
    return DEFAULT_VERSION

def save_local_version(version_str):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": version_str}, f, indent=4)

def check_and_update():
    print("=========================================")
    print(" ĐANG KIỂM TRA BẢN CẬP NHẬT...")
    print(f" Kết nối đến máy gốc: {SERVER_IP}:{SERVER_PORT}")
    print("=========================================")
    
    local_version = get_current_local_version()
    print(f"Phiên bản hiện tại trên máy con: {local_version}")
    
    try:
        # Tải thông tin phiên bản từ máy gốc
        response = requests.get(SERVER_JSON_URL, timeout=5)
        if response.status_code != 200:
            print("⚠️ Không thể kết nối tới máy gốc (Có thể máy gốc chưa bật Server hoặc khác mạng LAN).")
            print("-> Tiếp tục mở Tool mà không cập nhật.")
            return
        
        server_data = response.json()
        server_version = server_data.get("version")
        download_url = server_data.get("download_url")
        changelog = server_data.get("changelog", "Không có mô tả.")
        
        # So sánh phiên bản
        try:
            need_update = float(server_version) > float(local_version)
        except ValueError:
            need_update = server_version != local_version
            
        if need_update:
            print(f"\n🚀 PHÁT HIỆN BẢN CẬP NHẬT MỚI: {server_version}")
            print(f"Nội dung cập nhật: {changelog}")
            print("Đang tải file cập nhật (update.zip)...")
            
            # Tải file zip cập nhật
            zip_resp = requests.get(download_url, stream=True, timeout=10)
            zip_path = "update_temp.zip"
            with open(zip_path, "wb") as f:
                for chunk in zip_resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print("Đang giải nén và cập nhật tệp tin...")
            # Giải nén đè mã nguồn mới (ngoại trừ database.json và system.db để giữ dữ liệu của máy con)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    # Bảo vệ dữ liệu cục bộ của máy con
                    if file_info.filename in ["database.json", "system.db", "current_version.json"]:
                        continue
                    zip_ref.extract(file_info, ".")
            
            # Xóa file nén tạm
            os.remove(zip_path)
            # Ghi lại version mới cập nhật
            save_local_version(server_version)
            print("🎉 CẬP NHẬT HOÀN TẤT THÀNH CÔNG!")
            print("=========================================\n")
        else:
            print("✓ Bạn đang chạy phiên bản mới nhất từ máy gốc.")
            print("=========================================\n")
            
    except Exception as e:
        print(f"⚠️ Lỗi trong quá trình cập nhật: {e}")
        print("-> Tiếp tục khởi chạy Tool.")

if __name__ == "__main__":
    # 1. Chạy cập nhật
    check_and_update()
    
    # 2. Mở giao diện chính của Tool
    print("Đang khởi chạy ứng dụng...")
    try:
        if os.path.exists("Chay_Khong_CMD.pyw"):
            subprocess.Popen([sys.executable, "Chay_Khong_CMD.pyw"])
        else:
            subprocess.Popen([sys.executable, "gui.py"])
    except Exception as e:
        print(f"Lỗi khởi chạy GUI: {e}")
        input("Nhấn Enter để thoát.")
