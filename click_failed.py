"""Click deploy entry to see logs"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # Click first Deploy failed entry using JS
    pg.evaluate('''() => {
        const divs = document.querySelectorAll("div");
        for (const d of divs) {
            if (d.textContent.includes("Deploy failed for fa48ce1") &&
                d.textContent.includes("Exited")) {
                d.click();
                return;
            }
        }
    }''')
    time.sleep(4)
    print('Current URL:', pg.url)

    # Look for deploy log content
    body = pg.inner_text('body')
    # Find error messages - look for "Exited with status" context
    if 'Exited with status' in body:
        i = body.index('Exited with status')
        print(f'Exit context: {body[max(0,i-100):i+1000].replace(chr(10), " ")[:500]}')

    # Check every 200 chars for patterns
    for kw in ['Error', 'error', 'Traceback', 'ModuleNotFound', 'ImportError',
               'OperationalError', 'connection', 'DATABASE', 'sqlalchemy']:
        if kw in body:
            i = body.index(kw)
            print(f'{kw}: ...{body[max(0,i-50):i+400].replace(chr(10), " ")}...')

    browser.close()
