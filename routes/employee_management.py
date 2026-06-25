import json
import logging
from datetime import date, datetime, UTC
from io import StringIO

from flask import Blueprint, render_template, request, session, jsonify, send_file

from functools import wraps
from models import db, Employee
from models.employee_enhanced import (
    EmployeeExtended, EmployeeChild, EmployeeGrade,
    EmployeeQualification, EmployeeCertification,
    EmployeePromotion, PromotionEligibility, LeaveType,
    EmployeeLeaveBalance, EmployeeLeaveRequest,
    EmployeeDelegation, EmployeeTraining,
    EmployeePerformance, EmployeeDisciplinaryAction,
)
from services.promotion_service import PromotionService
from services.leave_service import LeaveService
from services.government_export import GovernmentExport
from utils.decorators import admin_required, login_required, own_data_only

employee_mgmt_bp = Blueprint('employee_mgmt', __name__)

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


# ─── EMPLOYEE PROFILE & MANAGEMENT PAGES ──────────────────────────────────

@employee_mgmt_bp.route('/admin/employees/<int:eid>/profile')
@admin_required
def employee_profile(eid):
    emp = Employee.query.get_or_404(eid)
    grades = EmployeeGrade.query.filter_by(is_active=True).order_by(EmployeeGrade.level).all()
    return render_template('admin/employee_profile.html', employee=emp, grades=grades)


@employee_mgmt_bp.route('/admin/employees/<int:eid>/performance')
@admin_required
def employee_performance_page(eid):
    emp = Employee.query.get_or_404(eid)
    return render_template('admin/employee_performance.html', employee=emp)


@employee_mgmt_bp.route('/admin/employees/<int:eid>/training')
@admin_required
def employee_training_page(eid):
    emp = Employee.query.get_or_404(eid)
    return render_template('admin/employee_training.html', employee=emp)


@employee_mgmt_bp.route('/admin/employees/<int:eid>/discipline')
@admin_required
def employee_discipline_page(eid):
    emp = Employee.query.get_or_404(eid)
    return render_template('admin/employee_discipline.html', employee=emp)


@employee_mgmt_bp.route('/admin/employees/<int:eid>/delegations')
@admin_required
def employee_delegations_page(eid):
    emp = Employee.query.get_or_404(eid)
    return render_template('admin/employee_delegations.html', employee=emp)


# ─── EMPLOYEE SELF-SERVICE ────────────────────────────────────────────────

@employee_mgmt_bp.route('/employee/my-profile')
@login_required
def my_profile():
    emp = Employee.query.get_or_404(session['user_id'])
    grades = EmployeeGrade.query.filter_by(is_active=True).order_by(EmployeeGrade.level).all()
    return render_template('employee/my_profile.html', employee=emp, grades=grades)


# ─── ADD EMPLOYEE FORM (Multi-Tab) ─────────────────────────────────────────

@employee_mgmt_bp.route('/admin/employees/add-form')
@admin_required
def add_employee_form():
    grades = EmployeeGrade.query.filter_by(is_active=True).order_by(EmployeeGrade.level).all()
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    return render_template('admin/add_employee_form.html',
                           grades=grades, leave_types=leave_types)


@employee_mgmt_bp.route('/admin/employees/add-form/save', methods=['POST'])
@admin_required
def save_add_employee():
    d = request.get_json() or {}
    emp_id = d.get('employee_id')
    if not emp_id:
        return jsonify({'ok': False, 'msg': 'Employee ID required'})
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'Employee not found'})
    extended = emp.extended
    if not extended:
        extended = EmployeeExtended(employee_id=emp.id)
    # Personal
    extended.national_id = d.get('national_id')
    extended.passport_number = d.get('passport_number')
    ext_id_expiry = d.get('id_expiry_date')
    extended.id_expiry_date = date.fromisoformat(ext_id_expiry) if ext_id_expiry else None
    extended.id_issuing_authority = d.get('id_issuing_authority')
    extended.id_verified = d.get('id_verified', False)
    extended.personal_phone = d.get('personal_phone')
    extended.work_phone = d.get('work_phone')
    extended.personal_email = d.get('personal_email')
    extended.work_email = d.get('work_email')
    extended.permanent_address = d.get('permanent_address')
    extended.current_address = d.get('current_address')
    # Emergency
    extended.emergency_name = d.get('emergency_name')
    extended.emergency_phone = d.get('emergency_phone')
    extended.emergency_relation = d.get('emergency_relation')
    # Bank
    extended.bank_name = d.get('bank_name')
    extended.bank_account_name = d.get('bank_account_name')
    extended.iban = d.get('iban')
    extended.bank_account_type = d.get('bank_account_type', 'personal')
    extended.bank_branch = d.get('bank_branch')
    # Family
    extended.marital_status = d.get('marital_status', 'single')
    extended.spouse_name = d.get('spouse_name')
    extended.dependent_children = d.get('dependent_children', 0)
    # Grade
    grade_id = d.get('grade_id')
    if grade_id:
        extended.grade_id = int(grade_id)
    extended.job_classification = d.get('job_classification')
    extended.career_path = d.get('career_path')
    extended.contract_type = d.get('contract_type', 'permanent')
    # Government
    extended.gov_file_number = d.get('gov_file_number')
    extended.gov_central_emp_id = d.get('gov_central_emp_id')
    extended.gov_region = d.get('gov_region')
    extended.gov_sector = d.get('gov_sector')
    extended.gov_parent_institution = d.get('gov_parent_institution')
    extended.gov_supervisory_body = d.get('gov_supervisory_body')
    # Clearance
    extended.clearance_level = d.get('clearance_level', 'public')
    ext_clearance_date = d.get('clearance_date')
    extended.clearance_date = date.fromisoformat(ext_clearance_date) if ext_clearance_date else None
    ext_clearance_expiry = d.get('clearance_expiry')
    extended.clearance_expiry = date.fromisoformat(ext_clearance_expiry) if ext_clearance_expiry else None
    extended.clearance_authority = d.get('clearance_authority')
    # Social Security
    extended.social_security_number = d.get('social_security_number')
    ext_ss_start = d.get('social_security_start')
    extended.social_security_start = date.fromisoformat(ext_ss_start) if ext_ss_start else None
    extended.social_security_rate = d.get('social_security_rate', 8.0)
    # Insurance
    extended.health_insurance_level = d.get('health_insurance_level', 'basic')
    extended.health_insurance_dependents = d.get('health_insurance_dependents', 0)
    extended.health_insurance_premium = d.get('health_insurance_premium', 0.0)
    extended.life_insurance_coverage = d.get('life_insurance_coverage', 0.0)
    extended.life_insurance_beneficiary = d.get('life_insurance_beneficiary')
    extended.life_insurance_premium = d.get('life_insurance_premium', 0.0)
    extended.injury_insurance_coverage = d.get('injury_insurance_coverage', 0.0)
    # Retirement
    extended.retirement_age = d.get('retirement_age', 60)
    extended.pension_rate = d.get('pension_rate', 2.5)
    extended.years_of_service = d.get('years_of_service', 0.0)
    extended.expected_pension = d.get('expected_pension', 0.0)
    # Leave defaults
    extended.annual_leave_days = d.get('annual_leave_days', 30)
    extended.sick_leave_days = d.get('sick_leave_days', 15)
    extended.maternity_leave_days = d.get('maternity_leave_days', 60)
    extended.paternity_leave_days = d.get('paternity_leave_days', 5)
    extended.marriage_leave_days = d.get('marriage_leave_days', 7)
    extended.hajj_leave_days = d.get('hajj_leave_days', 15)

    db.session.add(extended)

    # Children
    EmployeeChild.query.filter_by(employee_id=emp.id).delete()
    for child in d.get('children', []):
        birth = child.get('birth_date')
        db.session.add(EmployeeChild(
            employee_id=emp.id,
            full_name=child.get('full_name', ''),
            birth_date=date.fromisoformat(birth) if birth else None,
            relation=child.get('relation', 'child'),
            is_student=child.get('is_student', False),
            is_disabled=child.get('is_disabled', False),
        ))

    # Qualifications
    EmployeeQualification.query.filter_by(employee_id=emp.id).delete()
    for q in d.get('qualifications', []):
        db.session.add(EmployeeQualification(
            employee_id=emp.id,
            level=q.get('level', ''),
            specialization=q.get('specialization', ''),
            institution=q.get('institution', ''),
            graduation_year=q.get('graduation_year'),
            grade=q.get('grade'),
            is_foreign=q.get('is_foreign', False),
            equivalency_file=q.get('equivalency_file'),
            certificate_file=q.get('certificate_file'),
            is_verified=q.get('is_verified', False),
        ))

    # Certifications
    EmployeeCertification.query.filter_by(employee_id=emp.id).delete()
    for c in d.get('certifications', []):
        issue = c.get('issue_date')
        expiry = c.get('expiry_date')
        db.session.add(EmployeeCertification(
            employee_id=emp.id,
            cert_type=c.get('cert_type', ''),
            cert_number=c.get('cert_number'),
            issuing_body=c.get('issuing_body', ''),
            issue_date=date.fromisoformat(issue) if issue else None,
            expiry_date=date.fromisoformat(expiry) if expiry else None,
            is_valid=c.get('is_valid', True),
            cert_file=c.get('cert_file'),
        ))

    # Initialize leave balances
    LeaveService.initialize_balances(emp.id, date.today().year)

    db.session.commit()
    return jsonify({'ok': True, 'msg': 'Employee data saved successfully'})


@employee_mgmt_bp.route('/admin/employees/<int:eid>/extended')
@admin_required
def get_employee_extended(eid):
    emp = Employee.query.get_or_404(eid)
    data = {'employee': {'id': emp.id, 'full_name': emp.full_name, 'employee_code': emp.employee_code}}
    if emp.extended:
        data['extended'] = emp.extended.to_dict()
    data['children'] = [c.to_dict() for c in emp.children]
    data['qualifications'] = [q.to_dict() for q in emp.qualifications]
    data['certifications'] = [c.to_dict() for c in emp.certifications]
    data['grade'] = emp.extended.grade.to_dict() if emp.extended and emp.extended.grade else None
    return jsonify(data)


# ─── GRADES CRUD ───────────────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/grades')
@admin_required
def list_grades():
    grades = EmployeeGrade.query.filter_by(is_active=True).order_by(EmployeeGrade.level).all()
    return render_template('admin/grades.html', grades=grades)


@employee_mgmt_bp.route('/admin/grades', methods=['POST'])
@admin_required
def save_grade():
    d = request.get_json() or {}
    gid = d.get('id')
    if gid:
        grade = EmployeeGrade.query.get_or_404(gid)
    else:
        grade = EmployeeGrade()
    grade.code = d.get('code', grade.code)
    grade.name_ar = d.get('name_ar', grade.name_ar)
    grade.category = d.get('category', grade.category)
    grade.level = d.get('level', grade.level)
    grade.base_salary = d.get('base_salary', 0.0)
    grade.responsibility_allowance = d.get('responsibility_allowance', 0.0)
    grade.hazard_allowance = d.get('hazard_allowance', 0.0)
    grade.transport_allowance = d.get('transport_allowance', 0.0)
    grade.housing_allowance = d.get('housing_allowance', 0.0)
    grade.medical_insurance_level = d.get('medical_insurance_level', 'basic')
    grade.annual_leave_days = d.get('annual_leave_days', 30)
    grade.sick_leave_days = d.get('sick_leave_days', 15)
    grade.retirement_age = d.get('retirement_age', 60)
    grade.pension_rate = d.get('pension_rate', 2.5)
    grade.min_years_for_promotion = d.get('min_years_for_promotion', 5)
    grade.required_qualification = d.get('required_qualification')
    grade.next_grade_id = d.get('next_grade_id')
    db.session.add(grade)
    db.session.commit()
    return jsonify({'ok': True, 'grade': grade.to_dict()})


@employee_mgmt_bp.route('/admin/grades/<int:gid>', methods=['DELETE'])
@admin_required
def delete_grade(gid):
    grade = EmployeeGrade.query.get_or_404(gid)
    grade.is_active = False
    db.session.commit()
    return jsonify({'ok': True})


# ─── PROMOTIONS ────────────────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/promotions')
@admin_required
def promotions_page():
    grades = EmployeeGrade.query.filter_by(is_active=True).order_by(EmployeeGrade.level).all()
    return render_template('admin/employee_promotions.html', grades=grades)


@employee_mgmt_bp.route('/admin/promotions/check/<int:eid>')
@admin_required
def check_promotion(eid):
    result = PromotionService.check_eligibility(eid)
    if result is None:
        return jsonify({'ok': False, 'msg': 'Employee not found'})
    return jsonify({'ok': True, **result})


@employee_mgmt_bp.route('/admin/promotions/execute', methods=['POST'])
@admin_required
def execute_promotion():
    d = request.get_json() or {}
    eid = d.get('employee_id')
    if not eid:
        return jsonify({'ok': False, 'msg': 'Employee ID required'})
    dec_date = d.get('decision_date')
    eff_date = d.get('effective_date')
    result = PromotionService.execute_promotion(
        employee_id=eid,
        decision_number=d.get('decision_number'),
        decision_date=date.fromisoformat(dec_date) if dec_date else None,
        effective_date=date.fromisoformat(eff_date) if eff_date else None,
        approved_by=d.get('approved_by'),
        justification=d.get('justification'),
    )
    return jsonify(result)


@employee_mgmt_bp.route('/admin/promotions/history/<int:eid>')
@admin_required
def promotion_history(eid):
    promotions = PromotionService.get_promotion_history(eid)
    return jsonify({'promotions': [p.to_dict() for p in promotions]})


@employee_mgmt_bp.route('/admin/promotions/eligible')
@admin_required
def eligible_employees():
    results = PromotionService.get_eligible_employees()
    data = []
    for r in results:
        data.append({
            'id': r['employee'].id,
            'full_name': r['employee'].full_name,
            'employee_code': r['employee'].employee_code,
            'department': r['employee'].department,
            'eligibility': r['eligibility'],
        })
    return jsonify({'employees': data})


@employee_mgmt_bp.route('/admin/promotions/grades')
@admin_required
def grade_chain():
    return jsonify({'grades': PromotionService.get_grade_chain()})


# ─── LEAVE MANAGEMENT ──────────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/leave-mgmt')
@admin_required
def leaves_page():
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    return render_template('admin/leave_management.html', leave_types=leave_types)


@employee_mgmt_bp.route('/admin/leave-mgmt/request', methods=['POST'])
@admin_required
def create_leave_request():
    d = request.get_json() or {}
    start = date.fromisoformat(d['start_date'])
    end = date.fromisoformat(d['end_date'])
    result = LeaveService.request_leave(
        employee_id=d['employee_id'],
        leave_type_id=d['leave_type_id'],
        start_date=start,
        end_date=end,
        reason=d.get('reason'),
        attachment=d.get('attachment'),
    )
    return jsonify(result)


@employee_mgmt_bp.route('/admin/leave-mgmt/approve/<int:rid>', methods=['POST'])
@admin_required
def approve_leave(rid):
    d = request.get_json() or {}
    result = LeaveService.approve_leave(rid, session['user_id'], d.get('comment'))
    return jsonify(result)


@employee_mgmt_bp.route('/admin/leave-mgmt/reject/<int:rid>', methods=['POST'])
@admin_required
def reject_leave(rid):
    d = request.get_json() or {}
    result = LeaveService.reject_leave(rid, session['user_id'], d.get('comment'))
    return jsonify(result)


@employee_mgmt_bp.route('/admin/leave-mgmt/balance/<int:eid>')
@admin_required
def leave_balance(eid):
    year = request.args.get('year', type=int) or date.today().year
    balances = LeaveService.get_employee_balance(eid, year)
    return jsonify({'balances': balances})


@employee_mgmt_bp.route('/admin/leave-mgmt/requests/<int:eid>')
@admin_required
def employee_leave_requests(eid):
    status = request.args.get('status')
    requests = LeaveService.get_employee_requests(eid, status)
    return jsonify({'requests': [r.to_dict() for r in requests]})


@employee_mgmt_bp.route('/admin/leave-mgmt/pending')
@admin_required
def pending_leaves():
    requests = LeaveService.get_pending_requests()
    return jsonify({'requests': [r.to_dict() for r in requests]})


@employee_mgmt_bp.route('/admin/leave-mgmt/init-balance/<int:eid>', methods=['POST'])
@admin_required
def init_balance(eid):
    year = request.args.get('year', type=int) or date.today().year
    LeaveService.initialize_balances(eid, year)
    return jsonify({'ok': True})


@employee_mgmt_bp.route('/admin/leave-mgmt/carry-over/<int:eid>', methods=['POST'])
@admin_required
def carry_over(eid):
    d = request.get_json() or {}
    result = LeaveService.carry_over_balance(eid, d['from_year'], d['to_year'])
    return jsonify({'ok': True, **result})


@employee_mgmt_bp.route('/admin/leave-mgmt/leave-types')
@admin_required
def list_leave_types():
    types = LeaveService.get_leave_types()
    return jsonify({'leave_types': [t.to_dict() for t in types]})


# ─── GOVERNMENT EXPORTS ────────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/export/registry')
@admin_required
def export_registry():
    dept = request.args.get('dept')
    csv_data = GovernmentExport.export_employee_registry(dept)
    return send_file(
        StringIO(csv_data),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'employee_registry_{date.today().isoformat()}.csv'
    )


@employee_mgmt_bp.route('/admin/export/pension')
@admin_required
def export_pension():
    csv_data = GovernmentExport.export_pension_data()
    return send_file(
        StringIO(csv_data),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'pension_data_{date.today().isoformat()}.csv'
    )


@employee_mgmt_bp.route('/admin/export/insurance')
@admin_required
def export_insurance():
    csv_data = GovernmentExport.export_insurance_data()
    return send_file(
        StringIO(csv_data),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'insurance_data_{date.today().isoformat()}.csv'
    )


@employee_mgmt_bp.route('/admin/export/clearance')
@admin_required
def export_clearance():
    csv_data = GovernmentExport.export_clearance_report()
    return send_file(
        StringIO(csv_data),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'clearance_report_{date.today().isoformat()}.csv'
    )


@employee_mgmt_bp.route('/admin/export/grade-distribution')
@admin_required
def grade_distribution():
    data = GovernmentExport.generate_grade_distribution()
    return jsonify({'grades': data})


# ─── EMPLOYEE PERFORMANCE ──────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/performance/<int:eid>', methods=['GET', 'POST'])
@admin_required
def manage_performance(eid):
    if request.method == 'POST':
        d = request.get_json() or {}
        year = d.get('evaluation_year', date.today().year)
        period = d.get('evaluation_period', 'annual')
        existing = EmployeePerformance.query.filter_by(
            employee_id=eid, evaluation_year=year, evaluation_period=period
        ).first()
        if not existing:
            existing = EmployeePerformance(employee_id=eid)
        existing.evaluation_year = year
        existing.evaluation_period = period
        existing.overall_rating = d.get('overall_rating')
        existing.score = d.get('score')
        existing.evaluated_by = d.get('evaluated_by', session['user_id'])
        existing.comments = d.get('comments')
        existing.goals_next_period = d.get('goals_next_period')
        existing.status = d.get('status', 'completed')
        if existing.status == 'completed':
            existing.completed_at = datetime.now(UTC)
        db.session.add(existing)
        db.session.commit()
        return jsonify({'ok': True, 'performance': existing.to_dict()})
    evaluations = EmployeePerformance.query.filter_by(employee_id=eid)\
        .order_by(EmployeePerformance.created_at.desc()).all()
    return jsonify({'evaluations': [e.to_dict() for e in evaluations]})


# ─── DISCIPLINARY ACTIONS ──────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/discipline/<int:eid>', methods=['GET', 'POST'])
@admin_required
def manage_discipline(eid):
    if request.method == 'POST':
        d = request.get_json() or {}
        action = EmployeeDisciplinaryAction(employee_id=eid)
        action.action_type = d['action_type']
        action.description = d['description']
        action.decision_number = d.get('decision_number')
        dec_date = d.get('decision_date')
        action.decision_date = date.fromisoformat(dec_date) if dec_date else None
        action.issued_by = d.get('issued_by', session['user_id'])
        action.duration_days = d.get('duration_days')
        action.status = d.get('status', 'active')
        action.appeal_notes = d.get('appeal_notes')
        db.session.add(action)
        db.session.commit()
        return jsonify({'ok': True, 'action': action.to_dict()})
    actions = EmployeeDisciplinaryAction.query.filter_by(employee_id=eid)\
        .order_by(EmployeeDisciplinaryAction.created_at.desc()).all()
    return jsonify({'actions': [a.to_dict() for a in actions]})


@employee_mgmt_bp.route('/admin/discipline/<int:aid>/close', methods=['POST'])
@admin_required
def close_discipline(aid):
    action = EmployeeDisciplinaryAction.query.get_or_404(aid)
    action.status = 'closed'
    action.closed_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({'ok': True})


# ─── TRAINING ──────────────────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/training/<int:eid>', methods=['GET', 'POST'])
@admin_required
def manage_training(eid):
    if request.method == 'POST':
        d = request.get_json() or {}
        tid = d.get('id')
        if tid:
            training = EmployeeTraining.query.get_or_404(tid)
        else:
            training = EmployeeTraining(employee_id=eid)
        training.course_name = d['course_name']
        training.provider = d['provider']
        s_date = d.get('start_date')
        training.start_date = date.fromisoformat(s_date) if s_date else None
        e_date = d.get('end_date')
        training.end_date = date.fromisoformat(e_date) if e_date else None
        training.duration_hours = d.get('duration_hours')
        training.cert_earned = d.get('cert_earned', False)
        training.cert_file = d.get('cert_file')
        training.is_government_required = d.get('is_government_required', False)
        training.status = d.get('status', 'completed')
        training.notes = d.get('notes')
        db.session.add(training)
        db.session.commit()
        return jsonify({'ok': True, 'training': training.to_dict()})
    trainings = EmployeeTraining.query.filter_by(employee_id=eid)\
        .order_by(EmployeeTraining.created_at.desc()).all()
    return jsonify({'trainings': [t.to_dict() for t in trainings]})


# ─── DELEGATIONS ───────────────────────────────────────────────────────────

@employee_mgmt_bp.route('/admin/delegations/<int:eid>', methods=['GET', 'POST'])
@admin_required
def manage_delegations(eid):
    if request.method == 'POST':
        d = request.get_json() or {}
        did = d.get('id')
        if did:
            delegation = EmployeeDelegation.query.get_or_404(did)
        else:
            delegation = EmployeeDelegation(employee_id=eid)
        delegation.delegation_type = d['delegation_type']
        delegation.delegation_body = d['delegation_body']
        delegation.role = d.get('role')
        s_date = d.get('start_date')
        delegation.start_date = date.fromisoformat(s_date) if s_date else date.today()
        e_date = d.get('end_date')
        delegation.end_date = date.fromisoformat(e_date) if e_date else None
        delegation.decision_number = d.get('decision_number')
        delegation.notes = d.get('notes')
        delegation.is_active = d.get('is_active', True)
        db.session.add(delegation)
        db.session.commit()
        return jsonify({'ok': True, 'delegation': delegation.to_dict()})
    delegations = EmployeeDelegation.query.filter_by(employee_id=eid)\
        .order_by(EmployeeDelegation.created_at.desc()).all()
    return jsonify({'delegations': [d.to_dict() for d in delegations]})


# ─── EMPLOYEE ANALYTICS / STATS ───────────────────────────────────────────

@employee_mgmt_bp.route('/admin/employee-analytics')
@admin_required
def employee_analytics():
    return render_template('admin/employee_analytics.html')


@employee_mgmt_bp.route('/api/employee-stats')
@admin_required
@safe_api
def employee_stats():
    total = Employee.query.filter_by(is_active=True).count()
    extended_count = EmployeeExtended.query.count()
    with_extended = EmployeeExtended.query.filter(EmployeeExtended.employee_id.isnot(None)).count()
    by_gender = db.session.query(Employee.gender, db.func.count(Employee.id)).filter(
        Employee.is_active == True, Employee.gender.isnot(None)
    ).group_by(Employee.gender).all()
    grade_counts = db.session.query(
        EmployeeGrade.name_ar, db.func.count(EmployeeExtended.id)
    ).join(EmployeeGrade, EmployeeExtended.grade_id == EmployeeGrade.id).group_by(
        EmployeeGrade.name_ar, EmployeeGrade.id
    ).order_by(EmployeeGrade.level).all()
    clearance_levels = db.session.query(
        EmployeeExtended.clearance_level, db.func.count(EmployeeExtended.id)
    ).filter(EmployeeExtended.clearance_level.isnot(None)).group_by(
        EmployeeExtended.clearance_level
    ).all()
    marital_stats = db.session.query(
        EmployeeExtended.marital_status, db.func.count(EmployeeExtended.id)
    ).filter(EmployeeExtended.marital_status.isnot(None)).group_by(
        EmployeeExtended.marital_status
    ).all()
    contract_types = db.session.query(
        EmployeeExtended.contract_type, db.func.count(EmployeeExtended.id)
    ).filter(EmployeeExtended.contract_type.isnot(None)).group_by(
        EmployeeExtended.contract_type
    ).all()
    pending_leaves = EmployeeLeaveRequest.query.filter_by(status='pending').count()
    pending_promotions = EmployeePromotion.query.filter_by(status='pending').count()
    pending_discipline = EmployeeDisciplinaryAction.query.filter_by(status='active').count()
    dept_counts = db.session.query(
        Employee.department, db.func.count(Employee.id)
    ).filter(Employee.is_active == True, Employee.department.isnot(None)).group_by(
        Employee.department
    ).order_by(db.func.count(Employee.id).desc()).all()
    today = date.today()
    expiring_clearance = EmployeeExtended.query.filter(
        EmployeeExtended.clearance_expiry.isnot(None),
        EmployeeExtended.clearance_expiry <= today,
        EmployeeExtended.clearance_expiry.isnot(None)
    ).count()
    return jsonify({
        'total_employees': total,
        'extended_data_count': with_extended,
        'by_gender': dict(by_gender),
        'grade_distribution': [{'name': n, 'count': c} for n, c in grade_counts],
        'clearance_levels': dict(clearance_levels),
        'marital_status': dict(marital_stats),
        'contract_types': dict(contract_types),
        'department_counts': [{'name': n, 'count': c} for n, c in dept_counts],
        'pending_leaves': pending_leaves,
        'pending_promotions': pending_promotions,
        'pending_discipline': pending_discipline,
        'expiring_clearance': expiring_clearance,
    })
