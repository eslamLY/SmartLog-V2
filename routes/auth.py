import time
from datetime import datetime, timedelta, UTC
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, jsonify, make_response)
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Employee, LoginAttempt, BrandingConfig
from utils.helpers import validate_password_strength
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


@auth_bp.route('/admin/db-check')
def admin_db_check():
    if session.get('role') != 'admin':
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 403
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    existing = sorted(inspector.get_table_names())

    EXPECTED_TABLES = {
        'employees': ['id', 'full_name', 'username', 'password_hash', 'email', 'phone', 'department', 'role', 'device_id', 'is_active', 'force_password_change', 'password_changed_at', 'created_at', 'updated_at', 'deleted_at'],
        'departments': ['id', 'name_ar', 'name_en', 'code', 'is_active', 'created_at', 'updated_at'],
        'attendance_logs': ['id', 'employee_id', 'clock_in', 'clock_out', 'date', 'status', 'latitude', 'longitude', 'gps_accuracy', 'device_id', 'sync_id', 'created_at'],
        'payroll_records': ['id', 'employee_id', 'month', 'year', 'base_salary', 'allowances', 'deductions', 'net_salary', 'status', 'generated_at', 'paid_at'],
        'rbac_roles': ['id', 'name', 'name_ar', 'description', 'parent_id', 'scope', 'is_system', 'is_active', 'risk_level', 'max_assignees', 'created_at', 'updated_at'],
        'rbac_permissions': ['id', 'name', 'name_ar', 'code', 'description', 'module', 'is_high_risk', 'requires_2fa', 'requires_approval', 'created_at'],
        'employee_grades': ['id', 'name', 'level', 'min_salary', 'max_salary', 'is_active', 'created_at'],
        'employee_government': ['id', 'employee_id', 'first_name', 'second_name', 'family_name', 'national_id', 'username', 'is_active', 'created_at'],
        'blocked_ips': ['id', 'ip_address', 'violation_count', 'banned_at', 'ban_expiry', 'is_permanent', 'is_active', 'updated_at'],
        'geofence_zones': ['id', 'name', 'latitude', 'longitude', 'radius_meters', 'is_active', 'created_at'],
    }

    result = {}
    for t in existing:
        cols = [c['name'] for c in inspector.get_columns(t)]
        pk = inspector.get_pk_constraint(t).get('constrained_columns', [])
        fks = [(fk['constrained_columns'], fk['referred_table']) for fk in inspector.get_foreign_keys(t)]
        result[t] = {'columns': cols, 'primary_key': pk, 'foreign_keys': fks}

    expected_set = set(EXPECTED_TABLES.keys())
    existing_set = set(existing)
    missing_tables = sorted(expected_set - existing_set)
    extra_tables = sorted(existing_set - expected_set)
    mismatched = {}
    for t in sorted(existing_set & expected_set):
        have = {c['name'] for c in inspector.get_columns(t)}
        want = set(EXPECTED_TABLES[t])
        miss = want - have
        if miss:
            mismatched[t] = sorted(miss)

    return jsonify({
        'table_count': len(existing),
        'tables': result,
        'missing_tables': missing_tables,
        'extra_tables': extra_tables,
        'incomplete_tables': mismatched,
        'needs_migration': bool(missing_tables or mismatched)
    })
