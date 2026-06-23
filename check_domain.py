import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    body = pg.inner_text('body')
    # Find URLs
    for kw in ['https://', 'Custom Domain', 'Domains', 'smartlog']:
        if kw in body:
            i = body.index(kw)
            print(f'{kw}: {body[i:i+150].replace(chr(10)," ")}')
    browser.close()
