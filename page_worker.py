# -*- coding: utf-8 -*-
"""
page_worker.py - Per-profile CMD subprocess worker
===================================================
Called by gui.py to run all work tasks for ONE browser profile.
Each instance runs in its own CMD window for full isolation.

Usage: python page_worker.py <job_json_file>

job_json_file: path to a temp JSON file containing:
{
    "run_mode": "post_and_comment",
    "skip_commented": true,
    "auto_delete": true,
    "browser_config": {...},
    "profile_id": "3",
    "pages": [
        {
            "name": "Fanpage A",
            "link": "https://...",
            "folders": [...],
            "unposted_files": [["folderA", "video1.mp4"], ...]
        },
        ...
    ]
}
"""

import sys
import os
import json
import time

# Force Python to use UTF-8 for all I/O
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Ensure tool directory is in path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

# ── Timestamp stdout wrapper ────────────────────────────────────────────────
# Wraps EVERY print() (including from facebook_automator.py) with [HH:MM:SS]
class _TimestampWriter:
    def __init__(self, stream):
        self._stream = stream
        self._at_line_start = True

    def write(self, text):
        if not text:
            return
        parts = text.split('\n')
        out = []
        for i, part in enumerate(parts):
            if i < len(parts) - 1:          # not the last fragment
                if self._at_line_start and part:
                    out.append(f"[{time.strftime('%H:%M:%S')}] {part}\n")
                elif part:
                    out.append(part + '\n')
                else:
                    out.append('\n')
                self._at_line_start = True
            else:                            # last (possibly empty) fragment
                if part:
                    if self._at_line_start:
                        out.append(f"[{time.strftime('%H:%M:%S')}] {part}")
                    else:
                        out.append(part)
                    self._at_line_start = False
        self._stream.write(''.join(out))
        self._stream.flush()

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except: pass

sys.stdout = _TimestampWriter(sys.stdout)
sys.stderr = _TimestampWriter(sys.stderr)
# ────────────────────────────────────────────────────────────────────────────

from database import Database
from gemlogin_api import GemLoginAPI
from gpmlogin_api import GPMLoginAPI
from facebook_automator import FacebookAutomator, PageAccessDeniedException

def log(msg):
    # TimestampWriter adds [HH:MM:SS] prefix automatically to every print()
    print(msg, flush=True)

def is_browser_disconnected_exception(e):
    err_str = str(e).lower()
    indicators = [
        "connection refused", 
        "connectionrefusederror", 
        "max retries exceeded", 
        "invalid session id", 
        "chrome not reachable",
        "target window already closed",
        "no such window",
        "disconnected",
        "active refused",
        "10061"
    ]
    return any(ind in err_str for ind in indicators)

def run_worker(job_path):
    # Load job manifest
    with open(job_path, 'r', encoding='utf-8') as f:
        job = json.load(f)

    run_mode = job['run_mode']
    skip_commented = job.get('skip_commented', True)
    auto_delete = job.get('auto_delete', False)
    b_config = job['browser_config']
    p_id = str(job['profile_id'])
    pages = job['pages']
    profile_label = job.get('profile_label', f'Profile {p_id}')
    shopee_mode = job.get('shopee_mode', False)

    db_file = job.get('db_file', 'database.json')
    sqlite_file = job.get('sqlite_file', 'system.db')

    # Dynamically configure SQLite file path for the active profile
    from db_helper import db as sqlite_db
    sqlite_db.db_path = sqlite_file
    try:
        from init_db import init_db
        init_db(sqlite_file)
    except: pass

    db = Database(db_file)

    log(f"[Worker:{profile_label}] Bắt đầu xử lý {len(pages)} Fanpage.")

    # Determine browser API
    if b_config['type'] == 'gemlogin':
        api = GemLoginAPI(b_config['api_url'])
    else:
        api = GPMLoginAPI(b_config['api_url'])

    # --- Open browser ONCE for all pages ---
    launch_data = api.start_profile(p_id)
    if not launch_data or not launch_data.get('success'):
        log(f"[Worker:{profile_label}] Khởi động lỗi, thử force-close...")
        try:
            api.stop_profile(p_id)
            time.sleep(2)
        except: pass
        launch_data = api.start_profile(p_id)

    if not launch_data or not launch_data.get('success'):
        log(f"[Worker:{profile_label}] LỖI: Không thể mở profile {p_id}. Thoát.")
        return

    try:
        data_content = launch_data.get('data', {}) if isinstance(launch_data.get('data'), dict) else {}
        debugger_address = data_content.get('remote_debugging_address') or data_content.get('debugger_address')
        driver_path = data_content.get('driver_path')

        strats = db.get_comment_strategies()
        automator = FacebookAutomator(debugger_address, driver_path, strats)
        log(f"[Worker:{profile_label}] Đã kết nối trình duyệt.")

        # --- Process each page sequentially ---
        total_pages = len(pages)
        for idx, page in enumerate(pages, 1):
            page_name = page.get('name', 'Page_Không_Tên')
            stt = f"[{idx}/{total_pages}]"
            unposted_files = page.get('unposted_files', [])  # list of [folder, filename]
            to_comment_historic = page.get('to_comment_historic', [])

            if not unposted_files and not to_comment_historic:
                log(f"[Worker:{profile_label}] {stt} [{page_name}] Bỏ qua (Không có việc cần làm)")
                continue

            log(f"[Worker:{profile_label}] {stt} [{page_name}] Bắt đầu...")

            # Per-page shopee assignment map: {video_filename: {stt, name, url}}
            shopee_assignment = page.get('shopee_assignment', {})

            page_success = False
            page_attempts = 0
            max_page_attempts = 2

            while page_attempts < max_page_attempts and not page_success:
                page_attempts += 1
                try:
                    # Check if browser is alive. If not, try to restart and reconnect.
                    driver_alive = False
                    try:
                        if automator and automator.driver:
                            _ = automator.driver.current_url
                            driver_alive = True
                    except Exception:
                        pass

                    if not driver_alive:
                        log(f"[Worker:{profile_label}] [{page_name}] Trình duyệt mất kết nối. Đang khởi động lại (Lần thử {page_attempts}/{max_page_attempts})...")
                        try:
                            automator.close()
                        except: pass
                        try:
                            api.stop_profile(p_id)
                            time.sleep(3)
                        except: pass

                        launch_data = api.start_profile(p_id)
                        if not launch_data or not launch_data.get('success'):
                            log(f"[Worker:{profile_label}] Khởi động lại lỗi, thử force-close...")
                            try:
                                api.stop_profile(p_id)
                                time.sleep(2)
                            except: pass
                            launch_data = api.start_profile(p_id)

                        if launch_data and launch_data.get('success'):
                            data_content = launch_data.get('data', {}) if isinstance(launch_data.get('data'), dict) else {}
                            debugger_address = data_content.get('remote_debugging_address') or data_content.get('debugger_address')
                            driver_path = data_content.get('driver_path')
                            automator = FacebookAutomator(debugger_address, driver_path, strats)
                            log(f"[Worker:{profile_label}] Tái kết nối trình duyệt thành công.")
                        else:
                            raise Exception("Không thể khởi động lại trình duyệt.")

                    min_v = db.get_global_video_limits()[0]
                    max_v = db.get_global_video_limits()[1]
                    if min_v > max_v: min_v = max_v
                    
                    import random
                    num_to_run = random.randint(min_v, max_v)
                    log(f"[Worker:{profile_label}] [{page_name}] Giới hạn phiên này: {num_to_run} video (Random từ {min_v}-{max_v})")
                    
                    # Check recent logs from database to avoid posting duplicate videos
                    try:
                        recent_logs = db.get_logs(page['link']) or []
                        posted_set = {l.get('video') for l in recent_logs if l.get('status') in ('Success', 'Uploaded', 'Uploaded (No Comment)')}
                    except Exception:
                        posted_set = set()

                    # Create local copies of file lists to avoid mutating original lists across retries
                    # and filter out any files that do not exist anymore or are already posted
                    local_unposted = []
                    for folder, vf in unposted_files:
                        video_path = os.path.join(folder, vf)
                        if os.path.exists(video_path) and vf not in posted_set:
                            local_unposted.append([folder, vf])

                    local_comment_historic = list(to_comment_historic)

                    # Limit unposted_files
                    if local_unposted and len(local_unposted) > num_to_run:
                        random.shuffle(local_unposted)
                        local_unposted = local_unposted[:num_to_run]
                        log(f"[Worker:{profile_label}] [{page_name}] Đã giới hạn số bài đăng mới còn {len(local_unposted)} bài.")
                    
                    # Limit historical comments and filter out already commented
                    if local_comment_historic:
                        local_comment_historic = [v for v in local_comment_historic if not db.has_commented(page['link'], v)]
                        if len(local_comment_historic) > num_to_run:
                            random.shuffle(local_comment_historic)
                            local_comment_historic = local_comment_historic[:num_to_run]
                            log(f"[Worker:{profile_label}] [{page_name}] Đã giới hạn số bài comment cũ còn {len(local_comment_historic)} bài.")

                    uploaded_videos = []

                    # Upload new videos
                    if local_unposted and run_mode in ('post_and_comment', 'post_only'):
                        log(f"[Worker:{profile_label}] [{page_name}] Đăng {len(local_unposted)} video mới.")
                        asset_id = automator.resolve_asset_id(page['link'])
                        if not asset_id:
                            raise Exception("Không resolve được asset_id.")

                        batch_to_post = []
                        for folder, vf in local_unposted:
                            video_path = os.path.join(folder, vf)
                            title = os.path.splitext(vf)[0]
                            # Shopee mode: append product name to title
                            if shopee_mode and vf in shopee_assignment:
                                prod = shopee_assignment[vf]
                                log(f"[Worker:{profile_label}] [{page_name}] [Shopee] Chọn sản phẩm số {prod['stt']}: {prod['name']}")
                                title = title + " - " + prod['name']
                            batch_to_post.append((video_path, title))

                        # Upload in batches
                        batch_size = max(1, min(max_v, 10))
                        for chunk_start in range(0, len(batch_to_post), batch_size):
                            chunk = batch_to_post[chunk_start: chunk_start + batch_size]
                            result = automator.upload_reels_bulk(asset_id, chunk, upload_url=page.get('link'))
                            log(f"[Worker:{profile_label}] [{page_name}] Upload: {result}")

                            # Track successfully uploaded files
                            is_upload_success = result in ("Uploaded Bulk", "Done_Button_Not_Found")
                            if is_upload_success:
                                for video_path, title in chunk:
                                    for folder, vf in local_unposted:
                                        if os.path.join(folder, vf) == video_path:
                                            uploaded_videos.append((folder, vf))
                                            break

                            for video_path, title in chunk:
                                vf_name = os.path.basename(video_path)
                                
                                # Special handling for Done button failure (Requirement 2)
                                if result == "Done_Button_Not_Found":
                                    try:
                                        with open("loi_done.txt", "a", encoding="utf-8") as f:
                                            now = time.strftime('%Y-%m-%d %H:%M:%S')
                                            f.write(f"[{now}] Page: {page_name} | File: {vf_name} | Lỗi: Không tìm thấy nút Done sau 10 lần check\n")
                                        
                                        if os.path.exists(video_path):
                                            os.remove(video_path)
                                            log(f"[Worker:{profile_label}] [{page_name}] ⚠️ Đã xóa file do lỗi nút Done: {vf_name}")
                                    except Exception as log_e:
                                        log(f"[Worker:{profile_label}] Lỗi khi ghi log lỗi Done: {log_e}")

                                db.log_upload(page['link'], vf_name, 'Uploaded')
                                if auto_delete and os.path.exists(video_path):
                                    try:
                                        os.remove(video_path)
                                        log(f"[Worker:{profile_label}] [{page_name}] ✓ Đã xóa video: {vf_name}")
                                    except Exception as del_e:
                                        log(f"[Worker:{profile_label}] [{page_name}] Lỗi xóa video: {del_e}")

                        if run_mode == 'post_and_comment' and uploaded_videos:
                            for folder, vf in uploaded_videos:
                                time.sleep(10)
                                title = os.path.splitext(vf)[0]
                                # Determine comment text: Shopee URL or template
                                if shopee_mode and vf in shopee_assignment:
                                    prod = shopee_assignment[vf]
                                    comment_text = prod['url']
                                    log(f"[Worker:{profile_label}] [{page_name}] [Shopee] Comment link sản phẩm #{prod['stt']}: {comment_text}")
                                else:
                                    comment_text = db.get_effective_comment_template(page['link'])
                                
                                if comment_text.strip():
                                    ok, link = automator.comment_with_dual_strategy(asset_id, title, comment_text)
                                    if ok:
                                        db.add_comment_history(page['link'], vf, link or '')
                                        log(f"[Worker:{profile_label}] [{page_name}] Comment thành công: {vf}")
                                else:
                                    log(f"[Worker:{profile_label}] [{page_name}] Mẫu bình luận rỗng. Bỏ qua comment bài viết mới.")

                    # Handle historical comments (comment_only mode)
                    if local_comment_historic and run_mode == 'comment_only':
                        log(f"[Worker:{profile_label}] [{page_name}] Comment {len(local_comment_historic)} bài cũ.")
                        asset_id = automator.resolve_asset_id(page['link'])
                        if not asset_id:
                            raise Exception("Không resolve được asset_id.")
                        comment_template = db.get_effective_comment_template(page['link'])
                        if comment_template.strip():
                            for v_name in local_comment_historic:
                                title = os.path.splitext(v_name)[0]
                                ok, link = automator.comment_with_dual_strategy(asset_id, title, comment_template)
                                if ok:
                                    db.add_comment_history(page['link'], v_name, link or '')
                                    log(f"[Worker:{profile_label}] [{page_name}] Comment lịch sử thành công: {v_name}")
                        else:
                            log(f"[Worker:{profile_label}] [{page_name}] Mẫu bình luận rỗng. Bỏ qua comment bài viết cũ.")

                    page_success = True

                except PageAccessDeniedException as access_e:
                    log(f"[Worker:{profile_label}] {stt} [{page_name}] ⚠️ BỎ QUA PAGE: {access_e}")
                    page_success = True
                    break
                except Exception as page_e:
                    is_disconnect = is_browser_disconnected_exception(page_e)
                    if is_disconnect and page_attempts < max_page_attempts:
                        log(f"[Worker:{profile_label}] {stt} [{page_name}] LỖI mất kết nối trình duyệt (Thử lần {page_attempts}/{max_page_attempts}): {page_e}")
                        try: automator.close()
                        except: pass
                        try: api.stop_profile(p_id)
                        except: pass
                        automator = None
                        time.sleep(5)
                    else:
                        log(f"[Worker:{profile_label}] {stt} [{page_name}] LỖI: {page_e}")
                        import traceback
                        traceback.print_exc()
                        if global_logger:
                            global_logger.report_bug("AutoPostFanpage", "page_worker", str(page_e), {"page": page_name, "traceback": traceback.format_exc()})
                        break

        log(f"[Worker:{profile_label}] Hoàn tất tất cả {len(pages)} Fanpage.")

    except Exception as e:
        log(f"[Worker:{profile_label}] LỖI NGHIÊM TRỌNG: {e}")
        import traceback
        traceback.print_exc()
    finally:
        log(f"[Worker:{profile_label}] Đóng trình duyệt profile {p_id}...")
        try:
            api.stop_profile(p_id)
        except: pass
        # Clean up job file
        try:
            os.remove(job_path)
        except: pass
        log(f"[Worker:{profile_label}] ✓ Worker thoát.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python page_worker.py <job_json_file>")
        sys.exit(1)
    
    job_path = sys.argv[1]
    if not os.path.exists(job_path):
        print(f"ERROR: Job file not found: {job_path}")
        sys.exit(1)
    
    run_worker(job_path)
    # CMD window closes automatically — no prompt needed
