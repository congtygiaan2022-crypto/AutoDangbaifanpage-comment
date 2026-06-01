import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

port = 53158
options = Options()
options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
try:
    driver = webdriver.Chrome(options=options)
    print(f"Connected to browser. Current URL: {driver.current_url}")
    
    # Try grabbing the full HTML around the comment area
    # Facebook might use lexical editor
    print("\n--- Lexical Editors ---")
    lexicals = driver.find_elements(By.XPATH, "//*[contains(@class, 'lexical')]")
    for lx in lexicals:
        print(f"Lexical element text: {lx.text[:50]}")
    
    print("\n--- Textboxes ---")
    textboxes = driver.find_elements(By.XPATH, "//div[@role='textbox']")
    for i, t in enumerate(textboxes):
        if t.is_displayed():
            print(f"Textbox {i}: aria-label='{t.get_attribute('aria-label')}' text='{t.text[:30]}'")

    print("\n--- Buttons ---")
    buttons = driver.find_elements(By.XPATH, "//div[@role='button']")
    for b in buttons:
        if b.is_displayed():
            txt = b.text.lower()
            aria = (b.get_attribute('aria-label') or '').lower()
            if "comment" in txt or "bình luận" in txt or "comment" in aria or "bình luận" in aria:
                print(f"Button: text='{b.text.strip()}' aria-label='{b.get_attribute('aria-label')}' class='{b.get_attribute('class')}'")

except Exception as e:
    print(f"Error: {e}")
