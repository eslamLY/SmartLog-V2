"""Check more of the deploy log for the actual error"""
import sys, re, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # The failed deploy
    dep_url = 'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8sua11lpprs73flmnbg'
    pg.goto(dep_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    body = pg.inner_text('body')

    # Get the FULL text from the failed deploy event area
    # Find the section after "Exited with status 1"
    idx = body.find('Exited with status 1')
    if idx >= 0:
        # Get surrounding context
        snippet = body[max(0, idx-200):min(len(body), idx+500)]
        print('=== Context around "Exited with status 1" ===')
        print(snippet.replace('\n', '|'))
        print()

    # Look for all ERROR/FATAL lines
    lines = body.split('\n')
    print('=== ERROR lines ===')
    for line in lines:
        if 'ERROR' in line or 'FATAL' in line or 'CRITICAL' in line or 'Traceback' in line:
            print(line.strip())
        if 'exit 1' in line.lower() or 'status 1' in line.lower():
            print(line.strip())

    # Look for the actual crash
    print()
    print('=== All content after "gunicorn app:app" ===')
    g_idx = body.find("Running 'gunicorn app:app'")
    if g_idx >= 0:
        after = body[g_idx:g_idx+2000]
        print(after)

    browser.close()
