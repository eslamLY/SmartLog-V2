from tests.helpers import login, logout
from datetime import datetime, timedelta, UTC

def test_login_success(client):
    r = login(client, 'ADM001', 'admin123')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True

def test_login_fail_wrong_password(client):
    r = login(client, 'ADM001', 'wrong')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is False

def test_login_fail_nonexistent(client):
    r = login(client, 'NONEXIST', 'pwd')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is False

def test_login_required_blocks_anonymous(client):
    r = client.get('/admin')
    assert r.status_code == 302

def test_health_is_public(client):
    r = client.get('/api/health')
    assert r.status_code == 200

def test_logout(client):
    login(client)
    r = logout(client)
    assert r.status_code == 302

def test_admin_required_blocks_employee(client):
    login(client, 'EMP001', '123456')
    r = client.get('/admin')
    assert r.status_code == 302

def test_session_timeout(client):
    login(client)
    with client.session_transaction() as s:
        s['last_activity'] = (datetime.now(UTC) - timedelta(seconds=1000)).isoformat()
    r = client.get('/admin')
    assert r.status_code == 302

def test_security_headers_not_in_dev(client):
    """Dev mode must NOT inject HSTS/XCTO/XFO headers."""
    r = client.get('/api/health')
    assert 'Strict-Transport-Security' not in r.headers
    assert 'X-Content-Type-Options' not in r.headers
    assert 'X-Frame-Options' not in r.headers
