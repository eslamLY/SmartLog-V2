import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    # Go to dashboard
    pg.goto('https://dashboard.render.com/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    print('URL:', pg.url)
    body = pg.inner_text('body')
    # Look for service names/URLs
    for kw in ['smartlog', 'SmartLog', 'srv-', 'onrender']:
        if kw in body.lower():
            i = body.lower().index(kw)
            print(f'{kw}: {body[i:i+100].replace(chr(10)," ")}')
    browser.close()
