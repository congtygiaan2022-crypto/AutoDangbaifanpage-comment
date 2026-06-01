# -*- coding: utf-8 -*-
"""
git_dev_push.py - Công cụ đẩy bản cập nhật sạch lên GitHub (Máy Gốc)
==================================================================
Chạy script này để chỉ đẩy các tệp tin mã nguồn quan trọng của phần mềm lên Git,
loại bỏ toàn bộ dữ liệu cấu hình cá nhân, database, proxy, và logs.
"""

import os
import subprocess
import datetime

# DANH SÁCH CÁC FILE VÀ THƯ MỤC QUAN TRỌNG ĐƯỢC PHÉP ĐẨY LÊN GIT
ALLOWED_FILES = [
    # Các file mã nguồn chạy chính
    "gui.py",
    "page_worker.py",
    "database.py",
    "db_helper.py",
    "init_db.py",
    "facebook_automator.py",
    "gemlogin_api.py",
    "gpmlogin_api.py",
    "requirements.txt",
    
    # Trình chạy cho máy gốc
    "Chay_Chuong_Trinh.bat",
    "Chay_Khong_CMD.pyw",
    
    # Trình cập nhật và cấu hình Git
    "launcher_git.py",
    ".gitignore",
    "Day_Ban_Cap_Nhat_Sach.bat",
    "git_dev_push.py",
    
    # Thư mục cài đặt mồi cho máy con (chứa 5 file mồi sạch)
    "AutoDangBai_User_Setup/Cai_Dat_Thu_Vien.bat",
    "AutoDangBai_User_Setup/Chay_Tool.bat",
    "AutoDangBai_User_Setup/HUONG_DAN_CAI_DAT.txt",
    "AutoDangBai_User_Setup/requirements.txt",
    "AutoDangBai_User_Setup/launcher_git.py"
]

def run_clean_push():
    print("====================================================")
    print("  BAT DAU DONG GOI & DAY ANH CAP NHAT SACH LEN GIT")
    print("====================================================")
    
    if not os.path.exists(".git"):
        print("[LOI] Thu muc hien tai chua duoc khoi tao Git!")
        print("-> Vui long chay 'git init' va ket noi den repository truoc.")
        return
        
    try:
        # 1. Huy theo doi toan bo file trong Git index de reset lai danh sach sach
        print("[+] Buoc 1: Reset Git Index (Khong xoa file cuc bo)...")
        subprocess.run(["git", "rm", "-r", "--cached", "."], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Chi add cac file trong danh sach cho phep
        print("[+] Buoc 2: Them cac file quan trong vao danh sach phat hanh...")
        added_count = 0
        for file_path in ALLOWED_FILES:
            if os.path.exists(file_path):
                # Thay the dau gach cheo nguoc de tuong thich Git
                normalized_path = file_path.replace("\\", "/")
                subprocess.run(["git", "add", normalized_path], check=True)
                print(f"  [OK] Da them: {file_path}")
                added_count += 1
            else:
                print(f"  [CANH BAO] Khong tim thay: {file_path}")
                
        if added_count == 0:
            print("[LOI] Khong co file nao de day len Git.")
            return
            
        # 3. Tao commit message voi thoi gian hien tai
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        commit_msg = f"Release-Clean-{now_str}"
        print(f"\n[+] Buoc 3: Tao ban ghi commit: '{commit_msg}'...")
        
        # Kiem tra xem co gi thay doi de commit khong
        status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status_res.stdout.strip():
            print("[OK] Khong co thay doi nao so voi phien ban truoc tren Git.")
        else:
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            print("[OK] Tao ban ghi commit thanh cong.")
            
        # 4. Day code len Github
        print("\n[+] Buoc 4: Dang day phien ban sach len Github origin main...")
        result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("\n====================================================")
            print("  DA PHAT HANH PHIEN BAN SACH LEN GITHUB THANH CONG!")
            print("  Khach hang chi can chay Chay_Tool.bat la tu dong nhan.")
            print("====================================================")
        else:
            print("\n[LOI] KHI DAY LEN GITHUB:")
            print(result.stderr)
            
    except Exception as e:
        print(f"\n[LOI] Da xay ra loi trong qua trinh day code: {e}")

if __name__ == "__main__":
    run_clean_push()
    print("\nNhan Enter de thoat.")
    input()
