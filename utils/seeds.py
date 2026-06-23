from datetime import datetime, UTC, date
from sqlalchemy import text as sa_text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from models import db, Employee, Department, AttendanceLog, \
    AuditLog, Permission, Role, EmailTemplate, BrandingConfig, \
    BioTimeDevice, ShiftType
from utils.constants import DEPARTMENTS


def seed_db():
    if not Department.query.first():
        dept_codes = {
            'مختبر التحليل': 'LAB', 'بنك الدم': 'BB', 'التمريض': 'NUR',
            'الاستقبال': 'REC', 'الإدارة': 'ADM', 'المستودع': 'WH',
            'الصيدلية': 'PHA',
        }
        for d_name in DEPARTMENTS:
            code = dept_codes.get(d_name, d_name[:3].upper())
            db.session.add(Department(code=code, name_ar=d_name))
        db.session.commit()
    if not Employee.query.filter_by(username='ADM001').first():
        dept = Department.query.filter_by(name_ar='الإدارة').first()
        db.session.add(Employee(username='ADM001', full_name='مدير النظام',
                                department='الإدارة', department_id=dept.id if dept else None,
                                password_hash=generate_password_hash('admin123'),
                                role='admin', base_salary=6000))
    samples = [
        ('EMP001', 'أحمد محمد الورفلي', 'مختبر التحليل', 3500),
        ('EMP002', 'فاطمة علي الزاوي', 'بنك الدم', 3200),
        ('EMP003', 'محمد سالم البراني', 'الاستقبال', 2800),
        ('EMP004', 'عائشة خالد الدرسي', 'التمريض', 3000),
        ('EMP005', 'يوسف إبراهيم الرفادي', 'المستودع', 2600),
        ('EMP006', 'مريم عمر الطاهر', 'مختبر التحليل', 3100),
        ('EMP007', 'خالد مصطفى القوراري', 'بنك الدم', 3300),
        ('EMP008', 'سارة نجيب الشلماني', 'الإدارة', 2900),
    ]
    for u, n, d, s in samples:
        if not Employee.query.filter_by(username=u).first():
            dept = Department.query.filter_by(name_ar=d).first()
            db.session.add(Employee(username=u, full_name=n, department=d,
                                    department_id=dept.id if dept else None,
                                    password_hash=generate_password_hash('123456'),
                                    role='employee', base_salary=s))
    for emp in Employee.query.filter(Employee.department_id.is_(None)).all():
        dept = Department.query.filter_by(name_ar=emp.department).first()
        if dept:
            emp.department_id = dept.id
    db.session.commit()


def seed_shift_types():
    defaults = [
        ('صباحي',  7, 0, 15, 0, '#22c55e', 'الدوام الصباحي (7 ص – 3 م)',   2, False),
        ('مسائي', 15, 0, 23, 0, '#f59e0b', 'الدوام المسائي (3 م – 11 م)',  2, False),
        ('ليلي',  23, 0,  7, 0, '#818cf8', 'الدوام الليلي (11 م – 7 ص)',   2, True),
        ('مختلط',  8, 0, 16, 0, '#3b82f6', 'الدوام الكامل (8 ص – 4 م)',    3, False),
        ('مناوبة طوارئ', 0, 0, 24, 0, '#ef4444', 'مناوبة الطوارئ (24 ساعة)', 1, False),
        ('نداء حضور', 8, 0, 14, 0, '#64748b', 'تحت الطلب / On-Call',       1, False),
    ]
    for name, sh, sm, eh, em, color, desc, minst, overnight in defaults:
        if not ShiftType.query.filter_by(name=name).first():
            db.session.add(ShiftType(name=name, start_hour=sh, start_min=sm,
                                     end_hour=eh, end_min=em, color=color,
                                     description=desc, min_staff=minst,
                                     is_overnight=overnight))
    db.session.commit()


def seed_leave_types():
    from models.employee_enhanced import LeaveType
    defaults = [
        ('annual',   'إجازة سنوية',   30, True,  True,  30, True,  'إجازة سنوية مدفوعة الراتب'),
        ('sick',     'إجازة مرضية',   15, True,  True,  15, True,  'إجازة مرضية بتقرير طبي'),
        ('maternity','إجازة أمومة',   60, True,  False, 60, True,  'إجازة وضع وتربية الأطفال'),
        ('paternity','إجازة أبوة',     5, True,  False,  5, True,  'إجازة للأب بمناسبة المولود'),
        ('marriage', 'إجازة زواج',     7, True,  False,  7, True,  'إجازة زواج مدفوعة'),
        ('hajj',     'إجازة حج',      15, True,  False, 15, True,  'إجازة أداء فريضة الحج'),
        ('compassionate', 'إجازة وفاة', 5, True,  False,  5, True,  'إجازة وفاة أحد الأقارب'),
        ('study',    'إجازة دراسية',  14, True,  False, 30, True,  'إجازة للامتحانات والدراسة'),
        ('unpaid',   'إجازة بدون راتب', 30, False, False, 90, True, 'إجازة بدون راتب'),
        ('emergency','إجازة طارئة',     7, True,  False,  7, True,  'إجازة للظروف الطارئة'),
    ]
    for code, name, days, paid, recurring, maxc, req_appr, notes in defaults:
        if not LeaveType.query.filter_by(code=code).first():
            db.session.add(LeaveType(code=code, name_ar=name, default_days=days,
                                     is_paid=paid, is_recurring=recurring,
                                     max_consecutive=maxc, requires_approval=req_appr,
                                     notes=notes))
    db.session.commit()


def _ensure_indexes():
    for tbl, idx, cols in [
        ('attendance_logs', 'idx_att_emp_date', ('employee_id', 'log_date')),
        ('attendance_logs', 'idx_att_status_date', ('status', 'log_date')),
        ('leave_requests', 'idx_lev_emp_status', ('employee_id', 'status')),
        ('outing_requests', 'idx_out_emp_status', ('employee_id', 'status')),
        ('audit_logs', 'idx_aud_ts', ('timestamp',)),
        ('audit_logs', 'idx_aud_action', ('action',)),
    ]:
        try:
            col_str = ', '.join(cols)
            db.session.execute(sa_text(f'CREATE INDEX IF NOT EXISTS {idx} ON {tbl} ({col_str})'))
            db.session.commit()
        except Exception:
            db.session.rollback()


def seed_enterprise():
    if not Permission.query.first():
        defaults = [('إدارة الموظفين', 'manage_employees'), ('إدارة المناوبات', 'manage_shifts'),
                    ('إدارة الحضور', 'manage_attendance'), ('إدارة التقارير', 'manage_reports'),
                    ('إعدادات النظام', 'manage_settings'), ('إدارة المستندات', 'manage_documents'),
                    ('إدارة الأذونات', 'manage_permissions'), ('الإشعارات', 'manage_notifications')]
        for n, c in defaults:
            db.session.add(Permission(name=n, code=c))
        db.session.commit()
    if not Role.query.first():
        db.session.add(Role(name='مدير النظام', permissions='["manage_employees","manage_shifts","manage_attendance","manage_reports","manage_settings","manage_documents","manage_permissions","manage_notifications"]'))
        db.session.add(Role(name='مشرف', permissions='["manage_attendance","manage_reports","manage_documents"]'))
        db.session.commit()
    if not EmailTemplate.query.first():
        db.session.add(EmailTemplate(name='تنبيه حضور', subject='تنبيه حضور وانصراف', body='مرحباً {name}، تم تسجيل حضورك بنجاح.'))
        db.session.add(EmailTemplate(name='طلب إجازة', subject='طلب إجازة جديد', body='تم تقديم طلب إجازة جديد من {name}.'))
        db.session.commit()
    if not AuditLog.query.first():
        db.session.add(AuditLog(user_name='النظام', action='init', entity_type='system', changes='{"msg":"تهيئة النظام"}'))
        db.session.commit()
    _ensure_indexes()
    if not BrandingConfig.query.first():
        cfg = BrandingConfig()
        cfg.company_lat = 32.0755
        cfg.company_lng = 23.9752
        cfg.allowed_radius_meters = 200
        db.session.add(cfg)
    if not BioTimeDevice.query.first():
        db.session.add(BioTimeDevice(serial_no='BT-001', name='جهاز البصمة الرئيسي',
                        device_type='biometric', location='المدخل الرئيسي', is_active=True))
    db.session.commit()
    try:
        rows = db.session.execute(sa_text("SELECT id, base_salary FROM employees WHERE base_salary IS NOT NULL AND base_salary_encrypted IS NULL")).fetchall()
        for row in rows:
            from models import get_fernet
            enc = get_fernet().encrypt(str(float(row[1])).encode()).decode()
            db.session.execute(sa_text("UPDATE employees SET base_salary_encrypted = :enc_val WHERE id = :eid"),
                               {"enc_val": enc, "eid": row[0]})
        db.session.commit()
    except OperationalError:
        db.session.rollback()
    for alog in AttendanceLog.query.filter(AttendanceLog.lat_in.isnot(None), AttendanceLog.lat_in_enc.is_(None)).all():
        alog.set_clock_in_coords(alog.lat_in, alog.lng_in)
    for alog in AttendanceLog.query.filter(AttendanceLog.lat_out.isnot(None), AttendanceLog.lat_out_enc.is_(None)).all():
        alog.set_clock_out_coords(alog.lat_out, alog.lng_out)
    db.session.commit()
