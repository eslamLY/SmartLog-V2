import logging
from datetime import datetime, UTC
from functools import wraps

from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from werkzeug.security import generate_password_hash
from sqlalchemy import func

from models import db, Employee, AttendanceLog, BiometricDevice, Department
from routes.company_auth import company_login_required
from services.company_service import get_current_company

company_employees_bp = Blueprint('company_employees', __name__)
log = logging.getLogger(__name__)


@company_employees_bp.route('/company/employees')
@company_login_required
def company_employee_list():
    company = get_current_company()
    if not company:
        return redirect(url_for('company_auth.company_login'))
    return render_template('company/employees.html', company=company)


@company_employees_bp.route('/api/company/employees/list')
@company_login_required
def company_employee_list_api():
    company = get_current_company()
    if not company:
        return jsonify({'ok': False, 'msg': 'unauthorized'}), 403

    employees = Employee.query.filter_by(
        company_id=company.id,
        deleted_at=None
    ).order_by(Employee.full_name).all()

    return jsonify({
        'ok': True,
        'employees': [{
            'id': e.id,
            'username': e.username,
            'full_name': e.full_name,
            'department': e.department,
            'job_title': e.job_title,
            'phone': e.secure_phone,
            'email': e.secure_email,
            'is_active': e.is_active,
            'role': e.role,
            'gender': e.gender,
            'hire_date': e.hire_date.isoformat() if e.hire_date else None,
        } for e in employees],
    })


@company_employees_bp.route('/api/company/employees/add', methods=['POST'])
@company_login_required
def company_employee_add():
    company = get_current_company()
    if not company:
        return jsonify({'ok': False, 'msg': 'unauthorized'}), 403

    if not company.can_add_employee():
        return jsonify({'ok': False, 'msg': 'لقد تجاوزت الحد الأقصى للموظفين في باقتك'}), 400

    data = request.get_json() or {}
    username = data.get('username', '').strip().upper()
    full_name = data.get('full_name', '').strip()
    password = data.get('password', '123456')

    if not username or not full_name:
        return jsonify({'ok': False, 'msg': 'اسم المستخدم والاسم الكامل مطلوبان'})

    if Employee.query.filter_by(username=username).first():
        return jsonify({'ok': False, 'msg': 'اسم المستخدم موجود بالفعل'})

    emp = Employee(
        company_id=company.id,
        username=username,
        full_name=full_name,
        department=data.get('department', ''),
        job_title=data.get('job_title', ''),
        password_hash=generate_password_hash(password),
        role='employee',
        is_active=True,
        phone=data.get('phone', ''),
        email=data.get('email', ''),
        gender=data.get('gender', ''),
    )
    db.session.add(emp)
    db.session.commit()

    return jsonify({'ok': True, 'msg': f'تم إضافة الموظف {full_name}', 'id': emp.id})


@company_employees_bp.route('/api/company/employees/<int:eid>/toggle', methods=['POST'])
@company_login_required
def company_employee_toggle(eid):
    company = get_current_company()
    emp = Employee.query.filter_by(id=eid, company_id=company.id, deleted_at=None).first()
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404
    emp.is_active = not emp.is_active
    db.session.commit()
    status = 'تفعيل' if emp.is_active else 'تعطيل'
    return jsonify({'ok': True, 'msg': f'تم {status} الموظف'})


@company_employees_bp.route('/api/company/employees/<int:eid>/delete', methods=['POST'])
@company_login_required
def company_employee_delete(eid):
    company = get_current_company()
    emp = Employee.query.filter_by(id=eid, company_id=company.id, deleted_at=None).first()
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404
    emp.deleted_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف الموظف'})
