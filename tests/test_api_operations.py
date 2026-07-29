"""Tests for api_operations endpoints."""
import json
import pytest
from datetime import date

from models import db, Employee, AttendanceLog, LeaveRequest, Department


# ─── GET /api/departments (bare list for frontend) ──────────────────

def test_departments_list(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.get('/api/departments')
    data = resp.get_json()
    assert resp.status_code == 200
    assert isinstance(data, list)
    if data:
        assert 'id' in data[0]
        assert 'name' in data[0]


# ─── GET|POST /api/user/preferences ────────────────────────────────

def test_get_preferences(client):
    with client.session_transaction() as s:
        s['user_id'] = 2
        s['role'] = 'employee'
    resp = client.get('/api/user/preferences')
    assert resp.status_code == 200


def test_save_preferences(client):
    with client.session_transaction() as s:
        s['user_id'] = 2
        s['role'] = 'employee'
    resp = client.post('/api/user/preferences', json={'theme': 'dark', 'language': 'ar'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('ok') is True


# ─── GET /api/attendance/logs ──────────────────────────────────────

def test_attendance_logs(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.get('/api/attendance/logs')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'logs' in data or 'attendance' in data or 'ok' in data


# ─── POST /api/attendance/check-in ─────────────────────────────────

def test_check_in(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.post('/api/attendance/check-in', json={'employee_id': 2})
    assert resp.status_code in (200, 201, 400, 429)
    data = resp.get_json()
    assert data is not None


# ─── POST /api/attendance/check-out ────────────────────────────────

def test_check_out(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.post('/api/attendance/check-out', json={'employee_id': 2})
    assert resp.status_code in (200, 201)


# ─── POST /api/devices/sync ────────────────────────────────────────

def test_device_sync_no_device_id(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.post('/api/devices/sync', json={})
    assert resp.status_code == 400


# ─── POST /api/payroll/calculate ───────────────────────────────────

def test_payroll_calculate(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.post('/api/payroll/calculate', json={'month': 7, 'year': 2026})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('ok') is True
    assert 'rows' in data
    assert 'summary' in data


# ─── POST /api/payroll/generate ────────────────────────────────────

def test_payroll_generate(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.post('/api/payroll/generate', json={'month': 7, 'year': 2026})
    assert resp.status_code == 200


# ─── GET /api/reports/attendance ───────────────────────────────────

def test_reports_attendance(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.get('/api/reports/attendance')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('ok') is True


# ─── GET /api/reports/employees ────────────────────────────────────

def test_reports_employees(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.get('/api/reports/employees')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('ok') is True
    assert 'employees' in data


# ─── GET /api/reports/departments ──────────────────────────────────

def test_reports_departments(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.get('/api/reports/departments')
    assert resp.status_code == 200


# ─── POST /api/backups/create ──────────────────────────────────────

def test_backup_create(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.post('/api/backups/create', json={})
    assert resp.status_code == 200


# ─── GET /api/backups/list ─────────────────────────────────────────

def test_backup_list(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.get('/api/backups/list')
    assert resp.status_code == 200


# ─── GET /api/devices/list ─────────────────────────────────────────

def test_devices_list(client):
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['role'] = 'admin'
    resp = client.get('/api/devices/list')
    assert resp.status_code == 200


# ─── GET /api/system/health (public) ───────────────────────────────

def test_system_health(client):
    resp = client.get('/api/system/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'status' in data
