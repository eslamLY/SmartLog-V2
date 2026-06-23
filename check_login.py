"""Check if logged into Render"""
import sys
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    print('URL:', pg.url)
    body = pg.inner_text('body')
    for kw in ['log in', 'login', 'sign in', 'email', 'password', 'dashboard', 'SmartLog', 'Backend']:
        if kw in body.lower():
            idx = body.lower().index(kw)
            start = max(0, idx - 20)
            end = min(len(body), idx + 50)
            snippet = body[start:end].replace('\n', ' ')
            print(f'Found "{kw}": ...{snippet[:100]}...')
    browser.close()
