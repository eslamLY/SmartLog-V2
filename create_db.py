"""Create a free PostgreSQL database on Render"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to new database page
    pg.goto('https://dashboard.render.com/new/database', wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Fill in name
    name_input = pg.locator('input[id*="name" i], input[placeholder*="Name" i]').first
    if name_input.is_visible(timeout=3000):
        name_input.fill('smartlog-db')
        print('Filled name')

    # Select Free plan
    free_label = pg.locator('text=Free').first
    if free_label.is_visible(timeout=3000):
        free_label.click()
        print('Selected Free plan')

    # Scroll to Create Database button
    pg.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    time.sleep(1)

    # Click Create Database
    create_btn = pg.locator('button:has-text("Create Database")').first
    if create_btn.is_visible(timeout=3000):
        create_btn.click()
        print('Clicked Create Database!')
        time.sleep(5)
        print(f'Current URL: {pg.url}')
    else:
        print('Create button not found')

    # Take screenshot
    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_screenshots\10_create_db.png')

    browser.close()
