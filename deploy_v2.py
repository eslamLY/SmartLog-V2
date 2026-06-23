"""Trigger deploy on Render via CDP"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    page = browser.contexts[0].pages[0]

    # Go to the service page
    page.goto(
        'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
        wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Click "Manual Deploy" button
    try:
        btn = page.locator('button:has-text("Manual Deploy")').first
        if btn.is_visible(timeout=3000):
            print('Found Manual Deploy button, clicking...')
            btn.click()
            time.sleep(2)
        else:
            print('Manual Deploy button not visible')
    except Exception as e:
        print(f'Manual Deploy button error: {e}')

    # Click "Deploy latest commit"
    try:
        deploy_btn = page.locator('button:has-text("Deploy latest commit"), div:has-text("Deploy latest commit")').first
        if deploy_btn.is_visible(timeout=3000):
            print('Clicking Deploy latest commit...')
            deploy_btn.click()
            time.sleep(3)
            print('Deploy triggered!')
        else:
            print('Deploy latest commit not visible')

            # Try alternative: look for the menu item
            menu_item = page.locator('text=Deploy latest commit').first
            if menu_item.is_visible(timeout=2000):
                print('Clicking menu item...')
                menu_item.click()
                time.sleep(3)
                print('Deploy triggered!')
            else:
                print('No deploy option found')
    except Exception as e:
        print(f'Deploy button error: {e}')

    # Check current URL
    print(f'Current URL: {page.url}')

    # Take screenshot
    page.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_screenshots\08_deploy_v2.png')

    browser.close()
