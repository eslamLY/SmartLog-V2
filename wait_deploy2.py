"""Check deploy status after more waiting"""
import sys, time, urllib.request
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    for i in range(10):
        print(f'\n--- Check {i+1} at {time.strftime("%H:%M:%S")} ---')
        pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
                wait_until='domcontentloaded', timeout=30000)
        time.sleep(5)
        body = pg.inner_text('body')

        for kw in ['Live', 'Failed', 'Deploying', 'Build in progress']:
            if kw in body:
                idx = body.index(kw)
                start = max(0,idx-30)
                end = min(len(body),idx+80)
                snippet = body[start:end].replace(chr(10),' ')
                print(f'{kw}: {snippet}')

        if 'Live' in body:
            print('DEPLOY SUCCEEDED!')
            # Check health
            try:
                resp = urllib.request.urlopen('https://smartlog-v2-1.onrender.com/api/health', timeout=10)
                data = resp.read().decode()
                print(f'Health: {resp.status} - {data[:300]}')
            except Exception as e:
                print(f'Health: {e}')
            break

        if 'Failed' in body:
            print('DEPLOY FAILED!')
            break

        time.sleep(120)

    browser.close()
