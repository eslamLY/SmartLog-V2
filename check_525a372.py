import sys, time, re
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    html = pg.content()
    dep_ids = re.findall(r'/deploys/(dep-[a-z0-9]+)', html)
    print('Deploy IDs:', dep_ids)
    # Check each for 525a372
    for dep_id in set(dep_ids):
        pg.goto(f'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/{dep_id}', wait_until='domcontentloaded', timeout=30000)
        time.sleep(8)
        body = pg.inner_text('body')
        if '525a372' in body:
            print(f'\n*** 525a372 deploy: {dep_id} ***')
            # Print full log
            print(body)
            break
    browser.close()
