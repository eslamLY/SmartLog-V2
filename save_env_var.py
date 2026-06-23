"""Fill DATABASE_URL and save"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)

    pg.locator('button:has-text("Add variable")').first.click()
    time.sleep(3)

    # Fill key
    key_input = pg.locator('input[placeholder="NAME_OF_VARIABLE"]')
    key_input.fill('DATABASE_URL')
    print('Filled key: DATABASE_URL')

    # Fill value (textarea)
    val_input = pg.locator('textarea')
    conn = 'postgresql://smartlog_db_user:lmeG1NNv41Y6WrCRGfuxQ1x5AYQxdlBe@dpg-d8svlqurnols739v473g-a/smartlog_db'
    val_input.fill(conn)
    print('Filled value')

    # Click Save, rebuild, and deploy
    save_btn = pg.locator('button:has-text("Save, rebuild, and deploy")')
    save_btn.click()
    print('Clicked Save, rebuild, and deploy')

    time.sleep(2)
    print(f'Final URL: {pg.url}')

    browser.close()
