import csv
import io
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, UTC
from functools import wraps

from flask import Blueprint, request, session, jsonify, send_file


from models import db, AttendanceLog, BiometricDevice, Employee, Department, UserPreference
from models.payroll import PayrollRecord
from models.backup import BackupMetadata
from models.attendance_report import ReportDataService
from utils.decorators import login_required, admin_required
from utils.helpers import validate_coordinates
from utils.rate_limit import check_rate_limit, rate_limit_headers
from utils.constants import MONTH_NAMES
from services.clock_service import ClockService
from services.leave_service import LeaveService
from services.cached_queries import get_active_departments
from services.biotime_service import pull_attendance_logs
from services.payroll_service import PayrollService
from services.tax_calculator import TaxCalculator

LOGGER = logging.getLogger(__name__)

api_ops_bp = Blueprint('api_operations', __name__)


def _require_admin():
    uid = session.get('user_id')
    if not uid:
        return jsonify({'ok': False, 'msg': 'يجب تسجيل الدخول أولاً.'}), 401
    emp = Employee.query.get(uid)
    if not emp or not emp.is_active or emp.role != 'admin':
        return jsonify({'ok': False, 'msg': 'ليس لديك صلاحية.'}), 403
    return None


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': 'حدث خطأ داخلي.'}), 500
    return wrapper


def _resolve_employee_id(data):
    emp_id = data.get('employee_id')
    if emp_id and session.get('role') == 'admin':
        try:
            return int(emp_id)
        except (ValueError, TypeError):
            return None
    return session['user_id']


# ─── ATTENDANCE ─────────────────────────────────────────────────────────────


@api_ops_bp.route('/api/attendance/check-in', methods=['POST'])
@login_required
@safe_api
def api_check_in():
    allowed, remaining = check_rate_limit('api_clock_in', 6, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429

    data = request.get_json() or {}
    emp_id = _resolve_employee_id(data)
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404

    today = date.today()
    log = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()
    had_clock_out = log is not None and log.clock_out is not None

    if log and log.clock_in and not log.clock_out:
        return jsonify({'ok': False, 'msg': 'سجّلت حضورك اليوم بالفعل.'})

    if log and log.clock_out:
        log.clock_out = None
        log.lat_out = None; log.lng_out = None
        log.lat_out_enc = None; log.lng_out_enc = None

    if not had_clock_out:
        last_log = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.clock_in >= datetime.now(UTC) - timedelta(hours=1),
            AttendanceLog.clock_out == None
        ).first()
        if last_log and last_log.clock_in:
            return jsonify({'ok': False, 'msg': 'لا يمكن تسجيل الحضور مرتين خلال نفس الساعة.'})

    lat = data.get('lat')
    lng = data.get('lng')
    selfie = data.get('selfie', '')

    if not lat or not lng or not validate_coordinates(lat, lng):
        return jsonify({'ok': False, 'msg': 'بيانات الموقع الجغرافي غير صالحة.'})

    inside, dist = ClockService.check_geofence(lat, lng)
    now = datetime.now()
    late_min = ClockService.calc_late_minutes(now)
    status = 'late' if late_min > 0 else 'present'

    if log:
        log.clock_in = now; log.set_clock_in_coords(lat, lng)
        log.distance_in = dist; log.selfie_data = selfie
        log.status = status; log.late_minutes = late_min
        log.is_inside_geofence = inside
    else:
        log = AttendanceLog(employee_id=emp.id, log_date=today,
                            clock_in=now, distance_in=dist,
                            selfie_data=selfie,
                            status=status, late_minutes=late_min,
                            is_inside_geofence=inside)
        log.set_clock_in_coords(lat, lng)
        db.session.add(log)
    db.session.commit()

    msg = f'✅ تم تسجيل حضورك الساعة {now.strftime("%H:%M")}'
    if late_min > 0:
        msg += f' — متأخر {late_min} دقيقة'
    if not inside:
        msg += f' ⚠️ (خارج النطاق، المسافة {dist}م)'
    resp = jsonify({'ok': True, 'msg': msg, 'status': status,
                    'late_min': late_min, 'inside': inside, 'dist': dist})
    resp.headers.update(rate_limit_headers(6, remaining, 60))
    return resp


@api_ops_bp.route('/api/attendance/check-out', methods=['POST'])
@login_required
@safe_api
def api_check_out():
    allowed, remaining = check_rate_limit('api_clock_out', 6, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429

    data = request.get_json() or {}
    emp_id = _resolve_employee_id(data)
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404

    today = date.today()
    log = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()

    if not log or not log.clock_in:
        return jsonify({'ok': False, 'msg': 'لم تسجل حضورك اليوم بعد.'})
    if log.clock_out:
        return jsonify({'ok': False, 'msg': 'سجّلت انصرافك اليوم بالفعل.'})

    now = datetime.now()
    log.clock_out = now
    log.set_clock_out_coords(data.get('lat'), data.get('lng'))
    db.session.commit()

    diff = now - log.clock_in
    h, rem = divmod(int(diff.total_seconds()), 3600)
    m = rem // 60
    resp = jsonify({'ok': True, 'msg': f'✅ تم تسجيل انصرافك الساعة {now.strftime("%H:%M")} — عملت {h}س {m}د'})
    resp.headers.update(rate_limit_headers(6, remaining, 60))
    return resp


@api_ops_bp.route('/api/attendance/logs', methods=['GET'])
@login_required
@safe_api
def api_attendance_logs():
    emp_id = request.args.get('employee_id', type=int)
    if emp_id and session.get('role') == 'admin':
        pass
    else:
        emp_id = session['user_id']
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    q = AttendanceLog.query.filter_by(employee_id=emp_id)
    if from_date:
        try:
            q = q.filter(AttendanceLog.log_date >= date.fromisoformat(from_date))
        except (ValueError, TypeError):
            pass
    if to_date:
        try:
            q = q.filter(AttendanceLog.log_date <= date.fromisoformat(to_date))
        except (ValueError, TypeError):
            pass

    total = q.count()
    logs = q.order_by(AttendanceLog.log_date.desc()).offset(offset).limit(limit).all()

    rows = []
    for l in logs:
        h = ''
        if l.clock_in and l.clock_out:
            h = round((l.clock_out - l.clock_in).total_seconds() / 3600, 1)
        rows.append({
            'id': l.id,
            'date': l.log_date.isoformat(),
            'clock_in': l.clock_in.strftime('%H:%M') if l.clock_in else '',
            'clock_out': l.clock_out.strftime('%H:%M') if l.clock_out else '',
            'status': l.status or '',
            'late_minutes': l.late_minutes or 0,
            'early_leave_minutes': l.early_leave_minutes or 0,
            'overtime_minutes': l.overtime_minutes or 0,
            'work_hours': h,
            'is_inside_geofence': l.is_inside_geofence,
            'device_serial': l.device_serial,
        })

    return jsonify({'ok': True, 'logs': rows, 'total': total})


# ─── LEAVE MANAGEMENT ───────────────────────────────────────────────────────


@api_ops_bp.route('/api/leaves/request', methods=['POST'])
@login_required
@safe_api
def api_leave_request():
    data = request.get_json() or {}
    emp_id = _resolve_employee_id(data)
    if not emp_id:
        return jsonify({'ok': False, 'msg': 'employee_id غير صالح'}), 400
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404

    leave_type_id = data.get('leave_type_id')
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    reason = (data.get('reason') or '').strip()

    if not leave_type_id or not start_date_str or not end_date_str:
        return jsonify({'ok': False, 'msg': 'نوع الإجازة وتاريخ البداية والنهاية مطلوبون'}), 400

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'msg': 'تاريخ غير صحيح'}), 400

    if end_date < start_date:
        return jsonify({'ok': False, 'msg': 'تاريخ النهاية يجب أن يكون بعد تاريخ البداية'}), 400

    result = LeaveService.request_leave(
        employee_id=emp.id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
    )

    if not result.get('success'):
        return jsonify({'ok': False, 'msg': result.get('error', 'فشل تقديم الطلب')}), 400

    return jsonify({'ok': True, 'leave': result['request']}), 201


@api_ops_bp.route('/api/leaves/approve/<int:rid>', methods=['POST'])
@admin_required
@safe_api
def api_leave_approve(rid):
    auth = _require_admin()
    if auth:
        return auth
    result = LeaveService.approve_leave(rid, session['user_id'],
                                        (request.get_json() or {}).get('comment'))
    if not result.get('success'):
        return jsonify({'ok': False, 'msg': result.get('error', 'فشل الموافقة')}), 400
    return jsonify({'ok': True, 'msg': 'تمت الموافقة على طلب الإجازة', 'request': result['request']})


@api_ops_bp.route('/api/leaves/reject/<int:rid>', methods=['POST'])
@admin_required
@safe_api
def api_leave_reject(rid):
    auth = _require_admin()
    if auth:
        return auth
    result = LeaveService.reject_leave(rid, session['user_id'],
                                       (request.get_json() or {}).get('comment'))
    if not result.get('success'):
        return jsonify({'ok': False, 'msg': result.get('error', 'فشل الرفض')}), 400
    return jsonify({'ok': True, 'msg': 'تم رفض طلب الإجازة', 'request': result['request']})


@api_ops_bp.route('/api/leaves/approve', methods=['POST'])
@admin_required
@safe_api
def api_leave_approve_json():
    auth = _require_admin()
    if auth:
        return auth
    data = request.get_json() or {}
    rid = data.get('leave_id')
    if not rid:
        return jsonify({'ok': False, 'msg': 'leave_id مطلوب'}), 400
    try:
        rid = int(rid)
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'msg': 'leave_id يجب أن يكون رقمًا صحيحًا'}), 400
    result = LeaveService.approve_leave(rid, session['user_id'], data.get('comment'))
    if not result.get('success'):
        return jsonify({'ok': False, 'msg': result.get('error', 'فشل الموافقة')}), 400
    return jsonify({'ok': True, 'msg': 'تمت الموافقة على طلب الإجازة', 'request': result['request']})


@api_ops_bp.route('/api/leaves/reject', methods=['POST'])
@admin_required
@safe_api
def api_leave_reject_json():
    auth = _require_admin()
    if auth:
        return auth
    data = request.get_json() or {}
    rid = data.get('leave_id')
    if not rid:
        return jsonify({'ok': False, 'msg': 'leave_id مطلوب'}), 400
    try:
        rid = int(rid)
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'msg': 'leave_id يجب أن يكون رقمًا صحيحًا'}), 400
    result = LeaveService.reject_leave(rid, session['user_id'], data.get('comment'))
    if not result.get('success'):
        return jsonify({'ok': False, 'msg': result.get('error', 'فشل الرفض')}), 400
    return jsonify({'ok': True, 'msg': 'تم رفض طلب الإجازة', 'request': result['request']})


# ─── DEVICE MANAGEMENT ──────────────────────────────────────────────────────


@api_ops_bp.route('/api/devices/list', methods=['GET'])
@login_required
@safe_api
def api_device_list():
    devices = BiometricDevice.query.filter_by(deleted_at=None)\
        .order_by(BiometricDevice.created_at.desc()).limit(100).all()
    return jsonify({
        'ok': True,
        'devices': [d.to_dict() for d in devices],
    })


@api_ops_bp.route('/api/devices/sync', methods=['POST'])
@admin_required
@safe_api
def api_device_sync():
    data = request.get_json() or {}
    device_id = data.get('device_id')
    if not device_id:
        return jsonify({'ok': False, 'msg': 'device_id مطلوب'}), 400

    dev = BiometricDevice.query.get(int(device_id))
    if not dev or dev.deleted_at:
        return jsonify({'ok': False, 'msg': 'الجهاز غير موجود'}), 404

    if not dev.ip_address:
        return jsonify({'ok': False, 'msg': 'الجهاز ليس لديه IP'}), 400

    try:
        logs = pull_attendance_logs(dev.ip_address, dev.port or 4370, dev.comm_password)
    except Exception as e:
        LOGGER.error('Sync failed for device %d: %s', dev.id, e)
        return jsonify({'ok': False, 'msg': 'فشلت مزامنة الجهاز'}), 500

    dev.last_sync = datetime.now(UTC)
    db.session.commit()

    return jsonify({
        'ok': True,
        'msg': f'تمت المزامنة. تم سحب {len(logs)} سجل.',
        'pulled': len(logs),
    })


@api_ops_bp.route('/api/devices/status', methods=['GET'])
@login_required
@safe_api
def api_device_status():
    total = BiometricDevice.query.filter_by(deleted_at=None).count()
    online = BiometricDevice.query.filter_by(deleted_at=None, is_online=True).count()
    active = BiometricDevice.query.filter_by(deleted_at=None, is_active=True).count()
    offline = total - online

    return jsonify({
        'ok': True,
        'status': {
            'total': total,
            'online': online,
            'offline': offline,
            'active': active,
            'inactive': total - active,
        }
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ■ PAYROLL
# ═══════════════════════════════════════════════════════════════════════════════

def _get_month_range(month, year):
    if month == 12:
        return date(year, month, 1), date(year, month, 31)
    return date(year, month, 1), date(year, month + 1, 1) - timedelta(days=1)


def _get_attendance_data(emp_ids, month, year):
    start_date, end_date = _get_month_range(month, year)
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(emp_ids),
        AttendanceLog.log_date >= start_date,
        AttendanceLog.log_date <= end_date,
    ).order_by(AttendanceLog.employee_id, AttendanceLog.log_date).all()
    logs_by_emp = defaultdict(list)
    for l in logs:
        logs_by_emp[l.employee_id].append(l)
    return logs_by_emp, start_date, end_date


def _compute_employee_payroll(emp, logs):
    base = emp.base_salary or 0
    housing = emp.housing_allowance or 0
    transport = emp.transport_allowance or 0
    others = emp.other_allowances_list or []
    other_total = sum(a.get('amount', 0) for a in others)
    total_allowances = housing + transport + other_total
    mult = emp.overtime_multiplier or 1.5
    total_late_m = sum(l.late_minutes or 0 for l in logs)
    total_absent = sum(1 for l in logs if l.status == 'absent')
    total_present = sum(1 for l in logs if l.status in ('present', 'late'))
    total_ot_minutes = sum(l.overtime_minutes or 0 for l in logs)
    hourly_rate = PayrollService.hourly_rate(base)
    overtime_pay = round((total_ot_minutes / 60) * hourly_rate * mult, 2)
    late_deduction = PayrollService.calculate_deduction(base, total_late_m)
    absent_deduction = PayrollService.calculate_deduction(base, total_absent * 8 * 60)
    total_deductions = round(late_deduction + absent_deduction, 2)
    gross = round(base + total_allowances + overtime_pay, 2)
    tax_result = TaxCalculator.calculate(gross, total_deductions, emp)
    net = round(gross - total_deductions - tax_result['total_tax'], 2)
    return {
        'base': base,
        'housing_allowance': housing,
        'transport_allowance': transport,
        'other_allowances': others,
        'other_allowances_total': other_total,
        'total_allowances': total_allowances,
        'overtime_minutes': total_ot_minutes,
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
        'present_days': total_present,
    }


@api_ops_bp.route('/api/payroll/calculate', methods=['POST'])
@admin_required
@safe_api
def api_payroll_calculate():
    allowed, remaining = check_rate_limit('api_payroll_calc', 30, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429

    data = request.get_json() or {}
    try:
        month = int(data.get('month', date.today().month))
    except (ValueError, TypeError):
        month = date.today().month
    try:
        year = int(data.get('year', date.today().year))
    except (ValueError, TypeError):
        year = date.today().year
    try:
        emp_id = int(data['employee_id']) if 'employee_id' in data else None
    except (ValueError, TypeError):
        emp_id = None

    if emp_id:
        emp = Employee.query.get(emp_id)
        if not emp:
            return jsonify({'ok': False, 'msg': 'الموظف غير موجود'}), 404
        employees = [emp]
    else:
        employees = Employee.query.filter_by(role='employee', is_active=True).all()

    emp_ids = [e.id for e in employees]
    logs_by_emp, start_date, end_date = _get_attendance_data(emp_ids, month, year)
    rows = []

    for emp in employees:
        logs = logs_by_emp.get(emp.id, [])
        comp = _compute_employee_payroll(emp, logs)
        rows.append({
            'employee_id': emp.id,
            'full_name': emp.full_name,
            'department': emp.department,
            'base_salary': comp['base'],
            'total_allowances': comp['total_allowances'],
            'overtime_pay': comp['overtime_pay'],
            'gross': comp['gross'],
            'total_deductions': comp['total_deductions'],
            'total_tax': comp['total_tax'],
            'net': comp['net'],
            'present_days': comp['present_days'],
            'absent_days': comp['absent_days'],
            'late_minutes': comp['late_minutes'],
        })

    total_gross = sum(r['gross'] for r in rows)
    total_net = sum(r['net'] for r in rows)
    total_ded = sum(r['total_deductions'] for r in rows)
    total_tax = sum(r['total_tax'] for r in rows)

    return jsonify({
        'ok': True,
        'rows': rows,
        'summary': {
            'employees': len(rows),
            'total_gross': round(total_gross, 2),
            'total_net': round(total_net, 2),
            'total_deductions': round(total_ded, 2),
            'total_tax': round(total_tax, 2),
        },
        'month': month,
        'year': year,
        'month_name': MONTH_NAMES[month - 1] if 1 <= month <= 12 else '',
    })


@api_ops_bp.route('/api/payroll/generate', methods=['POST'])
@admin_required
@safe_api
def api_payroll_generate():
    allowed, remaining = check_rate_limit('api_payroll_gen', 30, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429

    data = request.get_json() or {}
    try:
        month = int(data.get('month', date.today().month))
    except (ValueError, TypeError):
        month = date.today().month
    try:
        year = int(data.get('year', date.today().year))
    except (ValueError, TypeError):
        year = date.today().year

    employees = Employee.query.filter_by(role='employee', is_active=True).all()
    emp_ids = [e.id for e in employees]
    logs_by_emp, _, _ = _get_attendance_data(emp_ids, month, year)
    saved = 0

    for emp in employees:
        logs = logs_by_emp.get(emp.id, [])
        comp = _compute_employee_payroll(emp, logs)
        existing = PayrollRecord.query.filter_by(
            employee_id=emp.id, month=month, year=year
        ).first()
        if existing:
            existing.base_salary = comp['base']
            existing.housing_allowance = comp['housing_allowance']
            existing.transport_allowance = comp['transport_allowance']
            existing.other_allowances = comp['other_allowances_total']
            existing.total_allowances = comp['total_allowances']
            existing.overtime_hours = comp['overtime_minutes'] / 60
            existing.overtime_pay = comp['overtime_pay']
            existing.gross_salary = comp['gross']
            existing.late_minutes = comp['late_minutes']
            existing.late_deduction = comp['late_deduction']
            existing.absent_days = comp['absent_days']
            existing.absent_deduction = comp['absent_deduction']
            existing.total_deductions = comp['total_deductions']
            existing.income_tax = comp['tax_income']
            existing.social_security = comp['tax_social']
            existing.total_tax = comp['total_tax']
            existing.net_salary = comp['net']
            existing.status = 'calculated'
        else:
            db.session.add(PayrollRecord(
                employee_id=emp.id, month=month, year=year,
                base_salary=comp['base'],
                housing_allowance=comp['housing_allowance'],
                transport_allowance=comp['transport_allowance'],
                other_allowances=comp['other_allowances_total'],
                total_allowances=comp['total_allowances'],
                overtime_hours=comp['overtime_minutes'] / 60,
                overtime_pay=comp['overtime_pay'],
                gross_salary=comp['gross'],
                late_minutes=comp['late_minutes'],
                late_deduction=comp['late_deduction'],
                absent_days=comp['absent_days'],
                absent_deduction=comp['absent_deduction'],
                total_deductions=comp['total_deductions'],
                income_tax=comp['tax_income'],
                social_security=comp['tax_social'],
                total_tax=comp['total_tax'],
                net_salary=comp['net'],
                status='calculated',
            ))
        saved += 1

    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم حفظ رواتب {saved} موظف', 'saved': saved})


@api_ops_bp.route('/api/payroll/export', methods=['GET'])
@admin_required
@safe_api
def api_payroll_export():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    dept = request.args.get('department', '').strip()

    qry = Employee.query.filter_by(role='employee', is_active=True)
    if dept:
        qry = qry.filter_by(department=dept)
    employees = qry.all()
    emp_ids = [e.id for e in employees]
    logs_by_emp, _, _ = _get_attendance_data(emp_ids, month, year)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'الموظف', 'القسم', 'الراتب الأساسي', 'بدل سكن', 'بدل مواصلات',
        'بدلات أخرى', 'العمل الإضافي', 'إجمالي الإضافات', 'إجمالي الراتب',
        'خصم التأخير', 'خصم الغياب', 'إجمالي الخصومات',
        'ضريبة الدخل', 'التأمينات', 'صافي الراتب',
    ])
    for emp in employees:
        logs = logs_by_emp.get(emp.id, [])
        comp = _compute_employee_payroll(emp, logs)
        writer.writerow([
            emp.full_name, emp.department, comp['base'],
            comp['housing_allowance'], comp['transport_allowance'],
            comp['other_allowances_total'], comp['overtime_pay'],
            comp['total_allowances'], comp['gross'],
            comp['late_deduction'], comp['absent_deduction'],
            comp['total_deductions'], comp['tax_income'],
            comp['tax_social'], comp['net'],
        ])

    mem = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    return send_file(mem, mimetype='text/csv', as_attachment=True,
                     download_name=f'payroll_{month}_{year}.csv')


# ═══════════════════════════════════════════════════════════════════════════════
# ■ REPORTS
# ═══════════════════════════════════════════════════════════════════════════════


@api_ops_bp.route('/api/reports/attendance', methods=['GET'])
@admin_required
@safe_api
def api_report_attendance():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    dept_id = request.args.get('department_id', type=int)
    emp_id = request.args.get('employee_id', type=int)

    result = ReportDataService.calculate_report(year, month, dept_id, emp_id)
    rows = result.get('rows', [])
    summary = result.get('summary', {})

    serialized = []
    for r in rows:
        serialized.append({
            'emp_id': r['emp_id'],
            'emp_name': r['emp_name'],
            'department': r['department'],
            'present': r['present'],
            'absent': r['absent'],
            'late_count': r['late_count'],
            'late_minutes': r['late_minutes'],
            'leave_days': r['leave_days'],
            'attendance_pct': r['attendance_pct'],
            'overtime_minutes': r.get('overtime_minutes', 0),
            'total_deduction': r.get('total_deduction', 0),
            'expected_days': r.get('expected_days', 0),
            'base_salary': r.get('base_salary', 0),
            'net_salary': r.get('net_salary', 0),
        })

    return jsonify({
        'ok': True,
        'rows': serialized,
        'summary': {
            'total_employees': summary.get('total_employees', 0),
            'overall_pct': summary.get('overall_pct', 0),
            'total_absent': summary.get('total_absent', 0),
            'total_late_minutes': summary.get('total_late_minutes', 0),
            'total_deductions': summary.get('total_deductions', 0),
        },
        'month': month,
        'year': year,
        'month_name': MONTH_NAMES[month - 1] if 1 <= month <= 12 else '',
    })


@api_ops_bp.route('/api/reports/employees', methods=['GET'])
@admin_required
@safe_api
def api_report_employees():
    dept_id = request.args.get('department_id', type=int)
    is_active = request.args.get('is_active')
    search = request.args.get('search', '').strip()

    q = Employee.query.filter(Employee.role == 'employee')
    if dept_id:
        q = q.filter(Employee.department_id == dept_id)
    if is_active is not None:
        q = q.filter(Employee.is_active == (is_active == '1'))
    if search:
        like = f'%{search}%'
        q = q.filter(db.or_(
            Employee.full_name.ilike(like),
            Employee.username.ilike(like),
            Employee.national_id.ilike(like),
        ))

    employees = q.order_by(Employee.department, Employee.full_name).all()
    rows = []
    for e in employees:
        rows.append({
            'id': e.id,
            'username': e.username,
            'full_name': e.full_name,
            'national_id': e.national_id,
            'department': e.department,
            'job_title': e.job_title or '',
            'employment_type': e.employment_type or '',
            'is_active': e.is_active,
            'hire_date': e.hire_date.isoformat() if e.hire_date else None,
            'base_salary': e.base_salary or 0,
        })

    return jsonify({
        'ok': True,
        'employees': rows,
        'total': len(rows),
    })


@api_ops_bp.route('/api/reports/departments', methods=['GET'])
@admin_required
@safe_api
def api_report_departments():
    rows = []
    departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar).all()
    for d in departments:
        emp_count = Employee.query.filter_by(department_id=d.id, is_active=True, role='employee').count()
        rows.append({
            'id': d.id,
            'name_ar': d.name_ar,
            'name_en': d.name_en or '',
            'code': d.code or '',
            'employee_count': emp_count,
            'manager_name': d.manager.full_name if d.manager else None,
            'parent_name': d.parent.name_ar if d.parent else None,
            'is_active': d.is_active,
        })

    total_employees = sum(r['employee_count'] for r in rows)
    return jsonify({
        'ok': True,
        'departments': rows,
        'total_departments': len(rows),
        'total_employees': total_employees,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ■ BACKUP
# ═══════════════════════════════════════════════════════════════════════════════


@api_ops_bp.route('/api/backups/create', methods=['POST'])
@admin_required
@safe_api
def api_backup_create():
    allowed, remaining = check_rate_limit('api_backup_create', 10, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429

    data = request.get_json() or {}
    backup_type = data.get('type', 'full')
    encrypt = data.get('encrypt', True)
    description = data.get('description', '').strip()

    from services.backup_service import create_full_backup, create_incremental_backup
    if backup_type == 'incremental':
        result = create_incremental_backup(encrypt=encrypt)
    else:
        result = create_full_backup(encrypt=encrypt)

    if not result.get('ok'):
        return jsonify({'ok': False, 'msg': result.get('error', 'فشل إنشاء النسخة الاحتياطية')}), 500

    meta = BackupMetadata(
        filename=result['filename'],
        backup_type=backup_type,
        size_bytes=result.get('size_bytes', 0),
        checksum=result.get('checksum'),
        encrypted=encrypt,
        filepath=result.get('filepath'),
        description=description,
    )
    db.session.add(meta)
    db.session.commit()

    return jsonify({
        'ok': True,
        'msg': 'تم إنشاء النسخة الاحتياطية بنجاح',
        'backup': {
            'id': meta.id,
            'filename': meta.filename,
            'type': meta.backup_type,
            'size_bytes': meta.size_bytes,
            'description': meta.description,
            'created_at': meta.created_at.isoformat() if meta.created_at else None,
        }
    })


@api_ops_bp.route('/api/backups/list', methods=['GET'])
@admin_required
@safe_api
def api_backup_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    backup_type = request.args.get('type', '').strip()

    query = BackupMetadata.query.filter(BackupMetadata.deleted_at.is_(None))
    if backup_type:
        query = query.filter_by(backup_type=backup_type)
    query = query.order_by(BackupMetadata.created_at.desc())

    total = query.count()
    backups = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        'ok': True,
        'backups': [{
            'id': b.id,
            'filename': b.filename,
            'type': b.backup_type,
            'size_bytes': b.size_bytes,
            'size_display': b.size_display,
            'checksum': b.checksum,
            'encrypted': b.encrypted,
            'status': b.status,
            'description': b.description,
            'created_at': b.created_at.isoformat() if b.created_at else None,
        } for b in backups],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@api_ops_bp.route('/api/backups/restore', methods=['POST'])
@admin_required
@safe_api
def api_backup_restore():
    allowed, remaining = check_rate_limit('api_backup_restore', 5, 120)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429

    data = request.get_json() or {}
    backup_id = data.get('backup_id')
    tables = data.get('tables')
    create_backup_first = data.get('create_backup_first', True)

    if not backup_id:
        return jsonify({'ok': False, 'msg': 'backup_id مطلوب'}), 400

    meta = BackupMetadata.query.get(int(backup_id))
    if not meta or meta.deleted_at:
        return jsonify({'ok': False, 'msg': 'النسخة غير موجودة'}), 404

    from services.restoration_service import restore_from_backup
    result = restore_from_backup(
        meta.filepath,
        create_backup_first=create_backup_first,
        tables=tables,
    )

    from models.backup import BackupRestoreLog
    log = BackupRestoreLog(
        backup_id=meta.id,
        backup_filename=meta.filename,
        restore_type='partial' if tables else 'full',
        status='completed' if result.get('ok') else 'failed',
        records_restored=result.get('records_restored', 0),
        tables_restored=result.get('tables_restored', 0),
        duration_seconds=result.get('duration_seconds'),
        error_message=result.get('error'),
    )
    db.session.add(log)
    db.session.commit()

    if not result.get('ok'):
        return jsonify({'ok': False, 'msg': result.get('error', 'فشلت عملية الاستعادة')}), 500

    return jsonify({
        'ok': True,
        'msg': 'تمت استعادة النسخة الاحتياطية بنجاح',
        'result': {
            'records_restored': result.get('records_restored', 0),
            'tables_restored': result.get('tables_restored', 0),
            'duration_seconds': result.get('duration_seconds'),
        }
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ■ MISC (frontend-facing)
# ═══════════════════════════════════════════════════════════════════════════════


@api_ops_bp.route('/api/departments', methods=['GET'])
@login_required
@safe_api
def api_departments_simple():
    return jsonify([{'id': d.id, 'name': d.name_ar} for d in get_active_departments()])


@api_ops_bp.route('/api/user/preferences', methods=['GET', 'POST'])
@login_required
@safe_api
def api_user_preferences():
    emp_id = session['user_id']
    if request.method == 'GET':
        pref = UserPreference.query.filter_by(employee_id=emp_id).first()
        if not pref:
            return jsonify({
                'theme': 'dark', 'language': 'ar',
                'notifications_enabled': True, 'email_notifications': True,
                'sms_notifications': False, 'share_location': True,
                'allow_biometric': True,
            })
        return jsonify({
            'theme': pref.theme or 'dark',
            'language': pref.language or 'ar',
            'notifications_enabled': pref.notifications_enabled,
            'email_notifications': pref.email_notifications,
            'sms_notifications': pref.sms_notifications,
            'share_location': pref.share_location,
            'allow_biometric': pref.allow_biometric,
        })

    data = request.get_json() or {}
    pref = UserPreference.query.filter_by(employee_id=emp_id).first()
    if not pref:
        pref = UserPreference(employee_id=emp_id)
        db.session.add(pref)
    pref.theme = data.get('theme', pref.theme)
    pref.language = data.get('language', pref.language)
    pref.notifications_enabled = data.get('notifications_enabled', pref.notifications_enabled)
    pref.email_notifications = data.get('email_notifications', pref.email_notifications)
    pref.sms_notifications = data.get('sms_notifications', pref.sms_notifications)
    pref.share_location = data.get('share_location', pref.share_location)
    pref.allow_biometric = data.get('allow_biometric', pref.allow_biometric)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حفظ التفضيلات'})


# ═══════════════════════════════════════════════════════════════════════════════
# ■ SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════


@api_ops_bp.route('/api/system/health', methods=['GET'])
@login_required
@safe_api
def api_system_health():
    db_ok = False
    try:
        db.session.execute(db.text('SELECT 1'))
        db_ok = True
    except Exception:
        pass

    import platform
    info = {
        'status': 'healthy' if db_ok else 'degraded',
        'database': 'connected' if db_ok else 'error',
        'timestamp': datetime.now(UTC).isoformat(),
        'python_version': platform.python_version(),
        'platform': platform.platform(),
    }
    try:
        import psutil
        info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
        info['memory_percent'] = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/')
        info['disk_free'] = disk.free
        info['disk_free_display'] = f'{disk.free / (1024**3):.1f} GB'
    except ImportError:
        info['psutil'] = 'not available'

    status_code = 200 if db_ok else 503
    return jsonify(info), status_code


@api_ops_bp.route('/api/system/logs', methods=['GET'])
@admin_required
@safe_api
def api_system_logs():
    lines_count = request.args.get('lines', 100, type=int)
    log_source = request.args.get('source', 'app')

    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    log_file = os.path.join(logs_dir, f'{log_source}.log')
    if not os.path.exists(log_file):
        alt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f'{log_source}.log')
        if os.path.exists(alt):
            log_file = alt
        else:
            return jsonify({'ok': False, 'msg': 'ملف السجلات غير موجود'}), 404

    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
        tail = all_lines[-lines_count:] if len(all_lines) > lines_count else all_lines
        lines = [l.rstrip('\n\r') for l in tail]
    except Exception as e:
        LOGGER.error('Failed to read log file: %s', e)
        return jsonify({'ok': False, 'msg': 'فشل قراءة ملف السجلات'}), 500

    return jsonify({
        'ok': True,
        'source': log_source,
        'file': log_file,
        'total_lines': len(lines),
        'available_lines': len(lines),
        'lines': lines,
    })
