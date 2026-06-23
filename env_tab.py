"""Navigate to Environment tab properly"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to service page first, then click Environment tab
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Try clicking Environment in the sidebar
    env_tab = pg.locator('a:has-text("Environment"), span:has-text("Environment"), div:has-text("Environment")').first
    print('Trying Environment tab...')
    if env_tab.is_visible(timeout=3000):
        env_tab.click()
        time.sleep(5)
        print('New URL:', pg.url)
        body = pg.inner_text('body')
        print('Body:', body[:3000])
    else:
        print('Environment tab not found in sidebar')
        # Try the main navigation
        env_link = pg.locator('a[href*="environment"]').first
        if env_link.is_visible(timeout=2000):
            env_link.click()
            time.sleep(5)
            print('New URL (from href):', pg.url)
            body = pg.inner_text('body')
            print('Body:', body[:3000])

    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_screenshots\12_env_tab.png')
    browser.close()
