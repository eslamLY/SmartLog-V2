"""Try to extract connection string from page HTML"""
import sys, time, re
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Get full HTML and save it
    html = pg.content()
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\db_full.html', 'w', encoding='utf-8') as f:
        f.write(html)

    # Try to click on each connection label to reveal value
    for label in ['Hostname', 'Port', 'Database', 'Username', 'Password', 'Internal Database URL', 'External Database URL']:
        try:
            el = pg.locator(f'text={label}').first
            if el.is_visible(timeout=2000):
                el.click()
                time.sleep(0.5)
        except:
            pass

    # After clicking, get text again
    body = pg.inner_text('body')
    time.sleep(2)
    body2 = pg.inner_text('body')

    # Also try getting all input values
    inputs = pg.evaluate('''() => {
        const inputs = document.querySelectorAll('input');
        return Array.from(inputs).map(i => ({id: i.id, name: i.name, value: i.value, type: i.type, placeholder: i.placeholder}));
    }''')
    print('Inputs:')
    for inp in inputs:
        if inp['value']:
            print(f"  {inp['name'] or inp['id']}: {inp['value']}")

    # Look for any element with postgres://
    elements_with_url = pg.evaluate('''() => {
        const all = document.querySelectorAll('*');
        const results = [];
        for (const el of all) {
            if (el.textContent && el.textContent.includes('postgres://')) {
                results.push(el.tagName + ': ' + el.textContent.substring(0, 200));
            }
        }
        return results.slice(0, 10);
    }''')
    print('\nElements with postgres://:')
    for el in elements_with_url:
        print(f'  {el}')

    browser.close()
