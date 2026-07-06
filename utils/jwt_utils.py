"""JWT access-token helpers and @jwt_required decorator."""
import os
import time
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, UTC
from functools import wraps

import jwt
from flask import request, jsonify, current_app

from models import db, Employee
from models.refresh_token import RefreshToken

log = logging.getLogger(__name__)

ACCESS_TOKEN_TTL = 15 * 60        # 15 minutes
REFRESH_TOKEN_TTL = 30 * 24 * 3600  # 30 days


def _jwt_secret():
    return current_app.config.get('JWT_SECRET_KEY') or current_app.secret_key


def create_access_token(user_id: int, role: str) -> str:
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': int(time.time()) + ACCESS_TOKEN_TTL,
        'iat': int(time.time()),
        'type': 'access',
    }
    return jwt.encode(payload, _jwt_secret(), algorithm='HS256')


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret(), algorithms=['HS256'])


def create_refresh_token(user_id: int, device_info: str = None) -> str:
    raw = secrets.token_hex(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    entry = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(seconds=REFRESH_TOKEN_TTL),
        device_info=device_info or '',
    )
    db.session.add(entry)
    db.session.commit()
    return raw


def revoke_refresh_token(raw_token: str) -> bool:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    entry = RefreshToken.query.filter_by(token_hash=token_hash).first()
    if not entry:
        return False
    entry.is_revoked = True
    entry.revoked_at = datetime.now(UTC)
    db.session.commit()
    return True


def validate_refresh_token(raw_token: str) -> RefreshToken:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    entry = RefreshToken.query.filter_by(token_hash=token_hash).first()
    if not entry:
        return None
    if entry.is_revoked:
        return None
    expires = entry.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        return None
    return entry


def jwt_required(f):
    """Decorator: require valid JWT access token in Authorization header.

    On failure returns JSON with ``error`` key so mobile clients can
    programmatically detect ``token_expired`` and call the refresh flow.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'missing_token', 'message': 'Authorization header required'}), 401
        token = auth[7:]
        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'token_expired', 'message': 'Access token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'invalid_token', 'message': 'Invalid access token'}), 401

        user = Employee.query.get(payload.get('user_id'))
        if not user or not user.is_active:
            return jsonify({'error': 'user_inactive', 'message': 'User account is inactive'}), 401

        kwargs['current_user'] = user
        return f(*args, **kwargs)
    return decorated
