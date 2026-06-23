"""Full browser login test"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # 1. Open login page
    pg.goto('https://smartlog-v2-1.onrender.com/login', wait_until='networkidle', timeout=120000)
    time.sleep(2)
    print('1. Login page loaded')

    # 2. Fill admin credentials
    pg.fill('#username', 'ADM001')
    pg.fill('#password', 'admin123')
    print('2. Filled admin credentials')

    # 3. Click login
    pg.click('#loginBtn')
    time.sleep(5)
    print(f'3. After login URL: {pg.url}')

    # 4. Check if redirected to admin dashboard
    if '/admin' in pg.url:
        print('4. SUCCESS: Redirected to admin dashboard!')
    else:
        print(f'4. Current page: {pg.title()}')
        body = pg.inner_text('body')
        if 'الاتصال' in body:
            i = body.index('الاتصال')
            print(f'Error: {body[max(0,i-20):i+100]}')
        else:
            print(f'Body: {body[:300]}')

    # 5. Test employee login in new page
    pg2 = browser.contexts[0].new_page()
    pg2.goto('https://smartlog-v2-1.onrender.com/login', wait_until='networkidle', timeout=120000)
    time.sleep(2)
    pg2.fill('#username', 'EMP001')
    pg2.fill('#password', '123456')
    pg2.click('#loginBtn')
    time.sleep(5)
    print(f'\n5. Employee login URL: {pg2.url}')
    if '/employee' in pg2.url:
        print('6. SUCCESS: Employee redirected to dashboard!')
    pg2.close()

    browser.close()
