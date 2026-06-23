"""Simulate user login from browser"""
import sys, time, json
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Open login page
    pg.goto('https://smartlog-v2-1.onrender.com/login', wait_until='networkidle', timeout=120000)
    time.sleep(3)
    print('Login page loaded')
    print('Title:', pg.title())
    
    # Take screenshot
    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\login_page.png')

    # Try to log in with credentials
    pg.fill('#username', 'EMP001')
    pg.fill('#password', 'password123')
    print('Filled credentials')

    # Click login button
    pg.click('#loginBtn')
    print('Clicked login button')

    # Wait for response
    time.sleep(5)

    # Check page content
    body = pg.inner_text('body')
    print(f'Page body length: {len(body)}')
    
    # Look for error message
    if 'الاتصال بالخادم' in body:
        i = body.index('الاتصال بالخادم')
        print(f'Connection error found: {body[i:i+100]}')
    elif 'بيانات خاطئة' in body:
        i = body.index('بيانات خاطئة')
        print(f'Wrong data error: {body[i:i+100]}')
    elif 'تجاوزت' in body:
        i = body.index('تجاوزت')
        print(f'Rate limit error: {body[i:i+100]}')
    else:
        print('No known error found')
        print('Body:', body[:500])

    browser.close()
