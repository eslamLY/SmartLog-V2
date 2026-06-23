"""Find PostgreSQL database info in Render dashboard"""
import sys, time, re
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Check if there's a Databases section
    pg.goto('https://dashboard.render.com/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    body = pg.inner_text('body')
    print('Dashboard text:')
    print(body[:2000])

    # Look for database-related links
    html = pg.content()
    links = re.findall(r'href="([^"]*)"', html)
    db_links = [l for l in links if 'databas' in l.lower() or 'postgres' in l.lower() or 'redis' in l.lower()]
    print('\nDB links:', db_links)

    browser.close()
