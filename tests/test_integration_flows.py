"""End-to-end integration tests covering complete user workflows."""
import json
from app import db, Employee


def _login(client, username, password):
    return client.post('/login', data=json.dumps({'username': username, 'password': password}),
                       content_type='application/json')


def test_integration_employee_full_day(client):
    """E2E: Employee login → clock in → clock out → verify attendance."""
    resp = _login(client, 'EMP001', '123456')
    assert resp.get_json()['ok'] is True

    resp = client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                       content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True

    resp = client.post('/employee/clockout', data=json.dumps({'lat': 32.077, 'lng': 23.977}),
                       content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True

    resp = client.get('/employee')
    assert resp.status_code == 200


def test_integration_admin_creates_employee(client):
    """E2E: Admin login → create employee → verify employee exists."""
    _login(client, 'ADM001', 'admin123')

    resp = client.post('/admin/employees/add', data=json.dumps({
        'username': 'INT001', 'full_name': 'موظف اختبار متكامل',
        'department_id': 1, 'role': 'employee',
        'salary': 3000, 'password': 'TestPwd123'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True

    emp = Employee.query.filter_by(username='INT001').first()
    assert emp is not None
    assert emp.full_name == 'موظف اختبار متكامل'


def test_integration_leave_request_flow(client):
    """E2E: Employee requests leave → verify request exists."""
    _login(client, 'EMP001', '123456')

    resp = client.post('/employee/leaves/new', data=json.dumps({
        'type': 'إجازة سنوية', 'start_date': '2026-07-01',
        'end_date': '2026-07-05', 'reason': 'إجازة عائلية'
    }), content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True

    resp = client.get('/employee/leaves')
    assert resp.status_code == 200


def test_integration_backup_and_verify(client):
    """E2E: Admin creates backup → verifies backup integrity."""
    _login(client, 'ADM001', 'admin123')

    resp = client.post('/api/admin/backup', content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True
    bid = data['id']

    resp = client.post(f'/api/admin/backups/{bid}/verify', content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True
    assert 'جدول' in data['msg'] or 'موظف' in data['msg']


def test_integration_password_reset(client):
    """E2E: Admin resets employee password → new password works."""
    _login(client, 'ADM001', 'admin123')

    resp = client.post('/admin/password-reset/2', data=json.dumps({'new_password': 'NewPwd789'}),
                       content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True

    client.get('/logout')

    resp = _login(client, 'EMP001', 'NewPwd789')
    assert resp.get_json()['ok'] is True
