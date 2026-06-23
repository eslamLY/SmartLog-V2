"""
Tobruk Blood Bank - Attendance Management System
Production entry point with bulletproof database startup.
"""
import os, sys, math, uuid, io, json, base64, hashlib, time, logging
from collections import defaultdict
from datetime import datetime, date, timedelta, UTC

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, send_file, send_from_directory, make_response)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, extract, text as sa_text
from itsdangerous import URLSafeTimedSerializer
from cryptography.fernet import Fernet
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s %(message)s')
log = logging.getLogger('app')
log.info('=' * 60)
log.info('SmartLog starting up')
log.info('=' * 60)

# Log ALL environment variables (safely)
log.info('Environment:')
for key in sorted(os.environ.keys()):
    val = os.environ[key]
    if any(s in key.upper() for s in ['KEY', 'SECRET', 'TOKEN', 'PASS', 'ENCRYPT']):
        val = '****'
    elif key == 'DATABASE_URL' and val:
        val = val.split('@')[0].split('://')[0] + '://****:****@' + val.split('@')[1] if '@' in val else '****'
    log.info('  %s=%s', key, val)

# Environment Detection
FLASK_ENV = os.environ.get('FLASK_ENV', 'development').lower()
ON_RENDER = os.environ.get('RENDER', '').lower() == 'true'
PRODUCTION = FLASK_ENV == 'production' or ON_RENDER \
             or os.environ.get('PRODUCTION', '').lower() in ('1', 'true', 'yes')

log.info('Detected: FLASK_ENV=%s ON_RENDER=%s PRODUCTION=%s',
         FLASK_ENV, ON_RENDER, PRODUCTION)

# Database URL Validation
log.info('Checking DATABASE_URL...')
_DB_URL = os.environ.get('DATABASE_URL', '').strip()
_DB_CONFIGURED = True
if not _DB_URL:
    log.error('=' * 60)
    log.error('WARNING: DATABASE_URL is NOT SET.')
    log.error('  App will start in DEGRADED mode.')
    log.error('  Health check returns 503 until DATABASE_URL is configured.')
    log.error('')
    if ON_RENDER:
        log.error('  To fix on Render:')
        log.error('    1. Dashboard -> Databases -> smartlog-db -> Connections')
        log.error('    2. Copy "Connection String"')
        log.error('    3. smartlog-backend -> Environment -> Add DATABASE_URL')
        log.error('    4. Paste value, click Save Changes')
    else:
        log.error('  Set: export DATABASE_URL=postgresql://user:pass@host:5432/db')
    log.error('=' * 60)
    _DB_URL = 'postgresql://placeholder:placeholder@localhost:5432/nonexistent'
    _DB_CONFIGURED = False

log.info('DATABASE_URL found: %d characters', len(_DB_URL))
log.info('DATABASE_URL starts with: %s...', _DB_URL[:20])

if _DB_URL.startswith('postgres://'):
    _DB_URL = _DB_URL.replace('postgres://', 'postgresql://', 1)
    log.info('Converted postgres:// -> postgresql://')

if not _DB_URL.startswith('postgresql://'):
    log.error('FATAL: DATABASE_URL must start with postgresql://')
    log.error('  Got start: %s...', _DB_URL[:30])
    sys.exit(1)

if '@' not in _DB_URL:
    log.error('FATAL: DATABASE_URL missing @ symbol')
    log.error('  Expected: postgresql://user:pass@host:5432/dbname')
    sys.exit(1)

_masked = _DB_URL.split('@')[0].split('://')[0] + '://****:****@' + _DB_URL.split('@')[1]
log.info('DATABASE_URL (masked): %s', _masked)

# Flask App
app = Flask(__name__)

app.config['ENV'] = FLASK_ENV
app.config['PRODUCTION'] = PRODUCTION
app.config['ON_RENDER'] = ON_RENDER
app.config['SQLALCHEMY_DATABASE_URI'] = _DB_URL

# Connection pooling
_DB_POOL_SIZE = int(os.environ.get('DB_POOL_SIZE', '10'))
_DB_POOL_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '20'))
_DB_POOL_TIMEOUT = int(os.environ.get('DB_POOL_TIMEOUT', '30'))
_DB_POOL_RECYCLE = int(os.environ.get('DB_POOL_RECYCLE', '3600'))

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': _DB_POOL_SIZE,
    'max_overflow': _DB_POOL_OVERFLOW,
    'pool_timeout': _DB_POOL_TIMEOUT,
    'pool_recycle': _DB_POOL_RECYCLE,
    'pool_pre_ping': True,
    'connect_args': {'sslmode': 'require'} if PRODUCTION else {},
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# Secret Key
app.secret_key = os.environ.get('SECRET_KEY', 'blood-bank-tobruk-secret-2024')
if PRODUCTION and not os.environ.get('SECRET_KEY'):
    log.error('WARNING: SECRET_KEY not set in production!')
    log.error('  Using built-in default — set SECRET_KEY env var for security.')
    if _DB_CONFIGURED:
        log.error('FATAL: SECRET_KEY required when database is configured.')
        sys.exit(1)

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if PRODUCTION:
    app.config['SESSION_COOKIE_SECURE'] = True

# Field-level encryption
_FIELD_KEY = os.environ.get('FIELD_ENCRYPTION_KEY')
if _FIELD_KEY:
    _key = _FIELD_KEY.encode() if isinstance(_FIELD_KEY, str) else _FIELD_KEY
else:
    _key = base64.urlsafe_b64encode(hashlib.sha256(app.secret_key.encode()).digest())
fernet = Fernet(_key)

# Database Initialization
from models import db, set_fernet as _set_fernet
from models import (Employee, Department, AttendanceLog,
    LeaveRequest, OutingRequest, GPSLog,
    BioTimeDevice, BrandingConfig, TrustedDevice,
    BiometricCredential, Notification, EmployeeDocument,
    AuditLog, Role, Permission, EmployeePermission,
    EmailTemplate, EmailLog, SmsLog,
    LoginAttempt, ShiftType, ShiftSchedule, ShiftSwapRequest,
    DocumentReference, ArchivedDocument, AttendanceReviewQueue)
_set_fernet(fernet)
db.init_app(app)
migrate = Migrate(app, db)

log.info('Engine options: pool_size=%d, max_overflow=%d, ssl=%s',
         _DB_POOL_SIZE, _DB_POOL_OVERFLOW, 'require' if PRODUCTION else 'no')

# Pre-flight: Test DB connection with retries
def _test_db_connection(max_retries=5, delay=3):
    for attempt in range(1, max_retries + 1):
        try:
            with app.app_context():
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
            log.info('DB connection test PASSED (attempt %d/%d)', attempt, max_retries)
            return True
        except Exception as exc:
            log.warning('DB connection test FAILED (attempt %d/%d): %s',
                        attempt, max_retries, exc)
            if attempt < max_retries:
                log.info('Retrying in %d seconds...', delay)
                time.sleep(delay)
    return False

if _DB_CONFIGURED:
    if not _test_db_connection():
        log.error('=' * 60)
        log.error('FATAL: Could not connect to database after retries.')
        log.error('  DATABASE_URL: %s', _masked)
        log.error('')
        log.error('  Possible causes:')
        log.error('  1. Database is still provisioning (wait 2 min, redeploy)')
        log.error('  2. DATABASE_URL has wrong credentials')
        log.error('  3. Database IP allow list blocks connection')
        log.error('  4. Database was paused (starter plan)')
        log.error('')
        log.error('  To verify connection string:')
        log.error('    psql "$DATABASE_URL" -c "SELECT 1"')
        log.error('')
        log.error('  In Render Dashboard:')
        log.error('    Databases -> smartlog-db -> Logs -> check for errors')
        log.error('    smartlog-backend -> Environment -> verify DATABASE_URL')
        log.error('=' * 60)
        sys.exit(1)

    # Auto-create tables
    with app.app_context():
        try:
            db.create_all()
            log.info('Tables: ALL verified (db.create_all() completed)')
        except Exception as exc:
            log.error('FATAL: db.create_all() failed: %s', exc)
            if PRODUCTION:
                sys.exit(1)
else:
    log.warning('DATABASE_URL not configured — skipping DB initialization')

# Route Blueprints
from routes.employee import employee_bp
from routes.auth import auth_bp
app.register_blueprint(employee_bp)
app.register_blueprint(auth_bp)
from routes.admin_attendance import admin_attendance_bp
app.register_blueprint(admin_attendance_bp)
from routes.attendance_policies import attendance_policies_bp
app.register_blueprint(attendance_policies_bp)
from routes.employees import admin_employees_bp
app.register_blueprint(admin_employees_bp)
from routes.employees_unified import employees_bp
app.register_blueprint(employees_bp)
from routes.devices import admin_devices_bp
app.register_blueprint(admin_devices_bp)
from routes.admin_system import admin_system_bp
app.register_blueprint(admin_system_bp)
from routes.admin_shifts import admin_shifts_bp
app.register_blueprint(admin_shifts_bp)
from routes.admin_ops import admin_ops_bp
app.register_blueprint(admin_ops_bp)
from routes.api_hrms import hrms_api_bp
app.register_blueprint(hrms_api_bp)
from routes.api_documents import api_documents_bp
app.register_blueprint(api_documents_bp)
from routes.departments import admin_departments_bp
app.register_blueprint(admin_departments_bp)
from routes.dashboard import admin_dashboard_bp
app.register_blueprint(admin_dashboard_bp)
from routes.reports import admin_reports_bp
app.register_blueprint(admin_reports_bp)
from routes.reports_attendance import reports_attendance_bp
app.register_blueprint(reports_attendance_bp)
from routes.payroll import payroll_bp
app.register_blueprint(payroll_bp)
from routes.api_offline_sync import api_offline_sync_bp
app.register_blueprint(api_offline_sync_bp)
from routes.gps_tracking import gps_bp
app.register_blueprint(gps_bp)
from models.api_gps_receiver import gps_api_bp
app.register_blueprint(gps_api_bp)
from routes.backup_management import backup_bp
app.register_blueprint(backup_bp)
from routes.roles_permissions import rbac_bp
app.register_blueprint(rbac_bp)
from routes.employee_management import employee_mgmt_bp
app.register_blueprint(employee_mgmt_bp)
from routes.ai_forecasting import ai_forecast_bp
app.register_blueprint(ai_forecast_bp)
from routes.forecasting import forecast_bp
app.register_blueprint(forecast_bp)
from routes.scenarios import scenarios_bp
app.register_blueprint(scenarios_bp)

# Inline Health Check (always available)
_start_time = time.time()

@app.route('/api/health')
def api_health_inline():
    result = {
        'status': 'healthy',
        'database': 'unknown',
        'database_configured': _DB_CONFIGURED,
        'timestamp': datetime.now(UTC).isoformat(),
        'environment': FLASK_ENV,
        'on_render': ON_RENDER,
    }
    if not _DB_CONFIGURED:
        result['status'] = 'degraded'
        result['database'] = 'not_configured'
        result['message'] = 'Set DATABASE_URL in environment and restart'
        return jsonify(result), 503, {'Content-Type': 'application/json; charset=utf-8'}
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text('SELECT 1'))
        result['database'] = 'connected'
    except Exception as exc:
        result['status'] = 'degraded'
        result['database'] = 'disconnected: ' + str(exc)
    result['uptime_seconds'] = int(time.time() - _start_time)
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code, {'Content-Type': 'application/json; charset=utf-8'}

# PWA Offline Page
@app.route('/pwa/offline')
def pwa_offline():
    return render_template('pwa/offline.html'), 200, {'Service-Worker-Allowed': '/'}

# Custom Jinja2 Filters
@app.template_filter('todatetime')
def todatetime_filter(val):
    from datetime import date
    if isinstance(val, (list, tuple)) and len(val) == 3:
        return date(val[0], val[1], val[2])
    return val

# CSRF & Rate Limiter
csrf = CSRFProtect(app)
app.config['WTF_CSRF_CHECK_DEFAULT'] = False
limiter = Limiter(get_remote_address, app=app,
    default_limits=["10000 per day", "2000 per hour"])

@app.errorhandler(429)
def rate_limit_handler(e):
    ip = request.remote_addr or 'unknown'
    try:
        db.session.add(AuditLog(user_name='rate_limiter', action='block',
            entity_type='request', changes=f'{{"ip":"{ip}","path":"{request.path}"}}',
            ip_address=ip))
        db.session.commit()
    except Exception:
        db.session.rollback()
    return render_template('blocked.html'), 429

from utils.constants import (BLOOD_BANK_LAT, BLOOD_BANK_LNG, GEOFENCE_RADIUS_M,
    WORK_START_HOUR, WORK_START_MINUTE, LATE_GRACE_MINUTES, MAX_LOGIN_ATTEMPTS,
    SESSION_TIMEOUT_SECS, MONTH_NAMES, DAY_NAMES, DEPARTMENTS)
from utils.rate_limit import (reset_rate_limits, check_rate_limit, rate_limit_headers,
    check_flood_limit, _request_log, _user_action_log, _user_blocked_until,
    check_ip_flood)
from utils.decorators import (login_required, admin_required, employee_required,
    audit_log_action, own_data_only)
from utils.helpers import (validate_coordinates, safe_json,
    monthly_deduction, work_hours_str, calculate_mean_and_std, get_analytics_data,
    coverage_status, check_conflict)
from services.payroll_service import PayrollService
from services.notification_service import NotificationService

qr_serializer = URLSafeTimedSerializer(app.secret_key)

@app.before_request
def check_auto_ban():
    if request.path.startswith(('/static/', '/manifest.json', '/sw.js', '/uploads/', '/logout', '/api/health', '/admin/backup')):
        return
    ip = request.remote_addr or 'unknown'
    result = check_ip_flood(ip, max_requests=266, window_seconds=60)
    if not result['ok']:
        return render_template('blocked.html'), 429

# Production Security Headers
@app.after_request
def production_security_headers(response):
    if not PRODUCTION:
        return response
    host = request.host.split(':')[0].lower()
    if host in ('localhost', '127.0.0.1', '::1'):
        return response
    if request.scheme == 'http':
        secure_url = request.url.replace('http://', 'https://', 1)
        return redirect(secure_url, code=301)
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response

# Startup: Migrations + Seeding
def run_startup():
    with app.app_context():
        try:
            from flask_migrate import upgrade
            upgrade()
            log.info('Startup: flask db upgrade completed')
        except Exception as exc:
            log.warning('Startup: flask db upgrade skipped (%s)', exc)

        from models import db as _db
        for col, typ in [('early_leave_minutes', 'INTEGER DEFAULT 0'),
                         ('overtime_minutes', 'INTEGER DEFAULT 0'),
                         ('policy_id', 'INTEGER REFERENCES attendance_policies(id)')]:
            try:
                _db.session.execute(_db.text(
                    f'ALTER TABLE attendance_logs ADD COLUMN {col} {typ}'))
                _db.session.commit()
                log.info('Startup: added column attendance_logs.%s', col)
            except Exception:
                _db.session.rollback()

        try:
            from utils.seeds import seed_enterprise, seed_db, seed_shift_types, seed_leave_types
            seed_enterprise()
            seed_db()
            seed_shift_types()
            seed_leave_types()
            log.info('Startup: seed data loaded')
        except Exception as exc:
            log.warning('Startup: seeding skipped (%s)', exc)

if _DB_CONFIGURED:
    run_startup()
else:
    log.warning('Startup: skipping migrations and seeding (DATABASE_URL not configured)')

log.info('=' * 60)
log.info('SmartLog startup complete — ready to serve')
log.info('=' * 60)

if __name__ == '__main__':
    app.run(debug=not PRODUCTION, host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)))
