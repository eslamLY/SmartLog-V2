import os, sys, json, tempfile, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['FIELD_ENCRYPTION_KEY'] = ''
os.environ['RATELIMIT_ENABLED'] = 'false'

_tmp_db = tempfile.mktemp(suffix='.db')
# Default stays a throwaway SQLite file. Set TEST_DATABASE_URL to run the suite
# against a real PostgreSQL server instead (e.g. Render). Point it at an
# isolated schema via options=-c search_path=... so real data is never touched.
os.environ['DATABASE_URL'] = (
    os.environ.get('TEST_DATABASE_URL') or f'sqlite:///{_tmp_db}'
)

from app import create_app as _create_app
from models import db as _db
from models import Employee, AttendanceLog, LeaveRequest, Department
from models import AuditLog, Role, Permission, EmailLog, SmsLog, EmailTemplate
from utils.rate_limit import reset_rate_limits
from datetime import datetime, date, timedelta

_app = _create_app()
_app.config['TESTING'] = True

def _seed():
    from utils.seeds import _SEED_LOCK
    with _SEED_LOCK:
        from werkzeug.security import generate_password_hash
        admin = Employee(username='ADM001', full_name='مدير النظام', department='إدارة',
            password_hash=generate_password_hash('admin123'),
            role='admin', email='admin@smartlog.ly', phone='+218911111111', is_active=True, base_salary=5000)
        emp = Employee(username='EMP001', full_name='موظف اختبار', department='اختبار',
            password_hash=generate_password_hash('123456'),
            role='employee', email='emp@smartlog.ly', phone='+218922222222', is_active=True, base_salary=3000)
        emp2 = Employee(username='EMP002', full_name='موظف اختبار 2', department='اختبار',
            password_hash=generate_password_hash('123456'),
            role='employee', email='emp2@smartlog.ly', phone='+218922222223', is_active=True, base_salary=0)
        _db.session.add_all([admin, emp, emp2])
        _db.session.commit()
        for pname,pcode in [('إدارة الحضور','manage_attendance'),('إدارة التقارير','manage_reports'),
            ('إدارة الموظفين','manage_employees'),('إدارة الإجازات','manage_leaves'),
            ('إعدادات النظام','system_settings'),('إدارة الأدوار','manage_roles'),
            ('سجل التدقيق','view_audit'),('النسخ الاحتياطي','manage_backups')]:
            if not Permission.query.filter_by(code=pcode).first():
                _db.session.add(Permission(name=pname, code=pcode))
        _db.session.commit()
        if not Role.query.filter_by(name='مدير النظام').first():
            perms = [p.id for p in Permission.query.all()]
            _db.session.add(Role(name='مدير النظام', permissions=json.dumps(perms)))
        if not EmailTemplate.query.first():
            _db.session.add(EmailTemplate(name='ترحيب', subject='مرحباً بك', body='مرحباً {{name}}'))
        _db.session.commit()

with _app.app_context():
    _seed()
    # Baseline of the reference tables. Tests are allowed to add roles,
    # templates and permissions, but those rows must not survive into the next
    # test or assertions like "data[0] is the seeded template" depend on which
    # tests happened to run first.
    _SEED_ROLE_IDS = {r.id for r in Role.query.all()}
    _SEED_TEMPLATE_IDS = {t.id for t in EmailTemplate.query.all()}
    _SEED_PERMISSION_IDS = {p.id for p in Permission.query.all()}

_SEED_USERNAMES = ('ADM001', 'EMP001', 'EMP002')
# Passwords the suite logs in with. Tests that change a password (policy,
# reset, integration flows) commit, and nothing else puts it back, so the next
# module's login silently fails.
_SEED_PASSWORDS = {'ADM001': 'admin123', 'EMP001': '123456', 'EMP002': '123456'}
# Reference tables are reset to the baseline captured after _seed() rather
# than skipped wholesale.
_REFERENCE_BASELINE = {
    'roles': _SEED_ROLE_IDS,
    'email_templates': _SEED_TEMPLATE_IDS,
    'permissions': _SEED_PERMISSION_IDS,
}

def _purge_test_rows():
    """Delete everything the tests created, keeping the seed data intact.

    ``Session.rollback()`` cannot undo a ``commit()`` performed inside a test,
    so suites that insert rows with fixed unique keys (employees.username,
    biometric_devices.license_key) hit a UNIQUE violation on the next test, and
    unrelated suites tripped over leftover rows. Walking the metadata in reverse
    dependency order removes children before parents.
    """
    from sqlalchemy import delete
    from models import Employee
    from services.performance import invalidate_cache

    _db.session.rollback()
    for table in reversed(_db.metadata.sorted_tables):
        baseline = _REFERENCE_BASELINE.get(table.name)
        if baseline is not None:
            # Reference table: keep only the rows seeded at session start.
            stmt = delete(table).where(~table.c.id.in_(baseline))
        elif table.name == 'employees':
            stmt = delete(Employee).where(
                ~Employee.username.in_(_SEED_USERNAMES))
        else:
            stmt = delete(table)
        _db.session.execute(stmt)
    _db.session.commit()
    # Restore the seed accounts to a known state: a previous test may have
    # changed a password or deactivated the account, which breaks every
    # later login in the suite.
    from werkzeug.security import generate_password_hash
    for emp in Employee.query.filter(Employee.username.in_(_SEED_USERNAMES)).all():
        emp.password_hash = generate_password_hash(_SEED_PASSWORDS[emp.username])
        emp.is_active = True
        emp.role = 'admin' if emp.username == 'ADM001' else 'employee'
    _db.session.commit()
    # The app memoises hot reads (departments, roles) for 60s. Purging rows
    # underneath that cache leaves tests reading rows that no longer exist, so
    # the cache has to be dropped whenever the data changes.
    invalidate_cache()

@pytest.fixture(autouse=True)
def app_context():
    with _app.app_context():
        reset_rate_limits()
        yield
        try:
            _purge_test_rows()
        except Exception:
            _db.session.rollback()

@pytest.fixture
def client():
    with _app.test_client() as c:
        yield c

def _cleanup_db():
    try:
        import gc; gc.collect()
        if os.path.exists(_tmp_db): os.remove(_tmp_db)
    except PermissionError: pass

def pytest_sessionfinish(session):
    _cleanup_db()

def pytest_unconfigure(config):
    _cleanup_db()
