"""Try admin login"""
import sys, time, json
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://smartlog-v2-1.onrender.com/login', wait_until='networkidle', timeout=120000)
    time.sleep(2)

    # Try admin login
    pg.fill('#username', 'ADM001')
    pg.fill('#password', 'admin123')
    pg.click('#loginBtn')
    time.sleep(5)

    url = pg.url
    body = pg.inner_text('body')
    print(f'URL after login: {url}')
    print(f'Redirected: {"تسجيل الدخول" not in url}')

    # Check for error
    if 'بيانات خاطئة' in body:
        print('Wrong credentials')
    elif 'الاتصال بالخادم' in body:
        print('CONNECTION ERROR')
    else:
        print(f'Current page title: {pg.title()}')
        print(f'Body: {body[:300]}')

    browser.close()
