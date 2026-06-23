"""Reveal internal database URL by clicking show button"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)

    # Find buttons near the internal-database-url input
    # Look for visibility toggle buttons (eye icon)
    buttons = pg.evaluate('''() => {
        const btns = document.querySelectorAll("button");
        const result = [];
        for (const btn of btns) {
            const html = btn.innerHTML;
            const text = btn.textContent.trim();
            result.push({
                text: text.substring(0, 40),
                html: html.substring(0, 60),
                ariaLabel: btn.getAttribute("aria-label") || "",
                className: btn.className.substring(0, 40),
                visible: btn.offsetParent !== null
            });
        }
        return result;
    }''')
    print('Buttons on page:')
    for b in buttons:
        print(f'  visible={b["visible"]} aria="{b["ariaLabel"]}" html="{b["html"]}" text="{b["text"]}"')

    # Try clicking the show/reveal button near internal database URL
    # The field is type=password with id="internal-database-url"
    # The reveal button should be nearby
    try:
        reveal_btn = pg.locator('button[aria-label*="show"], button[aria-label*="Show"], button[aria-label*="reveal"], button[aria-label*="toggle"]')
        if reveal_btn.count() > 0:
            reveal_btn.first.click()
            print('Clicked reveal button')
            time.sleep(1)
    except:
        print('No aria-label button found')

    # Try clicking any button that has an SVG child (likely eye icon)
    pg.evaluate('''() => {
        const btns = document.querySelectorAll("button");
        for (const btn of btns) {
            if (btn.querySelector("svg") || btn.querySelector("img")) {
                // Check if this button is near the internal-database-url input
                const urlInput = document.getElementById("internal-database-url");
                if (urlInput) {
                    const btnRect = btn.getBoundingClientRect();
                    const inpRect = urlInput.getBoundingClientRect();
                    if (Math.abs(btnRect.top - inpRect.top) < 50) {
                        btn.click();
                        return "Clicked button near internal-database-url";
                    }
                }
            }
        }
        return "No suitable button found";
    }''')

    time.sleep(1)

    # Now get the revealed value
    val = pg.evaluate('() => document.getElementById("internal-database-url")?.value || "not found"')
    print(f'Internal Database URL: {val}')
    
    val2 = pg.evaluate('() => document.getElementById("database-password")?.value || "not found"')
    print(f'Password: {val2}')
    
    val3 = pg.evaluate('() => document.getElementById("external-database-url")?.value || "not found"')
    print(f'External Database URL: {val3}')
    
    val4 = pg.evaluate('() => document.getElementById("psql-command")?.value || "not found"')
    print(f'PSQL Command: {val4}')

    browser.close()
