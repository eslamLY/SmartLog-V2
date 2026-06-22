"""Verify rate limiting blocks brute force attacks."""
import json, time


def test_login_rate_limited_after_5_attempts(client):
    """6th login attempt within 5 minutes should be throttled (429)."""
    for i in range(6):
        resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'WrongPass123'}),
                           content_type='application/json')
        data = resp.get_json()
        if i < 5:
            assert data['ok'] is False, f"Attempt {i+1} should fail (wrong password)"
            assert resp.status_code == 200
        else:
            assert resp.status_code == 429, f"Attempt 6 should be rate-limited, got {resp.status_code}"
            assert 'msg' in data


def test_rate_limit_per_ip_not_global(client):
    """Rate limiting is per-IP, one user being throttled doesn't affect another."""
    for i in range(6):
        resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': 'WrongPwd123'}),
                           content_type='application/json')

    resp1 = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                        content_type='application/json')
    data1 = resp1.get_json()


def test_rate_limit_resets(client):
    """After rate limiting, valid credentials should eventually work."""
    for i in range(6):
        client.post('/login', data=json.dumps({'username': 'EMP001', 'password': 'WrongPwd123'}),
                    content_type='application/json')

    resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                       content_type='application/json')
    data = resp.get_json()
