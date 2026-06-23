"""Screenshot env page and find Add variable"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Screenshot
    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\env_screen.png', full_page=True)
    print('Screenshot saved')

    # Get ALL elements including those with zero size or offscreen
    all_buttons = pg.evaluate('''() => {
        const all = document.querySelectorAll("button, a, [role='button']");
        return Array.from(all).map(el => ({
            text: el.textContent.trim().substring(0, 60),
            tag: el.tagName,
            rect: el.getBoundingClientRect(),
            visible: el.offsetParent !== null
        })).filter(e => e.text.includes("variable") || e.text.includes("Variable") ||
                       e.text.includes("Add") || e.text.includes("add") ||
                       e.text.includes("Save"));
    }''')
    print('\nVariable/Save related elements:')
    for el in all_buttons:
        print(f'  {el["tag"]} visible={el["visible"]} rect={el["rect"]} text="{el["text"]}"')

    # Also search page for "Add variable" in text
    body = pg.inner_text('body')
    idx = body.find('Add variable')
    if idx >= 0:
        print(f'\n"Add variable" found at position {idx}')
        print(f'Context: {body[max(0,idx-50):idx+100].replace(chr(10), " ")}')
    else:
        print('\n"Add variable" NOT found in body text')

    # Maybe it's behind a "More options" menu?
    more_options = pg.locator('button:has-text("More options")')
    if more_options.count() > 0:
        print(f'\nFound {more_options.count()} "More options" buttons')
        more_options.first.click()
        time.sleep(2)
        body2 = pg.inner_text('body')
        print('After clicking More options:')
        if 'Add variable' in body2:
            print('  "Add variable" now visible!')
        # Find what appeared
        menu_items = pg.evaluate('''() => {
            const all = document.querySelectorAll("button, a, [role='button'], [role='menuitem']");
            return Array.from(all).filter(el => el.offsetParent !== null).map(el => ({
                text: el.textContent.trim().substring(0, 60),
                tag: el.tagName
            }));
        }''')
        for item in menu_items:
            print(f'  {item["tag"]}: "{item["text"]}"')

    browser.close()
