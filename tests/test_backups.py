from tests.helpers import login

def test_list_backups_empty(client):
    login(client)
    r = client.get('/api/admin/backups')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)

def test_create_backup(client):
    login(client)
    r = client.post('/api/admin/backup', content_type='application/json', data='{}')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True

def test_create_then_list_backup(client):
    login(client)
    client.post('/api/admin/backup', content_type='application/json', data='{}')
    r = client.get('/api/admin/backups')
    data = r.get_json()
    assert len(data) >= 1
    assert len(data[0]['id']) == 12

def test_delete_backup(client):
    login(client)
    client.post('/api/admin/backup', content_type='application/json', data='{}')
    r = client.get('/api/admin/backups')
    bid = r.get_json()[0]['id']
    r2 = client.post(f'/api/admin/backups/{bid}/delete')
    assert r2.status_code == 200
    assert r2.get_json()['ok'] is True

def test_restore_nonexistent(client):
    login(client)
    r = client.post('/api/admin/restore/nonexist123')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is False

def test_download_nonexistent(client):
    login(client)
    r = client.get('/api/admin/backups/nonexist/download')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is False

def test_backup_page(client):
    login(client)
    r = client.get('/admin/backups')
    assert r.status_code == 200
