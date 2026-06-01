# -*- coding: utf-8 -*-
"""
launcher_git.py - Trình khởi chạy tự động cập nhật qua Git
==========================================================
Chạy file này trên các máy con để tự động đồng bộ code từ kho lưu trữ Git (GitHub).
"""

import sys
import os
import subprocess

# CẤU HÌNH ĐƯỜNG DẪN GIT CẬP NHẬT CỐ ĐỊNH
GIT_REPO_URL = "https://github.com/congtygiaan2022-crypto/AutoDangbaifanpage-comment.git"

def run_git_pull():
    print("=========================================")
    print(" ĐANG ĐỒNG BỘ CẬP NHẬT QUA GIT...")
    print("=========================================")
    
    # Tự động khởi tạo Git và liên kết Repo nếu chạy lần đầu trên máy mới tinh
    if not os.path.exists(".git"):
        print("📁 Phát hiện cài đặt mới tinh. Đang tự động kết nối đến kho Git...")
        try:
            # Khởi tạo git cục bộ
            subprocess.run(["git", "init"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Liên kết với remote origin
            subprocess.run(["git", "remote", "add", "origin", GIT_REPO_URL], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✓ Khởi tạo Git và liên kết Repository thành công.")
        except FileNotFoundError:
            print("❌ Lỗi: Máy tính này chưa được cài đặt phần mềm Git.")
            print("-> Tải Git tại: https://git-scm.com/")
            print("=========================================\n")
            return
        except Exception as e:
            print(f"⚠️ Lỗi khởi tạo Git: {e}")
            print("=========================================\n")
            return
        
    try:
        # Luôn đảm bảo remote origin trỏ đúng URL cấu hình
        subprocess.run(["git", "remote", "set-url", "origin", GIT_REPO_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        # Chạy lệnh git pull để đồng bộ code mới nhất
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=25
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if "Already up to date" in output:
                print("✓ Bạn đang chạy phiên bản mới nhất từ Git.")
            else:
                print("🚀 ĐÃ CẬP NHẬT PHIÊN BẢN MỚI THÀNH CÔNG!")
                print(output)
        else:
            # Nếu có lỗi khi pull (ví dụ conflict), thử reset remote để đè code sạch về
            print("⚠️ Phát hiện xung đột hoặc lỗi đồng bộ. Đang tự động làm sạch và đồng bộ lại...")
            subprocess.run(["git", "fetch", "--all"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "reset", "--hard", "origin/main"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✓ Đã đồng bộ thành công phiên bản sạch từ Git (Đè các thay đổi cục bộ).")
            
    except subprocess.TimeoutExpired:
        print("⚠️ Hết thời gian chờ kết nối (Timeout). Bỏ qua cập nhật.")
    except FileNotFoundError:
        print("❌ Lỗi: Máy tính này chưa được cài đặt phần mềm Git.")
        print("-> Tải Git tại: https://git-scm.com/")
    except Exception as e:
        print(f"⚠️ Không thể cập nhật: {e}")
        
    print("=========================================\n")

if __name__ == "__main__":
    # 1. Chạy cập nhật qua Git
    run_git_pull()
    
    # 2. Khởi chạy giao diện chính của Tool
    print("Đang khởi chạy ứng dụng...")
    try:
        if os.path.exists("Chay_Khong_CMD.pyw"):
            # Chạy nền không hiện CMD phụ
            subprocess.Popen([sys.executable, "Chay_Khong_CMD.pyw"])
        elif os.path.exists("gui.py"):
            subprocess.Popen([sys.executable, "gui.py"])
        else:
            print("❌ Không tìm thấy file chạy ứng dụng (gui.py hoặc Chay_Khong_CMD.pyw).")
            print("Vui lòng kiểm tra lại quá trình Git Pull tải code.")
            input("Nhấn Enter để thoát.")
    except Exception as e:
        print(f"Lỗi khởi chạy GUI: {e}")
        input("Nhấn Enter để thoát.")
