"""Check the failed deploy log"""
import sys, re, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Open the failed deploy page
    dep_url = 'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8sua11lpprs73flmnbg'
    pg.goto(dep_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Click on Logs tab or any deploy-related section
    html = pg.content()

    # Save the HTML to examine
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_page.html', 'w', encoding='utf-8') as f:
        f.write(html)

    # Get all text
    body = pg.inner_text('body')
    print('=== Page text (first 2000 chars) ===')
    print(body[:2000])
    print()
    print('=== Looking for error keywords ===')
    for kw in ['Traceback', 'ImportError', 'ModuleNotFound', 'FATAL',
               'SyntaxError', 'exit 1', 'No module', 'Error:',
               'permission denied', 'not found', '/entrypoint',
               'gunicorn', 'flask db', 'DATABASE_URL',
               'pip install', 'pip', 'requirements',
               'Step', 'RUN', 'COPY',
               'Successfully built', 'Successfully tagged']:
        if kw.lower() in body.lower():
            # Find all occurrences
            idxs = [m.start() for m in re.finditer(re.escape(kw), body, re.IGNORECASE)]
            for idx in idxs[:3]:  # Max 3 occurrences
                start = max(0, idx - 80)
                end = min(len(body), idx + 200)
                snippet = body[start:end].replace('\n', ' ')[:300]
                print(f'  [{kw}]: ...{snippet}...')

    browser.close()
