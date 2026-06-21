from bs4 import BeautifulSoup

with open('debug_dom_failure_v2.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

print("All elements with role='button' or <button> tag:")
count = 0
for el in soup.find_all(True):
    if el.name == 'button' or el.get('role') == 'button':
        txt = el.text.strip().replace('\n', ' ')
        if txt:
            print(f"Tag: {el.name}, Attrs: {el.attrs}, Text: {txt[:100]}")
            count += 1
            if count >= 30:
                print("... Truncated after 30 buttons ...")
                break
