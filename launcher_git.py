# -*- coding: utf-8 -*-
"""
launcher_git.py - Trình khởi chạy tự động cập nhật qua Git
==========================================================
Chạy file này trên các máy con để tự động đồng bộ code từ kho lưu trữ Git (GitHub/GitLab).
"""

import sys
import os
import subprocess

# CẤU HÌNH ĐƯỜNG DẪN GIT CẬP NHẬT CỐ ĐỊNH (Thay bằng link Git/GitHub của bạn)
GIT_REPO_URL = "https://github.com/congtygiaan2022-crypto/AutoDangbaifanpage-comment.git"

def run_git_pull():
    print("=========================================")
    print(" ĐANG ĐỒNG BỘ CẬP NHẬT QUA GIT...")
    print("=========================================")
    
    # Tự động khởi tạo Git và liên kết Repo nếu chạy lần đầu trên máy mới tinh
    if not os.path.exists(".git"):
        print("📁 Phát hiện cài đặt mới tinh. Đang tự động kết nối đến kho Git...")
        if GIT_REPO_URL == "https://github.com/congtygiaan2022-crypto/AutoDangbaifanpage-comment.git":
            print("⚠️ Cảnh báo: Bạn chưa cấu hình GIT_REPO_URL cố định trong launcher_git.py!")
            print("-> Vui lòng mở file launcher_git.py và sửa lại link Git của bạn.")
            print("=========================================\n")
            return
            
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
        # Cập nhật/ghi đè URL remote origin cố định để tránh sai sót cấu hình
        if GIT_REPO_URL != "https://github.com/congtygiaan2022-crypto/AutoDangbaifanpage-comment.git":
            subprocess.run(["git", "remote", "set-url", "origin", GIT_REPO_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        # Chạy lệnh git pull để đồng bộ code mới nhất
        result = subprocess.run(
            ["git", "pull", "origin", "main"], # Đổi "main" thành branch của bạn nếu cần
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
            print("⚠️ Lỗi đồng bộ Git:")
            print(result.stderr)
            
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
            subprocess.Popen([sys.executable, "Chay_Khong_CMD.pyw"])
        else:
            subprocess.Popen([sys.executable, "gui.py"])
    except Exception as e:
        print(f"Lỗi khởi chạy GUI: {e}")
        input("Nhấn Enter để thoát.")
