"""Verify all endpoints resist SQL injection attempts."""
import json
from app import db
from sqlalchemy import text


SQLI_PAYLOADS = [
    "' OR '1'='1",
    "1; DROP TABLE employees; --",
    "' UNION SELECT * FROM users; --",
    "admin'--",
    "1 OR 1=1",
    "'; SELECT pg_sleep(5); --",
    "1' AND 1=1; SELECT * FROM employees; --",
    "'; EXEC xp_cmdshell('dir'); --",
    "1' WAITFOR DELAY '0:0:5'--",
]


def test_login_sql_injection_resists_all_payloads(client):
    """Login endpoint must reject SQL injection payloads in username."""
    for idx, payload in enumerate(SQLI_PAYLOADS):
        resp = client.post('/login', data=json.dumps({'username': payload, 'password': 'test'}),
                           content_type='application/json')
        data = resp.get_json()
        assert resp.status_code in (200, 429), f"SQLi payload '{payload}' returned {resp.status_code}"
        if resp.status_code == 200:
            assert data['ok'] is False, f"SQLi payload '{payload}' should not authenticate"
            assert 'msg' in data


def test_employee_list_sql_injection(client):
    """Employee list search must resist SQL injection."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    for payload in SQLI_PAYLOADS:
        resp = client.get(f'/admin/employees?q={payload}')
        assert resp.status_code == 200


def test_clock_in_sql_injection(client):
    """Clock-in GPS coordinates must resist injection."""
    login_resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    for payload in ["' OR '1'='1", "DROP TABLE", "<script>"]:
        resp = client.post('/employee/clockin', data=json.dumps({'lat': payload, 'lng': 23.0}),
                           content_type='application/json')
        data = resp.get_json()
        assert data['ok'] is False, f"Clock-in with lat='{payload}' should fail"


def test_gps_log_sql_injection(client):
    """GPS log endpoint must resist injection in lat/lng."""
    login_resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    for payload in ["1; DROP TABLE gps_logs;", "' OR 1=1; --"]:
        resp = client.post('/employee/gps/log', data=json.dumps({'lat': 32.0, 'lng': payload}),
                           content_type='application/json')
        data = resp.get_json()
        assert data['ok'] is False, f"GPS log with lng='{payload}' should fail"


def test_add_employee_sql_injection(client):
    """Add employee endpoint must resist injection in name fields."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    for idx, payload in enumerate(SQLI_PAYLOADS):
        resp = client.post('/admin/employees/add', data=json.dumps({
            'username': f'INJ{idx}',
            'full_name': payload,
            'department_id': 1,
            'role': 'employee',
            'salary': 1000,
            'password': 'SecurePass1'
        }), content_type='application/json')
        assert resp.status_code == 200, f"Add employee with name='{payload}' should not crash"
