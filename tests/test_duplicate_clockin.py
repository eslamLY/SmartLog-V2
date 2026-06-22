"""Verify duplicate clock-in prevention (same hour)."""
import json, time, threading
from datetime import datetime, timedelta
from app import db, AttendanceLog


def _login_emp(client):
    resp = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                       content_type='application/json')
    data = resp.get_json()
    assert data['ok'] is True
    return data


def test_duplicate_clock_in_same_hour_rejected(client):
    """Second clock-in within same hour must be rejected."""
    _login_emp(client)

    resp1 = client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                        content_type='application/json')
    assert resp1.get_json()['ok'] is True

    resp2 = client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                        content_type='application/json')
    data2 = resp2.get_json()
    assert data2['ok'] is False
    assert 'ساعة' in data2['msg'] or 'مرتين' in data2['msg'] or 'بالفعل' in data2['msg']


def test_clock_out_then_clock_in_same_hour_allowed(client):
    """Clock out then clock in again within same hour should succeed."""
    _login_emp(client)

    resp1 = client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                        content_type='application/json')
    assert resp1.get_json()['ok'] is True

    resp_out = client.post('/employee/clockout', data=json.dumps({'lat': 32.077, 'lng': 23.977}),
                           content_type='application/json')
    assert resp_out.get_json()['ok'] is True

    resp2 = client.post('/employee/clockin', data=json.dumps({'lat': 32.078, 'lng': 23.978}),
                        content_type='application/json')
    data2 = resp2.get_json()
    assert data2['ok'] is True, f"Clock-in after clock-out should succeed: {data2}"


def test_different_employees_not_blocked(client):
    """Employee A clocking in should not affect Employee B."""
    resp_a = client.post('/login', data=json.dumps({'username': 'EMP001', 'password': '123456'}),
                         content_type='application/json')
    assert resp_a.get_json()['ok'] is True
    client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                content_type='application/json')

    resp_b = client.post('/login', data=json.dumps({'username': 'EMP002', 'password': '123456'}),
                         content_type='application/json')
    assert resp_b.get_json()['ok'] is True
    resp = client.post('/employee/clockin', data=json.dumps({'lat': 32.076, 'lng': 23.976}),
                       content_type='application/json')
    assert resp.get_json()['ok'] is True, "Different employee should be able to clock in"
