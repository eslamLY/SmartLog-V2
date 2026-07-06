"""Tests for the ADMS device push API with HMAC authentication."""
import json
import time
import hmac
import hashlib
import pytest
from datetime import datetime, UTC

from models import db, Company, BiometricDevice, Employee


def _hmac_headers(device_id, secret_key, body='', ts=None):
    ts = ts or int(time.time())
    message = body + str(ts)
    sig = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        'X-Device-Id': str(device_id),
        'X-Device-Timestamp': str(ts),
        'X-Device-Signature': sig,
        'Content-Type': 'application/json',
    }


@pytest.fixture
def device(app_context):
    company = Company(name_ar='Test Co HMAC', plan='pro', is_active=True, max_employees=500, max_devices=10)
    db.session.add(company)
    db.session.flush()

    dev = BiometricDevice(
        company_id=company.id,
        serial_no='BIO-HMAC-001',
        name='Test Device HMAC',
        license_key='test-lic-hmac-001',
        secret_key='aabb' * 16,
        is_active=True,
    )
    db.session.add(dev)
    db.session.flush()

    emp = Employee(
        username='EMPHMAC01',
        full_name='Test Employee HMAC',
        department='IT',
        company_id=company.id,
        role='employee',
        is_active=True,
        password_hash='scrypt:hash:placeholder',
    )
    db.session.add(emp)
    db.session.commit()

    yield {'device': dev, 'company': company, 'employee': emp}

    db.session.rollback()


# ── Missing / invalid HMAC headers ────────────────────────────────

def test_handshake_no_hmac_headers(client):
    resp = client.post('/api/device/handshake', json={})
    assert resp.status_code == 401
    assert b'Missing HMAC headers' in resp.data


def test_handshake_expired_timestamp(client, device):
    dev = device['device']
    ts = int(time.time()) - 400
    headers = _hmac_headers(dev.id, dev.secret_key, ts=ts)
    resp = client.post('/api/device/handshake', json={}, headers=headers)
    assert resp.status_code == 400
    assert b'Request expired' in resp.data


def test_handshake_bad_signature(client, device):
    dev = device['device']
    ts = int(time.time())
    headers = _hmac_headers(dev.id, 'wrong-secret', ts=ts)
    resp = client.post('/api/device/handshake', json={}, headers=headers)
    assert resp.status_code == 403
    assert b'Invalid signature' in resp.data


def test_handshake_tampered_body(client, device):
    dev = device['device']
    ts = int(time.time())
    body = json.dumps({'firmware_ver': 'V1.0'})
    headers = _hmac_headers(dev.id, dev.secret_key, body=body, ts=ts)
    tampered = json.dumps({'firmware_ver': 'V2.0'})
    resp = client.post('/api/device/handshake', data=tampered, headers=headers)
    assert resp.status_code == 403
    assert b'Invalid signature' in resp.data


def test_invalid_device_id(client, device):
    ts = int(time.time())
    headers = {
        'X-Device-Id': '99999',
        'X-Device-Timestamp': str(ts),
        'X-Device-Signature': 'x' * 64,
        'Content-Type': 'application/json',
    }
    resp = client.post('/api/device/handshake', json={}, headers=headers)
    assert resp.status_code == 401


# ── Happy path: HMAC handshake ────────────────────────────────────

def test_handshake_success(client, device):
    dev = device['device']
    body = json.dumps({'firmware_ver': 'V1.2', 'fp_enrolled': 10, 'txlog_used': 50})
    headers = _hmac_headers(dev.id, dev.secret_key, body=body)
    resp = client.post('/api/device/handshake', data=body, headers=headers)
    data = resp.get_json()
    assert data['ok'] is True
    assert 'server_time' in data
    assert data['sync_interval'] == 60
    assert resp.headers.get('X-API-Deprecated') == 'true'


# ── v1 API routes ────────────────────────────────────────────────────

def test_v1_handshake_success(client, device):
    dev = device['device']
    body = json.dumps({'firmware_ver': 'V1.0'})
    headers = _hmac_headers(dev.id, dev.secret_key, body=body)
    resp = client.post('/api/v1/devices/handshake', data=body, headers=headers)
    data = resp.get_json()
    assert data['ok'] is True
    assert 'server_time' in data
    assert resp.headers.get('X-API-Deprecated') is None


def test_v1_sync_data(client, device):
    dev = device['device']
    payload = {'records': [{'uid': 'EMPHMAC01', 'timestamp': datetime.now(UTC).isoformat()}]}
    body = json.dumps(payload)
    headers = _hmac_headers(dev.id, dev.secret_key, body=body)
    resp = client.post('/api/v1/devices/sync/data', data=body, headers=headers)
    data = resp.get_json()
    assert data['ok'] is True
    assert data['imported'] == 1
    assert resp.headers.get('X-API-Deprecated') is None


def test_v1_config_download(client, device):
    dev = device['device']
    headers = _hmac_headers(dev.id, dev.secret_key)
    resp = client.get('/api/v1/devices/config/download', headers=headers)
    data = resp.get_json()
    assert data['ok'] is True
    assert resp.headers.get('X-API-Deprecated') is None


def test_v1_missing_hmac(client):
    resp = client.post('/api/v1/devices/handshake', json={})
    assert resp.status_code == 401
    assert b'Missing HMAC headers' in resp.data


def test_old_route_deprecation_header(client, device):
    dev = device['device']
    headers = _hmac_headers(dev.id, dev.secret_key)
    for path in ['/api/device/handshake', '/api/device/sync/data',
                 '/api/device/config/download', '/api/device/command/execute',
                 '/api/device/sync/status']:
        method = 'GET' if 'download' in path or 'status' in path else 'POST'
        _h = headers if method == 'GET' else _hmac_headers(dev.id, dev.secret_key,
                    body='{}' if 'execute' in path else '')
        resp = client.open(path, method=method, headers=_h,
                           data='{}' if method == 'POST' else None,
                           content_type='application/json')
        assert resp.headers.get('X-API-Deprecated') == 'true', f'{path} missing deprecation header'


# ── Sync data ─────────────────────────────────────────────────────

def test_sync_data_new_record(client, device):
    dev = device['device']
    payload = {
        'records': [{
            'uid': 'EMPHMAC01',
            'timestamp': datetime.now(UTC).isoformat(),
        }]
    }
    body = json.dumps(payload)
    headers = _hmac_headers(dev.id, dev.secret_key, body=body)
    resp = client.post('/api/device/sync/data', data=body, headers=headers)
    data = resp.get_json()
    assert data['ok'] is True
    assert data['imported'] == 1


def test_sync_data_unknown_employee(client, device):
    dev = device['device']
    payload = {
        'records': [{
            'uid': 'UNKNOWN',
            'timestamp': datetime.now(UTC).isoformat(),
        }]
    }
    body = json.dumps(payload)
    headers = _hmac_headers(dev.id, dev.secret_key, body=body)
    resp = client.post('/api/device/sync/data', data=body, headers=headers)
    data = resp.get_json()
    assert data['ok'] is True
    assert data['imported'] == 0
    assert len(data['errors']) == 1
    assert 'employee not found' in data['errors'][0]['error']


# ── Config download (GET) ─────────────────────────────────────────

def test_config_download(client, device):
    dev = device['device']
    headers = _hmac_headers(dev.id, dev.secret_key)
    resp = client.get('/api/device/config/download', headers=headers)
    data = resp.get_json()
    assert data['ok'] is True


# ── Inactive device / company ─────────────────────────────────────

def test_device_inactive_returns_401(client, app_context, device):
    dev = BiometricDevice.query.get(device['device'].id)
    dev.is_active = False
    db.session.commit()
    headers = _hmac_headers(dev.id, device['device'].secret_key)
    resp = client.post('/api/device/handshake', json={}, headers=headers)
    assert resp.status_code == 401


def test_company_inactive_returns_403(client, app_context, device):
    comp = Company.query.get(device['company'].id)
    comp.is_active = False
    db.session.commit()
    dev = device['device']
    headers = _hmac_headers(dev.id, dev.secret_key)
    resp = client.post('/api/device/handshake', json={}, headers=headers)
    assert resp.status_code == 403


# ── Replay attack protection ──────────────────────────────────────

def test_replay_attack_rejected(client, device):
    dev = device['device']
    old_ts = int(time.time()) - 360
    body = json.dumps({'firmware_ver': 'V1.0'})
    headers = _hmac_headers(dev.id, dev.secret_key, body=body, ts=old_ts)
    resp = client.post('/api/device/handshake', data=body, headers=headers)
    assert resp.status_code == 400
    assert b'Request expired' in resp.data
