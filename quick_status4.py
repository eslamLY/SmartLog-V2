import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    print('URL:', pg.url)
    body = pg.inner_text('body')
    if 'Failed' in body:
        i = body.index('Failed')
        print('Failed:', body[i:i+200].replace('\n',' '))
    elif 'Live' in body:
        i = body.index('Live')
        print('Live:', body[i:i+200].replace('\n',' '))
    elif 'Deploying' in body:
        i = body.index('Deploying')
        print('Deploying:', body[i:i+200].replace('\n',' '))
    else:
        print('No status keyword found')
        # Look for fa48ce1
        if 'fa48ce1' in body:
            i = body.index('fa48ce1')
            print('fa48ce1 context:', body[i:i+200].replace('\n',' '))
    browser.close()
