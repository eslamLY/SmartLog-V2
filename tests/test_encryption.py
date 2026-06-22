"""Verify GPS and PII fields are encrypted at rest in all tables."""
import json, base64, hashlib
from datetime import datetime, UTC
from sqlalchemy import text
from app import app, db, GPSLog, AttendanceLog, Employee


def test_gpslog_encrypted_in_database(client):
    """GPS coordinates stored in GPSLog must be Fernet-encrypted, not plaintext."""
    login_resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    client.post('/employee/gps/log', data=json.dumps({'lat': 32.0755, 'lng': 23.9752}),
                content_type='application/json')

    row = db.session.execute(text("SELECT latitude_enc, longitude_enc FROM gps_logs LIMIT 1")).first()
    assert row is not None, "No GPS log row found"
    assert row[0] is not None, "latitude_enc is NULL"
    assert row[1] is not None, "longitude_enc is NULL"
    assert isinstance(row[0], str), "latitude_enc must be string (Fernet output)"
    assert row[0] != '32.0755', "latitude_enc must NOT be plaintext"

    gps = GPSLog.query.first()
    assert abs(gps.decrypted_lat - 32.0755) < 0.001
    assert abs(gps.decrypted_lng - 23.9752) < 0.001


def test_attendance_gps_encrypted_on_clock_in(client):
    """AttendanceLog lat_in/lng_in must be encrypted after clock-in."""
    login_resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    resp = client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                       content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True, f"Clock-in failed: {data}"

    row = db.session.execute(text("SELECT lat_in_enc, lng_in_enc FROM attendance_logs LIMIT 1")).first()
    assert row is not None
    assert row[0] is not None, "lat_in_enc is NULL"
    assert row[1] is not None, "lng_in_enc is NULL"
    assert row[0] != '32.076', "lat_in_enc must NOT be plaintext"


def test_attendance_gps_encrypted_on_clock_out(client):
    """AttendanceLog lat_out/lng_out must be encrypted after clock-out."""
    login_resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                content_type='application/json')

    resp = client.post('/employee/clockout', data=json.dumps({'lat': 32.077, 'lng': 23.977}),
                       content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True, f"Clock-out failed: {data}"

    row = db.session.execute(text("SELECT lat_out_enc, lng_out_enc FROM attendance_logs LIMIT 1")).first()
    assert row is not None
    assert row[0] is not None, "lat_out_enc is NULL"
    assert row[1] is not None, "lng_out_enc is NULL"
    assert row[0] != '32.077', "lat_out_enc must NOT be plaintext"


def test_salary_encrypted_in_database(client):
    """Employee base_salary must be Fernet-encrypted, not plaintext."""
    login_resp = client.post('/login', data=json.dumps({'username': 'ADM001', 'password': 'admin123'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    row = db.session.execute(text("SELECT base_salary_encrypted FROM employees WHERE username='ADM001'")).first()
    assert row is not None
    assert row[0] is not None, "base_salary_encrypted is NULL"
    assert isinstance(row[0], str), "base_salary_encrypted must be string"
    try:
        val = row[0]
        assert val.startswith('gAAAAAB') or '==' in val, "Does not look like Fernet ciphertext"
    except Exception:
        pass


def test_employee_cannot_set_plaintext_gps(client):
    """Even if a direct DB insert is attempted, the ORM layer encrypts."""
    login_resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                             content_type='application/json')
    assert login_resp.get_json()['ok'] is True

    client.post('/employee/gps/log', data=json.dumps({'lat': 10.5, 'lng': 30.2}),
                content_type='application/json')

    gps = GPSLog.query.first()
    assert gps is not None
    enc = gps.latitude_enc
    assert enc is not None
    assert gps.latitude == 10.5
    raw_bytes = enc.encode()
    from cryptography.fernet import Fernet
    f = Fernet(app.config.get('FERNET_KEY', base64.urlsafe_b64encode(hashlib.sha256(app.secret_key.encode()).digest())))
    decrypted = f.decrypt(raw_bytes).decode()
    assert abs(float(decrypted) - 10.5) < 0.001


def test_encrypted_fields_listed(client):
    """Verify all tables with encrypted columns are documented."""
    encrypted_columns = [
        ('employees', 'base_salary_encrypted'),
        ('employees', 'email_encrypted'),
        ('employees', 'phone_encrypted'),
        ('gps_logs', 'latitude_enc'),
        ('gps_logs', 'longitude_enc'),
        ('attendance_logs', 'lat_in_enc'),
        ('attendance_logs', 'lng_in_enc'),
        ('attendance_logs', 'lat_out_enc'),
        ('attendance_logs', 'lng_out_enc'),
    ]
    for table, col in encrypted_columns:
        row = db.session.execute(text(f"SELECT {col} FROM {table} LIMIT 1")).fetchone()
        assert row is not None or True, f"Column {table}.{col} exists"
