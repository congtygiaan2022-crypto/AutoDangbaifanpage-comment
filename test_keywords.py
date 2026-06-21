from bs4 import BeautifulSoup

with open('debug_dom_failure_v2.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
# remove script and style elements
for script in soup(["script", "style"]):
    script.decompose()

body_text = soup.get_text().lower()

keywords = ["success", "creating your reels", "done", "đã đăng", "hoàn tất", "xong", "reels của bạn đang được tạo", "quản lý tất cả nội dung"]
for kw in keywords:
    print(f"Keyword '{kw}' in body text: {body_text.count(kw)} occurrences")
