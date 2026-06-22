import json, os, io, re, random, string
from datetime import date, datetime, UTC
from uuid import uuid4

from flask import Blueprint, render_template, request, session, jsonify, current_app
from werkzeug.security import generate_password_hash
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from models import db, Employee, Department, AttendanceLog, AuditLog, \
    Permission, Role, EmployeePermission, Branch, ShiftType, BioTimeDevice
from utils.decorators import admin_required
from utils.helpers import validate_password_strength
from utils.constants import DEPARTMENTS

admin_employees_bp = Blueprint('admin_employees', __name__)

COUNTRY_CODES = [
    {'code': '+218', 'name': 'ليبيا'},
    {'code': '+20', 'name': 'مصر'},
    {'code': '+216', 'name': 'تونس'},
    {'code': '+213', 'name': 'الجزائر'},
    {'code': '+212', 'name': 'المغرب'},
    {'code': '+966', 'name': 'السعودية'},
    {'code': '+971', 'name': 'الإمارات'},
    {'code': '+974', 'name': 'قطر'},
    {'code': '+973', 'name': 'البحرين'},
    {'code': '+965', 'name': 'الكويت'},
    {'code': '+1', 'name': 'أمريكا/كندا'},
    {'code': '+44', 'name': 'بريطانيا'},
]
EMPLOYMENT_TYPES = [
    {'value': 'full_time', 'label': 'دوام كامل'},
    {'value': 'part_time', 'label': 'دوام جزئي'},
    {'value': 'contract', 'label': 'عقد'},
    {'value': 'temporary', 'label': 'مؤقت'},
]
PERMISSION_LEVELS = [
    {'value': 'admin', 'label': 'مدير نظام'},
    {'value': 'hr_manager', 'label': 'مدير موارد بشرية'},
    {'value': 'supervisor', 'label': 'مشرف'},
    {'value': 'employee', 'label': 'موظف'},
]
RELATIONSHIPS = [
    'أب', 'أم', 'زوج', 'زوجة', 'أخ', 'أخت', 'ابن', 'ابنة', 'آخر'
]
ALLOWED_PHOTO_EXT = {'.jpg', '.jpeg', '.png'}
MAX_PHOTO_SIZE = 2 * 1024 * 1024


def allowed_photo(filename):
    return '.' in filename and os.path.splitext(filename)[1].lower() in ALLOWED_PHOTO_EXT


def generate_employee_id():
    last = Employee.query.filter(Employee.username.like('EMP%')).order_by(Employee.id.desc()).first()
    if last:
        try:
            num = int(last.username.replace('EMP', ''))
            return f'EMP{num + 1:03d}'
        except ValueError:
            pass
    return 'EMP001'


def generate_random_password(length=12):
    chars = string.ascii_letters + string.digits + '@#$%&*'
    return ''.join(random.choice(chars) for _ in range(length))


# ─── PAGE: EMPLOYEE LIST (redirect to consolidated) ────────────

@admin_employees_bp.route('/admin/employees-legacy')
@admin_required
def admin_employees():
    return render_template('admin/employees.html',
        employees=[], q='', dept='', departments=DEPARTMENTS, depts_db=[],
        page_obj=None, branches=[], shifts=[], devices=[], managers=[],
        country_codes=COUNTRY_CODES, employment_types=EMPLOYMENT_TYPES,
        permission_levels=PERMISSION_LEVELS, relationships=RELATIONSHIPS)


# ─── API: AUTO-GENERATE EMP ID ────────────────────────────────

@admin_employees_bp.route('/admin/employees/next-id')
@admin_required
def next_employee_id():
    return jsonify({'ok': True, 'id': generate_employee_id()})


# ─── API: CHECK DUPLICATE ─────────────────────────────────────

@admin_employees_bp.route('/admin/employees/check-duplicate', methods=['POST'])
@admin_required
def check_duplicate_employee():
    d = request.get_json() or {}
    name = d.get('full_name', '').strip()
    nid  = d.get('national_id', '').strip()
    warnings = []
    if name:
        dup_name = Employee.query.filter(Employee.full_name.ilike(name), Employee.deleted_at == None).first()
        if dup_name:
            warnings.append(f'يوجد موظف بنفس الاسم: {dup_name.full_name} ({dup_name.username})')
    if nid:
        dup_nid = Employee.query.filter_by(national_id=nid, deleted_at=None).first()
        if dup_nid:
            warnings.append(f'الرقم الوطني مستخدم بالفعل للموظف: {dup_nid.full_name}')
    return jsonify({'ok': True, 'warnings': warnings})


# ─── API: ADD EMPLOYEE ────────────────────────────────────────

@admin_employees_bp.route('/admin/employees/add', methods=['POST'])
@admin_required
def add_employee():
    d = request.get_json() or {}
    username = d.get('username', '').strip().upper()
    if not username:
        username = generate_employee_id()
    if Employee.query.filter_by(username=username).first():
        return jsonify({'ok': False, 'msg': 'الرقم الوظيفي مستخدم بالفعل.'})
    password = d.get('password', generate_random_password())
    valid, msg = validate_password_strength(password)
    if not valid:
        return jsonify({'ok': False, 'msg': msg})
    dept = Department.query.get(int(d['department_id'])) if d.get('department_id') else None
    emp = Employee(
        username=username,
        full_name=d.get('full_name', '').strip(),
        department=dept.name_ar if dept else d.get('department', ''),
        department_id=dept.id if dept else None,
        role=d.get('role', 'employee'),
        password_hash=generate_password_hash(password),
        base_salary=float(d.get('salary', 0)),
        phone_country_code=d.get('phone_country_code', '+218'),
        national_id=d.get('national_id', '').strip() or None,
        date_of_birth=datetime.strptime(d['date_of_birth'], '%Y-%m-%d').date() if d.get('date_of_birth') else None,
        gender=d.get('gender'),
        marital_status=d.get('marital_status'),
        address=d.get('address', '').strip() or None,
        job_title=d.get('job_title', '').strip() or None,
        employment_type=d.get('employment_type', 'full_time'),
        hire_date=datetime.strptime(d['hire_date'], '%Y-%m-%d').date() if d.get('hire_date') else date.today(),
        contract_end_date=datetime.strptime(d['contract_end_date'], '%Y-%m-%d').date() if d.get('contract_end_date') else None,
        no_end_date=d.get('no_end_date', False),
        manager_id=int(d['manager_id']) if d.get('manager_id') else None,
        shift_type_id=int(d['shift_type_id']) if d.get('shift_type_id') else None,
        branch_id=int(d['branch_id']) if d.get('branch_id') else None,
        biotime_emp_id=int(d['biotime_emp_id']) if d.get('biotime_emp_id') else None,
        housing_allowance=float(d.get('housing_allowance', 0)),
        transport_allowance=float(d.get('transport_allowance', 0)),
        payment_method=d.get('payment_method', 'bank_transfer'),
        bank_account_number=d.get('bank_account_number', '').strip() or None,
        bank_name=d.get('bank_name', '').strip() or None,
        permission_level=d.get('permission_level', 'employee'),
        force_password_change=d.get('force_password_change', True),
        two_factor_enabled=d.get('two_factor_enabled', False),
        emergency_contact_name=d.get('emergency_contact_name', '').strip() or None,
        emergency_relationship=d.get('emergency_relationship', '').strip() or None,
        emergency_phone=d.get('emergency_phone', '').strip() or None,
        emergency_phone2=d.get('emergency_phone2', '').strip() or None,
    )
    other = d.get('other_allowances', [])
    if other:
        emp.other_allowances_list = other
    devices = d.get('assigned_devices', [])
    if devices:
        emp.assigned_device_ids = devices
    if d.get('phone'):
        emp.secure_phone = d['phone'].strip()
    db.session.add(emp)
    db.session.flush()
    db.session.add(AuditLog(user_name=session.get('full_name', 'admin'), action='create',
        entity_type='employee', entity_id=emp.id,
        changes=json.dumps({'username': emp.username, 'full_name': emp.full_name}),
        ip_address=request.remote_addr))
    db.session.commit()
    result = {'ok': True, 'msg': f'تم إضافة {emp.full_name} بنجاح.', 'id': emp.id, 'username': emp.username}
    return jsonify(result)


# ─── API: GET EMPLOYEE DETAIL ─────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>')
@admin_required
def get_employee(eid):
    emp = Employee.query.get_or_404(eid)
    return jsonify({'ok': True, 'employee': emp.to_dict(include_sensitive=True)})


# ─── API: UPDATE EMPLOYEE ─────────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/edit', methods=['POST'])
@admin_required
def edit_employee(eid):
    emp = Employee.query.get_or_404(eid)
    d   = request.get_json() or {}
    changed = {}
    if 'full_name' in d and d['full_name'] != emp.full_name:
        emp.full_name = d['full_name']; changed['full_name'] = d['full_name']
    if 'salary' in d:
        emp.base_salary = float(d['salary']); changed['salary'] = d['salary']
    if 'department_id' in d:
        dept = Department.query.get(int(d['department_id']))
        if dept: emp.department_id = dept.id; emp.department = dept.name_ar; changed['department'] = dept.name_ar
    if 'password' in d and d['password']:
        valid, msg = validate_password_strength(d['password'])
        if not valid: return jsonify({'ok': False, 'msg': msg})
        emp.password_hash = generate_password_hash(d['password']); changed['password'] = True
    if 'phone' in d: emp.secure_phone = d['phone']; changed['phone'] = d['phone']
    if 'phone_country_code' in d: emp.phone_country_code = d['phone_country_code']
    if 'national_id' in d: emp.national_id = d['national_id'] or None
    if 'date_of_birth' in d: emp.date_of_birth = datetime.strptime(d['date_of_birth'], '%Y-%m-%d').date() if d.get('date_of_birth') else None
    if 'gender' in d: emp.gender = d['gender']
    if 'marital_status' in d: emp.marital_status = d['marital_status']
    if 'address' in d: emp.address = d['address']
    if 'job_title' in d: emp.job_title = d['job_title']
    if 'employment_type' in d: emp.employment_type = d['employment_type']
    if 'hire_date' in d: emp.hire_date = datetime.strptime(d['hire_date'], '%Y-%m-%d').date() if d.get('hire_date') else None
    if 'contract_end_date' in d: emp.contract_end_date = datetime.strptime(d['contract_end_date'], '%Y-%m-%d').date() if d.get('contract_end_date') else None
    if 'no_end_date' in d: emp.no_end_date = d['no_end_date']
    if 'manager_id' in d: emp.manager_id = int(d['manager_id']) if d['manager_id'] else None
    if 'shift_type_id' in d: emp.shift_type_id = int(d['shift_type_id']) if d['shift_type_id'] else None
    if 'branch_id' in d: emp.branch_id = int(d['branch_id']) if d['branch_id'] else None
    if 'housing_allowance' in d: emp.housing_allowance = float(d['housing_allowance'])
    if 'transport_allowance' in d: emp.transport_allowance = float(d['transport_allowance'])
    if 'other_allowances' in d: emp.other_allowances_list = d['other_allowances']
    if 'payment_method' in d: emp.payment_method = d['payment_method']
    if 'bank_account_number' in d: emp.bank_account_number = d['bank_account_number'] or None
    if 'bank_name' in d: emp.bank_name = d['bank_name'] or None
    if 'permission_level' in d: emp.permission_level = d['permission_level']
    if 'force_password_change' in d: emp.force_password_change = d['force_password_change']
    if 'two_factor_enabled' in d: emp.two_factor_enabled = d['two_factor_enabled']
    if 'emergency_contact_name' in d: emp.emergency_contact_name = d['emergency_contact_name']
    if 'emergency_relationship' in d: emp.emergency_relationship = d['emergency_relationship']
    if 'emergency_phone' in d: emp.emergency_phone = d['emergency_phone']
    if 'emergency_phone2' in d: emp.emergency_phone2 = d['emergency_phone2']
    if 'biotime_emp_id' in d: emp.biotime_emp_id = int(d['biotime_emp_id']) if d['biotime_emp_id'] else None
    if 'assigned_devices' in d: emp.assigned_device_ids = d['assigned_devices']
    if changed:
        db.session.add(AuditLog(user_name=session.get('full_name', 'admin'), action='edit',
            entity_type='employee', entity_id=eid,
            changes=json.dumps(changed, ensure_ascii=False), ip_address=request.remote_addr))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم تحديث بيانات الموظف.'})


# ─── API: SOFT DELETE EMPLOYEE ────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/delete', methods=['POST'])
@admin_required
def delete_employee(eid):
    emp = Employee.query.get_or_404(eid)
    d = request.get_json() or {}
    reason = d.get('reason', '').strip()
    if not reason:
        return jsonify({'ok': False, 'msg': 'يرجى كتابة سبب الحذف.'})
    emp.deleted_at = datetime.now(UTC)
    emp.deleted_by = session['user_id']
    emp.delete_reason = reason
    emp.is_active = False
    db.session.add(AuditLog(user_name=session.get('full_name', 'admin'), action='delete',
        entity_type='employee', entity_id=eid,
        changes=json.dumps({'reason': reason}), ip_address=request.remote_addr))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف الموظف.'})


# ─── API: RESTORE EMPLOYEE ────────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/restore', methods=['POST'])
@admin_required
def restore_employee(eid):
    emp = Employee.query.get_or_404(eid)
    emp.deleted_at = None
    emp.deleted_by = None
    emp.delete_reason = None
    emp.is_active = True
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم استعادة الموظف.'})


# ─── API: TOGGLE ACTIVE ───────────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/toggle', methods=['POST'])
@admin_required
def toggle_employee(eid):
    emp = Employee.query.get_or_404(eid)
    emp.is_active = not emp.is_active
    db.session.commit()
    s = 'مفعّل' if emp.is_active else 'موقوف'
    return jsonify({'ok': True, 'msg': f'تم تحديث حالة الموظف إلى: {s}.'})


# ─── API: RESET DEVICE ────────────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/reset-device', methods=['POST'])
@admin_required
def reset_device(eid):
    emp = Employee.query.get_or_404(eid)
    emp.device_id = None
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إعادة ضبط الجهاز للموظف {emp.full_name}.'})


# ─── API: RESET PASSWORD ──────────────────────────────────────

@admin_employees_bp.route('/admin/password-reset/<int:eid>', methods=['POST'])
@admin_required
def admin_password_reset(eid):
    emp = Employee.query.get_or_404(eid)
    d = request.get_json() or {}
    new_pass = d.get('new_password', '').strip()
    if not new_pass:
        new_pass = generate_random_password()
    valid, msg = validate_password_strength(new_pass)
    if not valid:
        return jsonify({'ok': False, 'msg': msg})
    emp.password_hash = generate_password_hash(new_pass)
    emp.device_id = None
    emp.force_password_change = d.get('force_change', True)
    emp.password_changed_at = None
    db.session.add(AuditLog(user_name=session.get('full_name', 'admin'), action='password_reset',
        entity_type='employee', entity_id=eid,
        changes=json.dumps({'target': emp.full_name, 'initiator': session.get('full_name')}),
        ip_address=request.remote_addr))
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إعادة تعيين كلمة المرور.', 'password': new_pass})


# ─── API: PROFILE PHOTO UPLOAD ────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/photo', methods=['POST'])
@admin_required
def upload_employee_photo(eid):
    emp = Employee.query.get_or_404(eid)
    if 'photo' not in request.files:
        return jsonify({'ok': False, 'msg': 'لم يتم اختيار ملف.'})
    f = request.files['photo']
    if not f or not f.filename:
        return jsonify({'ok': False, 'msg': 'ملف غير صالح.'})
    if not allowed_photo(f.filename):
        return jsonify({'ok': False, 'msg': 'يُسمح فقط بملفات JPG و PNG.'})
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > MAX_PHOTO_SIZE:
        return jsonify({'ok': False, 'msg': 'حجم الملف يتجاوز 2 ميغابايت.'})
    ext = os.path.splitext(f.filename)[1].lower()
    fname = f'profile_{eid}_{uuid4().hex[:8]}{ext}'
    upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'profiles')
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, fname)
    f.save(path)
    if emp.profile_photo:
        old_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), emp.profile_photo)
        try:
            if os.path.exists(old_path):
                os.remove(old_path)
        except OSError:
            pass
    emp.profile_photo = f'profiles/{fname}'
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم رفع الصورة.', 'photo': emp.profile_photo})


# ─── API: BIOTIME SYNC ────────────────────────────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/biotime-sync', methods=['POST'])
@admin_required
def biotime_sync_employee(eid):
    emp = Employee.query.get_or_404(eid)
    device_ids = (request.get_json() or {}).get('device_ids', [])
    if not device_ids:
        return jsonify({'ok': False, 'msg': 'اختر جهازاً واحداً على الأقل للمزامنة.'})
    results = []
    all_ok = True
    for did in device_ids:
        device = BioTimeDevice.query.get(int(did))
        if not device:
            results.append({'device_id': did, 'status': 'error', 'msg': 'الجهاز غير موجود'})
            all_ok = False
            continue
        try:
            sync_ok = _push_to_biotime_device(device, emp)
            if sync_ok:
                results.append({'device_id': did, 'device_name': device.name, 'status': 'synced'})
                emp.biotime_emp_id = emp.id
                emp.sync_status = 'synced'
            else:
                results.append({'device_id': did, 'device_name': device.name, 'status': 'failed'})
                emp.sync_status = 'failed'
                all_ok = False
        except Exception as e:
            results.append({'device_id': did, 'device_name': device.name, 'status': 'error', 'msg': str(e)})
            emp.sync_status = 'failed'
            all_ok = False
    if all_ok:
        emp.last_sync = datetime.now(UTC)
    db.session.commit()
    return jsonify({'ok': all_ok, 'msg': 'تمت المزامنة' if all_ok else 'فشلت المزامنة لبعض الأجهزة', 'results': results})


@admin_employees_bp.route('/admin/employees/<int:eid>/biotime-status')
@admin_required
def biotime_employee_status(eid):
    emp = Employee.query.get_or_404(eid)
    devices = BioTimeDevice.query.filter_by(is_active=True).all()
    device_status = []
    for device in devices:
        enrolled = _check_biotime_enrollment(device, emp.id)
        device_status.append({
            'id': device.id,
            'name': device.name,
            'fingerprint': enrolled.get('fp', False),
            'face': enrolled.get('face', False),
            'last_sync': device.last_sync.isoformat() if device.last_sync else None,
        })
    return jsonify({
        'ok': True,
        'sync_status': emp.sync_status,
        'last_sync': emp.last_sync.isoformat() if emp.last_sync else None,
        'devices': device_status,
    })


def _push_to_biotime_device(device, emp):
    try:
        import requests as req
        url = f"http://{device.ip_address}/api/employees" if device.ip_address else None
        if not url:
            return False
        payload = {
            'employee_id': emp.username,
            'full_name': emp.full_name,
            'department': emp.department,
            'password': '123456',
        }
        if device.api_key:
            headers = {'X-API-Key': device.api_key, 'Content-Type': 'application/json'}
        else:
            headers = {'Content-Type': 'application/json'}
        resp = req.post(url, json=payload, headers=headers, timeout=10)
        return resp.status_code in (200, 201)
    except Exception:
        return False


def _check_biotime_enrollment(device, emp_id):
    try:
        import requests as req
        url = f"http://{device.ip_address}/api/employees/{emp_id}/enrollment" if device.ip_address else None
        if not url:
            return {'fp': False, 'face': False}
        headers = {}
        if device.api_key:
            headers['X-API-Key'] = device.api_key
        resp = req.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {'fp': data.get('fingerprint', False), 'face': data.get('face', False)}
        return {'fp': False, 'face': False}
    except Exception:
        return {'fp': False, 'face': False}


# ─── EXISTING ENDPOINTS (preserved unchanged) ─────────────────

@admin_employees_bp.route('/admin/employees/<int:eid>/grant-permission', methods=['POST'])
@admin_required
def grant_exit_permission(eid):
    today = date.today()
    log = AttendanceLog.query.filter_by(employee_id=eid, log_date=today).first()
    if not log:
        return jsonify({'ok': False, 'msg': 'لا يوجد سجل حضور لهذا الموظف اليوم.'})
    log.has_exit_permission = True
    log.is_inside_geofence = True
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم منح إذن الخروج المؤقت.'})


@admin_employees_bp.route('/admin/departments')
@admin_required
def admin_departments():
    depts = Department.query.order_by(Department.name_ar).all()
    return render_template('admin/departments.html', depts=depts)


@admin_employees_bp.route('/admin/departments/add', methods=['POST'])
@admin_required
def add_department():
    d = request.get_json() or {}
    name = d.get('name_ar', '').strip()
    if not name:
        return jsonify({'ok': False, 'msg': 'اسم القسم مطلوب.'})
    if Department.query.filter_by(name_ar=name).first():
        return jsonify({'ok': False, 'msg': 'القسم موجود مسبقاً.'})
    dept = Department(name_ar=name, name_en=d.get('name_en', '').strip() or None)
    db.session.add(dept); db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إضافة القسم "{name}".'})


@admin_employees_bp.route('/admin/departments/<int:did>/toggle', methods=['POST'])
@admin_required
def toggle_department(did):
    dept = Department.query.get_or_404(did)
    dept.is_active = not dept.is_active
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم {"تفعيل" if dept.is_active else "تعطيل"} القسم.'})


@admin_employees_bp.route('/admin/departments/<int:did>/delete', methods=['POST'])
@admin_required
def delete_department(did):
    dept = Department.query.get_or_404(did)
    if Employee.query.filter_by(department_id=did).first():
        return jsonify({'ok': False, 'msg': 'لا يمكن حذف قسم لديه موظفين.'})
    db.session.delete(dept); db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف القسم.'})


@admin_employees_bp.route('/admin/permissions')
@admin_required
def admin_permissions():
    return render_template('admin/permissions.html',
        employees=Employee.query.filter_by(role='employee', is_active=True, deleted_at=None).all())


@admin_employees_bp.route('/api/admin/permissions')
@admin_required
def api_list_permissions():
    perms = Permission.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'code': p.code} for p in perms])


@admin_employees_bp.route('/api/admin/roles')
@admin_required
def api_list_roles():
    roles = Role.query.all()
    return jsonify([{'id': r.id, 'name': r.name,
        'permissions': json.loads(r.permissions) if r.permissions else []} for r in roles])


@admin_employees_bp.route('/api/admin/roles', methods=['POST'])
@admin_required
def api_create_role():
    d = request.get_json() or {}
    if not d.get('name'): return jsonify({'ok': False, 'msg': 'اسم الدور مطلوب.'})
    if Role.query.filter_by(name=d['name']).first():
        return jsonify({'ok': False, 'msg': 'الدور موجود مسبقاً.'})
    r = Role(name=d['name'], permissions=json.dumps(d.get('permissions', []), ensure_ascii=False))
    db.session.add(r); db.session.commit()
    return jsonify({'ok': True, 'msg': f'✓ تم إنشاء الدور {r.name}.'})


@admin_employees_bp.route('/api/admin/roles/<int:rid>/delete', methods=['POST'])
@admin_required
def api_delete_role(rid):
    r = Role.query.get_or_404(rid)
    db.session.delete(r); db.session.commit()
    return jsonify({'ok': True, 'msg': f'✓ تم حذف الدور {r.name}.'})


@admin_employees_bp.route('/api/admin/employees/permissions')
@admin_required
def api_employee_permissions_list():
    emps = Employee.query.filter_by(is_active=True, deleted_at=None).all()
    result = []
    for emp in emps:
        ep = EmployeePermission.query.filter_by(employee_id=emp.id).all()
        pid_list = [e.permission_id for e in ep]
        pnames = [p.name for p in Permission.query.filter(Permission.id.in_(pid_list)).all()] if pid_list else []
        result.append({'employee_id': emp.id, 'employee_name': emp.full_name,
            'role_name': emp.role, 'permissions': pnames})
    return jsonify(result)


@admin_employees_bp.route('/api/admin/employees/<int:eid>/permissions')
@admin_required
def api_get_employee_permissions(eid):
    emp = Employee.query.get_or_404(eid)
    all_perms = Permission.query.all()
    assigned = [ep.permission_id for ep in EmployeePermission.query.filter_by(employee_id=eid).all()]
    return jsonify({'employee_id': eid, 'employee_name': emp.full_name, 'permissions': [
        {'id': p.id, 'name': p.name, 'code': p.code, 'assigned': p.id in assigned} for p in all_perms
    ]})


@admin_employees_bp.route('/api/admin/employees/<int:eid>/permissions', methods=['POST'])
@admin_required
def api_save_employee_permissions(eid):
    d = request.get_json() or {}
    EmployeePermission.query.filter_by(employee_id=eid).delete()
    for pid in (d.get('permissions') or []):
        db.session.add(EmployeePermission(employee_id=eid, permission_id=int(pid)))
    db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم حفظ الأذونات.'})
