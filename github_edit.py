"""Create commit via GitHub web interface"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to GitHub edit page for routes/auth.py on main branch
    pg.goto('https://github.com/eslamLY/SmartLog-V2/blob/main/routes/auth.py',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)
    print(f'URL: {pg.url}')
    print(f'Title: {pg.title()}')

    # Check if we're on the file page
    body = pg.inner_text('body')
    if 'Edit' in body:
        print('Edit button found')
        # Click Edit button
        pg.locator('a:has-text("Edit")').first.click()
        time.sleep(4)
        print(f'After edit click: {pg.url}')

        # Now at the editor - we need to modify the file
        # Look for the editor textarea
        try:
            editor = pg.locator('textarea, .cm-content, [contenteditable="true"]').first
            if editor.is_visible(timeout=3000):
                print('Editor found')
                # We need a different approach - GitHub uses CodeMirror
        except:
            pass

    browser.close()
