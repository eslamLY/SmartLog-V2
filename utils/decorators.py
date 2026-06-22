import json
from datetime import datetime, UTC
from functools import wraps

from flask import session, request, redirect, url_for, jsonify

from models import db, AuditLog
from utils.constants import SESSION_TIMEOUT_SECS

def login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        la = session.get('last_activity')
        if la:
            elapsed = (datetime.now(UTC) - datetime.fromisoformat(la)).total_seconds()
            if elapsed > SESSION_TIMEOUT_SECS:
                session.clear()
                return redirect(url_for('auth.login', timeout=1))
        session['last_activity'] = datetime.now(UTC).isoformat()
        return f(*a, **kw)
    return deco

def admin_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('auth.login'))
        la = session.get('last_activity')
        if la:
            elapsed = (datetime.now(UTC) - datetime.fromisoformat(la)).total_seconds()
            if elapsed > SESSION_TIMEOUT_SECS:
                session.clear()
                return redirect(url_for('auth.login', timeout=1))
        session['last_activity'] = datetime.now(UTC).isoformat()
        return f(*a, **kw)
    return deco

def employee_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if 'user_id' not in session or session.get('role') != 'employee':
            return redirect(url_for('auth.login'))
        la = session.get('last_activity')
        if la:
            elapsed = (datetime.now(UTC) - datetime.fromisoformat(la)).total_seconds()
            if elapsed > SESSION_TIMEOUT_SECS:
                session.clear()
                return redirect(url_for('auth.login', timeout=1))
        session['last_activity'] = datetime.now(UTC).isoformat()
        return f(*a, **kw)
    return deco

def audit_log_action(action=None, entity_type=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            resp = f(*args, **kwargs)
            try:
                uid   = session.get('user_id')
                uname = session.get('full_name', session.get('username', 'unknown'))
                ent   = entity_type
                ip    = request.remote_addr or 'unknown'
                db.session.add(AuditLog(
                    user_id=uid, user_name=uname,
                    action=action or request.method.lower(),
                    entity_type=ent, ip_address=ip,
                    changes=json.dumps({
                        'path': request.path,
                        'args': {k: v for k, v in request.args.items() if k not in ('password', 'token', 'api_key')}
                    })
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
            return resp
        return wrapper
    return decorator

def own_data_only(param_name='employee_id'):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            target_id = kwargs.get(param_name) or request.args.get(param_name, type=int) or (request.get_json(silent=True) or {}).get(param_name)
            role = session.get('role')
            uid  = session.get('user_id')
            if role != 'admin' and target_id and target_id != uid:
                return jsonify({'ok': False, 'msg': 'لا يمكنك الوصول إلى بيانات موظف آخر.'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator
