"""Check Render logs for 500 error"""
import sys, time, json, urllib.request
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to the Logs tab
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/logs',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(8)
    body = pg.inner_text('body')
    print('Logs page length:', len(body))

    # Save full log content
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\render_logs.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Look for errors
    for kw in ['Traceback', '500', 'Error:', 'Internal Server', 'Exception']:
        if kw in body:
            i = body.index(kw)
            start = max(0, i-200)
            end = min(len(body), i+500)
            print(f'\n{kw}: {body[start:end]}')

    browser.close()
