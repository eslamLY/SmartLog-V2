"""Click Edit to add another env var"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Click "Edit" button
    pg.locator('button:has-text("Edit")').click()
    print('Clicked Edit')
    time.sleep(3)

    # Now look at the page
    body = pg.inner_text('body')
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\env_after_edit.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Find form elements
    inputs = pg.evaluate('''() => {
        const inputs = document.querySelectorAll("input, textarea, select");
        return Array.from(inputs).map(inp => ({
            id: inp.id,
            type: inp.type,
            value: (inp.value || "").substring(0, 50),
            placeholder: (inp.placeholder || "").substring(0, 50),
            visible: inp.offsetParent !== null
        }));
    }''')
    print('\nForm inputs:')
    for inp in inputs:
        print(f'  id="{inp["id"]}" type={inp["type"]} val="{inp["value"]}" ph="{inp["placeholder"]}" visible={inp["visible"]}')

    # Also check for all visible input fields
    buttons = pg.evaluate('''() => {
        const btns = document.querySelectorAll("button");
        return Array.from(btns).filter(b => b.offsetParent !== null).map(b => ({
            text: b.textContent.trim().substring(0, 50),
            disabled: b.disabled
        }));
    }''')
    print('\nVisible buttons:')
    for b in buttons:
        print(f'  "{b["text"]}" disabled={b["disabled"]}')

    browser.close()
