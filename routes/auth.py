import os
import time
from datetime import datetime, timedelta, UTC
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, jsonify, make_response, current_app)
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Employee, LoginAttempt, BrandingConfig
from utils.helpers import validate_password_strength
from utils.constants import MAX_LOGIN_ATTEMPTS
from utils.rate_limit import check_rate_limit, rate_limit_headers

auth_bp = Blueprint('auth', __name__)
import logging
from functools import wraps

LOGGER = logging.getLogger(__name__)


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper




@auth_bp.route('/manifest.json')
def manifest():
    cfg = BrandingConfig.query.first()
    primary = cfg.primary_color if cfg and cfg.primary_color else '#dc2626'
    bg = cfg.bg_color if cfg and cfg.bg_color else '#0f172a'
    name = cfg.tenant_name if cfg and cfg.tenant_name else 'SMARTLOG'
    return jsonify({
        "name": name, "short_name": "SMARTLOG",
        "description": "نظام الحضور والموارد البشرية الذكي",
        "start_url": "/", "display": "standalone",
        "orientation": "portrait",
        "background_color": bg, "theme_color": primary,
        "lang": "ar", "dir": "rtl",
        "icons": [
            {"src": "/static/icons/icon-192.svg", "sizes": "192x192", "type": "image/svg+xml"},
            {"src": "/static/icons/icon-512.svg", "sizes": "512x512", "type": "image/svg+xml"}
        ]
    })


@auth_bp.route('/sw.js')
def service_worker():
    sw_path = os.path.join(current_app.static_folder, 'sw.js')
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = r"""const C='smartlog-v2.0';const O=['/login','/manifest.json'];self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(O)).then(()=>self.skipWaiting()))});self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});self.addEventListener('fetch',e=>{if(e.request.method!=='GET'||e.request.url.includes('/api/'))return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(r=>{if(r&&r.status===200){var c=r.clone();caches.open(C).then(ca=>ca.put(e.request,c))}return r}).catch(()=>caches.match(e.request).then(r=>r||new Response('',{status:503})))))});"""
    resp = make_response(content)
    resp.status_code = 200
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@auth_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_ops_bp.admin_dashboard') if session.get('role') == 'admin' else url_for('employee.employee_dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        allowed, remaining = check_rate_limit('login', 5, 300)
        if not allowed:
            return jsonify({'ok': False, 'msg': 'لقد تجاوزت الحد المسموح به من المحاولات. يرجى الانتظار 5 دقائق.'}), 429

        data      = request.get_json() or {}
        username  = data.get('username', '').strip().upper()
        password  = data.get('password', '').strip()
        device_id = data.get('device_id', '')
        ip        = request.remote_addr

        attempt = LoginAttempt.query.filter_by(ip_address=ip).first()
        if attempt and attempt.blocked_until:
            blocked_until_utc = attempt.blocked_until.replace(tzinfo=UTC) if attempt.blocked_until.tzinfo is None else attempt.blocked_until
            if blocked_until_utc > datetime.now(UTC):
                mins = int((blocked_until_utc - datetime.now(UTC)).total_seconds() / 60) + 1
                return jsonify({'ok': False, 'msg': f'هذا الجهاز محظور. حاول بعد {mins} دقيقة.'}), 429

        emp = Employee.query.filter_by(username=username, is_active=True).first()
        if emp and check_password_hash(emp.password_hash, password):
            if emp.role == 'employee':
                if emp.device_id and device_id and emp.device_id != device_id:
                    return jsonify({'ok': False, 'msg': 'هذا الحساب مرتبط بجهاز آخر. تواصل مع المدير لإعادة الضبط.'})
                if not emp.device_id and device_id:
                    emp.device_id = device_id
                    db.session.commit()
            if attempt:
                db.session.delete(attempt)
                db.session.commit()
            session.clear()
            session.permanent = True
            session.update({'user_id': emp.id, 'username': emp.username,
                            'full_name': emp.full_name, 'role': emp.role,
                            'department': emp.department,
                            'login_time': datetime.now(UTC).isoformat()})
            if emp.force_password_change:
                redir = url_for('auth.force_password_change')
            else:
                redir = url_for('admin_ops_bp.admin_dashboard') if emp.role == 'admin' else url_for('employee.employee_dashboard')
            return jsonify({'ok': True, 'redirect': redir})
        else:
            if not attempt:
                attempt = LoginAttempt(ip_address=ip, attempts=1)
                db.session.add(attempt)
            else:
                attempt.attempts += 1
                attempt.last_attempt = datetime.now(UTC)
                if attempt.attempts >= MAX_LOGIN_ATTEMPTS:
                    attempt.blocked_until = datetime.now(UTC) + timedelta(hours=1)
            db.session.commit()
            left = max(0, MAX_LOGIN_ATTEMPTS - (attempt.attempts))
            return jsonify({'ok': False, 'msg': 'بيانات خاطئة.'})

    return render_template('login.html', timeout=request.args.get('timeout'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/force-password-change', methods=['GET', 'POST'])
def force_password_change():
    eid = session.get('user_id')
    if not eid:
        return redirect(url_for('auth.login'))
    emp = Employee.query.get(eid)
    if not emp:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        data = request.get_json() or {}
        new_pass = data.get('password', '').strip()
        valid, msg = validate_password_strength(new_pass)
        if not valid:
            return jsonify({'ok': False, 'msg': msg}), 400
        emp.password_hash = generate_password_hash(new_pass)
        emp.force_password_change = False
        emp.password_changed_at = datetime.now(UTC)
        db.session.commit()
        redir = url_for('admin_ops_bp.admin_dashboard') if emp.role == 'admin' else url_for('employee.employee_dashboard')
        return jsonify({'ok': True, 'msg': 'تم تغيير كلمة المرور بنجاح.', 'redirect': redir})
    return render_template('force_password_change.html')


@auth_bp.route('/api/health')
@safe_api
def api_health():
    import psutil
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'memory': {'status': 'ok' if mem.percent < 90 else 'critical', 'used': f'{mem.used//1048576}MB', 'total': f'{mem.total//1048576}MB', 'percent': mem.percent},
        'disk': {'status': 'ok' if disk.percent < 90 else 'critical', 'used': f'{disk.used//1073741824}GB', 'total': f'{disk.total//1073741824}GB', 'percent': disk.percent},
        'uptime': str(timedelta(seconds=int(time.time() - psutil.boot_time()))) if hasattr(psutil, 'boot_time') else 'غير معروف'
    })


@auth_bp.route('/api/init-db')
@safe_api
def init_database():
    if session.get('role') != 'admin':
        return jsonify({'ok': False, 'msg': 'غير مصرح به. يجب تسجيل الدخول كمسؤول.'}), 403
    allowed, _ = check_rate_limit('init_db', 2, 3600)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'تجاوزت الحد المسموح. يمكنك استخدام هذه الميزة مرة كل 30 دقيقة.'}), 429
    from models import db
    try:
        from flask_migrate import upgrade
        upgrade()
    except Exception as exc:
        pass
    try:
        from utils.seeds import seed_enterprise, seed_db, seed_shift_types, seed_leave_types
        seed_enterprise()
        seed_db()
        seed_shift_types()
        seed_leave_types()
        return jsonify({'ok': True, 'msg': 'Database initialized successfully'})
    except Exception as exc:
        import traceback
        return jsonify({'ok': False, 'msg': str(exc), 'traceback': traceback.format_exc()})

