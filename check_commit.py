"""Check if GitHub commit was made"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://github.com/eslamLY/SmartLog-V2/commits/main',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Get the latest commit message
    commits = pg.evaluate('''() => {
        const items = document.querySelectorAll("[class*='commit'] a, [data-testid*='commit'] a");
        const results = [];
        for (const a of items) {
            const text = a.textContent.trim();
            if (text.length > 5) {
                results.push(text);
            }
        }
        return results.slice(0, 5);
    }''')
    print('Recent commits:')
    for c in commits:
        print(f'  {c[:80]}')

    # Also try to get commit messages from list
    body = pg.inner_text('body')
    # Look for commit messages
    lines = [l.strip() for l in body.split('\n') if l.strip() and ('init-db' in l.lower() or 'fix:' in l.lower() or 'add' in l.lower())]
    for l in lines[:10]:
        print(f'  {l[:80]}')

    browser.close()
