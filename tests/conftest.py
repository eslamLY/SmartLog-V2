import os, sys, json, tempfile, pytest, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['FIELD_ENCRYPTION_KEY'] = ''

# Use a temp file so backup/restore works
_tmp_db = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_tmp_db}'

from app import app as _app, db as _db, Employee, AttendanceLog, LeaveRequest, Department, reset_rate_limits
from app import AuditLog, Role, Permission, EmailLog, SmsLog, EmailTemplate
_app.config['TESTING'] = True
from app import limiter as _limiter
_limiter.enabled = False
from datetime import datetime, date, timedelta

@pytest.fixture(autouse=True)
def app_context():
    with _app.app_context():
        reset_rate_limits()
        _db.create_all()
        _seed_test_data()
        yield
        _db.session.remove()
        _db.drop_all()

def _cleanup_db():
    try:
        import gc
        gc.collect()
        if os.path.exists(_tmp_db):
            os.remove(_tmp_db)
    except PermissionError:
        pass

def pytest_sessionfinish(session):
    _cleanup_db()

def pytest_unconfigure(config):
    _cleanup_db()

@pytest.fixture
def client():
    _app.config['TESTING'] = True
    with _app.test_client() as c:
        yield c

def _seed_test_data():
    from werkzeug.security import generate_password_hash
    admin = Employee(username='ADM001', full_name='مدير النظام', department='إدارة', password_hash=generate_password_hash('admin123'),
        role='admin', email='admin@smartlog.ly', phone='+218911111111', is_active=True, base_salary=5000)
    emp = Employee(username='EMP001', full_name='موظف اختبار', department='اختبار', password_hash=generate_password_hash('123456'),
        role='employee', email='emp@smartlog.ly', phone='+218922222222', is_active=True, base_salary=3000)
    emp2 = Employee(username='EMP002', full_name='موظف اختبار 2', department='اختبار', password_hash=generate_password_hash('123456'),
        role='employee', email='emp2@smartlog.ly', phone='+218922222223', is_active=True, base_salary=0)
    _db.session.add_all([admin, emp, emp2])
    _db.session.commit()
    if not Department.query.get(1):
        _db.session.add(Department(id=1, code='GEN', name_ar='قسم عام', name_en='General'))
        _db.session.commit()
    for pname,pcode in [('إدارة الحضور','manage_attendance'),('إدارة التقارير','manage_reports'),('إدارة الموظفين','manage_employees'),('إدارة الإجازات','manage_leaves'),('إعدادات النظام','system_settings'),('إدارة الأدوار','manage_roles'),('سجل التدقيق','view_audit'),('النسخ الاحتياطي','manage_backups')]:
        if not Permission.query.filter_by(code=pcode).first():
            _db.session.add(Permission(name=pname, code=pcode))
    _db.session.commit()
    if not Role.query.filter_by(name='مدير النظام').first():
        perms = [p.id for p in Permission.query.all()]
        _db.session.add(Role(name='مدير النظام', permissions=json.dumps(perms)))
    if not EmailTemplate.query.first():
        _db.session.add(EmailTemplate(name='ترحيب', subject='مرحباً بك', body='مرحباً {{name}}'))
    _db.session.commit()
