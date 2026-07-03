import logging
from datetime import date, datetime, UTC, timedelta

from flask import Blueprint, render_template, request, session, jsonify
from sqlalchemy import func

from models import db, Company, Employee, AttendanceLog, BiometricDevice, Department, LeaveRequest, EmployeeDocument
from routes.company_auth import company_login_required
from services.company_service import get_current_company

company_dashboard_bp = Blueprint('company_dashboard', __name__)
log = logging.getLogger(__name__)

DAY_NAMES = ['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']


@company_dashboard_bp.route('/company/dashboard')
@company_login_required
def company_dashboard():
    company = get_current_company()
    if not company:
        return render_template('company/login.html')
    today = date.today()
    return render_template('company/dashboard.html',
        company=company,
        today=today,
        day_name=DAY_NAMES[today.weekday()],
        month_name=f'{today.month:02d}-{today.year}')


@company_dashboard_bp.route('/api/company/dashboard/stats')
@company_login_required
def company_dashboard_stats():
    company = get_current_company()
    if not company:
        return jsonify({'ok': False, 'msg': 'unauthorized'}), 403

    today = date.today()
    emp_ids = db.session.query(Employee.id).filter(
        Employee.company_id == company.id,
        Employee.deleted_at.is_(None),
        Employee.is_active == True,
    ).subquery()

    total = db.session.query(func.count(Employee.id)).filter(
        Employee.id.in_(db.session.query(emp_ids.c.id))
    ).scalar() or 0

    t_logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(db.session.query(emp_ids.c.id)),
        AttendanceLog.log_date == today,
    ).all()

    present = sum(1 for l in t_logs if l.status in ('present', 'late'))
    late = sum(1 for l in t_logs if l.status == 'late')
    absent = total - present

    on_leave = LeaveRequest.query.filter(
        LeaveRequest.employee_id.in_(db.session.query(emp_ids.c.id)),
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= today,
        LeaveRequest.end_date >= today,
    ).count()

    devices = BiometricDevice.query.filter_by(
        company_id=company.id,
        deleted_at=None
    ).count()
    online_devices = BiometricDevice.query.filter_by(
        company_id=company.id,
        deleted_at=None,
        is_online=True
    ).count()

    return jsonify({
        'ok': True,
        'total': total,
        'present': present,
        'absent': absent,
        'late': late,
        'on_leave': on_leave,
        'no_clockout': sum(1 for l in t_logs if l.clock_in and not l.clock_out),
        'devices': devices,
        'online_devices': online_devices,
        'max_employees': company.max_employees,
        'max_devices': company.max_devices,
        'employee_count': company.employee_count,
        'device_count': company.device_count,
    })


@company_dashboard_bp.route('/api/company/dashboard/recent')
@company_login_required
def company_dashboard_recent():
    company = get_current_company()
    if not company:
        return jsonify({'ok': False, 'msg': 'unauthorized'}), 403

    today = date.today()
    records = db.session.query(AttendanceLog, Employee).join(
        Employee, AttendanceLog.employee_id == Employee.id
    ).filter(
        Employee.company_id == company.id,
        AttendanceLog.log_date == today,
    ).order_by(AttendanceLog.clock_in.desc().nullslast()).limit(10).all()

    result = []
    for log, emp in records:
        result.append({
            'employee_name': emp.full_name,
            'department': emp.department,
            'clock_in': log.clock_in.strftime('%H:%M') if log.clock_in else None,
            'clock_out': log.clock_out.strftime('%H:%M') if log.clock_out else None,
            'status': log.status or 'absent',
        })

    return jsonify({'ok': True, 'items': result})
