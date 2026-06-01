from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import re

class FacebookAutomator:
    def __init__(self, debugger_address, driver_path=None):
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)
        
        try:
            if driver_path and os.path.exists(driver_path):
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Error connecting to browser: {e}")
            raise e

    def resolve_asset_id(self, page_link):
        # Try to find asset_id in URL without navigation first
        if "asset_id=" in page_link:
            return page_link.split("asset_id=")[-1].split("&")[0]
        
        # If it's a direct page ID in URL
        parts = page_link.strip("/").split("/")
        if parts[-1].isdigit():
            return parts[-1]
            
        # Must navigate
        print(f"[Automator] Navigating to resolve Asset ID: {page_link}")
        self.driver.get(page_link)
        time.sleep(5)
        
        if "asset_id=" in self.driver.current_url:
            return self.driver.current_url.split("asset_id=")[-1].split("&")[0]
            
        links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'asset_id=')]")
        for l in links:
            href = l.get_attribute("href")
            if "asset_id=" in href:
                return href.split("asset_id=")[-1].split("&")[0]
                
        import re
        match = re.search(r'"actorID":"(\d+)"', self.driver.page_source)
        if match: return match.group(1)
            
        return None

    def upload_reel_by_link(self, page_link, video_path, title, scrape_name=False):
        asset_id = self.resolve_asset_id(page_link)
        
        if not asset_id:
            raise Exception("Could not find Asset ID for this page link.")

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

                if not page_name:
                    print("[Automator] Failed to scrape name from Profile.")
                
            except Exception as e:
                print(f"[Automator] Profile scraping failed: {e}")

        upload_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={asset_id}"
        print(f"[Automator] Navigating to upload URL: {upload_url}")
        self.driver.get(upload_url)
        time.sleep(10)
        
        # Handle "Permission denied"
        if "Permission denied" in self.driver.page_source or "sufficient permissions" in self.driver.page_source:
             print("[Automator] Permission denied detected. Reloading page...")
             self.driver.refresh()
             time.sleep(12)
        
        try:
            # 1. Clean title: Remove all hashtags and non-BMP characters
            import re
            # Remove hashtags (words starting with #)
            clean_title = re.sub(r'#\w+', '', title)
            # Remove emojis/non-BMP
            clean_title = "".join(c for c in clean_title if ord(c) <= 0xFFFF)
            # Clean up double spaces
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            
            # Send file
            file_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
            )
            file_input.send_keys(os.path.abspath(video_path))
            print("[Automator] Video file sent.")
            
            # Wait for fields to appear
            print("[Automator] Waiting for title/description fields...")
            time.sleep(10) # Heavy wait for Meta Business Suite
            
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
                print(f"[Automator] Post published. Waiting 10s for UI to update...")
                time.sleep(10)
                # We return the basic confirmation. Link retrieval will be handled by the commenting flow or explicitly.
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
            self.driver.get(published_url)
            time.sleep(10)
            
            # Try to find and click the post
            short_title = clean_title[:40]
            xpath_title = f"//*[contains(text(), '{short_title}')]"
            print(f"[Automator] [Backup] Searching for post: {short_title}")
            
            for attempt in range(5):
                matches = self.driver.find_elements(By.XPATH, xpath_title)
                if matches:
                    print(f"[Automator] [Backup] Found post. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", matches[0])
                        time.sleep(2)
                        self.driver.execute_script("arguments[0].click();", matches[0])
                        time.sleep(8)  # Wait for panel to open
                        print(f"[Automator] [Backup] Panel opened successfully.")
                        return True
                    except Exception as click_err:
                        print(f"[Automator] [Backup] Error opening panel: {click_err}")
                
                print(f"[Automator] [Backup] Post not found (Attempt {attempt+1}/5). Refreshing...")
                self.driver.refresh()
                time.sleep(10)
            
            print("[Automator] [Backup] Failed to find/open post after 5 attempts.")
            return False
            
        except Exception as e:
            print(f"[Automator] [Backup] Error in find_and_open_post: {e}")
            return False

    def _get_clean_title(self, title_text):
        import re
        clean = re.sub(r'#\w+', '', title_text)
        clean = "".join(c for c in clean if ord(c) <= 0xFFFF)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def comment_in_feed_grid(self, asset_id, title_text, comment_template):
        """
        Primary Strategy: Comment directly on the Feed and Grid page.
        Enhanced with robust selectors and better scrolling.
        """
        try:
            url = f"https://business.facebook.com/latest/posts/feed_and_grid?asset_id={asset_id}"
            print(f"[Automator] [Primary] Navigating to: {url}")
            self.driver.get(url)
            time.sleep(10)
            
            clean_title = self._get_clean_title(title_text)
            # Use shorter title for more flexible matching
            short_title = clean_title[:40]
            
            # --- STEP 1: FIND POST CONTAINER ---
            xpath_post = f"//*[contains(text(), '{short_title}')]"
            print(f"[Automator] [Primary] Searching for post: {short_title}")
            
            matches = self.driver.find_elements(By.XPATH, xpath_post)
            if not matches:
                print(f"[Automator] [Primary] Post '{short_title}' not found.")
                return False, None
            
            target_post = None
            for m in matches:
                try:
                    if m.is_displayed():
                        target_post = m
                        break
                except: continue
            
            if not target_post:
                print("[Automator] [Primary] Post element found but not visible.")
                return False, None

            # Scroll post into middle of screen
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
            time.sleep(3)
            
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
            time.sleep(5)  # Wait 5 seconds between checks
            
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
            self.driver.get(url)
            time.sleep(10)
            
            clean_title = self._get_clean_title(title_text)
            short_title = clean_title[:40]
            
            # Find the post
            xpath_post = f"//*[contains(text(), '{short_title}')]"
            print(f"[Automator] [Tier3] Searching for post: {short_title}")
            
            matches = self.driver.find_elements(By.XPATH, xpath_post)
            if not matches:
                print(f"[Automator] [Tier3] Post not found.")
                return False, None
            
            target_post = None
            for m in matches:
                try:
                    if m.is_displayed():
                        target_post = m
                        break
                except: continue
            
            if not target_post:
                return False, None

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
            time.sleep(3)
            
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

    def comment_with_dual_strategy(self, asset_id, title_text, comment_template):
        """
        Three-tier strategy for maximum reliability:
        - Tier 1: Feed & Grid (5 attempts)
        - Tier 2: Published Posts Panel (5 attempts)
        - Tier 3: Published Posts Inline (5 attempts)
        
        Includes Facebook block detection to skip tiers immediately.
        """
        # --- TIER 1: FEED & GRID ---
        print("[Automator] Starting Tier 1: Feed & Grid")
        tier1_blocked = False
        for attempt in range(5):
            print(f"[Automator] Tier 1 - Attempt {attempt+1}/5")
            
            # Check for Facebook temporary block
            if self._check_for_block():
                print("[Automator] ⚠️ Facebook temporary block detected! Skipping to Tier 2...")
                tier1_blocked = True
                break
            
            success, link = self.comment_in_feed_grid(asset_id, title_text, comment_template)
            
            # Check again after attempted action
            if self._check_for_block():
                print("[Automator] ⚠️ Facebook temporary block detected after action! Skipping to Tier 2...")
                tier1_blocked = True
                break
            if success:
                print(f"[Automator] Tier 1 Success!")
                return True, link
            if attempt < 4:
                print("[Automator] Retrying Tier 1 in 10s...")
                time.sleep(10)
        
        # --- TIER 2: PUBLISHED POSTS PANEL ---
        if tier1_blocked:
            print("[Automator] Tier 1 blocked by Facebook. Starting Tier 2: Published Posts Panel")
        else:
            print("[Automator] Tier 1 failed. Starting Tier 2: Published Posts Panel")
        
        tier2_blocked = False
        for attempt in range(5):
            print(f"[Automator] Tier 2 - Attempt {attempt+1}/5")
            
            # Check for block removed here to allow navigation first
            # if self._check_for_block(): ...
            
            panel_opened = self.find_and_open_post(asset_id, title_text)
            if panel_opened:
                print("[Automator] [Backup] Panel opened. Attempting to comment...")
                success = self.post_comment_on_panel(comment_template)
                
                # Check again after attempted action
                if self._check_for_block():
                    print("[Automator] ⚠️ Facebook temporary block detected after action! Skipping to Tier 3...")
                    tier2_blocked = True
                    break
                if success:
                    print("[Automator] Tier 2 Success!")
                    # Try to get link (optional)
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
            if attempt < 4:
                print("[Automator] Retrying Tier 2 in 10s...")
                time.sleep(10)

        # --- TIER 3: PUBLISHED POSTS INLINE ---
        if tier2_blocked:
            print("[Automator] Tier 2 blocked by Facebook. Starting Tier 3: Published Posts Inline (Final Fallback)")
        else:
            print("[Automator] Tier 2 failed. Starting Tier 3: Published Posts Inline (Final Fallback)")
        
        for attempt in range(5):
            print(f"[Automator] Tier 3 - Attempt {attempt+1}/5")
            
            # Check for block removed here to allow navigation first
            # if self._check_for_block(): ...
            
            success, link = self.comment_in_published_posts_inline(asset_id, title_text, comment_template)
            
            # Check again after attempted action
            if self._check_for_block():
                print("[Automator] ⚠️ Facebook temporary block detected after Tier 3 action. Cannot proceed.")
                return False, None
            if success:
                print("[Automator] Tier 3 Success!")
                return True, link
            if attempt < 4:
                print("[Automator] Retrying Tier 3 in 10s...")
                time.sleep(10)

        print("[Automator] All 3 tiers failed after 15 total attempts.")
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
            "//textarea[contains(@placeholder, 'comment') or contains(@placeholder, 'bình luận')]",
            "//div[contains(@class, 'comment')]//div[@role='textbox']",
            "//div[@role='dialog']//div[@role='textbox']",
            "//div[contains(@style, 'editor')]//div[@role='textbox']",
            "//div[@contenteditable='true']"
        ]
        
        try:
            comment_box = None
            # Wait up to 15s for comment box to be ready
            for _ in range(3):
                for sel in selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, sel)
                        for b in btns:
                            if b.is_displayed():
                                comment_box = b
                                break
                        if comment_box: break
                    except: continue
                if comment_box: break
                time.sleep(5)
            
            if comment_box:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", comment_box)
                time.sleep(1)
                comment_box.click()
                time.sleep(1)
                
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
                for attempt in range(15): # 30s total wait
                    for ps in preview_selectors:
                        elements = self.driver.find_elements(By.XPATH, ps)
                        if elements:
                            # Log what we found for debugging
                            for elem in elements:
                                try:
                                    aria = elem.get_attribute("aria-label") or ""
                                    txt = elem.text or ""
                                    if "remove" in aria.lower() or "gỡ" in aria.lower() or "remove" in txt.lower() or "gỡ" in txt.lower():
                                        print(f"[Automator] Found preview control in Feed preview: aria='{aria}', text='{txt}'")
                                        found_preview = True
                                        break
                                except: continue
                        if found_preview: break
                    if found_preview: break
                    time.sleep(2)
                
                if found_preview:
                    print("[Automator] Link preview detected (Remove preview button found in Feed preview).")
                else:
                    print("[Automator] Warning: Could not detect Remove preview button in Feed preview after 30s.")
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

    def close(self):
        self.driver.quit()
