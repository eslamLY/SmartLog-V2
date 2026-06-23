"""Trigger deploy for latest commit (525a372)"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    page = browser.contexts[0].pages[0]

    page.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
              wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Click Manual Deploy
    try:
        btn = page.locator('button:has-text("Manual Deploy")').first
        if btn.is_visible(timeout=3000):
            btn.click()
            time.sleep(2)
    except:
        pass

    # Click Deploy latest commit
    try:
        deploy_btn = page.locator('text=Deploy latest commit').first
        if deploy_btn.is_visible(timeout=3000):
            deploy_btn.click()
            time.sleep(3)
            print('Deploy triggered!')
    except:
        pass

    page.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_screenshots\09_deploy_v3.png')
    browser.close()
