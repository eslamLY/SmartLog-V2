"""Open latest failed deploy logs"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Direct nav to latest failed deploy
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8svq87avr4c738jhdn0',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)
    print('URL:', pg.url)

    body = pg.inner_text('body')

    # Look for error messages
    for kw in ['Error', 'error', 'Traceback', 'Exception', 'failed', 'exit',
               'sqlalchemy', 'connection', 'refused', 'timeout', 'SSL', 'ssl']:
        if kw in body:
            i = body.index(kw) if kw in body else -1
            if i >= 0:
                ctx = body[max(0,i-50):i+500].replace(chr(10), ' ')
                print(f'\n--- Found "{kw}" ---')
                print(ctx)

    # Save full body
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_detail.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    print(f'\n\nBody preview (first 2000 chars):')
    print(body[:2000])

    browser.close()
