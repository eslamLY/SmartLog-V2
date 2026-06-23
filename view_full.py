"""Get full deploy log text for ce5ba49"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    dep_url = 'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8sugn3o8ins73bdd1ug'
    pg.goto(dep_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(10)

    body = pg.inner_text('body')
    print('Body length:', len(body))
    print()

    # Print the entire body
    print(body)

    browser.close()
