import re

with open('api/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Match getElementById('...')
js_ids = set(re.findall(r"getElementById\(['\"]([a-zA-Z0-9_\-]+)['\"]\)", content))

# Match id="..."
html_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_\-]+)["\']', content))

missing = [i for i in js_ids if i not in html_ids]
print(f"Total JS referenced IDs: {len(js_ids)}")
print(f"Total HTML defined IDs: {len(html_ids)}")
print(f"Missing IDs: {missing}")

if not missing:
    print("SUCCESS: 100% of DOM IDs referenced in JavaScript exist in HTML!")
