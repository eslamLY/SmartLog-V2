"""Check app runtime logs"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to Logs tab
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/logs',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(8)
    print('URL:', pg.url)

    body = pg.inner_text('body')
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\runtime_logs.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Look for log content  
    for kw in ['seed', 'Seed', 'Startup', 'Tables', 'startup complete',
               'smartlog', 'ready to serve', 'create_all', 'skipped',
               'loaded', 'ERROR', 'WARNING']:
        if kw in body:
            i = body.index(kw)
            ctx = body[max(0,i-50):i+300].replace(chr(10), ' ')
            print(f'{kw}: {ctx}')

    browser.close()
