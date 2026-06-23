import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    body = pg.inner_text('body')
    # Find what's live now
    for kw in ['Live', 'Deploy live', 'Currently live', 'Current deploy']:
        if kw in body:
            i = body.index(kw)
            print(f'{kw}: {body[i:i+300].replace(chr(10)," ")}')
    # Find any "fa48ce1" with Live context
    if 'fa48ce1' in body:
        i = body.index('fa48ce1')
        before = body[max(0,i-100):i]
        after = body[i:i+300]
        print(f'\nfa48ce1 context: ...{before.replace(chr(10)," ")[-100:]} | {after.replace(chr(10)," ")[:300]}')
    browser.close()
