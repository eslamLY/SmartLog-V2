"""Extract full deploy log content"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8svq87avr4c738jhdn0',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)

    # Look for the log viewer panel - it might be a div with class containing "log"
    log_html = pg.evaluate('''() => {
        const els = document.querySelectorAll("div, pre, code, section");
        const logs = [];
        for (const el of els) {
            const text = el.textContent;
            if (text.includes("03:28:46") || text.includes("INFO") ||
                text.includes("ERROR") || text.includes("WARNING") ||
                text.includes("Traceback") || text.includes("Exception") ||
                text.includes("connect") || text.includes("refused")) {
                logs.push({
                    tag: el.tagName,
                    text: text.substring(0, 200),
                    rect: el.getBoundingClientRect(),
                    visible: el.offsetParent !== null
                });
            }
        }
        return logs;
    }''')
    print(f'Found {len(log_html)} log-like elements')

    # Scroll down to load more logs
    for _ in range(10):
        pg.evaluate('window.scrollBy(0, 500)')
        time.sleep(0.5)

    time.sleep(2)

    # Get full body text
    body = pg.inner_text('body')
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_full.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Extract the log section specifically
    # Look for patterns in the log
    log_lines = [l.strip() for l in body.split('\n') if l.strip()]

    # Find lines with important patterns
    for line in log_lines:
        if any(kw in line for kw in ['ERROR', 'Traceback', 'Exception', 'exit', 'Exit',
                                      'sqlalchemy', 'connection', 'refused', 'timeout',
                                      'FATAL', 'could not connect', 'OperationalError',
                                      'SSL', 'ssl']):
            print(f'  {line[:300]}')

    browser.close()
