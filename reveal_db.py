"""Get the actual connection string from the DB page"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Try clicking "Connections" or the section
    try:
        conn_tab = pg.locator('text=Connections').first
        if conn_tab.is_visible(timeout=3000):
            conn_tab.click()
            time.sleep(2)
            print('Clicked Connections')
    except:
        pass

    # Try to find and click reveal/show password buttons
    try:
        show_btns = pg.locator('button:has-text("SHOW"), button:has-text("show"), button:has-text("Show"), button:has-text("\u25cf")').all()
        print(f'Found {len(show_btns)} show buttons')
        for btn in show_btns[:5]:
            if btn.is_visible(timeout=2000):
                print(f'Clicking button: {btn.text_content()[:50]}')
                btn.click()
                time.sleep(1)
    except:
        pass

    # Try clicking "OPEN" buttons
    try:
        open_btns = pg.locator('button:has-text("OPEN"), a:has-text("OPEN")').all()
        print(f'Found {len(open_btns)} OPEN buttons')
        for btn in open_btns[:5]:
            if btn.is_visible(timeout=2000):
                print(f'Clicking OPEN: {btn.text_content()[:50]}')
                btn.click()
                time.sleep(1)
    except:
        pass

    # Get the page HTML
    html = pg.content()
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\db_page.html', 'w', encoding='utf-8') as f:
        f.write(html)

    body = pg.inner_text('body')
    print()
    print('=== Full body ===')
    print(body)

    # Look for postgres:// pattern in HTML
    import re
    urls = re.findall(r'postgres://[^"\'\s<>]+', html)
    print(f'\nFound {len(urls)} postgres URLs')
    for u in urls:
        print(u)

    browser.close()
