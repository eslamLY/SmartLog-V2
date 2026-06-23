"""Get full deploy page text for ce5ba49"""
import sys, time, re
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    dep_url = 'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8sugn3o8ins73bdd1ug'
    pg.goto(dep_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(8)  # Give extra time for React to render

    # Get the page title/heading area
    body = pg.inner_text('body')

    # Save to file for analysis
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_ce5ba49.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    print('Full body length:', len(body))
    print()

    # Look for the deploy section that shows status
    # Find lines with "Failed", "Live", etc
    for line in body.split('\n'):
        stripped = line.strip()
        if any(kw in stripped for kw in ['Failed', 'Live', 'Building', 'Deploy', 'status',
                                          'Exited', 'exit', 'error', 'Error', 'Cancel',
                                          'INFO', 'ERROR', 'WARNING']):
            print(stripped[:200])

    browser.close()
