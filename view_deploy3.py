"""Check the failed deploy log for ce5ba49"""
import sys, re, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # First get all deploy IDs from the service page
    pg.goto(
        'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
        wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    html = pg.content()
    dep_ids = re.findall(r'/deploys/(dep-[a-z0-9]+)', html)
    print('Deploy IDs:', dep_ids)

    # Try each deploy and check which one failed for ce5ba49
    for dep_id in dep_ids:
        pg.goto(
            f'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/{dep_id}',
            wait_until='domcontentloaded', timeout=30000)
        time.sleep(5)
        body = pg.inner_text('body')
        if 'ce5ba49' in body:
            print(f'\n=== Found ce5ba49 deploy: {dep_id} ===')

            # Find all ERROR/FATAL/CRITICAL lines
            lines = body.split('\n')
            print('\n=== Errors ===')
            for line in lines:
                if any(kw in line for kw in ['ERROR', 'FATAL', 'CRITICAL', 'Traceback', 'exit 1']):
                    print(line.strip())

            print('\n=== Context around "Exited" ===')
            idx = body.find('Exited with status')
            if idx >= 0:
                start = max(0, idx - 300)
                end = min(len(body), idx + 200)
                print(body[start:end])

            print('\n=== Context around "Running" ===')
            idx = body.find("Running 'gunicorn")
            if idx >= 0:
                end = min(len(body), idx + 1500)
                print(body[idx:end])

            break

    browser.close()
