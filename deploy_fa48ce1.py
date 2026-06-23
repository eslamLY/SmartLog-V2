import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030', wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    btn = pg.locator('button:has-text("Manual Deploy")').first
    if btn.is_visible(timeout=3000): btn.click(); time.sleep(2)
    dep = pg.locator('text=Deploy latest commit').first
    if dep.is_visible(timeout=3000): dep.click(); print('Deploy triggered!')
    browser.close()
