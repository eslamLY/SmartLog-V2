from tests.helpers import login

def test_health_endpoint(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] == 'healthy'
    assert data['database'] == 'connected'
    assert 'memory' in data
    assert 'disk' in data

def test_metrics_endpoint(client):
    login(client)
    r = client.get('/api/admin/metrics')
    assert r.status_code == 200
    data = r.get_json()
    assert 'requests_per_minute' in data
    assert 'avg_response_time' in data
    assert 'error_rate' in data
    assert 'active_users' in data
    assert 'memory_usage' in data
    assert 'disk_usage' in data

def test_metrics_requires_admin(client):
    login(client, 'EMP001', '123456')
    r = client.get('/api/admin/metrics')
    assert r.status_code == 302

def test_system_health_page(client):
    login(client)
    r = client.get('/admin/system-health')
    assert r.status_code == 200
