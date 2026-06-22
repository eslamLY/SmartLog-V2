import time
from datetime import datetime, timedelta, UTC
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, jsonify, make_response)
from werkzeug.security import check_password_hash
from models import db, Employee, LoginAttempt, BrandingConfig
from utils.constants import MAX_LOGIN_ATTEMPTS
from utils.rate_limit import check_rate_limit, rate_limit_headers

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/manifest.json')
def manifest():
    cfg = BrandingConfig.query.first()
    primary = cfg.primary_color if cfg and cfg.primary_color else '#dc2626'
    bg = cfg.bg_color if cfg and cfg.bg_color else '#0f172a'
    name = cfg.tenant_name if cfg and cfg.tenant_name else 'منظومة بنك دم طبرق'
    return jsonify({
        "name": name, "short_name": "حضور طبرق",
        "description": "نظام الحضور والانصراف",
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
    content = r"""
const CACHE='bb-v3';
const OFFLINE=['/login','/manifest.json'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(CACHE).then(c=>c.addAll(OFFLINE)));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});
"""
    return make_response(content, 200, {'Content-Type': 'application/javascript'})


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
            session.update({'user_id': emp.id, 'username': emp.username,
                            'full_name': emp.full_name, 'role': emp.role,
                            'department': emp.department,
                            'last_activity': datetime.now(UTC).isoformat()})
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


@auth_bp.route('/api/health')
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
