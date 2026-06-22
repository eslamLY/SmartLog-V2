"""
منظومة بنك دم طبرق - نظام الحضور والانصراف
Tobruk Blood Bank - Attendance Management System
"""
import os, math, uuid, io, json, base64, hashlib, time
from collections import defaultdict
from datetime import datetime, date, timedelta, UTC

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, send_file, send_from_directory, make_response)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, extract
from itsdangerous import URLSafeTimedSerializer
from cryptography.fernet import Fernet
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

# ─── APP CONFIG ───────────────────────────────────────────────────────────────
app = Flask(__name__)

# ─── PRODUCTION MODE FLAG (must be evaluated before any fallback) ──────────
FLASK_ENV = os.environ.get('FLASK_ENV', 'development').lower()
PRODUCTION = FLASK_ENV == 'production' or os.environ.get('PRODUCTION', '').lower() in ('1', 'true', 'yes')
app.config['ENV'] = FLASK_ENV
app.config['PRODUCTION'] = PRODUCTION

# ─── PRODUCTION HARD-FAIL VALIDATION ──────────────────────────────────────
if PRODUCTION:
    _missing = []
    if not os.environ.get('SECRET_KEY'):
        _missing.append("'SECRET_KEY'")
    if not os.environ.get('DATABASE_URL'):
        _missing.append("'DATABASE_URL'")
    if not os.environ.get('FIELD_ENCRYPTION_KEY'):
        _missing.append("'FIELD_ENCRYPTION_KEY'")
    if _missing:
        raise RuntimeError(
            'CRITICAL CONFIGURATION ERROR: '
            + ', '.join(_missing)
            + ' environment variable(s) required in production mode!'
        )

_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if PRODUCTION:
        raise RuntimeError('CRITICAL: SECRET_KEY environment variable is required in production!')
    _secret_key = 'dev-default-insecure-key-do-not-use-in-production'
app.secret_key = _secret_key

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    if PRODUCTION:
        raise RuntimeError('CRITICAL: DATABASE_URL environment variable is required in production!')
    DATABASE_URL = 'sqlite:///bloodbank.db'
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# ─── SECURE SESSION CONFIG ───────────────────────────────────────────────
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if PRODUCTION:
    app.config['SESSION_COOKIE_SECURE'] = True

# ─── FIELD-LEVEL ENCRYPTION ──────────────────────────────────────────────
_FIELD_KEY = os.environ.get('FIELD_ENCRYPTION_KEY')
if _FIELD_KEY:
    _key = _FIELD_KEY.encode() if isinstance(_FIELD_KEY, str) else _FIELD_KEY
elif not PRODUCTION:
    _key = base64.urlsafe_b64encode(hashlib.sha256(app.secret_key.encode()).digest())
else:
    raise RuntimeError('CRITICAL: FIELD_ENCRYPTION_KEY environment variable is required in production!')
fernet = Fernet(_key)

from models import db, set_fernet
from models import (Employee, Department, AttendanceLog,
    LeaveRequest, OutingRequest, GPSLog,
    BioTimeDevice, BrandingConfig, TrustedDevice,
    BiometricCredential, Notification, EmployeeDocument,
    AuditLog, Role, Permission, EmployeePermission,
    EmailTemplate, EmailLog, SmsLog,
    LoginAttempt, ShiftType, ShiftSchedule, ShiftSwapRequest,
    DocumentReference, ArchivedDocument, AttendanceReviewQueue)
set_fernet(fernet)
db.init_app(app)
migrate = Migrate(app, db)
from routes.employee import employee_bp
from routes.auth import auth_bp
app.register_blueprint(employee_bp)
app.register_blueprint(auth_bp)
from routes.admin_attendance import admin_attendance_bp
app.register_blueprint(admin_attendance_bp)
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

# ─── PWA OFFLINE PAGE ──────────────────────────────────────────────────────
@app.route('/pwa/offline')
def pwa_offline():
    return render_template('pwa/offline.html'), 200, {'Service-Worker-Allowed': '/'}

# ─── CUSTOM JINJA2 FILTERS ────────────────────────────────────────────────
@app.template_filter('todatetime')
def todatetime_filter(val):
    """Convert a (year, month, day) tuple to a date object."""
    from datetime import date
    if isinstance(val, (list, tuple)) and len(val) == 3:
        return date(val[0], val[1], val[2])
    return val

# ─── CSRF & RATE LIMITER ──────────────────────────────────────────────────────
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

# QR token serializer — tokens expire in 5 seconds
qr_serializer = URLSafeTimedSerializer(app.secret_key)

@app.before_request
def check_auto_ban():
    if request.path.startswith(('/static/', '/manifest.json', '/sw.js', '/uploads/', '/logout', '/api/health', '/admin/backup')):
        return
    ip = request.remote_addr or 'unknown'
    result = check_ip_flood(ip, max_requests=266, window_seconds=60)
    if not result['ok']:
        return render_template('blocked.html'), 429

# ─── PRODUCTION MIDDLEWARE (HSTS + HTTPS REDIRECT) ────────────────────────
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

# ─── ALL ROUTE DEFINITIONS MOVED TO BLUEPRINTS ────────────────────────────────
# See: routes/admin_ops.py, routes/admin_shifts.py, routes/admin_attendance.py,
#      routes/admin_employees.py, routes/admin_system.py, routes/employee.py,
#      routes/auth.py

if __name__ == '__main__':
    with app.app_context():
        from flask_migrate import upgrade
        upgrade()
        from utils.seeds import seed_enterprise, seed_db, seed_shift_types, seed_leave_types
        seed_enterprise()
        seed_db()
        seed_shift_types()
        seed_leave_types()
        # Ensure backup + prediction tables exist (for new models not yet in migrations)
        from models import db
        from models.backup import BackupMetadata, BackupSchedule, BackupAuditLog, BackupConfig, BackupRestoreLog
        from models.predictions import ModelRegistry, ModelPerformanceLog, PredictionResult, CustomRule, HolidayCalendar, AnomalyLog, RiskAssessment
        db.create_all()
        if not BackupConfig.query.first():
            db.session.add(BackupConfig())
            db.session.commit()
    app.run(debug=True, host='0.0.0.0', port=5000)
