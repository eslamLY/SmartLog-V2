"""Check latest live deploy logs for seed messages"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Navigate to latest live deploy
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8t01467r5hc73ebj27g',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    body = pg.inner_text('body')
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\live_deploy.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Look for log content (the body might include scrollable log area)
    log_lines = [l.strip() for l in body.split('\n') if l.strip()]

    print('Log entries containing important keywords:')
    for line in log_lines:
        if any(kw in line for kw in ['seed', 'Seed', 'Startup', 'Tables', 'create_all',
                                      'DB connection', 'connection test', 'PASSED',
                                      'database connection', 'flask db', 'migration',
                                      'migrate', 'upgrade', 'skipped', 'seeding',
                                      'loaded', 'complete', 'ERROR', 'WARNING',
                                      'FATAL']):
            print(f'  {line[:200]}')

    browser.close()
