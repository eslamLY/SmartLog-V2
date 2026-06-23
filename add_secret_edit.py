"""Add SECRET_KEY env var via Edit form"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(4)

    # Click Edit
    pg.locator('button').filter(has_text='Edit').first.click()
    time.sleep(3)

    # Click Add variable
    pg.locator('button').filter(has_text='Add variable').click()
    time.sleep(2)

    # Find all inputs - the second name input is for the new var
    inputs = pg.locator('input[placeholder="NAME_OF_VARIABLE"]')
    count = inputs.count()
    print(f'Found {count} name inputs')

    if count >= 2:
        # Fill the SECOND name input (first is DATABASE_URL)
        inputs.nth(1).fill('SECRET_KEY')
        print('Filled SECRET_KEY')
    elif count >= 1:
        # Only one input - fill it
        inputs.first.fill('SECRET_KEY')
        print('Filled SECRET_KEY (only one input)')

    # Fill the value in the second textarea (or last)
    textareas = pg.locator('textarea')
    ta_count = textareas.count()
    print(f'Found {ta_count} textareas')
    if ta_count >= 2:
        textareas.nth(1).fill('7342b54eec91b8724e6f309532ebfc9c4737bca772a7acb973f118a2e8c48039')
        print('Filled value in second textarea')
    elif ta_count >= 1:
        textareas.first.fill('7342b54eec91b8724e6f309532ebfc9c4737bca772a7acb973f118a2e8c48039')
        print('Filled value in first textarea')

    # Click Save
    pg.locator('button').filter(has_text='Save, rebuild, and deploy').click()
    print('Clicked Save, rebuild, and deploy')

    time.sleep(3)
    print(f'URL: {pg.url}')

    browser.close()
