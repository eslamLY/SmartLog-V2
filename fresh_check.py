import sys, time, re
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    # Reload the service page to get fresh data
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030', wait_until='domcontentloaded', timeout=30000)
    time.sleep(8)
    body = pg.inner_text('body')
    # Search for fa48ce1 status
    if 'fa48ce1' in body:
        i = body.index('fa48ce1')
        # Get 500 chars around it
        start = max(0, i-50)
        end = min(len(body), i+500)
        snippet = body[start:end]
        print('Context around fa48ce1:')
        print(snippet)
    # Find deploy IDs
    html = pg.content()
    dep_ids = set(re.findall(r'/deploys/(dep-[a-z0-9]+)', html))
    print('\nDeploy IDs:', dep_ids)
    browser.close()
