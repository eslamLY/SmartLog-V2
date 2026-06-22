import json
from datetime import datetime, UTC

from flask import Blueprint, request, session, jsonify
from models import db, get_fernet
from models.hrms import EmployeeProfile, LeaveBalance, SalarySlipArchive
from models.employee import Employee
from utils.decorators import login_required, admin_required
from utils.rate_limit import check_rate_limit, rate_limit_headers
from services.payroll_service import PayrollService

hrms_api_bp = Blueprint('hrms_api_bp', __name__, url_prefix='/api/hrms')


def _employee_or_403(emp_id):
    """Return (Employee, None) on success or (None, jsonify(403)) on failure."""
    emp = Employee.query.get(emp_id)
    if not emp:
        return None, jsonify({'ok': False, 'msg': 'الموظف غير موجود.'}), 404
    role = session.get('role')
    uid = session.get('user_id')
    if role != 'admin' and uid != emp_id:
        return None, jsonify({'ok': False, 'msg': 'لا يمكنك الوصول إلى بيانات موظف آخر.'}), 403
    return emp, None


@hrms_api_bp.route('/profile/<int:emp_id>')
@login_required
def get_profile(emp_id):
    emp, err = _employee_or_403(emp_id)
    if err:
        return err
    profile = EmployeeProfile.query.filter_by(employee_id=emp_id).first()
    if not profile:
        return jsonify({'ok': False, 'msg': 'الملف الوظيفي غير موجود.'}), 404
    return jsonify({
        'ok': True,
        'profile': {
            'employee_id': profile.employee_id,
            'job_title': profile.job_title,
            'hire_date': profile.hire_date.isoformat() if profile.hire_date else None,
            'marital_status': profile.marital_status,
            'contract_expiry': profile.contract_expiry.isoformat() if profile.contract_expiry else None,
            'created_at': profile.created_at.isoformat(),
            'updated_at': profile.updated_at.isoformat(),
        }
    })


@hrms_api_bp.route('/profile/<int:emp_id>', methods=['POST'])
@admin_required
def update_profile(emp_id):
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود.'}), 404
    profile = EmployeeProfile.query.filter_by(employee_id=emp_id).first()
    if not profile:
        profile = EmployeeProfile(employee_id=emp_id)
        db.session.add(profile)
    data = request.get_json() or {}
    if 'job_title' in data:
        profile.job_title = str(data['job_title'])[:100]
    if 'hire_date' in data and data['hire_date']:
        try:
            profile.hire_date = datetime.strptime(data['hire_date'], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'msg': 'صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.'}), 400
    if 'marital_status' in data:
        profile.marital_status = str(data['marital_status'])[:20]
    if 'contract_expiry' in data and data['contract_expiry']:
        try:
            profile.contract_expiry = datetime.strptime(data['contract_expiry'], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'msg': 'صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.'}), 400
    db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم تحديث الملف الوظيفي.'})


@hrms_api_bp.route('/leave-balance/<int:emp_id>')
@login_required
def get_leave_balance(emp_id):
    emp, err = _employee_or_403(emp_id)
    if err:
        return err
    balances = LeaveBalance.query.filter_by(employee_id=emp_id).all()
    return jsonify({
        'ok': True,
        'leave_balances': [
            {
                'id': b.id,
                'leave_type': b.leave_type,
                'total_days': b.total_days,
                'used_days': b.used_days,
                'remaining_days': b.remaining_days,
            }
            for b in balances
        ]
    })


@hrms_api_bp.route('/payroll/archive', methods=['POST'])
@admin_required
def archive_payroll():
    allowed, remaining = check_rate_limit('hrms_archive_payroll', 10, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    data = request.get_json() or {}
    emp_id = data.get('employee_id')
    month = data.get('month')
    year = data.get('year')
    if not all([emp_id, month, year]):
        return jsonify({'ok': False, 'msg': 'الحقول employee_id و month و year مطلوبة.'}), 400
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود.'}), 404
    try:
        month_i, year_i = int(month), int(year)
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'msg': 'month و year يجب أن يكونا أرقاماً.'}), 400
    if not (1 <= month_i <= 12):
        return jsonify({'ok': False, 'msg': 'month يجب أن يكون بين 1 و 12.'}), 400
    if not (2000 <= year_i <= 2100):
        return jsonify({'ok': False, 'msg': 'year غير صالح.'}), 400
    existing = SalarySlipArchive.query.filter_by(
        employee_id=emp_id, month=month_i, year=year_i
    ).first()
    if existing:
        return jsonify({'ok': False, 'msg': 'تمت أرشفة هذا الشهر مسبقاً.'}), 409
    base = emp.base_salary
    fernet_inst = get_fernet()
    snapshot = fernet_inst.encrypt(str(base).encode()).decode() if base else None
    archive = SalarySlipArchive(
        employee_id=emp_id,
        month=month_i,
        year=year_i,
        base_salary_snapshot=snapshot,
        deductions=0.0,
        overtime_pay=0.0,
        net_salary=base,
    )
    db.session.add(archive)
    db.session.commit()
    resp = jsonify({'ok': True, 'msg': '✓ تم أرشفة المرتبات.', 'archive_id': archive.id})
    resp.headers.update(rate_limit_headers(10, remaining, 60))
    return resp


@hrms_api_bp.route('/payroll/archive/<int:emp_id>')
@login_required
def list_archives(emp_id):
    emp, err = _employee_or_403(emp_id)
    if err:
        return err
    archives = SalarySlipArchive.query.filter_by(employee_id=emp_id)\
        .order_by(SalarySlipArchive.year.desc(), SalarySlipArchive.month.desc()).all()
    return jsonify({
        'ok': True,
        'archives': [
            {
                'id': a.id,
                'month': a.month,
                'year': a.year,
                'deductions': a.deductions,
                'overtime_pay': a.overtime_pay,
                'net_salary': a.net_salary,
                'archived_at': a.archived_at.isoformat(),
            }
            for a in archives
        ]
    })
