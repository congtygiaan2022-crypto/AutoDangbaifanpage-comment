import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from gemlogin_api import GemLoginAPI

def test():
    print("Testing scroll on Facebook Business Suite")
    api = GemLoginAPI()
    
    profile = api.find_profile_by_name("Đăng bài Fanpage + comment")
    if not profile:
        print("Profile not found!")
        return

    launch_data = api.start_profile(profile['id'])
    if not launch_data or not launch_data.get('success'):
        print("Failed to start profile!")
        return

    data = launch_data.get('data', {})
    debugger_address = data.get('remote_debugging_address') or data.get('debugger_address')
    driver_path = data.get('driver_path')
    
    print(f"Debugger: {debugger_address}, Driver: {driver_path}")
    
    opts = Options()
    opts.debugger_address = debugger_address
    service = Service(executable_path=driver_path)
    
    driver = webdriver.Chrome(service=service, options=opts)
    
    # 1. Nav to Home
    url = "https://business.facebook.com/latest/home?asset_id=101291899113500"
    print(f"Navigating to {url}")
    driver.get(url)
    time.sleep(10)
    
    # 2. Find scrollable elements
    js_code = """
    let scrollables = [];
    document.querySelectorAll('*').forEach(el => {
        if (el.scrollHeight > el.clientHeight && el.clientHeight > 200) {
            scrollables.push({
                tag: el.tagName,
                class: el.className,
                role: el.getAttribute('role'),
                aria: el.getAttribute('aria-label'),
                sHeight: el.scrollHeight,
                cHeight: el.clientHeight,
                id: el.id
            });
        }
    });
    return scrollables;
    """
    
    results = driver.execute_script(js_code)
    print("Scrollable containers found:")
    for i, r in enumerate(results):
        print(f"[{i}] {r}")

    # Test ActionChains END key on body just in case
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    
    print("Attempting to scroll body using Keys.END...")
    ActionChains(driver).send_keys(Keys.END).perform()
    time.sleep(3)
    
    print("Attempting to scroll all found large containers via JS...")
    
    js_scroll_all = """
    document.querySelectorAll('*').forEach(el => {
        if (el.scrollHeight > el.clientHeight && el.clientHeight > 300) {
            el.scrollTop = el.scrollHeight;
        }
    });
    return true;
    """
    driver.execute_script(js_scroll_all)
    print("Scrolled all large containers using JS!")
    
    time.sleep(5)
    print("Test complete.")

if __name__ == "__main__":
    test()
