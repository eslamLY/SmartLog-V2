"""Add DATABASE_URL env var to SmartLog-V2-1 on Render"""
import sys, time, json
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to env tab
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # Click "Add variable"
    pg.locator('button:has-text("Add variable")').first.click()
    time.sleep(3)

    # Find inputs - there should be Key and Value fields
    inputs_after = pg.evaluate('''() => {
        const all = document.querySelectorAll('input, textarea');
        return Array.from(all).map(el => ({
            id: el.id,
            name: el.name,
            type: el.type,
            placeholder: el.placeholder || '',
            value: (el.value || '').substring(0, 40),
            className: el.className || '',
            rect: el.getBoundingClientRect(),
            visible: el.offsetParent !== null
        }));
    }''')
    print(f'Inputs ({len(inputs_after)}):')
    for inp in inputs_after:
        print(f'  id="{inp["id"]}" type={inp["type"]} placeholder="{inp["placeholder"]}" val="{inp["value"]}"')

    # Try to find key/value fields by placeholder or label
    try:
        key_input = pg.locator('input[placeholder="e.g. DATABASE_URL"]')
        if key_input.is_visible(timeout=2000):
            key_input.fill('DATABASE_URL')
            print('Filled key input')
    except:
        print('No key input with placeholder found')

    try:
        val_input = pg.locator('input[placeholder^="Value"]')
        if val_input.is_visible(timeout=2000):
            val_input.fill('postgresql://smartlog_db_user:lmeG1NNv41Y6WrCRGfuxQ1x5AYQxdlBe@dpg-d8svlqurnols739v473g-a/smartlog_db')
            print('Filled value input')
    except:
        # Try generic text inputs that might be the value field
        inputs = pg.locator('input').all()
        for inp in inputs:
            ph = inp.get_attribute('placeholder') or ''
            if 'value' in ph.lower() or 'val' in ph.lower():
                inp.fill('postgresql://smartlog_db_user:lmeG1NNv41Y6WrCRGfuxQ1x5AYQxdlBe@dpg-d8svlqurnols739v473g-a/smartlog_db')
                print(f'Filled input with placeholder "{ph}"')
                break

    # Look for save/apply button
    time.sleep(2)
    all_buttons = pg.evaluate('''() => {
        const all = document.querySelectorAll('button, a, [role="button"]');
        return Array.from(all).map(el => ({
            tag: el.tagName,
            text: el.textContent.trim().substring(0, 30),
            visible: el.offsetParent !== null,
            disabled: el.disabled || false
        })).filter(b => b.text.length > 0);
    }''')
    print(f'\nButtons ({len(all_buttons)}):')
    for btn in all_buttons:
        print(f'  tag={btn["tag"]} visible={btn["visible"]} disabled={btn["disabled"]} text="{btn["text"]}"')

    browser.close()
