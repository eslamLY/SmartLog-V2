"""Add SECRET_KEY env var (JS approach)"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Click Add variable via JS
    pg.evaluate('''() => {
        const btns = document.querySelectorAll("button");
        for (const b of btns) {
            if (b.textContent.includes("Add variable")) {
                b.click();
                return;
            }
        }
    }''')
    print('Clicked Add variable')
    time.sleep(3)

    # Fill key
    pg.evaluate('''() => {
        const inputs = document.querySelectorAll("input");
        for (const inp of inputs) {
            if (inp.placeholder === "NAME_OF_VARIABLE") {
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, "value"
                ).set;
                nativeInputValueSetter.call(inp, "SECRET_KEY");
                inp.dispatchEvent(new Event("input", { bubbles: true }));
                inp.dispatchEvent(new Event("change", { bubbles: true }));
                return;
            }
        }
    }''')
    print('Filled key')

    # Fill value
    pg.evaluate('''() => {
        const textareas = document.querySelectorAll("textarea");
        for (const ta of textareas) {
            if (ta.placeholder === "value") {
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, "value"
                ).set;
                nativeInputValueSetter.call(ta, "7342b54eec91b8724e6f309532ebfc9c4737bca772a7acb973f118a2e8c48039");
                ta.dispatchEvent(new Event("input", { bubbles: true }));
                ta.dispatchEvent(new Event("change", { bubbles: true }));
                return;
            }
        }
    }''')
    print('Filled value')

    time.sleep(1)

    # Click Save, rebuild, and deploy
    pg.evaluate('''() => {
        const btns = document.querySelectorAll("button");
        for (const b of btns) {
            if (b.textContent.includes("Save, rebuild, and deploy")) {
                b.click();
                return;
            }
        }
    }''')
    print('Clicked Save')

    time.sleep(3)
    print(f'URL: {pg.url}')
    browser.close()
