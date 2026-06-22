from tests.helpers import login
import json

def test_email_templates(client):
    login(client)
    r = client.get('/api/admin/email/templates')
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) >= 1
    assert data[0]['name'] == 'ترحيب'

def test_email_history_empty(client):
    login(client)
    r = client.get('/api/admin/email/history')
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)

def test_send_email(client):
    login(client)
    r = client.post('/api/admin/email/send', content_type='application/json',
        data=json.dumps({'to': '', 'subject': 'اختبار', 'body': 'مرحباً'}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

def test_send_email_to_specific(client):
    login(client)
    r = client.post('/api/admin/email/send', content_type='application/json',
        data=json.dumps({'to': 'user@test.com', 'subject': 'مرحباً', 'body': 'نص'}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

def test_send_email_missing_fields(client):
    login(client)
    r = client.post('/api/admin/email/send', content_type='application/json',
        data=json.dumps({'to': '', 'subject': '', 'body': ''}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is False

def test_email_history_after_send(client):
    login(client)
    from app import EmailLog
    before = EmailLog.query.count()
    client.post('/api/admin/email/send', content_type='application/json',
        data=json.dumps({'to': '', 'subject': 'اختبار', 'body': 'مرحباً'}))
    after = EmailLog.query.count()
    assert after > before

def test_sms_history_empty(client):
    login(client)
    r = client.get('/api/admin/sms/history')
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)

def test_send_sms(client):
    login(client)
    r = client.post('/api/admin/sms/send', content_type='application/json',
        data=json.dumps({'to': '', 'message': 'رسالة اختبارية'}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

def test_send_sms_to_specific(client):
    login(client)
    r = client.post('/api/admin/sms/send', content_type='application/json',
        data=json.dumps({'to': '+218901234567', 'message': 'رسالة'}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

def test_send_sms_missing_message(client):
    login(client)
    r = client.post('/api/admin/sms/send', content_type='application/json',
        data=json.dumps({'to': '', 'message': ''}))
    assert r.status_code == 200
    assert r.get_json()['ok'] is False

def test_email_page(client):
    login(client)
    r = client.get('/admin/email-notifications')
    assert r.status_code == 200

def test_sms_page(client):
    login(client)
    r = client.get('/admin/sms-notifications')
    assert r.status_code == 200
