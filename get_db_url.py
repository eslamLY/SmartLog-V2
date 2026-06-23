"""Get database connection string and set it as env var"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Click on smartlog-db to go to its details page
    pg.goto('https://dashboard.render.com/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Click on smartlog-db link
    db_link = pg.locator('a:has-text("smartlog-db")').first
    if db_link.is_visible(timeout=3000):
        db_link.click()
        time.sleep(5)
        print('URL:', pg.url)

        # Look for connection string
        body = pg.inner_text('body')
        print('\n=== DB Page Content (first 2000 chars) ===')
        print(body[:2000])

        # Look for "Connections" section
        connections = pg.locator('text=Connections').first
        if connections.is_visible(timeout=3000):
            connections.click()
            time.sleep(3)
            print('\n=== Connections section ===')
            body2 = pg.inner_text('body')
            print(body2[2000:3000])

    browser.close()
