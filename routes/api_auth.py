"""Stateless dual-token auth blueprint — /api/v1/auth/*."""
import logging
from datetime import datetime, UTC

from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash

from models import db, Employee
from utils.jwt_utils import (
    create_access_token, create_refresh_token,
    decode_access_token, validate_refresh_token,
    revoke_refresh_token, jwt_required,
)
from utils.rate_limit import check_rate_limit

api_auth_bp = Blueprint('api_auth', __name__, url_prefix='/api/v1/auth')
log = logging.getLogger(__name__)


@api_auth_bp.route('/login', methods=['POST'])
def login():
    allowed, _ = check_rate_limit('api_auth_login', 10, 300)
    if not allowed:
        return jsonify({'ok': False, 'error': 'rate_limited', 'message': 'Too many attempts'}), 429

    data = request.get_json() or {}
    username = data.get('username', '').strip().upper()
    password = data.get('password', '').strip()
    device_info = data.get('device_info', '')

    if not username or not password:
        return jsonify({'ok': False, 'error': 'validation', 'message': 'Username and password required'}), 400

    user = Employee.query.filter_by(username=username, is_active=True).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'ok': False, 'error': 'auth_failed', 'message': 'Invalid credentials'}), 401

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, device_info)

    return jsonify({
        'ok': True,
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': 900,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'role': user.role,
        },
    })


@api_auth_bp.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json() or {}
    raw_token = data.get('refresh_token', '').strip()

    if not raw_token:
        return jsonify({'ok': False, 'error': 'missing_token', 'message': 'Refresh token required'}), 400

    entry = validate_refresh_token(raw_token)
    if not entry:
        return jsonify({'ok': False, 'error': 'invalid_refresh', 'message': 'Invalid or expired refresh token'}), 401

    user = Employee.query.get(entry.user_id)
    if not user or not user.is_active:
        return jsonify({'ok': False, 'error': 'user_inactive', 'message': 'User account is inactive'}), 401

    new_access = create_access_token(user.id, user.role)

    return jsonify({
        'ok': True,
        'access_token': new_access,
        'token_type': 'Bearer',
        'expires_in': 900,
    })


@api_auth_bp.route('/logout', methods=['POST'])
def logout():
    data = request.get_json() or {}
    raw_token = data.get('refresh_token', '').strip()

    if raw_token:
        revoke_refresh_token(raw_token)

    return jsonify({'ok': True, 'message': 'Logged out successfully'})


@api_auth_bp.route('/me', methods=['GET'])
@jwt_required
def me(**kwargs):
    user = kwargs['current_user']
    return jsonify({
        'ok': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'role': user.role,
            'department': user.department,
            'is_active': user.is_active,
        },
    })
