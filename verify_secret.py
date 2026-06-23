"""Verify SECRET_KEY was saved"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/env',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    body = pg.inner_text('body')
    print('Body contains SECRET_KEY:', 'SECRET_KEY' in body)
    print('Body contains DATABASE_URL:', 'DATABASE_URL' in body)

    if 'SECRET_KEY' in body:
        i = body.index('SECRET_KEY')
        print(f'SECRET_KEY context: {body[max(0,i-10):i+80].replace(chr(10), " ")}')

    # Check if there's a "More options" or existing vars list
    # Look for key-value pairs
    for kw in ['SECRET_KEY', 'DATABASE_URL', 'KEY', 'VALUE']:
        if kw in body:
            i = body.index(kw)
            print(f'{kw}: ...{body[max(0,i-5):i+100].replace(chr(10), " ")}...')

    browser.close()
