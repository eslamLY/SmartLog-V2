"""Add SECRET_KEY env var (simpler)"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(4)

    pg.locator('button:has-text("Add variable")').first.click()
    time.sleep(3)

    pg.locator('input[placeholder="NAME_OF_VARIABLE"]').fill('SECRET_KEY')
    pg.locator('textarea').fill('7342b54eec91b8724e6f309532ebfc9c4737bca772a7acb973f118a2e8c48039')
    pg.locator('button:has-text("Save, rebuild, and deploy")').click()
    print('Saved')

    time.sleep(2)
    url = pg.url
    print(f'URL: {url}')
    browser.close()
