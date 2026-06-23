"""Check if DB is ready and get connection string"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    body = pg.inner_text('body')
    for kw in ['Internal Database URL', 'External Database URL', 'postgres://', 'Connection',
               'Hostname', 'Port', 'Database', 'Username', 'Password']:
        if kw in body:
            i = body.index(kw)
            snippet = body[i:i+200].replace('\n', ' ')
            print(f'{kw}: {snippet}')
    if 'Creating' in body:
        i = body.index('Creating')
        print(f'\nStatus: {body[i:i+100].replace(chr(10), " ")}')
    if 'Ready' in body:
        i = body.index('Ready')
        print(f'\nStatus: {body[i:i+100].replace(chr(10), " ")}')
    browser.close()
