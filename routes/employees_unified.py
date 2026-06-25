import csv, io, json, os, re
from datetime import date, datetime, UTC
from uuid import uuid4
from flask import Blueprint, render_template, request, session, jsonify, current_app
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from models import db, AuditLog
from models.employee_government import EmployeeGovernment
from models.employee_enhanced import (
    EmployeeChild, EmployeeGrade, EmployeeQualification,
    EmployeeCertification, EmployeePromotion, PromotionEligibility,
    EmployeeLeaveBalance, LeaveType,
)
from utils.decorators import admin_required
from utils.helpers import validate_password_strength
import logging
from functools import wraps

LOGGER = logging.getLogger(__name__)


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper


employees_bp = Blueprint('employees_unified', __name__)


def _auto_username():
    last = EmployeeGovernment.query.filter(
        EmployeeGovernment.username.like('EMP%')
    ).order_by(EmployeeGovernment.id.desc()).first()
    if last:
        try:
            num = int(last.username[3:]) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    return f'EMP{num:04d}'


def _validate_national_id(nid):
    if not nid or len(nid) < 8:
        return False
    return True


def _validate_phone(phone):
    if not phone:
        return True
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if cleaned.startswith('+218'):
        cleaned = cleaned[4:]
        return len(cleaned) == 9 and cleaned.isdigit()
    if cleaned.startswith('00218'):
        cleaned = cleaned[5:]
        return len(cleaned) == 9 and cleaned.isdigit()
    return len(cleaned) >= 7 and cleaned.isdigit()


def _employee_to_dict(emp, include_sensitive=False):
    d = emp.to_dict(include_sensitive=include_sensitive)
    children = EmployeeChild.query.filter_by(employee_id=emp.id).all()
    quals = EmployeeQualification.query.filter_by(employee_id=emp.id).all()
    certs = EmployeeCertification.query.filter_by(employee_id=emp.id).all()
    promos = EmployeePromotion.query.filter_by(employee_id=emp.id).order_by(
        EmployeePromotion.effective_date.desc()).all()
    elig = PromotionEligibility.query.filter_by(employee_id=emp.id).first()

    d['children'] = [c.to_dict() for c in children]
    d['qualifications'] = [q.to_dict() for q in quals]
    d['certifications'] = [c.to_dict() for c in certs]
    d['promotions'] = [p.to_dict() for p in promos]
    d['promotion_eligibility'] = elig.to_dict() if elig else None
    d['manager_name'] = emp.manager.full_name if emp.manager else None
    d['grade_name'] = emp.grade.name_ar if emp.grade else None
    d['department_name'] = emp.department_ref.name_ar if emp.department_ref else emp.department
    return d


# ─── PAGE ROUTE ───────────────────────────────────────────────────────────────

@employees_bp.route('/admin/employees')
@admin_required
def employees_page():
    grades = EmployeeGrade.query.filter_by(is_active=True).order_by(EmployeeGrade.level).all()
    return render_template('admin/employees_consolidated.html', grades=grades)


# ─── LIST EMPLOYEES ───────────────────────────────────────────────────────────

@employees_bp.route('/api/employees')
@admin_required
@safe_api
def list_employees():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '').strip()
    department = request.args.get('department', '').strip()
    status = request.args.get('status', '').strip()
    grade_id = request.args.get('grade_id', type=int)
    sort_by = request.args.get('sort_by', 'id')
    sort_dir = request.args.get('sort_dir', 'desc')

    query = EmployeeGovernment.query.filter(EmployeeGovernment.deleted_at.is_(None))

    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                EmployeeGovernment.first_name.ilike(like),
                EmployeeGovernment.second_name.ilike(like),
                EmployeeGovernment.third_name.ilike(like),
                EmployeeGovernment.fourth_name.ilike(like),
                EmployeeGovernment.family_name.ilike(like),
                EmployeeGovernment.national_id.ilike(like),
                EmployeeGovernment.username.ilike(like),
            )
        )
    if department:
        query = query.filter(EmployeeGovernment.department == department)
    if status:
        if status == 'active':
            query = query.filter(EmployeeGovernment.is_active == True)
        elif status == 'inactive':
            query = query.filter(EmployeeGovernment.is_active == False)
    if grade_id:
        query = query.filter(EmployeeGovernment.grade_id == grade_id)

    sort_col = getattr(EmployeeGovernment, sort_by, EmployeeGovernment.id)
    if sort_dir == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total = query.count()
    employees = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        'employees': [e.to_dict() for e in employees],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
    })


# ─── GET SINGLE EMPLOYEE ──────────────────────────────────────────────────────

@employees_bp.route('/api/employees/<int:emp_id>')
@admin_required
@safe_api
def get_employee(emp_id):
    emp = EmployeeGovernment.query.get_or_404(emp_id)
    include_sensitive = request.args.get('sensitive', '0') == '1'
    return jsonify(_employee_to_dict(emp, include_sensitive=include_sensitive))


# ─── CREATE EMPLOYEE ──────────────────────────────────────────────────────────

@employees_bp.route('/api/employees', methods=['POST'])
@admin_required
@safe_api
def create_employee():
    d = request.get_json(force=True) or {}
    errors = {}

    first_name = (d.get('first_name') or '').strip()
    second_name = (d.get('second_name') or '').strip()
    family_name = (d.get('family_name') or '').strip()
    national_id = (d.get('national_id') or '').strip()
    gender = d.get('gender', '').strip()
    department = (d.get('department') or '').strip()

    if not first_name:
        errors['first_name'] = 'الاسم الأول مطلوب'
    if not second_name:
        errors['second_name'] = 'الاسم الثاني مطلوب'
    if not family_name:
        errors['family_name'] = 'اسم العائلة مطلوب'
    if not national_id:
        errors['national_id'] = 'رقم الهوية الوطنية مطلوب'
    elif not _validate_national_id(national_id):
        errors['national_id'] = 'رقم هوية غير صالح'
    elif EmployeeGovernment.query.filter_by(national_id=national_id).first():
        errors['national_id'] = 'رقم الهوية موجود مسبقاً'
    if not gender:
        errors['gender'] = 'الجنس مطلوب'
    if not department:
        errors['department'] = 'القسم مطلوب'

    phone = d.get('personal_phone', '').strip()
    if phone and not _validate_phone(phone):
        errors['personal_phone'] = 'رقم هاتف غير صالح'

    dob_str = d.get('date_of_birth', '').strip()
    date_of_birth = None
    if dob_str:
        try:
            date_of_birth = date.fromisoformat(dob_str)
        except ValueError:
            errors['date_of_birth'] = 'تاريخ ميلاد غير صالح'
    else:
        errors['date_of_birth'] = 'تاريخ الميلاد مطلوب'

    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400

    contact_email = (d.get('personal_email') or '').strip()
    hire_str = d.get('hire_date', '').strip()
    hire_date = None
    if hire_str:
        try:
            hire_date = date.fromisoformat(hire_str)
        except ValueError:
            pass

    contract_end_str = d.get('contract_end_date', '').strip()
    contract_end = None
    if contract_end_str:
        try:
            contract_end = date.fromisoformat(contract_end_str)
        except ValueError:
            pass

    emp = EmployeeGovernment(
        username=_auto_username(),
        first_name=first_name,
        second_name=second_name,
        third_name=(d.get('third_name') or '').strip(),
        fourth_name=(d.get('fourth_name') or '').strip(),
        family_name=family_name,
        national_id=national_id,
        national_id_verified=d.get('national_id_verified', False),
        date_of_birth=date_of_birth,
        gender=gender,
        marital_status=d.get('marital_status', 'single'),
        passport_number=(d.get('passport_number') or '').strip(),
        passport_expiry=date.fromisoformat(d['passport_expiry']) if d.get('passport_expiry') else None,
        personal_phone=phone,
        work_phone=(d.get('work_phone') or '').strip(),
        personal_email=contact_email,
        work_email=(d.get('work_email') or '').strip(),
        permanent_address=(d.get('permanent_address') or '').strip(),
        current_address=(d.get('current_address') or '').strip(),
        residence_province=(d.get('residence_province') or '').strip(),
        emergency_name=(d.get('emergency_name') or '').strip(),
        emergency_phone=(d.get('emergency_phone') or '').strip(),
        emergency_relation=(d.get('emergency_relation') or '').strip(),
        department=department,
        department_id=d.get('department_id'),
        job_title=(d.get('job_title') or '').strip(),
        employment_type=d.get('employment_type', 'full_time'),
        contract_type=d.get('contract_type', 'permanent'),
        hire_date=hire_date,
        contract_end_date=contract_end,
        no_end_date=d.get('no_end_date', False),
        job_classification=(d.get('job_classification') or '').strip(),
        career_path=(d.get('career_path') or '').strip(),
        category=(d.get('category') or '').strip(),
        grade_id=d.get('grade_id'),
        manager_id=d.get('manager_id'),
        branch_id=d.get('branch_id'),
        base_salary=d.get('base_salary', 0),
        housing_allowance=d.get('housing_allowance', 0.0),
        transport_allowance=d.get('transport_allowance', 0.0),
        responsibility_allowance=d.get('responsibility_allowance', 0.0),
        hazard_allowance=d.get('hazard_allowance', 0.0),
        payment_method=d.get('payment_method', 'bank_transfer'),
        bank_name=(d.get('bank_name') or '').strip(),
        bank_account_name=(d.get('bank_account_name') or '').strip(),
        bank_account_number=(d.get('bank_account_number') or '').strip(),
        iban=(d.get('iban') or '').strip(),
        bank_account_type=d.get('bank_account_type', 'personal'),
        bank_branch=(d.get('bank_branch') or '').strip(),
        bank_account_verified=d.get('bank_account_verified', False),
        spouse_name=(d.get('spouse_name') or '').strip(),
        dependent_children=d.get('dependent_children', 0),
        password_hash=generate_password_hash(d.get('password', national_id[-6:])),
        role='employee',
        is_active=True,
    )

    db.session.add(emp)
    db.session.flush()

    # Children
    for child_data in d.get('children', []):
        birth = child_data.get('birth_date')
        db.session.add(EmployeeChild(
            employee_id=emp.id,
            full_name=child_data.get('full_name', ''),
            birth_date=date.fromisoformat(birth) if birth else None,
            relation=child_data.get('relation', 'child'),
            is_student=child_data.get('is_student', False),
            is_disabled=child_data.get('is_disabled', False),
        ))

    # Qualifications
    for q in d.get('qualifications', []):
        db.session.add(EmployeeQualification(
            employee_id=emp.id,
            level=q.get('level', 'bachelor'),
            specialization=q.get('specialization', ''),
            institution=q.get('institution', ''),
            graduation_year=q.get('graduation_year', date.today().year),
            grade=q.get('grade', ''),
            is_foreign=q.get('is_foreign', False),
        ))

    # Certifications
    for c in d.get('certifications', []):
        issue = c.get('issue_date')
        expiry = c.get('expiry_date')
        db.session.add(EmployeeCertification(
            employee_id=emp.id,
            cert_type=c.get('cert_type', ''),
            cert_number=c.get('cert_number', ''),
            issuing_body=c.get('issuing_body', ''),
            issue_date=date.fromisoformat(issue) if issue else date.today(),
            expiry_date=date.fromisoformat(expiry) if expiry else None,
        ))

    # Default leave balances
    current_year = date.today().year
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    for lt in leave_types:
        existing = EmployeeLeaveBalance.query.filter_by(
            employee_id=emp.id, leave_type_id=lt.id, year=current_year
        ).first()
        if not existing:
            db.session.add(EmployeeLeaveBalance(
                employee_id=emp.id,
                leave_type_id=lt.id,
                year=current_year,
                total_days=lt.default_days or 0,
                used_days=0,
                remaining_days=lt.default_days or 0,
            ))

    db.session.commit()

    return jsonify({'ok': True, 'employee': _employee_to_dict(emp)}), 201


# ─── UPDATE EMPLOYEE ──────────────────────────────────────────────────────────

@employees_bp.route('/api/employees/<int:emp_id>', methods=['PUT'])
@admin_required
@safe_api
def update_employee(emp_id):
    emp = EmployeeGovernment.query.get_or_404(emp_id)
    d = request.get_json(force=True) or {}
    errors = {}

    phone = d.get('personal_phone', '').strip()
    if phone and not _validate_phone(phone):
        errors['personal_phone'] = 'رقم هاتف غير صالح'

    national_id = (d.get('national_id') or '').strip()
    if national_id and national_id != emp.national_id:
        if not _validate_national_id(national_id):
            errors['national_id'] = 'رقم هوية غير صالح'
        elif EmployeeGovernment.query.filter(
            EmployeeGovernment.national_id == national_id,
            EmployeeGovernment.id != emp.id,
        ).first():
            errors['national_id'] = 'رقم الهوية موجود مسبقاً'

    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400

    scalar_fields = [
        'first_name', 'second_name', 'third_name', 'fourth_name', 'family_name',
        'national_id', 'gender', 'marital_status', 'passport_number',
        'personal_phone', 'work_phone', 'personal_email', 'work_email',
        'permanent_address', 'current_address', 'residence_province',
        'emergency_name', 'emergency_phone', 'emergency_relation',
        'department', 'job_title', 'employment_type', 'contract_type',
        'job_classification', 'career_path', 'category',
        'payment_method', 'bank_name', 'bank_account_name', 'bank_account_number',
        'iban', 'bank_account_type', 'bank_branch',
        'spouse_name',
        'gov_file_number', 'gov_central_emp_id', 'gov_region', 'gov_sector',
        'gov_parent_institution', 'gov_supervisory_body',
        'administrative_region', 'work_region',
        'clearance_level', 'clearance_authority',
        'social_security_number',
        'health_insurance_level', 'life_insurance_beneficiary',
        'permission_level',
    ]
    for field in scalar_fields:
        if field in d:
            setattr(emp, field, d[field])

    boolean_fields = [
        'national_id_verified', 'no_end_date', 'bank_account_verified',
        'is_active', 'force_password_change', 'two_factor_enabled',
        'fp_enrolled', 'face_enrolled',
    ]
    for field in boolean_fields:
        if field in d:
            setattr(emp, field, bool(d[field]))

    float_fields = [
        'base_salary', 'housing_allowance', 'transport_allowance',
        'responsibility_allowance', 'hazard_allowance',
        'social_security_rate', 'accumulated_contributions',
        'health_insurance_premium', 'life_insurance_coverage',
        'life_insurance_premium', 'injury_insurance_coverage',
        'pension_rate', 'years_of_service', 'expected_pension',
        'carried_over_days', 'used_leave_days', 'remaining_leave_days',
        'annual_leave_days', 'sick_leave_days', 'maternity_leave_days',
        'paternity_leave_days', 'marriage_leave_days', 'hajj_leave_days',
        'unpaid_leave_days',
    ]
    for field in float_fields:
        if field in d:
            setattr(emp, field, float(d[field]) if d[field] is not None else 0.0)

    int_fields = [
        'grade_id', 'manager_id', 'branch_id', 'department_id',
        'dependent_children', 'retirement_age',
        'health_insurance_dependents', 'biotime_emp_id',
    ]
    for field in int_fields:
        if field in d:
            val = d[field]
            setattr(emp, field, int(val) if val is not None else None)

    date_fields = [
        ('date_of_birth', 'date_of_birth'),
        ('passport_expiry', 'passport_expiry'),
        ('id_expiry_date', 'id_expiry_date'),
        ('id_issuing_authority', 'id_issuing_authority'),
        ('hire_date', 'hire_date'),
        ('contract_end_date', 'contract_end_date'),
        ('clearance_date', 'clearance_date'),
        ('clearance_expiry', 'clearance_expiry'),
        ('social_security_start', 'social_security_start'),
    ]
    for key, attr in date_fields:
        if key in d:
            val = d[key]
            if val:
                try:
                    setattr(emp, attr, date.fromisoformat(val))
                except (ValueError, TypeError):
                    pass
            else:
                setattr(emp, attr, None)

    dob_str = d.get('date_of_birth', '').strip()
    if dob_str:
        try:
            emp.date_of_birth = date.fromisoformat(dob_str)
        except ValueError:
            pass

    if 'password' in d and d['password']:
        emp.password_hash = generate_password_hash(d['password'])

    if 'other_allowances' in d:
        emp.other_allowances_list = d['other_allowances']

    if 'assigned_devices' in d:
        emp.assigned_device_ids = d['assigned_devices']

    # Children
    if 'children' in d:
        EmployeeChild.query.filter_by(employee_id=emp.id).delete()
        for child_data in d['children']:
            birth = child_data.get('birth_date')
            db.session.add(EmployeeChild(
                employee_id=emp.id,
                full_name=child_data.get('full_name', ''),
                birth_date=date.fromisoformat(birth) if birth else None,
                relation=child_data.get('relation', 'child'),
                is_student=child_data.get('is_student', False),
                is_disabled=child_data.get('is_disabled', False),
            ))

    # Qualifications
    if 'qualifications' in d:
        EmployeeQualification.query.filter_by(employee_id=emp.id).delete()
        for q in d['qualifications']:
            db.session.add(EmployeeQualification(
                employee_id=emp.id,
                level=q.get('level', 'bachelor'),
                specialization=q.get('specialization', ''),
                institution=q.get('institution', ''),
                graduation_year=q.get('graduation_year', date.today().year),
                grade=q.get('grade', ''),
                is_foreign=q.get('is_foreign', False),
            ))

    # Certifications
    if 'certifications' in d:
        EmployeeCertification.query.filter_by(employee_id=emp.id).delete()
        for c in d['certifications']:
            issue = c.get('issue_date')
            expiry = c.get('expiry_date')
            db.session.add(EmployeeCertification(
                employee_id=emp.id,
                cert_type=c.get('cert_type', ''),
                cert_number=c.get('cert_number', ''),
                issuing_body=c.get('issuing_body', ''),
                issue_date=date.fromisoformat(issue) if issue else date.today(),
                expiry_date=date.fromisoformat(expiry) if expiry else None,
            ))

    db.session.commit()
    return jsonify({'ok': True, 'employee': _employee_to_dict(emp)})


# ─── DELETE EMPLOYEE (soft) ───────────────────────────────────────────────────

@employees_bp.route('/api/employees/<int:emp_id>', methods=['DELETE'])
@admin_required
@safe_api
def delete_employee(emp_id):
    emp = EmployeeGovernment.query.get_or_404(emp_id)
    reason = (request.get_json(force=True) or {}).get('reason', '')
    emp.deleted_at = datetime.now(UTC)
    emp.deleted_by = session.get('user_id')
    emp.delete_reason = reason
    emp.is_active = False
    db.session.commit()
    return jsonify({'ok': True, 'message': 'تم حذف الموظف'})


# ─── SEARCH ────────────────────────────────────────────────────────────────────

@employees_bp.route('/api/employees/search')
@admin_required
@safe_api
def search_employees():
    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)
    if len(q) < 2:
        return jsonify({'employees': []})

    like = f'%{q}%'
    employees = EmployeeGovernment.query.filter(
        EmployeeGovernment.deleted_at.is_(None),
        db.or_(
            EmployeeGovernment.first_name.ilike(like),
            EmployeeGovernment.second_name.ilike(like),
            EmployeeGovernment.family_name.ilike(like),
            EmployeeGovernment.national_id.ilike(like),
            EmployeeGovernment.username.ilike(like),
        ),
        EmployeeGovernment.is_active == True,
    ).limit(limit).all()

    return jsonify({
        'employees': [{
            'id': e.id,
            'username': e.username,
            'full_name': e.full_name,
            'national_id': e.national_id,
            'department': e.department,
            'job_title': e.job_title,
            'grade_name': e.grade.name_ar if e.grade else None,
        } for e in employees],
    })


# ─── BULK IMPORT ──────────────────────────────────────────────────────────────

@employees_bp.route('/api/employees/import', methods=['POST'])
@admin_required
@safe_api
def import_employees():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'الملف مطلوب'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'ok': False, 'error': 'يجب أن يكون الملف CSV'}), 400

    stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)
    imported = 0
    errors = []

    for row_idx, row in enumerate(reader, start=2):
        try:
            first = (row.get('first_name') or '').strip()
            second = (row.get('second_name') or '').strip()
            family = (row.get('family_name') or '').strip()
            nid = (row.get('national_id') or '').strip()
            dept = (row.get('department') or '').strip()
            gender = (row.get('gender') or '').strip() or 'ذكر'

            if not first or not second or not family or not nid or not dept:
                errors.append(f'الصف {row_idx}: بيانات ناقصة')
                continue

            if EmployeeGovernment.query.filter_by(national_id=nid).first():
                errors.append(f'الصف {row_idx}: رقم الهوية {nid} موجود مسبقاً')
                continue

            dob_str = (row.get('date_of_birth') or '').strip()
            dob = None
            if dob_str:
                try:
                    dob = date.fromisoformat(dob_str)
                except ValueError:
                    pass

            emp = EmployeeGovernment(
                username=_auto_username(),
                first_name=first,
                second_name=second,
                family_name=family,
                national_id=nid,
                date_of_birth=dob,
                gender=gender,
                department=dept,
                job_title=(row.get('job_title') or '').strip(),
                marital_status=(row.get('marital_status') or 'single').strip(),
                personal_phone=(row.get('personal_phone') or '').strip(),
                password_hash=generate_password_hash(nid[-6:]),
                role='employee',
                is_active=True,
            )
            db.session.add(emp)
            imported += 1
        except Exception as e:
            errors.append(f'الصف {row_idx}: {str(e)}')

    db.session.commit()
    return jsonify({
        'ok': True,
        'imported': imported,
        'errors': errors,
        'total_rows': row_idx - 1,
    })


# ─── EMPLOYEE STATS ───────────────────────────────────────────────────────────

@employees_bp.route('/api/employees/stats')
@admin_required
@safe_api
def employee_stats():
    total = EmployeeGovernment.query.filter(
        EmployeeGovernment.deleted_at.is_(None)
    ).count()
    active = EmployeeGovernment.query.filter(
        EmployeeGovernment.deleted_at.is_(None),
        EmployeeGovernment.is_active == True,
    ).count()
    inactive = total - active
    dept_stats = db.session.query(
        EmployeeGovernment.department,
        db.func.count(EmployeeGovernment.id),
    ).filter(
        EmployeeGovernment.deleted_at.is_(None),
        EmployeeGovernment.is_active == True,
    ).group_by(EmployeeGovernment.department).all()

    return jsonify({
        'total': total,
        'active': active,
        'inactive': inactive,
        'departments': [{'name': d, 'count': c} for d, c in dept_stats],
    })


# ─── NEXT EMPLOYEE ID ──────────────────────────────────────────────────────

@employees_bp.route('/api/employees/next-id')
@admin_required
@safe_api
def next_employee_id():
    return jsonify({'ok': True, 'id': _auto_username()})


# ─── CHECK DUPLICATE ───────────────────────────────────────────────────────

@employees_bp.route('/api/employees/check-duplicate', methods=['POST'])
@admin_required
@safe_api
def check_duplicate():
    d = request.get_json() or {}
    nid = (d.get('national_id') or '').strip()
    warnings = []
    if nid:
        dup = EmployeeGovernment.query.filter(
            EmployeeGovernment.national_id == nid,
            EmployeeGovernment.deleted_at.is_(None),
        ).first()
        if dup:
            warnings.append(f'رقم الهوية مستخدم للموظف: {dup.first_name} {dup.family_name}')
    return jsonify({'ok': True, 'warnings': warnings})


# ─── TOGGLE ACTIVE ─────────────────────────────────────────────────────────

@employees_bp.route('/api/employees/<int:emp_id>/toggle', methods=['POST'])
@admin_required
@safe_api
def toggle_employee(emp_id):
    emp = EmployeeGovernment.query.get_or_404(emp_id)
    emp.is_active = not emp.is_active
    db.session.commit()
    s = 'مفعّل' if emp.is_active else 'موقوف'
    return jsonify({'ok': True, 'msg': f'تم تحديث الحالة إلى: {s}.'})


# ─── RESTORE EMPLOYEE ──────────────────────────────────────────────────────

@employees_bp.route('/api/employees/<int:emp_id>/restore', methods=['POST'])
@admin_required
@safe_api
def restore_employee(emp_id):
    emp = EmployeeGovernment.query.get_or_404(emp_id)
    emp.deleted_at = None
    emp.deleted_by = None
    emp.delete_reason = None
    emp.is_active = True
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم استعادة الموظف.'})


# ─── RESET PASSWORD ────────────────────────────────────────────────────────

@employees_bp.route('/api/employees/<int:emp_id>/reset-password', methods=['POST'])
@admin_required
@safe_api
def reset_password(emp_id):
    emp = EmployeeGovernment.query.get_or_404(emp_id)
    d = request.get_json() or {}
    new_pass = (d.get('new_password') or '').strip()
    if not new_pass:
        new_pass = emp.national_id[-6:] if emp.national_id else '123456'
    valid, msg = validate_password_strength(new_pass)
    if not valid:
        return jsonify({'ok': False, 'msg': msg})
    emp.password_hash = generate_password_hash(new_pass)
    emp.force_password_change = d.get('force_change', True)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إعادة تعيين كلمة المرور.', 'password': new_pass})


# ─── PROFILE PHOTO UPLOAD ──────────────────────────────────────────────────

ALLOWED_PHOTO_EXT = {'.jpg', '.jpeg', '.png'}
MAX_PHOTO_SIZE = 2 * 1024 * 1024

@employees_bp.route('/api/employees/<int:emp_id>/photo', methods=['POST'])
@admin_required
@safe_api
def upload_photo(emp_id):
    emp = EmployeeGovernment.query.get_or_404(emp_id)
    if 'photo' not in request.files:
        return jsonify({'ok': False, 'msg': 'لم يتم اختيار ملف.'})
    f = request.files['photo']
    if not f or not f.filename:
        return jsonify({'ok': False, 'msg': 'ملف غير صالح.'})
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_PHOTO_EXT:
        return jsonify({'ok': False, 'msg': 'يُسمح فقط بملفات JPG و PNG.'})
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > MAX_PHOTO_SIZE:
        return jsonify({'ok': False, 'msg': 'حجم الملف يتجاوز 2 ميغابايت.'})
    fname = f'profile_{emp_id}_{uuid4().hex[:8]}{ext}'
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
