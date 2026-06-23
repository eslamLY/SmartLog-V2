"""Click show secret buttons to reveal DB credentials"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a', wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Click all "Show secret" buttons (eye icon) to reveal hidden values
    show_btns = pg.locator('button[aria-label="Show secret"]')
    count = show_btns.count()
    print(f'Found {count} Show secret buttons')
    for i in range(count):
        btn = show_btns.nth(i)
        if btn.is_visible(timeout=2000):
            btn.click()
            time.sleep(0.5)
            print(f'Clicked button {i+1}')

    time.sleep(1)

    # Now read the revealed values
    inputs = pg.evaluate('''() => {
        const fields = ['database-hostname', 'database-port', 'database-name', 'database-username',
                        'database-password', 'internal-database-url', 'external-database-url', 'psql-command'];
        const result = {};
        for (const id of fields) {
            const el = document.getElementById(id);
            if (el) result[id] = el.value;
        }
        return result;
    }''')
    for k, v in inputs.items():
        print(f'{k}: {v}')

    browser.close()
