"""Clear login attempts and test login"""
import sys, json, urllib.request
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')

EXTERNAL_DB_URL = 'postgresql+pg8000://smartlog_db_user:lmeG1NNv41Y6WrCRGfuxQ1x5AYQxdlBe@dpg-d8svlqurnols739v473g-a.frankfurt-postgres.render.com/smartlog_db'

from sqlalchemy import create_engine, text
engine = create_engine(EXTERNAL_DB_URL)

with engine.connect() as conn:
    result = conn.execute(text("DELETE FROM login_attempts"))
    conn.commit()
    print(f'Cleared login attempts')

engine.dispose()

# Now test login
url = 'https://smartlog-v2-1.onrender.com/login'

for creds in [('ADM001', 'admin123'), ('EMP001', '123456')]:
    data = json.dumps({'username': creds[0], 'password': creds[1]}).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        resp = json.loads(r.read())
        print(f'{creds[0]} login: {json.dumps(resp, ensure_ascii=False)}')
    except urllib.error.HTTPError as e:
        print(f'{creds[0]} login HTTP {e.code}: {e.read().decode()[:200]}')
