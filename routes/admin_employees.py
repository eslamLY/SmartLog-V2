import json
from datetime import date

from flask import Blueprint, render_template, request, session, jsonify
from werkzeug.security import generate_password_hash

from models import db, Employee, Department, AttendanceLog, AuditLog, \
    Permission, Role, EmployeePermission
from utils.decorators import admin_required
from utils.helpers import validate_password_strength
from utils.constants import DEPARTMENTS

admin_employees_bp = Blueprint('admin_employees', __name__)


@admin_employees_bp.route('/admin/employees')
@admin_required
def admin_employees():
    q    = request.args.get('q', '').strip()
    dept = request.args.get('dept', '')
    page = request.args.get('page', 1, type=int)
    today= date.today()
    query= Employee.query.filter_by(role='employee')
    if q:
        query = query.filter(db.or_(Employee.full_name.ilike(f'%{q}%'),
                                    Employee.username.ilike(f'%{q}%')))
    if dept:
        query = query.filter_by(department=dept)
    pagination = query.order_by(Employee.department, Employee.full_name).paginate(page=page, per_page=20, error_out=False)
    employees = pagination.items
    for emp in employees:
        log = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()
        emp.today_status = log.status if log else 'absent'
        emp.today_log    = log
        emp.clocked_in   = bool(log and log.clock_in)
    depts_db = Department.query.filter_by(is_active=True).order_by(Department.name_ar).all()
    return render_template('admin/employees.html',
        employees=employees, q=q, dept=dept, departments=DEPARTMENTS, depts_db=depts_db,
        page_obj=pagination)


@admin_employees_bp.route('/admin/employees/add', methods=['POST'])
@admin_required
def add_employee():
    d = request.get_json() or {}
    if Employee.query.filter_by(username=d['username'].upper()).first():
        return jsonify({'ok': False, 'msg': 'الرقم الوظيفي مستخدم بالفعل.'})
    valid, msg = validate_password_strength(d.get('password', ''))
    if not valid:
        return jsonify({'ok': False, 'msg': msg})
    dept = Department.query.get(int(d['department_id'])) if d.get('department_id') else None
    emp = Employee(username=d['username'].upper(), full_name=d['full_name'],
                   department=dept.name_ar if dept else d.get('department', ''),
                   department_id=dept.id if dept else None,
                   role=d.get('role', 'employee'),
                   password_hash=generate_password_hash(d['password']),
                   base_salary=float(d.get('salary', 0)))
    db.session.add(emp)
    db.session.commit()
    db.session.add(AuditLog(user_name=session.get('full_name', 'admin'), action='create',
        entity_type='employee', entity_id=emp.id,
        changes=json.dumps({'username': emp.username, 'full_name': emp.full_name}),
        ip_address=request.remote_addr))
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إضافة {emp.full_name} بنجاح.', 'id': emp.id})


@admin_employees_bp.route('/admin/employees/<int:eid>/edit', methods=['POST'])
@admin_required
def edit_employee(eid):
    emp = Employee.query.get_or_404(eid)
    d   = request.get_json() or {}
    if 'full_name'  in d: emp.full_name  = d['full_name']
    if 'salary'     in d: emp.base_salary = float(d['salary'])
    if 'department_id' in d:
        dept = Department.query.get(int(d['department_id']))
        if dept: emp.department_id = dept.id; emp.department = dept.name_ar
    if 'password' in d and d['password']:
        valid, msg = validate_password_strength(d['password'])
        if not valid:
            return jsonify({'ok': False, 'msg': msg})
        emp.password_hash = generate_password_hash(d['password'])
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم تحديث بيانات الموظف.'})


@admin_employees_bp.route('/admin/employees/<int:eid>/reset-device', methods=['POST'])
@admin_required
def reset_device(eid):
    emp = Employee.query.get_or_404(eid)
    emp.device_id = None
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إعادة ضبط الجهاز للموظف {emp.full_name}.'})


@admin_employees_bp.route('/admin/password-reset/<int:eid>', methods=['POST'])
@admin_required
def admin_password_reset(eid):
    emp = Employee.query.get_or_404(eid)
    d = request.get_json() or {}
    new_pass = d.get('new_password', '').strip()
    valid, msg = validate_password_strength(new_pass)
    if not valid:
        return jsonify({'ok': False, 'msg': msg})
    emp.password_hash = generate_password_hash(new_pass)
    emp.device_id = None
    db.session.add(AuditLog(user_name=session.get('full_name', 'admin'), action='password_reset',
        entity_type='employee', entity_id=eid,
        changes=json.dumps({'target': emp.full_name, 'initiator': session.get('full_name')}),
        ip_address=request.remote_addr))
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إعادة تعيين كلمة المرور للموظف {emp.full_name}. تم مسح ربط الجهاز.'})


@admin_employees_bp.route('/admin/employees/<int:eid>/toggle', methods=['POST'])
@admin_required
def toggle_employee(eid):
    emp = Employee.query.get_or_404(eid)
    emp.is_active = not emp.is_active
    db.session.commit()
    s = 'مفعّل' if emp.is_active else 'موقوف'
    return jsonify({'ok': True, 'msg': f'تم تحديث حالة الموظف إلى: {s}.'})


@admin_employees_bp.route('/admin/employees/<int:eid>/grant-permission', methods=['POST'])
@admin_required
def grant_exit_permission(eid):
    today = date.today()
    log   = AttendanceLog.query.filter_by(employee_id=eid, log_date=today).first()
    if not log:
        return jsonify({'ok': False, 'msg': 'لا يوجد سجل حضور لهذا الموظف اليوم.'})
    log.has_exit_permission = True
    log.is_inside_geofence  = True
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم منح إذن الخروج المؤقت.'})


# ─── ADMIN DEPARTMENTS ───────────────────────────────────────────────────────

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


# ─── ADMIN PERMISSIONS PAGE ──────────────────────────────────────────────────

@admin_employees_bp.route('/admin/permissions')
@admin_required
def admin_permissions():
    return render_template('admin/permissions.html', employees=Employee.query.filter_by(role='employee', is_active=True).all())


# ─── API: PERMISSIONS ────────────────────────────────────────────────────────

@admin_employees_bp.route('/api/admin/permissions')
@admin_required
def api_list_permissions():
    perms = Permission.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'code': p.code} for p in perms])


@admin_employees_bp.route('/api/admin/roles')
@admin_required
def api_list_roles():
    roles = Role.query.all()
    return jsonify([{'id': r.id, 'name': r.name, 'permissions': json.loads(r.permissions) if r.permissions else []} for r in roles])


@admin_employees_bp.route('/api/admin/roles', methods=['POST'])
@admin_required
def api_create_role():
    d = request.get_json() or {}
    if not d.get('name'): return jsonify({'ok': False, 'msg': 'اسم الدور مطلوب.'})
    if Role.query.filter_by(name=d['name']).first(): return jsonify({'ok': False, 'msg': 'الدور موجود مسبقاً.'})
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
    emps = Employee.query.filter_by(is_active=True).all()
    result = []
    for emp in emps:
        ep = EmployeePermission.query.filter_by(employee_id=emp.id).all()
        pid_list = [e.permission_id for e in ep]
        pnames = [p.name for p in Permission.query.filter(Permission.id.in_(pid_list)).all()] if pid_list else []
        result.append({'employee_id': emp.id, 'employee_name': emp.full_name, 'role_name': emp.role, 'permissions': pnames})
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
