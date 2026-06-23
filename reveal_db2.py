"""Try to generate default credentials to get connection string"""
import sys, time, re
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a', wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Try clicking "New default credential" button
    try:
        btn = pg.locator('button:has-text("New default credential"), span:has-text("New default credential"), div:has-text("New default credential")').first
        if btn.is_visible(timeout=3000):
            btn.click()
            time.sleep(5)
            print('Clicked New default credential')
        else:
            print('New default credential button not visible')
    except Exception as e:
        print(f'Click error: {e}')

    body = pg.inner_text('body')
    print('Body:', body)

    # Look for postgres:// or postgresql:// in HTML
    html = pg.content()
    urls = re.findall(r'postgres(?:ql)?://[^"\'<>\s]+', html)
    print(f'\npostgres URLs in HTML: {len(urls)}')
    for u in urls:
        print(u)

    browser.close()
