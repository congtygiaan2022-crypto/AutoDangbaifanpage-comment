from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
import re
import random

class FacebookAutomator:
    def __init__(self, debugger_address, driver_path=None, strategies=None):
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)
        
        self.strategies = strategies or {}
        
        try:
            if driver_path and os.path.exists(driver_path):
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            
            # Set timeouts to prevent hanging
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(60)
            self.driver.implicitly_wait(2)

            # Close other tabs to prevent tab confusion and save memory
            try:
                handles = self.driver.window_handles
                if len(handles) > 1:
                    current_handle = self.driver.current_window_handle
                    for h in handles:
                        if h != current_handle:
                            try:
                                self.driver.switch_to.window(h)
                                self.driver.close()
                            except: pass
                    self.driver.switch_to.window(current_handle)
            except Exception as tab_e:
                print(f"Error cleaning up tabs: {tab_e}")
        except Exception as e:
            print(f"Error connecting to browser: {e}")
            raise e

    def resolve_asset_id(self, page_link):
        # Try to find asset_id in URL without navigation first
        asset_id = None
        if "asset_id=" in page_link:
            asset_id = page_link.split("asset_id=")[-1].split("&")[0]
        
        # If it's a direct page ID in URL
        if not asset_id:
            parts = page_link.strip("/").split("/")
            if parts[-1].isdigit():
                asset_id = parts[-1]
            
        # Must navigate to resolve or confirm
        print(f"[Automator] Navigating to resolve IDs: {page_link}")
        self.driver.get(page_link)
        time.sleep(5)
        
        if "asset_id=" in self.driver.current_url:
            asset_id = self.driver.current_url.split("asset_id=")[-1].split("&")[0]
            
        if not asset_id:
            links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'asset_id=')]")
            for l in links:
                href = l.get_attribute("href")
                if "asset_id=" in href:
                    asset_id = href.split("asset_id=")[-1].split("&")[0]
                    break
                
        if not asset_id:
            import re
            match = re.search(r'"actorID":"(\d+)"', self.driver.page_source)
            if match: asset_id = match.group(1)
            
        # Also resolve business_id while we are here
        self.business_id = "1016985112612772" # Hardcoded fallback from logs
        if "business_id=" in self.driver.current_url:
            self.business_id = self.driver.current_url.split("business_id=")[-1].split("&")[0]
        else:
             import re
             match_biz = re.search(r'"businessID":"(\d+)"', self.driver.page_source)
             if match_biz: self.business_id = match_biz.group(1)

        return asset_id

    def upload_reel_by_link(self, page_link, video_path, title, scrape_name=False):
        asset_id = self.resolve_asset_id(page_link)
        if not asset_id:
            raise Exception("Could not find Asset ID for this page link.")

        # Luôn dùng Phương án Bulk (Phương án chính hiện tại)
        # Nếu là string đơn lẻ, bọc lại thành list để Bulk xử lý đồng nhất
        batch = video_path if isinstance(video_path, list) else [(video_path, title)]
        return self.upload_reels_bulk(asset_id, batch)

    def log(self, msg):
        print(f"[Automator] {msg}")

    def set_timeout(self):
        try:
            self.driver.set_page_load_timeout(300)
        except:
            pass

    def _wait_for_element(self, xpaths, timeout=15, interval=0.5):
        """Poll DOM until any of the given xpath selectors appears. Returns (True, element) or (False, None)."""
        if isinstance(xpaths, str):
            xpaths = [xpaths]
        start = time.time()
        self.driver.implicitly_wait(0)
        try:
            while time.time() - start < timeout:
                for xp in xpaths:
                    try:
                        els = self.driver.find_elements(By.XPATH, xp)
                        if els and els[0].is_displayed():
                            return True, els[0]
                    except: pass
                time.sleep(interval)
        finally:
            self.driver.implicitly_wait(2)
        return False, None

    def _wait_for_text_in_page(self, keywords, timeout=30, interval=0.5):
        """Poll page source until any keyword appears. Returns True immediately when found."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                src = self.driver.page_source.lower()
                if any(k.lower() in src for k in keywords):
                    return True
            except: pass
            time.sleep(interval)
        return False


    def upload_reels_bulk(self, asset_id, batch_list):
        """
        batch_list: List of (video_path, title)
        """
        self.set_timeout()
        upload_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={asset_id}"
        
        # 0. Skip redundant navigation if already there
        if upload_url.lower() not in self.driver.current_url.lower():
            self.log(f"[BULK] Navigating to: {upload_url}")
            self._safe_get(upload_url)
        else:
            self.log(f"[BULK] Already at composer URL: {upload_url}. Skipping reload.")

        # Handle "Select Page" or "Get Started" screen if needed
        self._dismiss_tooltips()
        
        # Event-driven: wait for page to show the upload UI (Add videos button or file input)
        # Increased timeout to 30s for slow profiles
        ready, _ = self._wait_for_element([
            "//div[@role='button'][contains(., 'Add videos') or contains(., 'Thêm video')]",
            "//div[@role='button'][contains(., 'Select Page') or contains(., 'Chọn trang')]",
            "//input[@type='file']"
        ], timeout=30)
        
        if not ready:
            self.log("[BULK] Warning: Upload page did not load expected UI in 30s, proceeding anyway.")
        
        # 1. Tìm input và tải video lên
        paths = [os.path.abspath(v[0]) for v in batch_list]
        
        try:
            # 1. Tìm input file (Chạy trực tiếp thay vì bấm nút gây popup hệ thống)
            input_file = None
            for attempt in range(2): # 1st: current context, 2nd: frames
                inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                self.log(f"[BULK] Found {len(inputs)} file inputs in context (Attempt {attempt+1}).")
                
                for inp in inputs:
                    mult = inp.get_attribute("multiple") or ""
                    acc = (inp.get_attribute("accept") or "").lower()
                    if mult == "true" or "video" in acc or acc == "" or acc == "*":
                        input_file = inp
                        break
                
                if input_file: break
                
                if attempt == 0:
                    self.log("[BULK] Input not found in main context, searching in iframes...")
                    if self._switch_to_composer_frame_recursive():
                        continue 
                    else:
                        self.driver.switch_to.default_content()
            
            # 2. Fallback: Nếu vẫn không thấy, thử bấm nút "Thêm video" để kích hoạt injection
            if not input_file:
                self.log("[BULK] Input not found after frame search. Trying to click 'Add videos' button...")
                btn_selectors = [
                    "//div[@role='button'][contains(., 'Add videos') or contains(., 'Thêm video')]",
                    "//div[@role='button'][descendant::span[contains(text(), 'Add videos') or contains(text(), 'Thêm video')]]",
                    "//div[@role='button'][@aria-label='Add videos' or @aria-label='Thêm video']",
                    "//div[contains(text(), 'Add videos') or contains(text(), 'Thêm video')]/ancestor::div[@role='button']"
                ]
                found_btn = False
                for sel in btn_selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, sel)
                        for b in btns:
                            if b.is_displayed():
                                self.log(f"[BULK] Found 'Add videos' button via {sel}. Clicking...")
                                self.driver.execute_script("arguments[0].click();", b)
                                time.sleep(5)
                                found_btn = True
                                break
                        if found_btn: break
                    except: continue
                
                if found_btn:
                    # Re-search after click (check main + frames again)
                    self.driver.switch_to.default_content()
                    for attempt in range(2):
                        inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                        for inp in inputs:
                            mult = inp.get_attribute("multiple") or ""
                            acc = (inp.get_attribute("accept") or "").lower()
                            if mult == "true" or "video" in acc or acc == "" or acc == "*":
                                input_file = inp
                                break
                        if input_file: break
                        if attempt == 0: self._switch_to_composer_frame_recursive()

            if not input_file:
                # Capture a screenshot or log more DOM info here if needed
                self.log("[BULK] CRITICAL: No file input found after clicking button and frame search.")
                raise Exception("Không tìm thấy input file ngay cả sau khi bấm nút và tìm trong iframe.")

            # 3. Gửi file
            text_paths = "\n".join(paths)
            
            # Ép hiện ổn định trước khi send_keys
            self.driver.execute_script("""
                arguments[0].style.display = 'block'; 
                arguments[0].style.visibility = 'visible'; 
                arguments[0].style.opacity = '1'; 
                arguments[0].style.position = 'absolute';
                arguments[0].style.top = '0';
                arguments[0].style.left = '0';
                arguments[0].style.width = '100px'; 
                arguments[0].style.height = '100px';
            """, input_file)
            time.sleep(2)
            
            # Reset input
            self.driver.execute_script("arguments[0].value = '';", input_file)
            
            input_file.send_keys(text_paths)
            self.log(f"[BULK] Sent {len(paths)} files to input.")
            
            # 4. Kích hoạt React bằng chuỗi sự kiện mở rộng
            js_script = """
            var input = arguments[0];
            var files = input.files;
            if (files.length > 0) {
                // Thứ tự sự kiện quan trọng cho React
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                
                // Giả lập thêm sự kiện drop vào vùng chứa cha
                var dropzone = input.parentElement;
                while (dropzone && !dropzone.innerText.includes('Add videos')) {
                    dropzone = dropzone.parentElement;
                }
                dropzone = dropzone || input.parentElement;

                var dataTransfer = new DataTransfer();
                for(var i=0; i<files.length; i++) { dataTransfer.items.add(files[i]); }
                
                var dropEvent = new DragEvent('drop', {
                    bubbles: true,
                    dataTransfer: dataTransfer
                });
                dropzone.dispatchEvent(dropEvent);
            }
            """
            self.driver.execute_script(js_script, input_file)

        except Exception as e:
            self.log(f"[BULK] Error in injection chain: {e}")
            raise e

        # 2. Đợi load xong mẻ video (Event-driven: ngay khi ô nhập liệu hoặc row xuất hiện)
        self.log(f"[BULK] Waiting for processing (max 60s)...")
        start_t = time.time()
        upload_started = False
        while time.time() - start_t < 60:
            # Check xem còn chữ "Upload up to 50 videos" không
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Upload up to 50 videos" not in body_text and "Thumbnail" in body_text:
                upload_started = True
                self.log("[BULK] Video list detected.")
                break  # Proceed immediately — no extra sleep
            
            # Check xem có ô textbox nào hiện ra chưa
            boxes = self.driver.find_elements(By.XPATH, "//div[@role='textbox'] | //textarea")
            if any(b.is_displayed() for b in boxes):
                upload_started = True
                self.log("[BULK] Metadata boxes appeared.")
                break  # Proceed immediately
            
            time.sleep(0.5)  # Poll every 0.5s instead of 3s

        
        if not upload_started:
            self.log("[BULK] Warning: Timeout waiting for video list. Proceeding anyway...")
        
        # 3. Điền Title cho từng video
        self.log(f"[BULK] Filling titles for each video...")
        
        # Thử tìm các ô nhập liệu bằng nhiều cách (localized placeholders/labels)
        for i, (video_path, title) in enumerate(batch_list):
            try:
                # Meta thường dùng "Description" hoặc "Mô tả"
                # Ta tìm textbox dựa trên thứ tự xuất hiện hoặc nhãn
                selectors = [
                    f"(//div[@role='textbox' or @role='textarea' or @contenteditable='true'])[{i+1}]",
                    f"(//textarea)[{i+1}]",
                    f"//div[contains(@aria-label, 'Description') or contains(@aria-label, 'Mô tả')][{i+1}]",
                    f"//textarea[contains(@placeholder, 'Description') or contains(@placeholder, 'Mô tả')][{i+1}]"
                ]
                
                target_box = None
                for sel in selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, sel)
                        if elements and elements[0].is_displayed():
                            target_box = elements[0]
                            break
                    except: continue
                
                if target_box:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_box)
                    time.sleep(1)
                    target_box.click()
                    time.sleep(0.5)
                    # Sử dụng thuật toán làm sạch tiêu đề (xóa hashtag...)
                    clean_title = self._get_clean_title(title)
                    target_box.send_keys(clean_title)
                    self.log(f"[BULK] Filled title for video #{i+1}: {clean_title}")
                else:
                    self.log(f"[BULK] Warning: Could not find box for video #{i+1} using multiple selectors.")
                    try:
                        snipped_text = self.driver.find_element(By.TAG_NAME, "body").text[:200].replace('\n', ' ')
                        self.log(f"[BULK] Debug UI Text: {snipped_text}")
                    except: pass
            except Exception as e:
                self.log(f"[BULK] Error filling title for video #{i+1}: {e}")

        # 4. Sequence Next/Publish
        # Bulk upload thường cần 1-2 lần bấm Tiếp và 1 lần Đăng
        for step in range(4):
            self.log(f"[BULK] Next Sequence step {step+1}...")
            # Event-driven: wait for footer button to appear (no fixed sleep before search)
            self._wait_for_element([
                "//div[@role='button'][contains(., 'Next') or contains(., 'Tiếp') or contains(., 'Publish') or contains(., 'Đăng') or contains(., 'Share')]"
            ], timeout=5)
            self._dismiss_tooltips()
            
            clicked = False
            # Lấy thông tin viewport để lọc nút chân trang (Footer)
            # Theo nghiên cứu DOM, nút Next/Publish thật nằm ở 15% dưới cùng và 30% bên phải
            v_height = self.driver.execute_script("return window.innerHeight;")
            v_width = self.driver.execute_script("return window.innerWidth;")
            footer_y_threshold = v_height * 0.85 
            footer_x_threshold = v_width * 0.65
            
            buttons = self.driver.find_elements(By.XPATH, "//div[@role='button']")
            best_button = None
            priority_texts = ["tiếp", "next", "đăng", "publish", "share", "chia sẻ"]

            # 1. Tìm theo text + tọa độ FOOTER (Rất quan trọng để tránh decoy)
            for p_text in priority_texts:
                for b in buttons:
                    try:
                        if b.is_displayed() and b.is_enabled():
                            loc = b.location
                            # Chỉ xét các nút nằm ở khu vực Footer bên phải
                            if loc['y'] > footer_y_threshold and loc['x'] > footer_x_threshold:
                                t = b.text.lower()
                                if p_text in t and not any(w in t for w in ["hủy", "cancel", "back", "quay lại"]):
                                    best_button = b
                                    break
                    except: continue
                if best_button: break
            
            # 2. Fallback: Nếu không tìm thấy theo text ở footer, lấy nút "nằm xa nhất về phía dưới bên phải"
            if not best_button:
                max_score = 0
                for b in buttons:
                    try:
                        if b.is_displayed():
                            loc = b.location
                            if loc['y'] > footer_y_threshold:
                                score = loc['x'] + loc['y']
                                if score > max_score:
                                    max_score = score
                                    best_button = b
                    except: continue

            if best_button:
                btn_text = best_button.text or "Unknown"
                self.log(f"[BULK] Clicking button: {btn_text}")
                self.driver.execute_script("arguments[0].click();", best_button)
                clicked = True
            
            if not clicked:
                self.log("[BULK] No clickable button found in sequence.")
                break
                
            # Check thành công bằng text hoặc URL hoặc biến mất của composer
            page_text = self.driver.page_source.lower()
            current_url = self.driver.current_url.lower()
            
            # Nếu đã quay về trang home hoặc content, coi như xong
            if "bulk_upload_composer" not in current_url:
                self.log("[BULK] Composer URL changed. Assuming success.")
                wait_time = random.randint(5, 15)
                self.log(f"[BULK] Waiting {wait_time}s for stability after publish...")
                time.sleep(wait_time)
                return "Uploaded Bulk"

            success_keywords = [
                "success", "creating your reels", "done", "đã đăng", "hoàn tất", 
                "xong", " reels của bạn đang được tạo", "quản lý tất cả nội dung"
            ]
            if any(k in page_text for k in success_keywords):
                self.log("[BULK] Success message detected. Entering aggressive search for 'Done' button...")
                
                # --- AGGRESSIVE DONE BUTTON SEARCH (5 RETRIES) ---
                done_selectors = [
                    "//div[@role='dialog']//div[@role='button']//span[text()='Done' or text()='Xong' or text()='Hoàn tất']",
                    "//div[@role='dialog']//div[@role='button'][contains(., 'Done') or contains(., 'Xong') or contains(., 'Hoàn tất')]",
                    "//div[@role='button']//span[text()='Done' or text()='Xong' or text()='Hoàn tất']",
                    "//button[contains(., 'Done') or contains(., 'Xong') or contains(., 'Hoàn tất')]",
                    "//div[@aria-label='Done' or @aria-label='Xong' or @aria-label='Hoàn tất']"
                ]
                
                done_clicked = False
                for attempt in range(1, 11):
                    self.log(f"[BULK] Done button search (Attempt {attempt}/10)...")
                    for sel in done_selectors:
                        btns = self.driver.find_elements(By.XPATH, sel)
                        for b in btns:
                            try:
                                if b.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", b)
                                    self.log(f"[BULK] ✓ Clicked 'Done' button via selector: {sel}")
                                    time.sleep(5)
                                    done_clicked = True
                                    break
                            except: continue
                        if done_clicked: break
                    
                    if done_clicked: break
                    time.sleep(4) # Wait between retries
                
                if not done_clicked:
                    self.log("[BULK] Warning: Could not find 'Done' button after 10 attempts. Checking generic closure...")
                    self._close_popups_v2() # Fallback only if specific Done button fails
                    
                    # Requirement: Signal that Done button was missing so caller can log/delete
                    return "Done_Button_Not_Found"
                
                # Event-driven final wait: poll for URL change or dialog disappearance (max 15s)
                self.log(f"[BULK] Waiting for upload to finalize...")
                deadline = time.time() + 15
                while time.time() < deadline:
                    cur_url = self.driver.current_url.lower()
                    if "bulk_upload_composer" not in cur_url:
                        break  # URL changed -> done
                    try:
                        # Check if publish dialog is gone
                        dialogs = self.driver.find_elements(By.XPATH, "//div[@role='dialog']")
                        if not any(d.is_displayed() for d in dialogs):
                            break  # Dialog closed -> done
                    except: pass
                    time.sleep(0.5)
                
                return "Uploaded Bulk"

        self.log("[BULK] Warning: Finished button sequence without confirmed success text.")
        return "Bulk Flow Finished"

    # upload_reel_v2 (Plan 1) đã bị gỡ bỏ theo yêu cầu của User.

    def _dismiss_tooltips(self):
        """ Closes small tooltips/overlays that block logic """
        tooltips = [
            "//div[@role='dialog']//div[@role='button'][contains(., 'Got it') or contains(., 'Đã hiểu')]",
            "//div[contains(@class, 'x1i10hfl')]//div[contains(., 'Done') or contains(., 'Xong')]",
            "//div[@role='button'][@aria-label='Close' or @aria-label='Đóng']",
            "//div[contains(text(), 'You can now add a collaborator')]/following-sibling::div[@role='button']"
        ]
        for ts in tooltips:
            try:
                btns = self.driver.find_elements(By.XPATH, ts)
                for b in btns:
                    if b.is_displayed():
                        print(f"[Automator] [V2] Dismissing tooltip via {ts}")
                        self.driver.execute_script("arguments[0].click();", b)
                        time.sleep(1)
            except: continue

    def _switch_to_composer_frame_recursive(self):
        """ Recursive search for composer marker """
        self.driver.switch_to.default_content()
        return self._search_frames_for_marker()

    def _search_frames_for_marker(self):
        markers = [
            "//input[@type='file']",
            "//div[@role='button'][contains(translate(@aria-label, 'VIDEO', 'video'), 'video')]",
            "//*[contains(text(), 'Add Video') or contains(text(), 'Thêm video')]",
            "//div[@role='textbox']"
        ]
        # Check current
        for m in markers:
            try:
                if self.driver.find_elements(By.XPATH, m):
                    print(f"[Automator] [V2] Context found via {m}")
                    return True
            except: continue
        
        # Check kids
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for i, frame in enumerate(iframes):
            try:
                self.driver.switch_to.frame(frame)
                if self._search_frames_for_marker(): return True
                self.driver.switch_to.parent_frame()
            except:
                try: self.driver.switch_to.parent_frame()
                except: self.driver.switch_to.default_content()
        return False

    def _close_popups_v2(self):
        """ Specialized popup closer for Business Suite Composer """
        try:
            popup_selectors = [
                 "//div[@role='button'][@aria-label='Close' or @aria-label='Đóng' or @aria-label='Dismiss']",
                 "//div[@role='button'][descendant::span[text()='Dismiss' or text()='Bỏ qua' or text()='Maybe later' or text()='Lúc khác']]",
                 "//div[contains(@aria-label, 'Got it')]",
                 "//div[contains(@class, 'x1i10hfl')]//div[@role='button'][.//i]" 
            ]
            for sel in popup_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    if el.is_displayed():
                        print(f"[Automator] [V2] Closing popup: {sel}")
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(1)
        except: pass

    def upload_reel_old(self, asset_id, video_path, title, scrape_name=False):
        """ The original bulk_upload_composer method, kept as Backup 2 """
        if scrape_name:
            page_name = None
            try:
                profile_url = f"https://www.facebook.com/{asset_id}"
                print(f"[Automator] Scrape requested. Navigating to profile: {profile_url}")
                self.driver.get(profile_url)
                time.sleep(5)
                
                # Method 1: Regex Search for "Switch into ... 's Page"
                try:
                    # Search for any element containing the key phrase
                    xpath_switch = "//*[contains(text(), 'Switch into') or contains(text(), 'Chuyển sang')]"
                    elements = self.driver.find_elements(By.XPATH, xpath_switch)
                    
                    found_name = None
                    for el in elements:
                        txt = el.text.strip()
                        # Regex to capture content between "Switch into " and "'s"
                        # English: "Switch into [Tanglike.net 8092...] 's Page"
                        # Vietnamese: "Chuyển sang trang [Tanglike.net 8092...]" ? Or "Chuyển sang [Name]..."
                        # User matched: "Switch into Tanglike.net 809248679251752381748's Page"
                        
                        # English Pattern
                        match_en = re.search(r"Switch into (.*?)'s Page", txt)
                        if match_en:
                            found_name = match_en.group(1).strip()
                            print(f"[Automator] Regex Match (EN): {found_name}")
                            break
                            
                        # Vietnamese Pattern (Approximation based on standard FB translation)
                        # Usually "Chuyển sang trang của [Name]" or "Chuyển sang [Name]"
                        if "Chuyển sang" in txt:
                             # Try to capture reasonable length text after Chuyển sang
                             match_vi = re.search(r"Chuyển sang (.*?)( trang|$)", txt)
                             if match_vi:
                                 found_name = match_vi.group(1).strip()
                                 print(f"[Automator] Regex Match (VI): {found_name}")
                                 break
                    
                    if found_name:
                        page_name = found_name
                        print(f"[Automator] Scraped Name from Regex: {page_name}")
                        
                except Exception as e:
                    print(f"[Automator] Regex search failed: {e}")

                # Method 2: H1 Tag (Visible name)
                if not page_name:
                    try:
                        h1_el = self.driver.find_element(By.TAG_NAME, "h1")
                        if h1_el:
                            page_name = h1_el.text.strip()
                            print(f"[Automator] Scraped Name from H1: {page_name}")
                    except: pass

                # Method 3: Meta Tag og:title
                if not page_name:
                    try:
                        meta_title = self.driver.find_element(By.XPATH, "//meta[@property='og:title']")
                        content = meta_title.get_attribute("content")
                        if content and "Facebook" not in content:
                            page_name = content.strip()
                            print(f"[Automator] Scraped Name from og:title: {page_name}")
                    except: pass
                
                # Method 4: Page Title (Last Resort)
                if not page_name:
                    page_title = self.driver.title
                    if page_title and "Facebook" in page_title:
                         clean = re.sub(r'\(\d+\)\s*', '', page_title)
                         clean = clean.replace("| Facebook", "").replace("Facebook", "").strip()
                         if clean: 
                            page_name = clean
                            print(f"[Automator] Scraped Name from Title: {page_name}")
                
                # Method 4: Page Title (Last Resort)
                if not page_name:
                    page_title = self.driver.title
                    if page_title and "Facebook" in page_title:
                         clean = re.sub(r'\(\d+\)\s*', '', page_title)
                         clean = clean.replace("| Facebook", "").replace("Facebook", "").strip()
                         if clean: 
                            page_name = clean
                            print(f"[Automator] Scraped Name from Title: {page_name}")

                if not page_name:
                    print("[Automator] Failed to scrape name from Profile.")
                
            except Exception as e:
                print(f"[Automator] Profile scraping failed: {e}")

        upload_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={asset_id}"
        print(f"[Automator] [Backup] Navigating to upload URL: {upload_url}")
        
        # Thêm vòng lặp refresh trang nếu trắng do lỗi phần cứng/mạng
        max_wait_time = 180 # 3 phút
        start_wait = time.time()
        file_input = None
        reload_count = 0
        
        self._safe_get(upload_url)
        time.sleep(3)
        # Reverted: self._close_popups_v2() here was causing issues with the upload composer
        

        while time.time() - start_wait < max_wait_time:
            # Handle "Permission denied"
            if "Permission denied" in self.driver.page_source or "sufficient permissions" in self.driver.page_source:
                 print("[Automator] Permission denied detected. Reloading page...")
                 self.driver.refresh()
                 time.sleep(4)
            
            try:
                # 1. Clean title: Remove all hashtags and non-BMP characters
                import re
                # Remove hashtags (words starting with #)
                clean_title = re.sub(r'#\w+', '', title)
                # Remove emojis/non-BMP
                clean_title = "".join(c for c in clean_title if ord(c) <= 0xFFFF)
                # Clean up double spaces
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                
                # Chờ nút upload
                file_input = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
                )
                break # Tìm thấy nút -> thoát vòng lặp chờ
            except Exception as e:
                reload_count += 1
                if reload_count >= 3:
                     print("[Automator] Đã tải lại 3 lần nhưng vẫn trắng trang. Bỏ qua page này.")
                     raise Exception("SKIP_PAGE: Lỗi trắng trang liên tục không tìm thấy nút upload")
                print(f"[Automator] Không tìm thấy input upload, trắng trang hoặc lỗi mạng. F5 lại trang... ({reload_count}/3)")
                try:
                    self.driver.refresh()
                    time.sleep(3)
                except:
                    pass

        if not file_input:
            raise Exception("Quá 3 phút không load được trang upload (trắng trang liên tục).")

        try:
            file_input.send_keys(os.path.abspath(video_path))
            print("[Automator] Video file sent.")
            
            # Wait for fields to appear
            print("[Automator] Waiting for title/description fields...")
            time.sleep(3) # Heavy wait for Meta Business Suite
            
            # Find all text areas (usually Title, Description, etc.)
            fields = self.driver.find_elements(By.XPATH, "//textarea | //div[@role='textbox']")
            print(f"[Automator] Found {len(fields)} text fields.")
            
            for field in fields:
                try:
                    # Clear and fill every visible text field with the clean title
                    if field.is_displayed():
                        field.click()
                        time.sleep(1)
                        # Use Ctrl+A, Backspace to clear if clear() doesn't work well
                        from selenium.webdriver.common.keys import Keys
                        field.send_keys(Keys.CONTROL + "a")
                        field.send_keys(Keys.BACKSPACE)
                        field.send_keys(clean_title)
                        print(f"[Automator] Filled a field with: {clean_title}")
                except Exception as e:
                    print(f"[Automator] Error filling field: {e}")

            # Click 'Next' steps - usually 2-3 steps
            for i in range(3):
                print(f"[Automator] Attempting to click Next step {i+1}...")
                time.sleep(5) # Wait for processing/UI
                
                next_selectors = [
                    "//div[@role='button']//span[translate(text(), 'NEXTTIEPTUCPublishĐăng', 'nexttieptucpublishdang')='next' or translate(text(), 'NEXTTIEPTUCPublishĐăng', 'nexttieptucpublishdang')='tiếp' or translate(text(), 'NEXTTIEPTUCPublishĐăng', 'nexttieptucpublishdang')='tiếp tục']",
                    "//div[contains(@aria-label, 'Next') or contains(@aria-label, 'Tiếp') or contains(@aria-label, 'Tiếp tục')][@role='button']",
                    "//div[@role='button'][descendant::span[contains(text(), 'Next') or contains(text(), 'Tiếp')]]",
                    "//span[text()='Next' or text()='Tiếp' or text()='Tiếp tục']/ancestor::div[@role='button']"
                ]
                
                clicked = False
                for sel in next_selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, sel)
                        for btn in btns:
                            if btn.is_displayed() and btn.is_enabled():
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                                time.sleep(1)
                                self.driver.execute_script("arguments[0].click();", btn)
                                print(f"[Automator] Success clicking Next via: {sel}")
                                clicked = True
                                break
                        if clicked: break
                    except: continue
                
                if not clicked:
                    print(f"[Automator] Could not find Next button for step {i+1} via selectors. Logging all buttons:")
                    all_btns = self.driver.find_elements(By.XPATH, "//div[@role='button']")
                    for b in all_btns:
                        try:
                            t = b.text.strip().replace("\n", " ")
                            a = b.get_attribute("aria-label") or ""
                            if t or a:
                                print(f"  - Button: text='{t}', aria='{a}'")
                                if any(word in t.lower() or word in a.lower() for word in ["next", "tiếp", "tiếp tục", "publish", "đăng", "chia sẻ"]):
                                    self.driver.execute_script("arguments[0].click();", b)
                                    print(f"  -> Clicked based on heuristic: {t}/{a}")
                                    clicked = True
                                    break
                        except: continue
                
                if not clicked:
                    print(f"[Automator] Step {i+1} Next button really not found, maybe reached end or not ready.")
                    time.sleep(5)
                else:
                    time.sleep(7) # Wait for page transition
            
            # Final Publish
            print("[Automator] Waiting for final Publish button...")
            publish_selectors = [
                "//div[@role='button']//span[text()='Publish' or text()='Đăng' or text()='Chia sẻ' or text()='Share']",
                "//div[contains(@aria-label, 'Publish') or contains(@aria-label, 'Đăng') or contains(@aria-label, 'Chia sẻ') or contains(@aria-label, 'Share')][@role='button']",
                "//div[@role='button'][descendant::span[contains(text(), 'Publish') or contains(text(), 'Đăng') or contains(text(), 'Chia sẻ')]]",
                "//span[text()='Publish' or text()='Đăng' or text()='Chia sẻ' or text()='Share']/ancestor::div[@role='button']"
            ]
            
            publish_clicked = False
            for sel in publish_selectors:
                try:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for btn in btns:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                            time.sleep(1)
                            self.driver.execute_script("arguments[0].click();", btn)
                            print(f"[Automator] Success clicking Publish via: {sel}")
                            publish_clicked = True
                            break
                    if publish_clicked: break
                except: continue
            
            if not publish_clicked:
                print("[Automator] No Publish button found via selectors. Searching by text...")
                all_b = self.driver.find_elements(By.XPATH, "//div[@role='button']")
                for b in all_b:
                    try:
                        txt = b.text.lower()
                        if any(w in txt for w in ["publish", "đăng", "chia sẻ", "share"]):
                            self.driver.execute_script("arguments[0].click();", b)
                            print(f"[Automator] Clicked Publish via text search: {txt}")
                            publish_clicked = True
                            break
                    except: continue

            if publish_clicked:
                # Reverted: long wait loop here. Now handled by gui.py refreshing after success.
                return "Uploaded successfully"
            else:
                raise Exception("Could not find or click Publish button.")
            
        except Exception as e:
            print(f"[Automator] Error during upload: {e}")
            raise e

    def find_and_open_post(self, asset_id, title_text):
        """
        Navigates to Published Posts, finds post by title, and opens its details panel.
        Returns True if panel opened successfully, False otherwise.
        NOTE: This method no longer extracts the post link - it just opens the panel for commenting.
        """
        try:
            clean_title = self._get_clean_title(title_text)
            
            # Navigate to Published Posts page
            published_url = f"https://business.facebook.com/latest/posts/published_posts/?asset_id={asset_id}"
            print(f"[Automator] [Backup] Navigating to: {published_url}")
            self._safe_get(published_url)
            time.sleep(3)
            self._close_popups_v2()
            
            # Try to find and click the post with 3 scrolls
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Backup] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_post = self._find_target_post_element(clean_title)
                
                if target_post:
                    print(f"[Automator] [Backup] Found post. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
                        time.sleep(2)
                        self.driver.execute_script("arguments[0].click();", target_post)
                        time.sleep(3)  # Wait for panel to open
                        print(f"[Automator] [Backup] Panel opened successfully.")
                        return True
                    except Exception as click_err:
                        print(f"[Automator] [Backup] Error opening panel: {click_err}")
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Backup] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4) # Chờ load thêm nội dung
                    self._close_popups_v2()
            
            print("[Automator] [Backup] Failed to find/open post after 3 scrolls.")
            return False
            
        except Exception as e:
            print(f"[Automator] [Backup] Error in find_and_open_post: {e}")
            return False

    def _get_clean_title(self, title_text):
        import re
        clean = re.sub(r'#\w+', '', title_text)
        clean = "".join(c for c in clean if ord(c) <= 0xFFFF)
        clean = re.sub(r'\s+', ' ', clean).strip()
        clean = clean.replace("'", "").replace('"', "")
        return clean

    def _robust_js_scroll(self):
        """
        Facebook uses nested flex containers with overflow. Scrolling window.scrollTo does not work.
        This JS snippet finds all scrollable div containers and scrolls them to the bottom.
        """
        js_scroll_all = """
        document.querySelectorAll('div').forEach(el => {
            if (el.scrollHeight > el.clientHeight && el.clientHeight > 300) {
                el.scrollTop = el.scrollHeight;
            }
        });
        """
        self.driver.execute_script(js_scroll_all)

    def _find_target_post_element(self, clean_title):
        """
        Searches for a post by iteratively reducing title length to find the best match.
        Now integrated with more specific container matching to avoid picking wrong posts.
        """
        lengths = [len(clean_title), 80, 60, 40, 25]
        lengths = sorted(list(set([l for l in lengths if l <= len(clean_title)])), reverse=True)
        
        # Priority 1: Elements inside potential post containers or with heading roles
        # Priority 2: Generic text matches
        
        container_xpaths = [
            # Business Suite Grid/Feed containers
            "//div[contains(@id, 'feed')]//*[contains(text(), '{0}')]",
            "//div[contains(@class, 'card')]//*[contains(text(), '{0}')]",
            "//div[@role='article']//*[contains(text(), '{0}')]",
            # Direct text match as fallback
            "//*[contains(text(), '{0}')]"
        ]

        # Temporarily disable implicit wait for fast scanning
        self.driver.implicitly_wait(0)
        
        try:
            for l in lengths:
                search_str = clean_title[0:l]
                if not search_str.strip(): continue
                
                for cx in container_xpaths:
                    try:
                        xpath_post = cx.format(search_str)
                        matches = self.driver.find_elements(By.XPATH, xpath_post)
                        for m in matches:
                            try:
                                if m.is_displayed():
                                    # Verify it's actually looking like a title (not too long, not an input)
                                    tag = m.tag_name.lower()
                                    if tag not in ['input', 'textarea', 'script', 'style']:
                                        return m
                            except: continue
                    except: continue
            return None
        finally:
            # Restore implicit wait
            self.driver.implicitly_wait(2)

    def comment_in_feed_grid(self, asset_id, title_text, comment_template):
        """
        Primary Strategy: Comment directly on the Feed and Grid page.
        Enhanced with robust selectors and better scrolling.
        """
        try:
            url = f"https://business.facebook.com/latest/posts/feed_and_grid?asset_id={asset_id}"
            print(f"[Automator] [Primary] Navigating to: {url}")
            self._safe_get(url)
            # Event-driven: proceed when page content appears
            self._wait_for_element(["//div[@role='main']", "//div[@role='article']"], timeout=5)
            self._close_popups_v2()
            
            # --- STEP 1: FIND POST CONTAINER WITH 3 SCROLLS ---
            clean_title = self._get_clean_title(title_text)
            
            target_post = None
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Primary] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_post = self._find_target_post_element(clean_title)
                
                if target_post:
                    print(f"[Automator] [Primary] Found post on attempt {scroll_attempt}.")
                    break
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Primary] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    # Event-driven: wait for new content to load (max 3s)
                    self._wait_for_element(["//div[@role='article']|//div[contains(@class,'card')]"], timeout=3)
                    self._close_popups_v2()
            
            if not target_post:
                print(f"[Automator] [Primary] Post '{clean_title[:40]}' not found after 3 scrolls.")
                return False, None

            # Scroll post into middle of screen
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
            # No fixed sleep, proceed immediately
            
            # --- STEP 2: FIND COMMENT BOX OR BUTTON ---
            # Strategy: Sometimes the textbox is hidden behind a "Comment" button, 
            # and sometimes it's already visible as "Comment as..."
            
            # Sub-Strategy A: Look for "Comment as..." or Vietnamese equivalent directly
            textbox_selectors = [
                "//div[@role='textbox'][contains(@aria-label, 'Comment as') or contains(@aria-label, 'Bình luận dưới tên') or contains(@aria-label, 'Bình luận với tư cách')]",
                "//div[@role='textbox'][@aria-label='Write a comment...' or @aria-label='Viết bình luận...']",
                "//div[@contenteditable='true']"
            ]
            
            # Sub-Strategy B: Look for "Comment" button to reveal textbox
            btn_selectors = [
                "//div[@aria-label='Leave a comment' or @aria-label='Viết bình luận' or @aria-label='Bình luận']",
                "//div[@role='button'][descendant::span[contains(text(), 'Comment') or contains(text(), 'Bình luận')]]",
                "//span[contains(text(), 'Comment') or contains(text(), 'Bình luận')]/ancestor::div[@role='button']"
            ]
            
            textbox = None
            title_y = target_post.location['y']
            
            # Try to find textbox directly first (it's faster)
            for sel in textbox_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    try:
                        if el.is_displayed() and abs(el.location['y'] - title_y) < 1200:
                            textbox = el
                            break
                    except: continue
                if textbox: break

            # If no textbox, try the Comment button
            if not textbox:
                print("[Automator] [Primary] Textbox not visible. Searching for Comment button...")
                comment_btn = None
                for sel in btn_selectors:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    min_dist = 1200
                    for b in btns:
                        try:
                            if b.is_displayed():
                                dist = abs(b.location['y'] - title_y)
                                if dist < min_dist:
                                    min_dist = dist
                                    comment_btn = b
                        except: continue
                    if comment_btn: break
                
                if comment_btn:
                    print("[Automator] [Primary] Found Comment button. Clicking...")
                    self.driver.execute_script("arguments[0].click();", comment_btn)
                    print("[Automator] [Primary] Waiting 5s for textbox to appear...")
                    time.sleep(5)
                    
                    # Re-search for textbox after click with detailed logging
                    print("[Automator] [Primary] Searching for textbox after click...")
                    for sel in textbox_selectors:
                        elements = self.driver.find_elements(By.XPATH, sel)
                        print(f"[Automator] [Primary] Selector '{sel[:50]}...' found {len(elements)} elements")
                        for el in elements:
                            try:
                                is_displayed = el.is_displayed()
                                el_y = el.location['y']
                                dist = abs(el_y - title_y)
                                aria = el.get_attribute('aria-label') or ''
                                print(f"[Automator] [Primary]   - Element: displayed={is_displayed}, dist={dist}, aria='{aria[:50]}'")
                                if is_displayed and dist < 1200:
                                    textbox = el
                                    print(f"[Automator] [Primary]   - SELECTED this textbox!")
                                    break
                            except Exception as e:
                                print(f"[Automator] [Primary]   - Error checking element: {e}")
                                continue
                        if textbox: break
                else:
                    print("[Automator] [Primary] No Comment button found.")
            
            if not textbox:
                print("[Automator] [Primary] Failed to find comment interaction area.")
                return False, None
            
            # --- STEP 3: TYPE AND POST ---
            spun_comment = self._spin_text(comment_template)
            clean_comment = "".join(c for c in spun_comment if ord(c) <= 0xFFFF)
            
            print(f"[Automator] [Primary] Posting comment: {clean_comment[:30]}...")
            
            # Use JS click to avoid interception
            self.driver.execute_script("arguments[0].click();", textbox)
            time.sleep(1)
            
            from selenium.webdriver.common.keys import Keys
            textbox.send_keys(Keys.CONTROL + "a")
            textbox.send_keys(Keys.BACKSPACE)
            
            lines = clean_comment.split('\n')
            for i, line in enumerate(lines):
                textbox.send_keys(line)
                if i < len(lines) - 1:
                    textbox.send_keys(Keys.SHIFT + Keys.ENTER)
            
            time.sleep(1)
            textbox.send_keys(Keys.ENTER)
            print("[Automator] [Primary] Comment sent. Verifying submission...")
            
            # --- STEP 4: VERIFY COMMENT POSTED ---
            verified = self._verify_comment_posted()
            
            if not verified:
                print("[Automator] [Primary] Warning: Could not verify comment was posted.")
                return False, None
            
            print("[Automator] [Primary] Comment verified successfully!")
            
            # --- STEP 5: FETCH LINK ---
            post_link = None
            try:
                all_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/posts/') or contains(@href, '/videos/')]")
                for l in all_links:
                    try:
                        if abs(l.location['y'] - title_y) < 400:
                            href = l.get_attribute("href")
                            if "facebook.com" in href:
                                post_link = href
                                break
                    except: continue
            except: pass
            
            return True, post_link

        except Exception as e:
            print(f"[Automator] [Primary] Error during Feed \u0026 Grid comment: {e}")
            return False, None

    def _verify_comment_posted(self):
        """
        Verify that a comment was successfully posted by checking for the 'Remove Preview' clickable text.
        Checks 3 times with 5-second intervals to account for network lag and Facebook moderation.
        """
        preview_selectors = [
            # Clickable text elements (span, a, div)
            "//span[contains(text(), 'Remove preview') or contains(text(), 'Gỡ bản xem trước')]",
            "//a[contains(text(), 'Remove preview') or contains(text(), 'Gỡ bản xem trước')]",
            "//div[contains(text(), 'Remove preview') or contains(text(), 'Gỡ bản xem trước')]",
            # Case-insensitive search
            "//*[contains(translate(text(), 'REMOVE PREVIEW', 'remove preview'), 'remove preview')]",
            "//*[contains(translate(text(), 'GỠ BẢN XEM TRƯỚC', 'gỡ bản xem trước'), 'gỡ bản xem trước')]"
        ]
        
        for attempt in range(3):
            print(f"[Automator] Verification attempt {attempt+1}/3...")
            # Event-driven: check immediately, wait up to 3s between tries
            self.driver.implicitly_wait(0)
            try:
                for sel in preview_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, sel)
                        for elem in elements:
                            try:
                                if elem.is_displayed():
                                    txt = elem.text.strip()
                                    if txt and ("remove" in txt.lower() or "gỡ" in txt.lower()):
                                        print(f"[Automator] ✓ Found Remove Preview text: '{txt}'")
                                        return True
                            except: continue
                    except: continue
            finally:
                self.driver.implicitly_wait(10)
        
        print("[Automator] ✗ Remove Preview text not found after 3 attempts.")
        return False

    def comment_in_published_posts_inline(self, asset_id, title_text, comment_template):
        """
        Tier 3: Comment directly on Published Posts list without opening panel.
        Similar to Feed & Grid but on the Published Posts page.
        """
        try:
            url = f"https://business.facebook.com/latest/posts/published_posts/?asset_id={asset_id}"
            print(f"[Automator] [Tier3] Navigating to: {url}")
            self._safe_get(url)
            # Event-driven: proceed when published posts appear
            self._wait_for_element(["//div[@role='main']", "//div[@role='article']"], timeout=5)
            self._close_popups_v2()
            
            # --- FIND POST WITH 3 SCROLLS ---
            clean_title = self._get_clean_title(title_text)
            
            target_post = None
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Tier3] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_post = self._find_target_post_element(clean_title)
                
                if target_post:
                    print(f"[Automator] [Tier3] Found post on attempt {scroll_attempt}.")
                    break
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Tier3] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4)
                    self._close_popups_v2()
            
            if not target_post:
                print(f"[Automator] [Tier3] Post '{clean_title[:40]}' not found after 3 scrolls.")
                return False, None

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
            time.sleep(2)
            
            # Try to find comment textbox or button
            textbox_selectors = [
                "//div[@role='textbox'][contains(@aria-label, 'Comment as') or contains(@aria-label, 'Bình luận dưới tên')]",
                "//div[@contenteditable='true']"
            ]
            
            btn_selectors = [
                "//div[@aria-label='Leave a comment' or @aria-label='Viết bình luận' or @aria-label='Bình luận']",
                "//span[contains(text(), 'Comment') or contains(text(), 'Bình luận')]/ancestor::div[@role='button']"
            ]
            
            textbox = None
            title_y = target_post.location['y']
            
            # Try textbox first
            for sel in textbox_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    try:
                        if el.is_displayed() and abs(el.location['y'] - title_y) < 1200:
                            textbox = el
                            break
                    except: continue
                if textbox: break

            # If no textbox, try button
            if not textbox:
                for sel in btn_selectors:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for b in btns:
                        try:
                            if b.is_displayed() and abs(b.location['y'] - title_y) < 1200:
                                self.driver.execute_script("arguments[0].click();", b)
                                time.sleep(3)
                                # Re-search for textbox
                                for t_sel in textbox_selectors:
                                    elements = self.driver.find_elements(By.XPATH, t_sel)
                                    for el in elements:
                                        try:
                                            if el.is_displayed() and abs(el.location['y'] - title_y) < 1200:
                                                textbox = el
                                                break
                                        except: continue
                                    if textbox: break
                                break
                        except: continue
                    if textbox: break
            
            if not textbox:
                print("[Automator] [Tier3] Could not find comment area.")
                return False, None
            
            # Post comment
            spun_comment = self._spin_text(comment_template)
            clean_comment = "".join(c for c in spun_comment if ord(c) <= 0xFFFF)
            
            textbox.click()
            time.sleep(1)
            
            from selenium.webdriver.common.keys import Keys
            textbox.send_keys(Keys.CONTROL + "a")
            textbox.send_keys(Keys.BACKSPACE)
            
            lines = clean_comment.split('\n')
            for i, line in enumerate(lines):
                textbox.send_keys(line)
                if i < len(lines) - 1:
                    textbox.send_keys(Keys.SHIFT + Keys.ENTER)
            
            time.sleep(1)
            textbox.send_keys(Keys.ENTER)
            print("[Automator] [Tier3] Comment sent. Verifying...")
            
            # Verify
            verified = self._verify_comment_posted()
            if not verified:
                print("[Automator] [Tier3] Verification failed.")
                return False, None
            
            print("[Automator] [Tier3] Comment verified!")
            return True, None

        except Exception as e:
            print(f"[Automator] [Tier3] Error: {e}")
            return False, None

    def comment_in_insights_overview(self, asset_id, title_text, comment_template):
        """
        Tier 4: Comment via Insights Overview.
        Navigates to Insights Overview, finds the post, opens panel, and posts comment.
        """
        try:
            url = f"https://business.facebook.com/latest/insights/overview/?asset_id={asset_id}&business_id=1016985112612772"
            print(f"[Automator] [Tier4] Navigating to: {url}")
            self._safe_get(url)
            # Increased wait to 10s as requested because Insights pages are heavy
            time.sleep(10) 
            self.log("[Tier4] Checking for initial popups (robust mode)...")
            # Multiple checks as requested to ensure page is fully loaded and popups are caught
            for i in range(2):
                if self._close_popups_v2():
                    time.sleep(3)
                else:
                    time.sleep(2)
            
            clean_title = self._get_clean_title(title_text)
        
            panel_opened = False
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Tier4] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_match = self._find_target_post_element(clean_title)
                
                if target_match:
                    print(f"[Automator] [Tier4] Found post. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_match)
                        time.sleep(2)
                        self.driver.execute_script("arguments[0].click();", target_match)
                        time.sleep(3)
                        panel_opened = True
                        break
                    except Exception as e:
                        print(f"[Automator] [Tier4] Error opening panel: {e}")
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Tier4] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4)
                    self._close_popups_v2()
            
            if not panel_opened:
                print("[Automator] [Tier4] Post not found or could not open panel.")
                return False, None
            
            print("[Automator] [Tier4] Panel opened. Attempting to comment...")
            success = self.post_comment_on_panel(comment_template)
            
            link = None
            if success:
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/') or contains(@href, '/posts/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
            
            return success, link

        except Exception as e:
            print(f"[Automator] [Tier4] Error: {e}")
            return False, None

    def comment_in_insights_base(self, asset_id, title_text, comment_template):
        """
        Tier 5: Comment via Base Insights Content.
        Navigates to Insights Content, finds the post, opens panel, and posts comment.
        """
        try:
            url = f"https://business.facebook.com/latest/insights/content?asset_id={asset_id}&business_id=1016985112612772"
            print(f"[Automator] [Tier5] Navigating to: {url}")
            self._safe_get(url)
            time.sleep(3)
            self._close_popups_v2()
            
            clean_title = self._get_clean_title(title_text)
        
            panel_opened = False
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Tier5] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_match = self._find_target_post_element(clean_title)
                
                if target_match:
                    print(f"[Automator] [Tier5] Found post. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_match)
                        time.sleep(2)
                        self.driver.execute_script("arguments[0].click();", target_match)
                        time.sleep(3)
                        panel_opened = True
                        break
                    except Exception as e:
                        print(f"[Automator] [Tier5] Error opening panel: {e}")
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Tier5] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4)
                    self._close_popups_v2()
            
            if not panel_opened:
                print("[Automator] [Tier5] Post not found or could not open panel.")
                return False, None
            
            print("[Automator] [Tier5] Panel opened. Attempting to comment...")
            success = self.post_comment_on_panel(comment_template)
            
            link = None
            if success:
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/') or contains(@href, '/posts/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
            
            return success, link

        except Exception as e:
            print(f"[Automator] [Tier5] Error: {e}")
            return False, None

    def comment_via_home_scroll(self, asset_id, title_text, comment_template):
        """
        New Tier: Navigate to Home -> Scroll 10 times -> find post -> comment.
        Requirement updates: 10 scrolls, 6s delay, Back button navigation.
        """
        try:
            clean_title = self._get_clean_title(title_text)
            
            home_url = f"https://business.facebook.com/latest/home?asset_id={asset_id}"
            current_url = self.driver.current_url
            
            # Smart navigation: Skip reload if already on the correct Home page
            if "latest/home" not in current_url or f"asset_id={asset_id}" not in current_url:
                print(f"[Automator] [HomeTier] Navigating to Home: {home_url}")
                self._safe_get(home_url)
                time.sleep(5)
                self._close_popups_v2()
            else:
                print(f"[Automator] [HomeTier] Already on Home page. Skipping navigation to avoid excessive loading.")
            
            panel_opened = False
        
            # Increased to 10 scrolls as requested
            for scroll_attempt in range(1, 11): 
                print(f"[Automator] [HomeTier] Scroll Attempt {scroll_attempt}/10 via JS...")
                
                self._robust_js_scroll()
                time.sleep(6) # Increased delay to 6s (prev 4s) as requested
                self._close_popups_v2()
                
                target_match = self._find_target_post_element(clean_title)
                
                if target_match:
                    print(f"[Automator] [HomeTier] Found post on Home. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_match)
                        time.sleep(1)
                        self.driver.execute_script("arguments[0].click();", target_match)
                        time.sleep(7) # Wait for post view/panel to load
                        panel_opened = True
                        break
                    except: continue
                else:
                    print(f"[Automator] [HomeTier] Post not found in attempt {scroll_attempt}.")

            if not panel_opened:
                print("[Automator] [HomeTier] Post not found on Home page after 10 scrolls.")
                return False, None
                
            self._close_popups_v2()
            print("[Automator] [HomeTier] Panel opened. Attempting to comment...")
            success = self.post_comment_on_panel(comment_template)
            
            # Click Back button instead of reloading the page (Requirement 3)
            print("[Automator] [HomeTier] Comment finished. Clicking Back button to return to feed...")
            self._click_back_button_v2()
            time.sleep(3)
            
            link = None
            if success:
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/') or contains(@href, '/posts/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
            
            return success, link

        except Exception as e:
            print(f"[Automator] [HomeTier] Error: {e}")
            return False, None

    def _click_back_button_v2(self):
        """
        Clicks the 'Back' arrow button inside a post view/panel.
        Uses aria-labels and descriptive selectors for robust detection.
        """
        back_selectors = [
            "//div[@aria-label='Back']",
            "//div[@aria-label='Quay lại']",
            "//div[@role='button'][@aria-label='Back' or @aria-label='Quay lại']",
            "//div[contains(@class, 'x1i10hfl')]//i[contains(@class, 'sp_') and parent::div[@role='button']]",
            "//div[@role='button' and .//i[contains(@class, 'x1b0d499')]]",
            "//div[@role='button'][@aria-label='Close' or @aria-label='Đóng']"
        ]
        
        try:
            # Prefer buttons on the left side (x < 500)
            for sel in back_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    try:
                        if el.is_displayed():
                            loc = el.location
                            if loc['x'] < 500:
                                print(f"[Automator] Clicked Back button (left-side) via: {sel}")
                                self.driver.execute_script("arguments[0].click();", el)
                                return True
                    except: continue
            
            # Fallback to any visible match
            for sel in back_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    try:
                        if el.is_displayed():
                            print(f"[Automator] Clicked Back button via: {sel}")
                            self.driver.execute_script("arguments[0].click();", el)
                            return True
                    except: continue
                    
            print("[Automator] Back button not found. Using driver.back() as last resort.")
            self.driver.back()
            return True
        except Exception as e:
            print(f"[Automator] Error clicking back button: {e}")
            return False

    def comment_with_dual_strategy(self, asset_id, title_text, comment_template):
        """
        Dynamically executes enabled commenting strategies in priority order.
        Respects the 'comment_strategies' configuration from the UI.
        """
        
        # Define all available strategies in priority order
        strategy_map = [
            ("home_scroll", "Home Scroll Page", self.comment_via_home_scroll),
            ("feed_grid", "Feed & Grid Page", self.comment_in_feed_grid),
            ("published_panel", "Published Posts (Panel)", lambda a, t, c: self._backup_panel_flow(a, t, c)),
            ("published_inline", "Published Posts (Inline)", self.comment_in_published_posts_inline),
            ("insight_overview", "Insights Overview", self.comment_in_insights_overview),
            ("insight_content", "Insights Content", self.comment_in_insights_base)
        ]

        active_strategies = []
        for key, name, func in strategy_map:
            if self.strategies.get(key, True):
                active_strategies.append((name, func))
        
        if not active_strategies:
            print("[Automator] No commenting strategies enabled in settings!")
            return False, None

        print(f"[Automator] Starting custom strategy chain with {len(active_strategies)} methods.")
        
        for name, func in active_strategies:
            print(f"[Automator] >>> Trying Strategy: {name}")
            
            # Check for block before starting each tier
            if self._check_for_block():
                print(f"[Automator] ⚠️ Facebook temporary block detected! Cannot proceed with {name}.")
                # If Home or Feed is blocked, usually all are blocked. We stop here.
                break
            
            try:
                # Most functions take (asset_id, title_text, comment_template)
                # Some are lambda wrappers
                success, link = func(asset_id, title_text, comment_template)
                
                if self._check_for_block():
                    print(f"[Automator] ⚠️ Facebook temporary block detected after {name} attempt!")
                    break
                    
                if success:
                    print(f"[Automator] ✓ Strategy {name} Succeeded!")
                    return True, link
                    
                print(f"[Automator] ✗ Strategy {name} failed. Moving to next...")
            except Exception as e:
                print(f"[Automator] ! Error in Strategy {name}: {e}")
            
            time.sleep(5) # Small gap between tiers

        print("[Automator] All enabled strategies failed.")
        return False, None

    def _backup_panel_flow(self, asset_id, title_text, comment_template):
        """ Helper for Published Posts Panel strategy """
        panel_opened = self.find_and_open_post(asset_id, title_text)
        if panel_opened:
            success = self.post_comment_on_panel(comment_template)
            if success:
                link = None
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
                return True, link
        return False, None

    def _spin_text(self, text):
        import re
        import random
        while True:
            match = re.search(r'\{([^{}]+)\}', text)
            if not match:
                break
            options = match.group(1).split('|')
            text = text.replace(match.group(0), random.choice(options), 1)
        return text

    def _check_for_block(self):
        """
        Checks for Facebook's 'You're Temporarily Blocked' dialog/modal.
        Returns True if blocked, False otherwise.
        """
        try:
            # check page source first (fastest)
            src = self.driver.page_source
            if "You’re Temporarily Blocked" in src or "You're Temporarily Blocked" in src or \
               "You’re temporarily blocked" in src or "You're temporarily blocked" in src or \
               "Bạn tạm thời bị chặn" in src or "bị chặn tạm thời" in src:
               print("[Automator] ⚠️ Block detected in page source.")
               return True

            # check specific dialogs (more reliable for dynamic modals)
            block_selectors = [
                "//div[@role='dialog'][contains(., 'Temporarily Blocked')]",
                "//div[@role='dialog'][contains(., 'tạm thời bị chặn')]",
                "//span[contains(text(), 'Temporarily Blocked')]",
                "//span[contains(text(), 'tạm thời bị chặn')]",
                "//*[contains(text(), 'It looks like you were misusing this feature')]"
            ]
            
            for sel in block_selectors:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            print(f"[Automator] ⚠️ Block modal detected via selector: {sel}")
                            return True
                except: continue
                
            return False
        except:
            return False

    def post_comment_on_panel(self, comment_template):
        if not comment_template: return False
        
        spun_comment = self._spin_text(comment_template)
        # Filter emojis for selenium
        spun_comment = "".join(c for c in spun_comment if ord(c) <= 0xFFFF)
        
        print(f"[Automator] Attempting to post auto-comment: {spun_comment}")
        
        selectors = [
            "//div[@role='textbox'][contains(@aria-label, 'comment') or contains(@aria-label, 'bình luận')]",
            "//div[@role='textbox'][@contenteditable='true']",
            "//div[@aria-placeholder='Bình luận...' or @aria-placeholder='Viết bình luận...']",
            "//div[@aria-label='Bình luận...' or @aria-label='Bình luận']",
            "//textarea[contains(@placeholder, 'comment') or contains(@placeholder, 'bình luận')]",
            "//div[contains(@class, 'comment')]//div[@role='textbox']",
            "//div[@role='dialog']//div[@role='textbox']",
            "//div[contains(@style, 'editor')]//div[@role='textbox']",
            "//div[@contenteditable='true']"
        ]
        
        try:
            comment_box = None
            # Event-driven: wait up to 10s for comment box to appear
            found, comment_box = self._wait_for_element(selectors, timeout=10)
            
            if comment_box:
                # Scroll into view with offset to avoid sticky header
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_box)
                # No fixed sleep: proceed immediately after scroll
                
                # Use JS click for reliability and wait for focus
                self.driver.execute_script("arguments[0].click();", comment_box)
                time.sleep(0.3)
                
                # Clear if needed (though usually empty)
                # For role=textbox we might need to select all and delete
                from selenium.webdriver.common.keys import Keys
                
                # Split by lines if multi-line template given
                lines = spun_comment.split('\n')
                for i, line in enumerate(lines):
                    comment_box.send_keys(line)
                    if i < len(lines) - 1:
                        comment_box.send_keys(Keys.SHIFT + Keys.ENTER) # New line in FB comment
                
                time.sleep(1)
                comment_box.send_keys(Keys.ENTER)
                print("[Automator] Comment sent. Waiting for link preview (Remove preview button)...")
                
                # Verification loop: Wait for "Remove preview" or "Gỡ bản xem trước" within Feed preview area
                preview_selectors = [
                    "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trước bảng feed')]//div[@role='button'][contains(@aria-label, 'Remove preview') or contains(@aria-label, 'Gỡ bản xem trước') or contains(@aria-label, 'remove preview') or contains(@aria-label, 'gỡ bản xem trước')]",
                    "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trước bảng feed')]//div[contains(@aria-label, 'Remove preview') or contains(@aria-label, 'Gỡ bản xem trước') or contains(@aria-label, 'remove preview') or contains(@aria-label, 'gỡ bản xem trước')]",
                    "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trước bảng feed')]//*[contains(text(), 'Remove preview') or contains(text(), 'Gỡ bản xem trước') or contains(text(), 'remove preview') or contains(text(), 'gỡ bản xem trước')]",
                    "//div[@role='dialog']//div[@role='button'][contains(@aria-label, 'Remove') or contains(@aria-label, 'Gỡ')]",
                    "//div[@role='dialog']//*[contains(text(), 'Remove preview') or contains(text(), 'Gỡ bản xem trước')]"
                ]
                
                found_preview = False
                # use _wait_for_element for immediate proceed when found
                found_preview, _ = self._wait_for_element(preview_selectors, timeout=4)
                
                if found_preview:
                    print("[Automator] Link preview detected (Remove preview button found in Feed preview).")
                else:
                    print("[Automator] Notice: No removable preview detected after 4s (Proceeding).")
                    # Log Feed preview area for debugging
                    print("[Automator] Logging buttons in Feed preview/dialog area:")
                    feed_area = self.driver.find_elements(By.XPATH, "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trước bảng feed') or @role='dialog']")
                    if feed_area:
                        btns_in_feed = feed_area[0].find_elements(By.XPATH, ".//div[@role='button'] | .//a[@role='button']")
                        for b in btns_in_feed[:15]:
                            try:
                                if b.is_displayed():
                                    aria = b.get_attribute("aria-label") or ""
                                    txt = b.text.strip()[:50] or ""
                                    print(f"  - aria='{aria}', text='{txt}'")
                            except: continue
                    else:
                        print("  - Could not find Feed preview area")

                print("[Automator] Comment posting task complete.")
                return True
            else:
                print("[Automator] Could not find comment box in panel.")
                return False
        except Exception as e:
            print(f"[Automator] Error posting comment: {e}")
            return False
    def _close_popups_v2(self):
        """
        Detects and closes common Facebook Business Suite popups, dialogs, and overlays.
        """
        # self.log("Checking for popups/overlays...") # Too noisy if called often
        self.driver.implicitly_wait(0)
        try:
            # 0. Intercept "Get started" screen
            go_home_selectors = [
                "//div[@role='button'][contains(., 'Go to Home') or contains(., 'Đi đến trang chủ') or contains(., 'Đi đến Trang chủ')]",
                "//div[@role='button'][descendant::span[text()='Go to Home' or text()='Đi đến trang chủ']]"
            ]
            for sel in go_home_selectors:
                try:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for b in btns:
                        if b.is_displayed():
                            self.log(f"ℹ️ Detected 'Get started' screen. Clicking '{b.text}'...")
                            self.driver.execute_script("arguments[0].click();", b)
                            time.sleep(5)
                            return True 
                except: pass

            # Sơ kiểm xem có dấu hiệu của modal/dialog/overlay không
            overlay_indicators = [
                "//div[@role='dialog']",
                "//div[@role='presentation']", # Sometimes popups use this
                "//div[contains(@class, 'x1n2onr6') and contains(@class, 'x1vjfegm')]", # Lớp mờ của FB
                "//div[contains(@style, 'z-index') and @role='button']", # Floating buttons that might be popups
                "//*[text()='Dismiss' or text()='Bỏ qua' or text()='Xong' or text()='Done' or text()='Get Started' or text()='Bắt đầu']"
            ]
            
            has_popup = False
            for ind in overlay_indicators[:4]: 
                if self.driver.find_elements(By.XPATH, ind):
                    has_popup = True
                    break
            
            if not has_popup:
                # Still check for some common floating close buttons even if no dialog detected
                quick_close = [
                    "//div[@aria-label='Close' or @aria-label='Đóng'][@role='button']",
                    "//div[contains(@class, 'x1i10hfl')]//div[@role='button'][@aria-label='Close' or @aria-label='Đóng']"
                ]
                for q in quick_close:
                    try:
                        els = self.driver.find_elements(By.XPATH, q)
                        for el in els:
                            if el.is_displayed():
                                self.log(f"ℹ️ Found floating close button: {q}")
                                self.driver.execute_script("arguments[0].click();", el)
                                time.sleep(1)
                                return True
                    except: pass
                return False

            # Nút ưu tiên: Hoàn tất, Bỏ qua, Xong, Đóng
            popup_selectors = [
                "//div[@role='button'][contains(., 'Done') or contains(., 'Xong') or contains(., 'Hoàn tất')]",
                "//div[@role='button'][contains(., 'Dismiss') or contains(., 'Bỏ qua')]",
                "//div[@role='button'][contains(., 'OK') or contains(., 'Ok')]",
                "//div[@role='button'][contains(., 'Show later') or contains(., 'Hiển thị sau') or contains(., 'Để sau') or contains(., 'Lúc khác')]",
                "//div[@role='button'][@aria-label='Close' or @aria-label='Đóng' or @aria-label='Dismiss']",
                "//div[@aria-label='Close' or @aria-label='Đóng']",
                "//div[@role='dialog']//div[@role='button'][@aria-label='Close' or @aria-label='Đóng']", # X button in Insight popups
                "//div[@role='dialog']//i[@data-visualcompletion='css-img' and parent::div[@role='button']]",
                "//div[@role='dialog']//div[contains(@class, 'x1i10hfl')]//div[@role='button'][.//i]",
                "//div[contains(@class, 'x1i10hfl')]//div[@role='button'][@aria-label='Close' or @aria-label='Đóng']"
            ]
                
            closed_any = False
            for _ in range(3):
                found_in_round = False
                for sel in popup_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, sel)
                        for el in elements:
                            if el.is_displayed():
                                self.log(f"ℹ️ Closing detected popup: {sel}")
                                self.driver.execute_script("arguments[0].click();", el)
                                time.sleep(1.5)
                                found_in_round = True
                                closed_any = True
                                break 
                        if found_in_round: break
                    except: continue
                if not found_in_round:
                    break
                
            return closed_any
        except:
            return False
        finally:
            self.driver.implicitly_wait(10)

    def _safe_get(self, url):
        """
        Navigates to a URL while handling blocking alerts and using timeouts.
        """
        try:
            # First try to handle any existing alert
            try:
                alert = self.driver.switch_to.alert
                print(f"[Automator] [Alert] Dismissing pre-navigation alert: {alert.text}")
                alert.dismiss()
            except: pass
            
            print(f"[Automator] Navigating to: {url}")
            self.driver.get(url)
        except Exception as e:
            print(f"[Automator] [Navigation Error] {e}. Trying JS fallback...")
            try:
                self.driver.execute_script(f"window.location.href = '{url}';")
            except:
                print("[Automator] [Severe] Navigation failed even via JS.")

    def close(self):
        self.driver.quit()
