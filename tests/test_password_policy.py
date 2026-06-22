"""Verify password policy is enforced on creation and changes."""
import json


def test_password_too_short(client):
    """Password < 8 chars must be rejected."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    resp = client.post('/admin/employees/add', data=json.dumps({
        'username': 'NEW001', 'full_name': 'جديد', 'department_id': 1,
        'role': 'employee', 'salary': 2000, 'password': 'Ab1'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is False
    assert '8' in data['msg'] or 'أحرف' in data['msg']


def test_password_no_uppercase(client):
    """Password without uppercase must be rejected."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    resp = client.post('/admin/employees/add', data=json.dumps({
        'username': 'NEW002', 'full_name': 'جديد', 'department_id': 1,
        'role': 'employee', 'salary': 2000, 'password': 'lowercase123'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is False
    assert 'كبير' in data['msg'] or 'large' in data['msg'].lower()


def test_password_no_digit(client):
    """Password without digits must be rejected."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    resp = client.post('/admin/employees/add', data=json.dumps({
        'username': 'NEW003', 'full_name': 'جديد', 'department_id': 1,
        'role': 'employee', 'salary': 2000, 'password': 'OnlyLettersA'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is False
    assert 'رقم' in data['msg'] or 'digit' in data['msg'].lower()


def test_password_no_lowercase(client):
    """Password without lowercase must be rejected."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    resp = client.post('/admin/employees/add', data=json.dumps({
        'username': 'NEW004', 'full_name': 'جديد', 'department_id': 1,
        'role': 'employee', 'salary': 2000, 'password': 'UPPERCASE123'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is False


def test_valid_password_accepted(client):
    """Valid password meeting all requirements must be accepted."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    resp = client.post('/admin/employees/add', data=json.dumps({
        'username': 'NEW005', 'full_name': 'جديد', 'department_id': 1,
        'role': 'employee', 'salary': 2000, 'password': 'SecurePwd1'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True, f"Valid password should be accepted: {data}"


def test_password_change_enforces_policy(client):
    """Password change on edit must validate policy."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    resp = client.post('/admin/employees/add', data=json.dumps({
        'username': 'NEW006', 'full_name': 'جديد', 'department_id': 1,
        'role': 'employee', 'salary': 2000, 'password': 'ValidPwd1'
    }), content_type='application/json')
    assert resp.get_json()['ok'] is True
    eid = resp.get_json()['id']

    resp = client.post(f'/admin/employees/{eid}/edit', data=json.dumps({
        'full_name': 'جديد', 'salary': 2000, 'password': 'weak'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is False
    assert '8' in data['msg'] or 'أحرف' in data['msg']
