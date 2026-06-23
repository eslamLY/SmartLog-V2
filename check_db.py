"""Check database status on Render"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)
    print('URL:', pg.url)

    body = pg.inner_text('body')
    # Look for key details
    for kw in ['Status', 'Ready', 'Available', 'Connection', 'region',
               'postgresql', 'provision', 'active', 'created']:
        if kw in body:
            i = body.index(kw)
            ctx = body[max(0,i-30):i+200].replace(chr(10), ' ')
            print(f'{kw}: {ctx}')

    # Get connection string
    for kw in ['Internal', 'Connection String', 'PSQL', 'DATABASE']:
        if kw in body:
            i = body.index(kw)
            ctx = body[max(0,i-50):i+500].replace(chr(10), ' ')
            print(f'\n{kw}: {ctx}')

    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\db_status.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    browser.close()
