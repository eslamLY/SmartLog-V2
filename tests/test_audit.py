from tests.helpers import login
from datetime import datetime, UTC

def test_list_audit_logs(client):
    login(client)
    r = client.get('/api/admin/audit-logs')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)

def test_audit_logs_date_filter(client):
    login(client)
    today = datetime.now(UTC).strftime('%Y-%m-%d')
    r = client.get(f'/api/admin/audit-logs?date={today}')
    assert r.status_code == 200

def test_audit_logs_action_filter(client):
    login(client)
    r = client.get('/api/admin/audit-logs?action=create')
    assert r.status_code == 200

def test_audit_log_created_on_backup(client):
    login(client)
    from app import AuditLog
    before = AuditLog.query.count()
    client.post('/api/admin/backup', content_type='application/json', data='{}')
    after = AuditLog.query.count()
    assert after > before

def test_audit_logs_page(client):
    login(client)
    r = client.get('/admin/audit-logs')
    assert r.status_code == 200
