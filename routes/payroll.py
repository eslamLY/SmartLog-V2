import json, io, csv, math, calendar
import logging
from datetime import datetime, date, timedelta, UTC
from collections import defaultdict, OrderedDict
from functools import wraps

from flask import Blueprint, request, jsonify, render_template, session, send_file
from sqlalchemy import func, extract, case, and_, desc
from sqlalchemy.orm import joinedload

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.misc import LeaveRequest
from models.shifts import ShiftType, ShiftSchedule
from models.department import Department
from models.payroll import (
    PayrollRecord, SalaryComponent, DeductionRecord,
    SalaryAdvance, ApprovalWorkflow, ApprovalStep,
    PayrollAuditLog, BankPaymentDetail
)
from utils.decorators import admin_required
from utils.constants import MONTH_NAMES
from services.payroll_service import PayrollService
from services.salary_calculator import SalaryCalculator
from services.tax_calculator import TaxCalculator
from services.approval_workflow import ApprovalEngine
from services.bank_export import BankExportService

payroll_bp = Blueprint('payroll_bp', __name__, url_prefix='/admin/payroll')

PAGE_SIZE = 25

def get_month_range(month, year):
    if month == 12:
        return date(year, month, 1), date(year, month, 31)
    return date(year, month, 1), date(year, month + 1, 1) - timedelta(days=1)

def employee_basic_data(emp):
    return {
        'id': emp.id,
        'username': emp.username,
        'full_name': emp.full_name,
        'department': emp.department,
        'job_title': emp.job_title or '',
        'employment_type': emp.employment_type or 'full_time',
        'base_salary': emp.base_salary,
        'housing_allowance': emp.housing_allowance or 0,
        'transport_allowance': emp.transport_allowance or 0,
        'other_allowances': emp.other_allowances_list,
        'payment_method': emp.payment_method or 'bank_transfer',
        'bank_name': emp.bank_name or '',
        'bank_account_number': emp.bank_account_number or '',
        'hire_date': emp.hire_date.isoformat() if emp.hire_date else '',
        'overtime_multiplier': emp.overtime_multiplier or 1.5,
        'is_active': emp.is_active,
    }

def get_attendance_data(emp_ids, month, year):
    start_date, end_date = get_month_range(month, year)
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(emp_ids),
        AttendanceLog.log_date >= start_date,
        AttendanceLog.log_date <= end_date,
    ).order_by(AttendanceLog.employee_id, AttendanceLog.log_date).all()
    logs_by_emp = defaultdict(list)
    for l in logs:
        logs_by_emp[l.employee_id].append(l)
    shifts = ShiftSchedule.query.filter(
        ShiftSchedule.employee_id.in_(emp_ids),
        ShiftSchedule.scheduled_date >= start_date,
        ShiftSchedule.scheduled_date <= end_date,
        ShiftSchedule.status == 'confirmed',
    ).all()
    shifts_by_emp = defaultdict(list)
    for s in shifts:
        shifts_by_emp[s.employee_id].append(s)
    return logs_by_emp, shifts_by_emp, start_date, end_date

def compute_employee_payroll(emp, logs, shifts):
    base = emp.base_salary
    housing = emp.housing_allowance or 0
    transport = emp.transport_allowance or 0
    others = emp.other_allowances_list
    other_total = sum(a.get('amount', 0) for a in others)
    total_allowances = housing + transport + other_total
    mult = emp.overtime_multiplier or 1.5
    total_late_m = sum(l.late_minutes or 0 for l in logs)
    total_absent = sum(1 for l in logs if l.status == 'absent')
    total_present = sum(1 for l in logs if l.status in ('present', 'late'))
    total_ot_hours = sum(s.overtime_hours or 0 for s in shifts)
    hourly_rate = PayrollService.hourly_rate(base)
    overtime_pay = round(total_ot_hours * hourly_rate * mult, 2)
    late_deduction = PayrollService.calculate_deduction(base, total_late_m)
    absent_deduction = PayrollService.calculate_deduction(base, total_absent * 8 * 60)
    total_deductions = round(late_deduction + absent_deduction, 2)
    gross = round(base + total_allowances + overtime_pay, 2)
    tax_result = TaxCalculator.calculate(gross, total_deductions, emp)
    net = round(gross - total_deductions - tax_result['total_tax'], 2)
    day_details = []
    for l in logs:
        ot_this = 0
        for s in shifts:
            if s.scheduled_date == l.log_date:
                ot_this = s.overtime_hours or 0
                break
        day_details.append({
            'date': l.log_date.isoformat(),
            'clock_in': l.clock_in.strftime('%H:%M') if l.clock_in else '-',
            'clock_out': l.clock_out.strftime('%H:%M') if l.clock_out else '-',
            'status': l.status,
            'late_min': l.late_minutes or 0,
            'ot_hours': ot_this,
            'ot_pay': round(ot_this * hourly_rate * mult, 2) if ot_this else 0,
        })
    return {
        'base': base,
        'housing_allowance': housing,
        'transport_allowance': transport,
        'other_allowances': others,
        'other_allowances_total': other_total,
        'total_allowances': total_allowances,
        'overtime_hours': total_ot_hours,
        'overtime_pay': overtime_pay,
        'gross': gross,
        'late_minutes': total_late_m,
        'late_deduction': late_deduction,
        'absent_days': total_absent,
        'absent_deduction': absent_deduction,
        'total_deductions': total_deductions,
        'tax_income': tax_result['income_tax'],
        'tax_social': tax_result['social_security'],
        'total_tax': tax_result['total_tax'],
        'net': net,
        'days': day_details,
    }

@payroll_bp.route('')
@admin_required
def payroll_main():
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year = request.args.get('year', today.year, type=int)
    dept = request.args.get('dept', '')
    tab = request.args.get('tab', '1')
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    qry = Employee.query.filter_by(role='employee', is_active=True)
    if dept:
        qry = qry.filter_by(department=dept)
    if search:
        qry = qry.filter(
            db.or_(
                Employee.full_name.ilike(f'%{search}%'),
                Employee.username.ilike(f'%{search}%'),
            )
        )
    pagination = qry.order_by(Employee.department, Employee.full_name).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )
    employees = pagination.items
    emp_ids = [e.id for e in employees]
    logs_by_emp, shifts_by_emp, s_date, e_date = get_attendance_data(emp_ids, month, year)
    pay_rows = []
    for emp in employees:
        logs = logs_by_emp.get(emp.id, [])
        shifts = shifts_by_emp.get(emp.id, [])
        comp = compute_employee_payroll(emp, logs, shifts)
        pay_rows.append({
            'emp': employee_basic_data(emp),
            'comp': comp,
        })
    depts = [d[0] for d in db.session.query(Employee.department).distinct().all() if d[0]]
    total_base = sum(r['comp']['base'] for r in pay_rows)
    total_allowances = sum(r['comp']['total_allowances'] for r in pay_rows)
    total_overtime = sum(r['comp']['overtime_pay'] for r in pay_rows)
    total_gross = sum(r['comp']['gross'] for r in pay_rows)
    total_deductions = sum(r['comp']['total_deductions'] for r in pay_rows)
    total_tax = sum(r['comp']['total_tax'] for r in pay_rows)
    total_net = sum(r['comp']['net'] for r in pay_rows)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    ps, pe = get_month_range(prev_month, prev_year)
    prev_emps = Employee.query.filter_by(role='employee', is_active=True).count()
    summary = {
        'total_employees': len(employees),
        'total_base': total_base,
        'total_allowances': total_allowances,
        'total_overtime': total_overtime,
        'total_gross': total_gross,
        'total_deductions': total_deductions,
        'total_tax': total_tax,
        'total_net': total_net,
        'avg_base': round(total_base / len(employees), 2) if employees else 0,
        'max_base': max((r['comp']['base'] for r in pay_rows), default=0),
        'min_base': min((r['comp']['base'] for r in pay_rows), default=0),
        'allowances_pct': round(total_allowances / total_gross * 100, 1) if total_gross else 0,
        'deductions_pct': round(total_deductions / total_gross * 100, 1) if total_gross else 0,
        'tax_pct': round(total_tax / total_gross * 100, 1) if total_gross else 0,
        'housing_total': sum(r['comp']['housing_allowance'] for r in pay_rows),
        'transport_total': sum(r['comp']['transport_allowance'] for r in pay_rows),
        'other_allow_total': sum(r['comp']['other_allowances_total'] for r in pay_rows),
        'late_ded_total': sum(r['comp']['late_deduction'] for r in pay_rows),
        'absent_ded_total': sum(r['comp']['absent_deduction'] for r in pay_rows),
        'bank_transfer_total': sum(r['comp']['net'] for r in pay_rows if r['emp']['payment_method'] == 'bank_transfer'),
        'cash_total': sum(r['comp']['net'] for r in pay_rows if r['emp']['payment_method'] == 'cash'),
        'check_total': sum(r['comp']['net'] for r in pay_rows if r['emp']['payment_method'] == 'check'),
    }
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'pay_rows': pay_rows,
            'summary': summary,
            'page': pagination.page,
            'total_pages': pagination.pages,
            'total': pagination.total,
            'month': month,
            'year': year,
            'month_name': MONTH_NAMES[month - 1],
            'start_date': s_date.isoformat(),
            'end_date': e_date.isoformat(),
            'tab': tab,
        })
    return render_template('admin/payroll_main.html',
        pay_rows=pay_rows,
        summary=summary,
        month=month,
        year=year,
        dept=dept,
        tab=tab,
        search=search,
        page=pagination.page,
        total_pages=pagination.pages,
        total=pagination.total,
        month_name=MONTH_NAMES[month - 1],
        months=MONTH_NAMES,
        departments=depts,
        today=today,
    )

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

@payroll_bp.route('/api/employee/<int:eid>')
@safe_api
@admin_required
def employee_payslip(eid):
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    emp = Employee.query.get_or_404(eid)
    logs, shifts, s_date, e_date = get_attendance_data([eid], month, year)
    comp = compute_employee_payroll(emp, logs.get(eid, []), shifts.get(eid, []))
    return jsonify({
        'emp': employee_basic_data(emp),
        'comp': comp,
        'month': month,
        'year': year,
        'month_name': MONTH_NAMES[month - 1],
        'start_date': s_date.isoformat(),
        'end_date': e_date.isoformat(),
    })

@payroll_bp.route('/api/payslip/<int:eid>/print')
@safe_api
@admin_required
def payslip_print(eid):
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    emp = Employee.query.get_or_404(eid)
    logs, shifts, s_date, e_date = get_attendance_data([eid], month, year)
    comp = compute_employee_payroll(emp, logs.get(eid, []), shifts.get(eid, []))
    return render_template('admin/payroll_individual_slip.html',
        emp=employee_basic_data(emp),
        comp=comp,
        month=month,
        year=year,
        month_name=MONTH_NAMES[month - 1],
        start_date=s_date,
        end_date=e_date,
        today=date.today(),
    )

@payroll_bp.route('/api/analytics')
@safe_api
@admin_required
def salary_analytics():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    dept = request.args.get('dept', '')
    qry = Employee.query.filter_by(role='employee', is_active=True)
    if dept:
        qry = qry.filter_by(department=dept)
    employees = qry.all()
    emp_ids = [e.id for e in employees]
    logs_by_emp, shifts_by_emp, s_date, e_date = get_attendance_data(emp_ids, month, year)
    salary_data = []
    for emp in employees:
        logs = logs_by_emp.get(emp.id, [])
        shifts = shifts_by_emp.get(emp.id, [])
        comp = compute_employee_payroll(emp, logs, shifts)
        salary_data.append({
            'emp': employee_basic_data(emp),
            'comp': comp,
        })
    salaries = [d['comp']['net'] for d in salary_data]
    gross_salaries = [d['comp']['gross'] for d in salary_data]
    n = len(salaries)
    avg_sal = round(sum(salaries) / n, 2) if n else 0
    avg_gross = round(sum(gross_salaries) / n, 2) if n else 0
    sorted_sals = sorted(salaries)
    median_sal = sorted_sals[n // 2] if n else 0
    variance = sum((x - avg_sal) ** 2 for x in salaries) / n if n else 0
    std_dev = round(math.sqrt(variance), 2)
    min_sal = min(salaries) if salaries else 0
    max_sal = max(salaries) if salaries else 0
    cv = round(std_dev / avg_sal * 100, 1) if avg_sal else 0
    highest = max(salary_data, key=lambda x: x['comp']['net']) if salary_data else None
    lowest = min(salary_data, key=lambda x: x['comp']['net']) if salary_data else None
    dept_groups = defaultdict(list)
    for d in salary_data:
        dept_groups[d['emp']['department']].append(d['comp']['net'])
    dept_stats = {}
    for dept_name, sals in dept_groups.items():
        dept_stats[dept_name] = {
            'count': len(sals),
            'avg': round(sum(sals) / len(sals), 2),
            'min': min(sals),
            'max': max(sals),
            'total': round(sum(sals), 2),
        }
    range_counts = OrderedDict()
    ranges = [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000), (4000, 5000), (5000, 10000)]
    range_labels = ['0-1,000', '1,000-2,000', '2,000-3,000', '3,000-4,000', '4,000-5,000', '5,000+']
    for i, (lo, hi) in enumerate(ranges):
        range_counts[range_labels[i]] = sum(1 for s in salaries if lo <= s < hi)
    component_totals = {
        'base': sum(d['comp']['base'] for d in salary_data),
        'allowances': sum(d['comp']['total_allowances'] for d in salary_data),
        'overtime': sum(d['comp']['overtime_pay'] for d in salary_data),
        'deductions': sum(d['comp']['total_deductions'] for d in salary_data),
        'tax': sum(d['comp']['total_tax'] for d in salary_data),
        'net': sum(d['comp']['net'] for d in salary_data),
    }
    total_payroll = component_totals['base'] + component_totals['allowances'] + component_totals['overtime']
    monthly_cost = total_payroll
    annual_projected = monthly_cost * 12
    cost_per_emp = round(monthly_cost / n, 2) if n else 0
    insights = []
    for dept_name, ds in dept_stats.items():
        if ds['avg'] > avg_sal * 1.05:
            insights.append({
                'type': 'warning',
                'icon': '📊',
                'title': f'رواتب {dept_name} أعلى من المتوسط',
                'detail': f'متوسط {ds["avg"]} د.ل مقابل {avg_sal} د.ل للمؤسسة ({round((ds["avg"]/avg_sal-1)*100,1)}% أعلى)',
            })
    below_avg_count = sum(1 for s in salaries if s < avg_sal)
    insights.append({
        'type': 'info',
        'icon': '💡',
        'title': f'{below_avg_count} موظفين لديهم رواتب أقل من المتوسط',
        'detail': f'من أصل {n} موظف، {"%.0f" % (below_avg_count/n*100)}% يحصلون على أقل من متوسط الراتب ({avg_sal} د.ل)',
    })
    total_ded_val = component_totals['deductions'] + component_totals['tax']
    if total_payroll:
        insights.append({
            'type': 'info',
            'icon': '📉',
            'title': 'تكلفة الخصومات',
            'detail': f'الخصومات تشكل {round(total_ded_val/total_payroll*100,1)}% من إجمالي الرواتب ({round(total_ded_val,2)} د.ل)',
        })
    ot_pct = round(component_totals['overtime'] / total_payroll * 100, 1) if total_payroll else 0
    insights.append({
        'type': 'info',
        'icon': '⏰',
        'title': 'العمل الإضافي',
        'detail': f'العمل الإضافي يمثل {ot_pct}% من إجمالي الرواتب ({component_totals["overtime"]} د.ل)',
    })
    salary_trend = []
    for m in range(max(1, month - 5), month + 1):
        m_logs, m_shifts, ms, me = get_attendance_data(emp_ids, m, year)
        m_total = 0
        m_count = 0
        for emp in employees:
            elogs = m_logs.get(emp.id, [])
            eshifts = m_shifts.get(emp.id, [])
            comp = compute_employee_payroll(emp, elogs, eshifts)
            m_total += comp['net']
            m_count += 1
        salary_trend.append({
            'month': MONTH_NAMES[m - 1],
            'month_num': m,
            'avg': round(m_total / m_count, 2) if m_count else 0,
            'total': round(m_total, 2),
        })
    return jsonify({
        'stats': {
            'avg_salary': avg_sal,
            'avg_gross': avg_gross,
            'median_salary': median_sal,
            'std_deviation': std_dev,
            'min_salary': min_sal,
            'max_salary': max_sal,
            'cv': cv,
            'n': n,
            'highest_paid': {'name': highest['emp']['full_name'], 'salary': highest['comp']['net']} if highest else None,
            'lowest_paid': {'name': lowest['emp']['full_name'], 'salary': lowest['comp']['net']} if lowest else None,
        },
        'dept_stats': dept_stats,
        'range_distribution': range_counts,
        'component_totals': component_totals,
        'total_payroll': total_payroll,
        'annual_projected': annual_projected,
        'cost_per_employee': cost_per_emp,
        'insights': insights,
        'trend': salary_trend,
        'month': month,
        'year': year,
        'month_name': MONTH_NAMES[month - 1],
    })

@payroll_bp.route('/api/advances')
@safe_api
@admin_required
def salary_advances():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    dept = request.args.get('dept', '')
    qry = SalaryAdvance.query
    if dept:
        qry = qry.join(Employee).filter(Employee.department == dept)
    advances = qry.order_by(SalaryAdvance.created_at.desc()).all()
    result = []
    for adv in advances:
        emp = Employee.query.get(adv.employee_id)
        if not emp:
            continue
        repaid = sum(adv.installments_paid or [])
        remaining = adv.amount - repaid
        result.append({
            'id': adv.id,
            'employee_id': emp.id,
            'employee_name': emp.full_name,
            'employee_username': emp.username,
            'department': emp.department,
            'amount': adv.amount,
            'repaid': repaid,
            'remaining': remaining,
            'repaid_pct': round(repaid / adv.amount * 100, 1) if adv.amount else 0,
            'installments': adv.installments_count or 1,
            'installment_amount': adv.installment_amount or 0,
            'installments_paid': adv.installments_paid or [],
            'last_advance_date': adv.created_at.isoformat() if adv.created_at else '',
            'reason': adv.reason or '',
            'auto_deduct': adv.auto_deduct or False,
            'status': adv.status or 'active',
            'notes': adv.notes or '',
        })
    total_advanced = sum(a['amount'] for a in result)
    total_repaid = sum(a['repaid'] for a in result)
    total_remaining = sum(a['remaining'] for a in result)
    return jsonify({
        'advances': result,
        'total_advanced': total_advanced,
        'total_repaid': total_repaid,
        'total_remaining': total_remaining,
        'count': len(result),
        'active_count': sum(1 for a in result if a['status'] == 'active'),
        'month': month,
        'year': year,
    })

@payroll_bp.route('/api/advances/create', methods=['POST'])
@safe_api
@admin_required
def create_advance():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'msg': 'الرجاء إرسال البيانات'}), 400
    emp_id = data.get('employee_id')
    amount = data.get('amount', type=float)
    installments = data.get('installments', 1, type=int)
    reason = data.get('reason', '')
    auto_deduct = data.get('auto_deduct', False)
    if not emp_id or not amount:
        return jsonify({'ok': False, 'msg': 'الموظف والمبلغ مطلوبان'}), 400
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404
    installment_amt = round(amount / installments, 2) if installments else amount
    advance = SalaryAdvance(
        employee_id=emp_id,
        amount=amount,
        installments_count=installments,
        installment_amount=installment_amt,
        reason=reason,
        auto_deduct=auto_deduct,
        status='active',
    )
    db.session.add(advance)
    db.session.commit()
    PayrollAuditLog.log(
        action='create_advance',
        employee_id=emp_id,
        changed_by=session.get('user_id'),
        details=f'تم إنشاء سلفة بقيمة {amount} د.ل لـ {emp.full_name}',
    )
    return jsonify({'ok': True, 'msg': 'تم إنشاء السلفة بنجاح', 'id': advance.id})

@payroll_bp.route('/api/advances/<int:aid>/repay', methods=['POST'])
@safe_api
@admin_required
def repay_advance(aid):
    advance = SalaryAdvance.query.get_or_404(aid)
    data = request.get_json() or {}
    amount = data.get('amount', type=float)
    if not amount:
        return jsonify({'ok': False, 'msg': 'المبلغ مطلوب'}), 400
    paid = list(advance.installments_paid or [])
    paid.append(amount)
    advance.installments_paid = paid
    repaid = sum(paid)
    if repaid >= advance.amount:
        advance.status = 'settled'
        advance.settled_at = datetime.now(UTC)
    db.session.commit()
    emp = Employee.query.get(advance.employee_id)
    PayrollAuditLog.log(
        action='repay_advance',
        employee_id=advance.employee_id,
        changed_by=session.get('user_id'),
        details=f'تم سداد قسط سلفة بقيمة {amount} د.ل',
    )
    return jsonify({'ok': True, 'msg': 'تم تسجيل السداد'})

@payroll_bp.route('/api/approvals')
@safe_api
@admin_required
def approval_list():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    dept = request.args.get('dept', '')
    status_filter = request.args.get('status', '')
    qry = ApprovalWorkflow.query.filter_by(month=month, year=year)
    if status_filter:
        qry = qry.filter_by(status=status_filter)
    if dept:
        qry = qry.join(Employee).filter(Employee.department == dept)
    approvals = qry.order_by(ApprovalWorkflow.created_at.desc()).all()
    result = []
    for wf in approvals:
        emp = Employee.query.get(wf.employee_id)
        steps = ApprovalStep.query.filter_by(workflow_id=wf.id).order_by(ApprovalStep.step_order).all()
        result.append({
            'id': wf.id,
            'employee_id': wf.employee_id,
            'employee_name': emp.full_name if emp else '—',
            'employee_username': emp.username if emp else '—',
            'department': emp.department if emp else '—',
            'proposed_gross': wf.proposed_gross,
            'proposed_net': wf.proposed_net,
            'current_gross': wf.current_gross,
            'change_pct': round((wf.proposed_gross - wf.current_gross) / wf.current_gross * 100, 1) if wf.current_gross else 0,
            'status': wf.status,
            'current_step': wf.current_step,
            'total_steps': wf.total_steps,
            'steps': [{
                'id': s.id,
                'step_order': s.step_order,
                'approver_id': s.approver_id,
                'approver_name': s.approver_name or '',
                'status': s.status,
                'comment': s.comment or '',
                'acted_at': s.acted_at.isoformat() if s.acted_at else '',
            } for s in steps],
            'created_at': wf.created_at.isoformat() if wf.created_at else '',
            'notes': wf.notes or '',
        })
    return jsonify({
        'approvals': result,
        'count': len(result),
        'pending': sum(1 for a in result if a['status'] == 'pending'),
        'approved': sum(1 for a in result if a['status'] == 'approved'),
        'rejected': sum(1 for a in result if a['status'] == 'rejected'),
    })

@payroll_bp.route('/api/approvals/initiate', methods=['POST'])
@safe_api
@admin_required
def initiate_approval():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'msg': 'الرجاء إرسال البيانات'}), 400
    emp_id = data.get('employee_id')
    proposed_gross = data.get('proposed_gross', type=float)
    proposed_net = data.get('proposed_net', type=float)
    reason = data.get('reason', '')
    month = data.get('month', date.today().month, type=int)
    year = data.get('year', date.today().year, type=int)
    if not emp_id or proposed_gross is None:
        return jsonify({'ok': False, 'msg': 'بيانات غير كاملة'}), 400
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404
    existing = ApprovalWorkflow.query.filter_by(
        employee_id=emp_id, month=month, year=year, status='pending'
    ).first()
    if existing:
        return jsonify({'ok': False, 'msg': 'يوجد طلب موافقة معلق لهذا الموظف'}), 409
    wf = ApprovalWorkflow(
        employee_id=emp_id,
        month=month,
        year=year,
        current_gross=emp.base_salary,
        proposed_gross=proposed_gross,
        proposed_net=proposed_net,
        status='pending',
        current_step=1,
        total_steps=2,
        notes=reason,
    )
    db.session.add(wf)
    db.session.flush()
    managers = Employee.query.filter_by(role='admin', is_active=True).all()
    for idx, mgr in enumerate(managers[:2]):
        step = ApprovalStep(
            workflow_id=wf.id,
            step_order=idx + 1,
            approver_id=mgr.id,
            approver_name=mgr.full_name,
            status='pending',
        )
        db.session.add(step)
    db.session.commit()
    PayrollAuditLog.log(
        action='initiate_approval',
        employee_id=emp_id,
        changed_by=session.get('user_id'),
        details=f'تم بدء طلب موافقة على راتب {emp.full_name}: {proposed_gross} د.ل',
    )
    return jsonify({'ok': True, 'msg': 'تم بدء طلب الموافقة', 'id': wf.id})

@payroll_bp.route('/api/approvals/<int:wid>/act', methods=['POST'])
@safe_api
@admin_required
def act_on_approval(wid):
    wf = ApprovalWorkflow.query.get_or_404(wid)
    data = request.get_json() or {}
    action = data.get('action', '')
    comment = data.get('comment', '')
    if action not in ('approve', 'reject', 'request_changes'):
        return jsonify({'ok': False, 'msg': 'إجراء غير صالح'}), 400
    user_id = session.get('user_id')
    step = ApprovalStep.query.filter_by(
        workflow_id=wid, step_order=wf.current_step, status='pending'
    ).first()
    if not step:
        return jsonify({'ok': False, 'msg': 'لا توجد خطوة موافقة معلقة'}), 400
    step.status = action
    step.comment = comment
    step.acted_at = datetime.now(UTC)
    step.acted_by = user_id
    if action == 'reject':
        wf.status = 'rejected'
        wf.reviewed_at = datetime.now(UTC)
        wf.reviewed_by = user_id
    elif action == 'request_changes':
        wf.status = 'changes_requested'
    elif action == 'approve':
        if wf.current_step >= wf.total_steps:
            wf.status = 'approved'
            wf.reviewed_at = datetime.now(UTC)
            wf.reviewed_by = user_id
            emp = Employee.query.get(wf.employee_id)
            if emp:
                emp.base_salary = wf.proposed_gross
        else:
            wf.current_step += 1
    db.session.commit()
    emp = Employee.query.get(wf.employee_id)
    PayrollAuditLog.log(
        action=f'approval_{action}',
        employee_id=wf.employee_id,
        changed_by=user_id,
        details=f'{action} على طلب الموافقة لـ {emp.full_name if emp else ""}',
    )
    return jsonify({'ok': True, 'msg': 'تم تحديث الموافقة'})

@payroll_bp.route('/api/bank')
@safe_api
@admin_required
def bank_payments():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    dept = request.args.get('dept', '')
    status_filter = request.args.get('status', '')
    qry = BankPaymentDetail.query.filter_by(month=month, year=year)
    if status_filter:
        qry = qry.filter_by(status=status_filter)
    if dept:
        qry = qry.join(Employee).filter(Employee.department == dept)
    payments = qry.order_by(BankPaymentDetail.employee_id).all()
    pay_rows = []
    for p in payments:
        emp = Employee.query.get(p.employee_id)
        pay_rows.append({
            'id': p.id,
            'employee_id': p.employee_id,
            'employee_name': emp.full_name if emp else '—',
            'employee_username': emp.username if emp else '—',
            'department': emp.department if emp else '—',
            'iban': p.iban or '',
            'bank_name': p.bank_name or (emp.bank_name if emp else ''),
            'net_amount': p.net_amount,
            'status': p.status or 'pending',
            'payment_date': p.payment_date.isoformat() if p.payment_date else '',
            'notes': p.notes or '',
        })
    total_amount = sum(p['net_amount'] for p in pay_rows)
    status_counts = defaultdict(int)
    for p in pay_rows:
        status_counts[p['status']] += 1
    missing_iban = [p for p in pay_rows if not p['iban']]
    return jsonify({
        'payments': pay_rows,
        'total_amount': total_amount,
        'count': len(pay_rows),
        'status_counts': dict(status_counts),
        'missing_iban_count': len(missing_iban),
        'missing_iban_list': missing_iban,
        'month': month,
        'year': year,
    })

@payroll_bp.route('/api/bank/generate', methods=['POST'])
@safe_api
@admin_required
def generate_bank_payments():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    dept = request.args.get('dept', '')
    qry = Employee.query.filter_by(role='employee', is_active=True)
    if dept:
        qry = qry.filter_by(department=dept)
    employees = qry.all()
    emp_ids = [e.id for e in employees]
    logs_by_emp, shifts_by_emp, s_date, e_date = get_attendance_data(emp_ids, month, year)
    logs_by_emp, shifts_by_emp, s_date, e_date = get_attendance_data(emp_ids, month, year)
    log_b, shift_b, _, _ = get_attendance_data(emp_ids, month, year)
    count = 0
    for emp in employees:
        logs = log_b.get(emp.id, [])
        shifts = shift_b.get(emp.id, [])
        comp = compute_employee_payroll(emp, logs, shifts)
        existing = BankPaymentDetail.query.filter_by(
            employee_id=emp.id, month=month, year=year
        ).first()
        if existing:
            existing.net_amount = comp['net']
            existing.iban = emp.bank_account_number or existing.iban
            existing.bank_name = emp.bank_name or existing.bank_name
            existing.status = 'pending'
        else:
            bpd = BankPaymentDetail(
                employee_id=emp.id,
                month=month,
                year=year,
                net_amount=comp['net'],
                iban=emp.bank_account_number or '',
                bank_name=emp.bank_name or '',
                status='pending',
            )
            db.session.add(bpd)
        count += 1
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إنشاء {count} قيد دفع بنكي', 'count': count})

@payroll_bp.route('/api/bank/update-status', methods=['POST'])
@safe_api
@admin_required
def update_bank_status():
    data = request.get_json() or {}
    payment_ids = data.get('ids', [])
    new_status = data.get('status', '')
    if not payment_ids or new_status not in ('pending', 'processing', 'completed', 'failed'):
        return jsonify({'ok': False, 'msg': 'بيانات غير صالحة'}), 400
    payments = BankPaymentDetail.query.filter(BankPaymentDetail.id.in_(payment_ids)).all()
    for p in payments:
        p.status = new_status
        if new_status == 'completed':
            p.payment_date = date.today()
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم تحديث {len(payments)} معاملة'})

@payroll_bp.route('/api/bank/export/<fmt>')
@safe_api
@admin_required
def export_bank_file(fmt):
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    if fmt == 'csv':
        payments = BankPaymentDetail.query.filter_by(month=month, year=year, status='pending').all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['اسم الموظف', 'رقم IBAN', 'اسم البنك', 'صافي الراتب', 'الشهر', 'السنة'])
        for p in payments:
            emp = Employee.query.get(p.employee_id)
            writer.writerow([
                emp.full_name if emp else '',
                p.iban or '',
                p.bank_name or '',
                p.net_amount,
                month,
                year,
            ])
        mem = io.BytesIO(output.getvalue().encode('utf-8-sig'))
        return send_file(mem, mimetype='text/csv', as_attachment=True,
            download_name=f'payments_bank_{month}_{year}.csv')
    elif fmt == 'txt':
        payments = BankPaymentDetail.query.filter_by(month=month, year=year, status='pending').all()
        lines = []
        for p in payments:
            emp = Employee.query.get(p.employee_id)
            name = emp.full_name if emp else 'Unknown'
            lines.append(f'{name}\t{p.iban or ""}\t{p.net_amount}')
        mem = io.BytesIO('\n'.join(lines).encode('utf-8'))
        return send_file(mem, mimetype='text/plain', as_attachment=True,
            download_name=f'payments_bank_{month}_{year}.txt')
    return jsonify({'ok': False, 'msg': 'الصيغة غير مدعومة'}), 400

@payroll_bp.route('/api/compare')
@safe_api
@admin_required
def payroll_comparison():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    compare_month = request.args.get('compare_month', prev_month, type=int)
    compare_year = request.args.get('compare_year', prev_year, type=int)
    all_emps = Employee.query.filter_by(role='employee', is_active=True).all()
    emp_ids = [e.id for e in all_emps]
    cur_logs, cur_shifts, cs, ce = get_attendance_data(emp_ids, month, year)
    prv_logs, prv_shifts, ps, pe = get_attendance_data(emp_ids, compare_month, compare_year)
    rows = []
    for emp in all_emps:
        cur_c = compute_employee_payroll(emp, cur_logs.get(emp.id, []), cur_shifts.get(emp.id, []))
        prv_c = compute_employee_payroll(emp, prv_logs.get(emp.id, []), prv_shifts.get(emp.id, []))
        net_change = round(cur_c['net'] - prv_c['net'], 2)
        net_change_pct = round(net_change / prv_c['net'] * 100, 1) if prv_c['net'] else 0
        gross_change = round(cur_c['gross'] - prv_c['gross'], 2)
        rows.append({
            'emp': employee_basic_data(emp),
            'current': cur_c,
            'previous': prv_c,
            'net_change': net_change,
            'net_change_pct': net_change_pct,
            'gross_change': gross_change,
        })
    cur_total_net = sum(r['current']['net'] for r in rows)
    prv_total_net = sum(r['previous']['net'] for r in rows)
    total_change = round(cur_total_net - prv_total_net, 2)
    total_change_pct = round(total_change / prv_total_net * 100, 1) if prv_total_net else 0
    raises = [r for r in rows if r['net_change'] > 0]
    cuts = [r for r in rows if r['net_change'] < 0]
    return jsonify({
        'rows': rows,
        'summary': {
            'current_total_net': cur_total_net,
            'previous_total_net': prv_total_net,
            'total_change': total_change,
            'total_change_pct': total_change_pct,
            'raises_count': len(raises),
            'cuts_count': len(cuts),
            'no_change_count': len(rows) - len(raises) - len(cuts),
            'current_month': month,
            'current_year': year,
            'current_label': f'{MONTH_NAMES[month - 1]} {year}',
            'previous_month': compare_month,
            'previous_year': compare_year,
            'previous_label': f'{MONTH_NAMES[compare_month - 1]} {compare_year}',
        },
    })

@payroll_bp.route('/api/employee-history/<int:eid>')
@safe_api
@admin_required
def employee_salary_history(eid):
    emp = Employee.query.get_or_404(eid)
    months_data = []
    today = date.today()
    for i in range(6):
        m = today.month - i
        y = today.year
        while m < 1:
            m += 12
            y -= 1
        l, s, sd, ed = get_attendance_data([eid], m, y)
        comp = compute_employee_payroll(emp, l.get(eid, []), s.get(eid, []))
        months_data.append({
            'month': MONTH_NAMES[m - 1],
            'month_num': m,
            'year': y,
            'net': comp['net'],
            'gross': comp['gross'],
            'base': comp['base'],
            'allowances': comp['total_allowances'],
            'overtime': comp['overtime_pay'],
            'deductions': comp['total_deductions'],
            'tax': comp['total_tax'],
        })
    months_data.reverse()
    return jsonify({
        'emp': employee_basic_data(emp),
        'history': months_data,
    })

@payroll_bp.route('/api/audit')
@safe_api
@admin_required
def payroll_audit():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    qry = PayrollAuditLog.query.order_by(PayrollAuditLog.created_at.desc())
    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)
    logs = []
    for log in pagination.items:
        emp = Employee.query.get(log.employee_id)
        changer = Employee.query.get(log.changed_by)
        logs.append({
            'id': log.id,
            'action': log.action,
            'action_ar': log.get_action_arabic(),
            'employee_id': log.employee_id,
            'employee_name': emp.full_name if emp else '—',
            'changed_by': log.changed_by,
            'changed_by_name': changer.full_name if changer else '—',
            'details': log.details or '',
            'old_value': log.old_value or '',
            'new_value': log.new_value or '',
            'created_at': log.created_at.isoformat() if log.created_at else '',
        })
    return jsonify({
        'logs': logs,
        'page': pagination.page,
        'total_pages': pagination.pages,
        'total': pagination.total,
    })

@payroll_bp.route('/api/save-record', methods=['POST'])
@safe_api
@admin_required
def save_payroll_record():
    data = request.get_json() or {}
    emp_id = data.get('employee_id')
    month = data.get('month', date.today().month, type=int)
    year = data.get('year', date.today().year, type=int)
    if not emp_id:
        return jsonify({'ok': False, 'msg': 'الموظف مطلوب'}), 400
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404
    logs, shifts, s_date, e_date = get_attendance_data([emp_id], month, year)
    comp = compute_employee_payroll(emp, logs.get(emp_id, []), shifts.get(emp_id, []))
    existing = PayrollRecord.query.filter_by(
        employee_id=emp_id, month=month, year=year
    ).first()
    if existing:
        old_net = existing.net_salary
        existing.base_salary = comp['base']
        existing.total_allowances = comp['total_allowances']
        existing.overtime_pay = comp['overtime_pay']
        existing.gross_salary = comp['gross']
        existing.total_deductions = comp['total_deductions']
        existing.total_tax = comp['total_tax']
        existing.net_salary = comp['net']
        existing.status = 'calculated'
    else:
        existing = PayrollRecord(
            employee_id=emp_id,
            month=month,
            year=year,
            base_salary=comp['base'],
            total_allowances=comp['total_allowances'],
            overtime_pay=comp['overtime_pay'],
            gross_salary=comp['gross'],
            total_deductions=comp['total_deductions'],
            total_tax=comp['total_tax'],
            net_salary=comp['net'],
            status='calculated',
        )
        db.session.add(existing)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حفظ سجل الراتب', 'id': existing.id})

@payroll_bp.route('/api/bulk-save', methods=['POST'])
@safe_api
@admin_required
def bulk_save_payroll():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    emp_ids = [e.id for e in Employee.query.filter_by(role='employee', is_active=True).all()]
    logs_by_emp, shifts_by_emp, _, _ = get_attendance_data(emp_ids, month, year)
    saved = 0
    for emp in Employee.query.filter_by(role='employee', is_active=True).all():
        logs = logs_by_emp.get(emp.id, [])
        shifts = shifts_by_emp.get(emp.id, [])
        comp = compute_employee_payroll(emp, logs, shifts)
        existing = PayrollRecord.query.filter_by(employee_id=emp.id, month=month, year=year).first()
        if existing:
            existing.base_salary = comp['base']
            existing.total_allowances = comp['total_allowances']
            existing.overtime_pay = comp['overtime_pay']
            existing.gross_salary = comp['gross']
            existing.total_deductions = comp['total_deductions']
            existing.total_tax = comp['total_tax']
            existing.net_salary = comp['net']
        else:
            db.session.add(PayrollRecord(
                employee_id=emp.id, month=month, year=year,
                base_salary=comp['base'], total_allowances=comp['total_allowances'],
                overtime_pay=comp['overtime_pay'], gross_salary=comp['gross'],
                total_deductions=comp['total_deductions'], total_tax=comp['total_tax'],
                net_salary=comp['net'], status='calculated',
            ))
        saved += 1
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم حفظ رواتب {saved} موظف'})

@payroll_bp.route('/api/export/csv')
@safe_api
@admin_required
def export_payroll_csv():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    dept = request.args.get('dept', '')
    qry = Employee.query.filter_by(role='employee', is_active=True)
    if dept:
        qry = qry.filter_by(department=dept)
    employees = qry.all()
    emp_ids = [e.id for e in employees]
    logs_by_emp, shifts_by_emp, _, _ = get_attendance_data(emp_ids, month, year)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['الموظف', 'رقم الموظف', 'القسم', 'الراتب الأساسي', 'بدل سكن', 'بدل مواصلات', 'بدلات أخرى',
                     'العمل الإضافي', 'إجمالي الإضافات', 'إجمالي الراتب', 'خصم التأخير', 'خصم الغياب',
                     'إجمالي الخصومات', 'ضريبة الدخل', 'التأمينات', 'صافي الراتب'])
    for emp in employees:
        logs = logs_by_emp.get(emp.id, [])
        shifts = shifts_by_emp.get(emp.id, [])
        comp = compute_employee_payroll(emp, logs, shifts)
        writer.writerow([
            emp.full_name, emp.username, emp.department, comp['base'],
            comp['housing_allowance'], comp['transport_allowance'], comp['other_allowances_total'],
            comp['overtime_pay'], comp['total_allowances'], comp['gross'],
            comp['late_deduction'], comp['absent_deduction'],
            comp['total_deductions'], comp['tax_income'], comp['tax_social'], comp['net'],
        ])
    mem = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    return send_file(mem, mimetype='text/csv', as_attachment=True,
        download_name=f'payroll_{month}_{year}.csv')
