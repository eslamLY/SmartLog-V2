"""Tests for the ADMS device push API (multi-tenant)."""
import json
import pytest
from datetime import datetime, UTC, date
from werkzeug.security import generate_password_hash
from flask import Flask

from models import db, Company, CompanyAdmin, BiometricDevice, DeviceSyncLog, Employee, AttendanceLog


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test'
    db.init_app(app)

    with app.app_context():
        db.create_all()
        from routes.device_api import device_api_bp
        app.register_blueprint(device_api_bp)

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def license_key(app):
    with app.app_context():
        company = Company(name_ar='Test Co', plan='pro', is_active=True, max_employees=500, max_devices=10)
        db.session.add(company)
        db.session.flush()

        device = BiometricDevice(
            company_id=company.id,
            serial_no='BIO-TEST-001',
            name='Test Device',
            license_key='test-license-key-001',
            is_active=True,
        )
        db.session.add(device)
        db.session.flush()

        emp = Employee(
            username='EMP001',
            full_name='Test Employee',
            department='IT',
            company_id=company.id,
            password_hash=generate_password_hash('123456'),
            role='employee',
            is_active=True,
        )
        db.session.add(emp)
        db.session.commit()

        return 'test-license-key-001'


def test_handshake_unauthorized(client):
    resp = client.post('/api/device/handshake', json={})
    assert resp.status_code == 401


def test_handshake_success(client, license_key):
    resp = client.post('/api/device/handshake',
        json={'firmware_ver': 'V1.2', 'fp_enrolled': 10, 'txlog_used': 50},
        headers={'Authorization': f'Bearer {license_key}'})
    data = resp.get_json()
    assert data['ok'] is True
    assert 'server_time' in data
    assert data['sync_interval'] == 60


def test_sync_data_new_record(client, license_key):
    payload = {
        'records': [{
            'uid': 'EMP001',
            'timestamp': datetime.now(UTC).isoformat(),
        }]
    }
    resp = client.post('/api/device/sync/data',
        json=payload,
        headers={'Authorization': f'Bearer {license_key}'})
    data = resp.get_json()
    assert data['ok'] is True
    assert data['imported'] == 1


def test_sync_data_unknown_employee(client, license_key):
    payload = {
        'records': [{
            'uid': 'UNKNOWN',
            'timestamp': datetime.now(UTC).isoformat(),
        }]
    }
    resp = client.post('/api/device/sync/data',
        json=payload,
        headers={'Authorization': f'Bearer {license_key}'})
    data = resp.get_json()
    assert data['ok'] is True
    assert data['imported'] == 0
    assert len(data['errors']) == 1
    assert 'employee not found' in data['errors'][0]['error']


def test_config_download(client, license_key):
    resp = client.get(f'/api/device/config/download?license_key={license_key}')
    data = resp.get_json()
    assert data['ok'] is True
    assert len(data['employees']) == 1
    assert data['employees'][0]['uid'] == 'EMP001'


def test_device_inactive_returns_401(client, app, license_key):
    with app.app_context():
        device = BiometricDevice.query.filter_by(license_key=license_key).first()
        device.is_active = False
        db.session.commit()
    resp = client.post('/api/device/handshake',
        json={},
        headers={'Authorization': f'Bearer {license_key}'})
    assert resp.status_code == 401


def test_company_inactive_returns_403(client, app, license_key):
    with app.app_context():
        device = BiometricDevice.query.filter_by(license_key=license_key).first()
        company = Company.query.get(device.company_id)
        company.is_active = False
        db.session.commit()
    resp = client.post('/api/device/handshake',
        json={},
        headers={'Authorization': f'Bearer {license_key}'})
    assert resp.status_code == 403
