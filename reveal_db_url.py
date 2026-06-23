"""Reveal and copy Internal Database URL"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)

    # Click all reveal buttons (they look like buttons with dots/bullets)
    # Find elements with password-like masking
    pg.evaluate('''() => {
        const all = document.querySelectorAll("button, span, div");
        for (const el of all) {
            if (el.textContent.includes("Internal Database URL")) {
                console.log("Found Internal DB URL section");
                // Click nearby reveal/copy buttons
                const parent = el.closest("div");
                if (parent) {
                    const btns = parent.querySelectorAll("button");
                    console.log("Buttons in section:", btns.length);
                }
            }
        }
    }''')

    # Take a screenshot to see the layout
    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\db_screen.png')
    print('Screenshot saved')

    # Get full HTML of connections section
    html = pg.evaluate('''() => {
        const allText = document.body.innerText;
        // Find the section around Internal Database URL
        const idx = allText.indexOf("Internal Database URL");
        if (idx >= 0) {
            return allText.substring(Math.max(0, idx - 100), idx + 1000);
        }
        return "Not found";
    }''')
    print('\nSection around Internal DB URL:')
    print(html.replace(chr(10), '\n'))

    browser.close()
