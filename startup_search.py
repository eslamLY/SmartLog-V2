"""Search for startup messages in deploy logs"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8t01467r5hc73ebj27g',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(6)

    # Get all text that looks like log entries (between timestamps)
    all_main_text = pg.evaluate('''() => {
        const main = document.querySelector("main");
        if (!main) return document.body.innerText;
        return main.innerText;
    }''')
    
    # Search for startup related keywords
    for kw in ['starting', 'SmartLog', 'DATABASE_URL', 'DB connection', 'PASSED',
               'Tables', 'create_all', 'seed', 'startup', 'ready to serve',
               'complete', 'loaded', 'degraded', 'configured', 'skipped']:
        if kw in all_main_text:
            i = all_main_text.index(kw)
            ctx = all_main_text[max(0,i-50):i+300].replace(chr(10), ' ')
            print(f'{kw}: {ctx}')
            print('---')

    # Also look for "INFO" patterns (log lines)
    lines = all_main_text.split('\n')
    info_lines = [l.strip() for l in lines if 'INFO' in l or 'WARNING' in l or 'ERROR' in l]
    print(f'\nTotal log-like lines: {len(info_lines)}')
    for line in info_lines[:30]:
        print(f'  {line[:200]}')

    browser.close()
