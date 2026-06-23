"""Check env page state and add SECRET_KEY"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Get ALL visible text
    body = pg.inner_text('body')

    # Check for existing env vars
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\env_state.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Count occurrences of KEY, Key, key
    for kw in ['KEY', 'VARIABLE', 'DATABASE', 'SECRET', 'Save, rebuild', 'Cancel', 'Add variable']:
        if kw in body:
            cnt = body.count(kw)
            print(f'{kw}: {cnt} occurrences')

    # Look at the buttons currently on the page
    buttons = pg.evaluate('''() => {
        const btns = document.querySelectorAll("button");
        return Array.from(btns).filter(b => b.offsetParent !== null).map(b => ({
            text: b.textContent.trim().substring(0, 50),
            disabled: b.disabled
        }));
    }''')
    print('\nVisible buttons:')
    for b in buttons:
        print(f'  {b["text"]} (disabled={b["disabled"]})')

    browser.close()
