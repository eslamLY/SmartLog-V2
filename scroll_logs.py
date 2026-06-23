"""Scroll and check deploy log fully"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8t01467r5hc73ebj27g',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Try to scroll log content area
    pg.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    time.sleep(3)
    pg.evaluate('window.scrollTo(0, 0)')
    time.sleep(2)

    # Get full body
    body = pg.inner_text('body')
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\live_deploy_full.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Try to find any text content between timestamps
    log_section = pg.evaluate('''() => {
        const main = document.querySelector("main");
        if (main) return main.innerText;
        // Try other common log containers
        for (const sel of ["[class*='log']", "[class*='Log']", "pre", "code"]) {
            const el = document.querySelector(sel);
            if (el) return el.innerText.substring(0, 5000);
        }
        return "No log container found";
    }''')
    print('Log content:')
    print(log_section[:2000])

    browser.close()
