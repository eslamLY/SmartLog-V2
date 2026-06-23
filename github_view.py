"""Screenshot GitHub edit page"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://github.com/eslamLY/SmartLog-V2/edit/main/routes/auth.py',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)

    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\github_edit.png', full_page=True)
    print('Screenshot saved')

    html = pg.content()
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\github_edit.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print('HTML saved')

    body = pg.inner_text('body')
    print(f'Body length: {len(body)}')
    print(f'Body: {body[:1000]}')

    browser.close()
