"""Tests for stateless dual-token auth (/api/v1/auth/*)."""
import time
import json
import pytest
from werkzeug.security import generate_password_hash
from unittest.mock import patch

from models import db, Employee, RefreshToken
from utils.jwt_utils import create_access_token, decode_access_token


@pytest.fixture
def test_user(app_context):
    user = Employee(
        username='JWTUSER',
        full_name='JWT Test User',
        department='IT',
        role='admin',
        is_active=True,
        password_hash=generate_password_hash('testpass123'),
    )
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.rollback()


# ── POST /api/v1/auth/login ───────────────────────────────────────

def test_login_success(client, test_user):
    resp = client.post('/api/v1/auth/login', json={
        'username': 'JWTUSER',
        'password': 'testpass123',
    })
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['ok'] is True
    assert 'access_token' in data
    assert 'refresh_token' in data
    assert data['token_type'] == 'Bearer'
    assert data['expires_in'] == 900
    assert data['user']['username'] == 'JWTUSER'


def test_login_wrong_password(client, test_user):
    resp = client.post('/api/v1/auth/login', json={
        'username': 'JWTUSER',
        'password': 'wrongpass',
    })
    assert resp.status_code == 401
    assert b'auth_failed' in resp.data


def test_login_missing_fields(client):
    resp = client.post('/api/v1/auth/login', json={'username': ''})
    assert resp.status_code == 400
    assert b'validation' in resp.data


# ── GET /api/v1/auth/me (jwt_required) ────────────────────────────

def test_me_success(client, test_user):
    token = create_access_token(test_user.id, test_user.role)
    resp = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['ok'] is True
    assert data['user']['id'] == test_user.id
    assert data['user']['username'] == 'JWTUSER'


def test_me_no_token(client):
    resp = client.get('/api/v1/auth/me')
    assert resp.status_code == 401
    assert b'missing_token' in resp.data


def test_me_expired_token(client, test_user):
    with patch('utils.jwt_utils.time') as mock_time:
        mock_time.time.return_value = time.time() - 3600
        token = create_access_token(test_user.id, test_user.role)
    resp = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 401
    assert b'token_expired' in resp.data


def test_me_invalid_token(client):
    resp = client.get('/api/v1/auth/me',
                      headers={'Authorization': 'Bearer invalidtoken123'})
    assert resp.status_code == 401
    assert b'invalid_token' in resp.data


# ── POST /api/v1/auth/refresh ─────────────────────────────────────

def test_refresh_success(client, test_user):
    login_resp = client.post('/api/v1/auth/login', json={
        'username': 'JWTUSER',
        'password': 'testpass123',
    })
    data = login_resp.get_json()
    refresh_token = data['refresh_token']

    resp = client.post('/api/v1/auth/refresh', json={
        'refresh_token': refresh_token,
    })
    data2 = resp.get_json()
    assert resp.status_code == 200
    assert data2['ok'] is True
    assert 'access_token' in data2
    assert data2['token_type'] == 'Bearer'
    assert data2['expires_in'] == 900


def test_refresh_invalid_token(client):
    resp = client.post('/api/v1/auth/refresh', json={
        'refresh_token': 'invalid-refresh-token',
    })
    assert resp.status_code == 401
    assert b'invalid_refresh' in resp.data


def test_refresh_revoked_token(client, test_user):
    login_resp = client.post('/api/v1/auth/login', json={
        'username': 'JWTUSER',
        'password': 'testpass123',
    })
    data = login_resp.get_json()
    refresh_token = data['refresh_token']

    # Logout (revokes token)
    client.post('/api/v1/auth/logout', json={'refresh_token': refresh_token})

    # Try to refresh with revoked token
    resp = client.post('/api/v1/auth/refresh', json={
        'refresh_token': refresh_token,
    })
    assert resp.status_code == 401
    assert b'invalid_refresh' in resp.data


# ── POST /api/v1/auth/logout ──────────────────────────────────────

def test_logout_revokes_token(client, test_user):
    login_resp = client.post('/api/v1/auth/login', json={
        'username': 'JWTUSER',
        'password': 'testpass123',
    })
    data = login_resp.get_json()
    refresh_token = data['refresh_token']

    resp = client.post('/api/v1/auth/logout', json={'refresh_token': refresh_token})
    assert resp.status_code == 200
    assert data['ok'] is True

    from utils.jwt_utils import validate_refresh_token
    assert validate_refresh_token(refresh_token) is None


# ── Access token round-trip ───────────────────────────────────────

def test_access_token_round_trip(client, test_user):
    token = create_access_token(test_user.id, test_user.role)
    payload = decode_access_token(token)
    assert payload['user_id'] == test_user.id
    assert payload['role'] == 'admin'
    assert payload['type'] == 'access'
