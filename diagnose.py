"""Full diagnostic of both services"""
import sys, json, urllib.request
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')

services = [
    'https://smartlog-v2.onrender.com',
    'https://smartlog-v2-1.onrender.com',
]

for url in services:
    print(f'\n=== {url} ===')

    # Health
    try:
        req = urllib.request.Request(f'{url}/api/health')
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        print(f'  Health: {resp.status} - db={data.get("database")} status={data.get("status")}')
    except Exception as e:
        print(f'  Health ERROR: {e}')

    # Main page
    try:
        req = urllib.request.Request(f'{url}/')
        resp = urllib.request.urlopen(req, timeout=30)
        body = resp.read().decode()
        has_login = 'تسجيل الدخول' in body
        print(f'  Main page: {resp.status} - login_text={has_login}')
    except Exception as e:
        print(f'  Main page ERROR: {e}')

    # Login POST with valid credentials
    try:
        login_data = json.dumps({"username": "EMP001", "password": "test"}).encode()
        req = urllib.request.Request(f'{url}/login', data=login_data,
            headers={'Content-Type': 'application/json'}, method='POST')
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        print(f'  Login POST: {resp.status} - ok={data.get("ok")} msg={data.get("msg","")[:50]}')
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'  Login POST ERROR {e.code}: {body[:100]}')
    except Exception as e:
        print(f'  Login POST ERROR: {e}')

print('\n=== Done ===')
