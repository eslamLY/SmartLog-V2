"""Find deploy IDs from the main service page"""
import sys, re, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to main service page
    pg.goto(
        'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
        wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    html = pg.content()

    # Find all href attributes
    hrefs = re.findall(r'href=[\"]([^\"]*)[\"]', html)
    for h in hrefs:
        if 'deploy' in h.lower() or 'dep-' in h.lower():
            print('Link:', h)

    # Also inner text
    body = pg.inner_text('body')
    for kw in ['Deploy failed', 'dep-', 'a07462a', 'Exited with status']:
        if kw in body:
            idx = body.index(kw)
            start = max(0, idx - 30)
            end = min(len(body), idx + 100)
            print(f'Found "{kw}": {body[start:end].replace(chr(10), " ")[:200]}')

    browser.close()
