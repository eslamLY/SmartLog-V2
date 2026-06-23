"""Scroll down and find environment variable inputs"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go directly to environment page
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/environment',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Scroll down
    pg.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    time.sleep(2)

    # Get the full HTML
    html = pg.content()
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\env_page.html', 'w', encoding='utf-8') as f:
        f.write(html)

    # Look for environment variable related elements
    inputs = pg.evaluate('''() => {
        const inputs = document.querySelectorAll('input');
        return Array.from(inputs).map(i => ({
            id: i.id,
            name: i.name,
            placeholder: i.placeholder,
            value: i.value.substring(0, 30),
            type: i.type
        }));
    }''')
    print('Input fields:')
    for inp in inputs:
        print(f'  {inp["id"] or inp["name"]}: type={inp["type"]} placeholder={inp["placeholder"]} value={inp["value"][:30]}')

    # Look for buttons related to env vars
    buttons = pg.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        return Array.from(btns).map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 50);
    }''')
    print('\nButtons:', buttons[:30])

    browser.close()
