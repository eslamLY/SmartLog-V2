"""Verify employees cannot access other employees' data."""
import json


def _login(client, username, password):
    resp = client.post('/login', data=json.dumps({'username': username, 'password': password}),
                       content_type='application/json')
    return resp.get_json().get('ok', False)


def test_employee_cannot_access_admin(client):
    """Employee user cannot access admin routes."""
    _login(client, 'EMP001', '123456')
    resp = client.get('/admin')
    assert resp.status_code == 302


def test_employee_cannot_access_admin_api(client):
    """Employee user cannot access admin API endpoints."""
    _login(client, 'EMP001', '123456')
    resp = client.get('/admin/employees')
    assert resp.status_code == 302


def test_admin_can_access_admin(client):
    """Admin user can access admin routes."""
    _login(client, 'ADM001', 'admin123')
    resp = client.get('/admin/employees')
    assert resp.status_code == 200


def test_anonymous_blocked_from_all_protected(client):
    """Unauthenticated users are redirected from all protected routes."""
    protected = ['/admin', '/admin/employees', '/admin/attendance',
                 '/employee', '/admin/reports', '/admin/payroll',
                 '/admin/analytics']
    for route in protected:
        resp = client.get(route)
        assert resp.status_code == 302, f"Route {route} should redirect anonymous users, got {resp.status_code}"


def test_employee_dashboard_self_data_only(client):
    """Employee dashboard uses session user_id, not external parameter."""
    _login(client, 'EMP001', '123456')
    resp = client.get('/employee')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert 'موظف اختبار' in html or 'EMP001' in html


def test_logout_clears_session(client):
    """After logout, protected routes should redirect to login."""
    _login(client, 'ADM001', 'admin123')
    client.get('/logout')
    resp = client.get('/admin')
    assert resp.status_code == 302
