from tests.helpers import login
import json

def test_list_permissions(client):
    login(client)
    r = client.get('/api/admin/permissions')
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) >= 6
    codes = [p['code'] for p in data]
    assert 'manage_attendance' in codes

def test_list_roles(client):
    login(client)
    r = client.get('/api/admin/roles')
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) >= 1

def test_create_role(client):
    login(client)
    r = client.post('/api/admin/roles', content_type='application/json',
        data=json.dumps({'name': 'مشرف', 'permissions': [1, 2]}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

def test_create_duplicate_role(client):
    login(client)
    client.post('/api/admin/roles', content_type='application/json',
        data=json.dumps({'name': 'مشرف', 'permissions': [1]}))
    r = client.post('/api/admin/roles', content_type='application/json',
        data=json.dumps({'name': 'مشرف', 'permissions': [2]}))
    assert r.get_json()['ok'] is False

def test_delete_role(client):
    login(client)
    r = client.post('/api/admin/roles', content_type='application/json',
        data=json.dumps({'name': 'دور مؤقت', 'permissions': []}))
    from app import Role
    r_id = Role.query.filter_by(name='دور مؤقت').first().id
    r2 = client.post(f'/api/admin/roles/{r_id}/delete')
    assert r2.status_code == 200
    assert r2.get_json()['ok'] is True

def test_employee_permissions_list(client):
    login(client)
    r = client.get('/api/admin/employees/permissions')
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) >= 2

def test_get_employee_permissions(client):
    login(client)
    r = client.get('/api/admin/employees/1/permissions')
    assert r.status_code == 200
    data = r.get_json()
    assert data['employee_id'] == 1
    assert 'permissions' in data

def test_save_employee_permissions(client):
    login(client)
    r = client.post('/api/admin/employees/2/permissions', content_type='application/json',
        data=json.dumps({'permissions': [1, 2, 3]}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

def test_permissions_page(client):
    login(client)
    r = client.get('/admin/permissions')
    assert r.status_code == 200
