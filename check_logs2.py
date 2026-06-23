"""Check latest deploy runtime logs"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8t01467r5hc73ebj27g',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(6)

    # Try multiple scrolls to load log content
    for i in range(5):
        pg.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(1)

    # Get log section (main content or log viewer)
    log_text = pg.evaluate('''() => {
        // Try to find the log viewer section
        const selectors = ["[class*='log']", "[class*='Log']", "main", 
                           "[class*='terminal']", "[class*='build']", "pre", "code"];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.innerText.length > 500) {
                return {found: sel, text: el.innerText.substring(0, 10000)};
            }
        }
        return {found: "none", text: document.body.innerText.substring(0, 5000)};
    }''')
    
    print(f'Log source: {log_text["found"]}')
    print('Log content:')
    print(log_text["text"][:5000])
    
    # Search for key messages
    text = log_text["text"]
    for kw in ['seed', 'Seed', 'Startup', 'Tables', 'create_all', 
               'database connection', 'PASSED', 'complete', 'ready',
               'FATAL', 'ERROR', 'WARNING', 'loaded', 'skipped',
               'migrate', 'upgrade', 'SmartLog']:
        if kw in text:
            i = text.index(kw)
            print(f'\n{kw}: ...{text[max(0,i-30):i+200]}...')

    browser.close()
