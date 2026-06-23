"""Set DATABASE_URL environment variable on the web service"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to the web service environment page
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/environment',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    print('URL:', pg.url)

    body = pg.inner_text('body')
    print('Body first 2000:', body[:2000])

    # Look for "Add Environment Variable" button or similar
    env_section = pg.locator('text=Environment Variables').first
    if env_section.is_visible(timeout=3000):
        print('Found Environment Variables section')
        env_section.click()
        time.sleep(2)

    # Look for "Add" or "New" button in the env vars area
    try:
        add_btn = pg.locator('button:has-text("Add"), button:has-text("New"), button:has-text("+")').first
        if add_btn.is_visible(timeout=3000):
            add_btn.click()
            time.sleep(2)
            print('Clicked Add button')
    except:
        pass

    body2 = pg.inner_text('body')
    print('\nAfter interaction:', body2[:2000])

    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_screenshots\11_env_page.png')
    browser.close()
