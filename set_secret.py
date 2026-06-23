"""Add SECRET_KEY env var on Render"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # First check if DATABASE_URL already exists and there's a "Save" or "add" option
    body = pg.inner_text('body')

    # Click "Add variable" to open the form
    pg.locator('button:has-text("Add variable")').first.click()
    time.sleep(3)

    # Fill key
    key_input = pg.locator('input[placeholder="NAME_OF_VARIABLE"]')
    key_input.fill('SECRET_KEY')
    print('Filled key: SECRET_KEY')

    # Fill value
    val_input = pg.locator('textarea')
    secret_key = '7342b54eec91b8724e6f309532ebfc9c4737bca772a7acb973f118a2e8c48039'
    val_input.fill(secret_key)
    print('Filled value')

    # Click Save, rebuild, and deploy
    save_btn = pg.locator('button:has-text("Save, rebuild, and deploy")')
    save_btn.click()
    print('Clicked Save, rebuild, and deploy')

    time.sleep(3)
    print(f'Final URL: {pg.url}')

    body2 = pg.inner_text('body')
    if 'Deploy started' in body2:
        i = body2.index('Deploy started')
        print(f'Deploy event: {body2[i:i+200].replace(chr(10), " ")}')

    browser.close()
