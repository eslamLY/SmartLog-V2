import hashlib
import html
import logging
import secrets
from datetime import datetime, date, timedelta, UTC
from flask import (Blueprint, render_template, request, session,
                   jsonify, current_app)
from models import db, Employee, AttendanceLog, LeaveRequest, OutingRequest, \
    ShiftSchedule, ShiftSwapRequest, BiometricCredential, GPSLog, ShiftType, \
    Notification, EmployeeDocument, Department, QRToken
from utils.decorators import login_required
from utils.helpers import validate_coordinates, work_hours_str, monthly_deduction
from utils.rate_limit import check_rate_limit, rate_limit_headers
from utils.constants import (MONTH_NAMES, WORK_START_HOUR, WORK_START_MINUTE,
                              LATE_GRACE_MINUTES)
from services.clock_service import ClockService
from sqlalchemy import extract

employee_bp = Blueprint('employee', __name__)

QR_TOKEN_MAX_AGE = 5
LOGGER = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ■ AREA 1 — DASHBOARD, CLOCK-IN, CLOCK-OUT
# ═══════════════════════════════════════════════════════════════════════════════


@employee_bp.route('/employee')
@login_required
def employee_dashboard():
    emp   = Employee.query.get(session['user_id'])
    today = date.today()
    log   = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()

    month_logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id == emp.id,
        extract('month', AttendanceLog.log_date) == today.month,
        extract('year',  AttendanceLog.log_date) == today.year
    ).order_by(AttendanceLog.log_date.asc()).all()

    present_days = sum(1 for l in month_logs if l.status in ('present', 'late'))
    late_days    = sum(1 for l in month_logs if l.status == 'late')
    total_late   = sum(l.late_minutes for l in month_logs)
    deduction, _ = monthly_deduction(emp.id, today.year, today.month)

    colleagues = Employee.query.filter(
        Employee.department == emp.department,
        Employee.id != emp.id,
        Employee.is_active == True
    ).order_by(Employee.full_name).all()

    my_schedules = ShiftSchedule.query.filter(
        ShiftSchedule.employee_id == emp.id,
        ShiftSchedule.scheduled_date >= today,
        ShiftSchedule.status == 'confirmed'
    ).order_by(ShiftSchedule.scheduled_date).all()

    return render_template('employee/dashboard.html',
        emp=emp, log=log, today=today,
        present_days=present_days, late_days=late_days,
        total_late=total_late, deduction=deduction,
        month_logs=month_logs,
        colleagues=colleagues,
        my_schedules=my_schedules,
        shift_types=ShiftType.query.filter_by(is_active=True).all(),
        work_hours=work_hours_str(log),
        month_name=MONTH_NAMES[today.month - 1]
    )


@employee_bp.route('/employee/clockin', methods=['POST'])
@login_required
def clock_in():
    allowed, remaining = check_rate_limit('clock_in', 6, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    if request.content_length and request.content_length > 1024 * 1024:
        return jsonify({'ok': False, 'msg': 'البيانات كبيرة جداً.'}), 413

    emp   = Employee.query.get(session['user_id'])
    today = date.today()
    log   = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()
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

    data   = request.get_json() or {}
    lat    = data.get('lat')
    lng    = data.get('lng')
    selfie = data.get('selfie', '')

    if not lat or not lng or not validate_coordinates(lat, lng):
        return jsonify({'ok': False, 'msg': 'بيانات الموقع الجغرافي غير صالحة.'})

    inside, dist = ClockService.check_geofence(lat, lng)
    now          = datetime.now()
    late_min     = ClockService.calc_late_minutes(now)
    status       = 'late' if late_min > 0 else 'present'

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


@employee_bp.route('/employee/clockout', methods=['POST'])
@login_required
def clock_out():
    allowed, remaining = check_rate_limit('clock_out', 6, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    if request.content_length and request.content_length > 1024 * 1024:
        return jsonify({'ok': False, 'msg': 'البيانات كبيرة جداً.'}), 413

    emp   = Employee.query.get(session['user_id'])
    today = date.today()
    log   = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()

    if not log or not log.clock_in:
        return jsonify({'ok': False, 'msg': 'لم تسجل حضورك اليوم بعد.'})
    if log.clock_out:
        return jsonify({'ok': False, 'msg': 'سجّلت انصرافك اليوم بالفعل.'})

    data = request.get_json() or {}
    now  = datetime.now()
    log.clock_out = now
    log.set_clock_out_coords(data.get('lat'), data.get('lng'))
    db.session.commit()

    diff    = now - log.clock_in
    h, rem  = divmod(int(diff.total_seconds()), 3600)
    m       = rem // 60
    resp = jsonify({'ok': True, 'msg': f'✅ تم تسجيل انصرافك الساعة {now.strftime("%H:%M")} — عملت {h}س {m}د'})
    resp.headers.update(rate_limit_headers(6, remaining, 60))
    return resp


@employee_bp.route('/employee/geofence', methods=['POST'])
@login_required
def geofence_check():
    data = request.get_json() or {}
    lat  = data.get('lat')
    lng  = data.get('lng')
    if not lat or not lng or not validate_coordinates(lat, lng):
        return jsonify({'inside': False, 'dist': 0})
    inside, dist = ClockService.check_geofence(lat, lng)
    emp_id = session['user_id']
    today  = date.today()
    log    = AttendanceLog.query.filter_by(employee_id=emp_id, log_date=today).first()
    if log and log.clock_in and not log.clock_out and not log.has_exit_permission:
        if not inside and log.is_inside_geofence:
            log.is_inside_geofence   = False
            log.geofence_violated_at = datetime.now()
        elif inside and not log.is_inside_geofence:
            log.is_inside_geofence   = True
            log.geofence_violated_at = None
        db.session.commit()
    return jsonify({'inside': inside, 'dist': dist})


@employee_bp.route('/api/qr-token')
@login_required
def qr_token():
    raw = secrets.token_urlsafe(32)
    h   = QRToken.hash_raw(raw)
    now = datetime.now(UTC)
    t   = QRToken(token_hash=h, expires_at=now + timedelta(seconds=QR_TOKEN_MAX_AGE))
    db.session.add(t)
    db.session.commit()
    QRToken.cleanup_expired()
    return jsonify({'token': raw, 'expires_in': QR_TOKEN_MAX_AGE})


@employee_bp.route('/employee/clock-in/qr', methods=['POST'])
@login_required
def clock_in_qr():
    data = request.get_json() or {}
    raw  = data.get('token', '')
    if not raw:
        return jsonify({'ok': False, 'msg': 'رمز QR غير صالح.'}), 400

    h = QRToken.hash_raw(raw)
    t = QRToken.query.filter_by(token_hash=h).first()

    now = datetime.now(UTC)

    if not t:
        LOGGER.warning('QR_CLOCKIN_FAIL token_not_found ip=%s user=%s',
                       request.remote_addr, session.get('user_id'))
        return jsonify({'ok': False, 'msg': 'رمز QR منتهي الصلاحية أو غير صالح. أعد المسح.'}), 400

    if t.used_at is not None:
        LOGGER.warning('QR_CLOCKIN_FAIL token_reused ip=%s user=%s token_id=%s used_at=%s',
                       request.remote_addr, session.get('user_id'), t.id, t.used_at)
        return jsonify({'ok': False, 'msg': 'رمز QR مستخدم مسبقاً. كل رمز يستخدم مرة واحدة فقط.'}), 400

    if t.expires_at < now:
        LOGGER.warning('QR_CLOCKIN_FAIL token_expired ip=%s user=%s token_id=%s',
                       request.remote_addr, session.get('user_id'), t.id)
        db.session.delete(t)
        db.session.commit()
        return jsonify({'ok': False, 'msg': 'رمز QR منتهي الصلاحية. أعد المسح.'}), 400

    emp   = Employee.query.get(session['user_id'])
    today = date.today()
    log   = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()
    if log and log.clock_in:
        return jsonify({'ok': False, 'msg': 'سجّلت حضورك اليوم بالفعل.'})

    now_local = datetime.now()
    late_min  = ClockService.calc_late_minutes(now_local)
    status    = 'late' if late_min > 0 else 'present'

    if log:
        log.clock_in = now_local; log.is_inside_geofence = True
        log.status = status; log.late_minutes = late_min
        log.override_reason = 'QR_Backup'
    else:
        log = AttendanceLog(employee_id=emp.id, log_date=today,
                            clock_in=now_local, is_inside_geofence=True,
                            status=status, late_minutes=late_min,
                            override_reason='QR_Backup')
        db.session.add(log)

    t.used_at = now
    db.session.commit()

    msg = f'✅ تم تسجيل حضورك عبر QR — {now_local.strftime("%H:%M")}'
    if late_min > 0:
        msg += f' (متأخر {late_min} دقيقة)'
    return jsonify({'ok': True, 'msg': msg})


# ═══════════════════════════════════════════════════════════════════════════════
# ■ AREA 2 — LEAVE AND OUTING REQUESTS
# ═══════════════════════════════════════════════════════════════════════════════


@employee_bp.route('/employee/leaves')
@login_required
def employee_leaves():
    emp    = Employee.query.get(session['user_id'])
    leaves = LeaveRequest.query.filter_by(employee_id=emp.id)\
                .order_by(LeaveRequest.created_at.desc()).all()
    return render_template('employee/leaves.html', emp=emp, leaves=leaves)


@employee_bp.route('/employee/documents')
@login_required
def employee_documents():
    emp = Employee.query.get(session['user_id'])
    return render_template('employee/documents.html', emp=emp)


@employee_bp.route('/employee/leaves/new', methods=['POST'])
@login_required
def new_leave():
    data = request.get_json() or {}
    sd   = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    ed   = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None
    lv   = LeaveRequest(employee_id=session['user_id'],
                        request_type=data['type'],
                        start_date=sd, end_date=ed,
                        reason=data.get('reason', '').strip())
    db.session.add(lv)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إرسال طلبك بنجاح وسيتم مراجعته من قِبل الإدارة.'})


@employee_bp.route('/employee/history')
@login_required
def employee_history():
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year  = request.args.get('year',  today.year,  type=int)
    emp   = Employee.query.get(session['user_id'])

    logs  = AttendanceLog.query.filter(
        AttendanceLog.employee_id == emp.id,
        extract('month', AttendanceLog.log_date) == month,
        extract('year',  AttendanceLog.log_date) == year
    ).order_by(AttendanceLog.log_date.desc()).all()

    deduction, total_late = monthly_deduction(emp.id, year, month)
    present_days = sum(1 for l in logs if l.status in ('present', 'late'))
    absent_days  = sum(1 for l in logs if l.status == 'absent')

    return render_template('employee/history.html',
        emp=emp, logs=logs, month=month, year=year,
        month_name=MONTH_NAMES[month-1], months=MONTH_NAMES,
        deduction=deduction, total_late=total_late,
        present_days=present_days, absent_days=absent_days,
        work_hours_str=work_hours_str
    )


@employee_bp.route('/employee/permission/outing', methods=['POST'])
@login_required
def request_outing():
    emp_id = session['user_id']
    today  = date.today()
    log    = AttendanceLog.query.filter_by(employee_id=emp_id, log_date=today).first()
    if not log or not log.clock_in:
        return jsonify({'ok': False, 'msg': 'يجب تسجيل الحضور أولاً.'})
    if log.clock_out:
        return jsonify({'ok': False, 'msg': 'لقد سجّلت انصرافك بالفعل.'})
    if log.has_exit_permission:
        return jsonify({'ok': False, 'msg': 'لديك إذن خروج نشط مسبقاً.'})
    existing = OutingRequest.query.filter_by(employee_id=emp_id, outing_date=today, status='pending').first()
    if existing:
        return jsonify({'ok': False, 'msg': 'لديك طلب خروج قيد الانتظار بالفعل.'})
    data = request.get_json() or {}
    oreq = OutingRequest(employee_id=emp_id, outing_date=today, reason=data.get('reason', '').strip())
    db.session.add(oreq)
    db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم إرسال طلب الإذن للمراجعة.'})


@employee_bp.route('/employee/shifts')
@login_required
def employee_shifts():
    import calendar as _cal
    emp   = Employee.query.get(session['user_id'])
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year  = request.args.get('year',  today.year,  type=int)

    my_schedules = ShiftSchedule.query.filter(
        ShiftSchedule.employee_id == emp.id,
        ShiftSchedule.status == 'confirmed',
        extract('month', ShiftSchedule.scheduled_date) == month,
        extract('year',  ShiftSchedule.scheduled_date) == year
    ).order_by(ShiftSchedule.scheduled_date).all()

    upcoming = ShiftSchedule.query.filter(
        ShiftSchedule.employee_id == emp.id,
        ShiftSchedule.status == 'confirmed',
        ShiftSchedule.scheduled_date >= today
    ).order_by(ShiftSchedule.scheduled_date).limit(7).all()

    colleagues = Employee.query.filter(
        Employee.department == emp.department,
        Employee.id != emp.id,
        Employee.role == 'employee',
        Employee.is_active == True
    ).all()

    my_swaps_sent = ShiftSwapRequest.query.filter_by(requester_id=emp.id)\
                        .filter(ShiftSwapRequest.status != 'approved')\
                        .order_by(ShiftSwapRequest.created_at.desc()).limit(5).all()
    my_swaps_recv = ShiftSwapRequest.query.filter_by(target_id=emp.id, status='pending')\
                        .order_by(ShiftSwapRequest.created_at.desc()).all()

    total_hours  = sum((ss.shift_type.duration_hours if ss.shift_type else 0) for ss in my_schedules)
    shift_counts = {}
    for ss in my_schedules:
        if ss.shift_type:
            nm = ss.shift_type.name
            shift_counts[nm] = shift_counts.get(nm, 0) + 1

    _, days_in_month = _cal.monthrange(year, month)
    cal_weeks = _cal.monthcalendar(year, month)
    cal_dates = {d: date(year, month, d) for d in range(1, days_in_month + 1)}
    day_map = {}
    for ss in my_schedules:
        d = ss.scheduled_date
        if d not in day_map:
            day_map[d] = {}
        st_id = ss.shift_type_id
        if st_id not in day_map[d]:
            day_map[d][st_id] = []
        day_map[d][st_id].append({'emp_name': emp.full_name, 'sched_id': ss.id})

    return render_template('employee/shifts.html',
        emp=emp, today=today, month=month, year=year,
        month_name=MONTH_NAMES[month-1], months=MONTH_NAMES,
        my_schedules=my_schedules, upcoming=upcoming,
        colleagues=colleagues,
        my_swaps_sent=my_swaps_sent, my_swaps_recv=my_swaps_recv,
        total_hours=round(total_hours, 1), shift_counts=shift_counts,
        shift_types=ShiftType.query.filter_by(is_active=True).order_by(ShiftType.start_hour).all(),
        cal_weeks=cal_weeks, cal_dates=cal_dates, day_map=day_map,
        days_in_month=days_in_month
    )


@employee_bp.route('/employee/shifts/swap/request', methods=['POST'])
@login_required
def request_shift_swap():
    d = request.get_json() or {}
    emp = Employee.query.get(session['user_id'])

    my_sched_id  = d.get('my_schedule_id')
    tgt_emp_id   = int(d.get('target_employee_id'))
    tgt_sched_id = d.get('target_schedule_id')
    reason       = (d.get('reason') or '').strip()

    if not tgt_emp_id:
        return jsonify({'ok': False, 'msg': 'يرجى اختيار الزميل.'})
    if my_sched_id == tgt_sched_id:
        return jsonify({'ok': False, 'msg': 'لا يمكن التبديل مع نفس المناوبة.'})

    existing = ShiftSwapRequest.query.filter_by(
        requester_id=emp.id, target_id=tgt_emp_id,
        req_sched_id=my_sched_id, status='pending').first()
    if existing:
        return jsonify({'ok': False, 'msg': 'طلب التبديل هذا موجود بالفعل.'})

    swap = ShiftSwapRequest(
        requester_id=emp.id, target_id=tgt_emp_id,
        req_sched_id=my_sched_id if my_sched_id else None,
        tgt_sched_id=tgt_sched_id if tgt_sched_id else None,
        reason=reason, status='pending'
    )
    db.session.add(swap); db.session.commit()

    tgt = Employee.query.get(tgt_emp_id)
    return jsonify({'ok': True, 'msg': f'✓ تم إرسال طلب التبديل إلى {tgt.full_name}. بانتظار الموافقة.'})


@employee_bp.route('/employee/shifts/swaps/<int:swap_id>/respond', methods=['POST'])
@login_required
def respond_swap(swap_id):
    swap    = ShiftSwapRequest.query.get_or_404(swap_id)
    emp_id  = session['user_id']
    if swap.target_id != emp_id:
        return jsonify({'ok': False, 'msg': 'غير مصرح.'})
    d      = request.get_json() or {}
    action = d.get('action')
    if action == 'accept':
        swap.status          = 'target_approved'
        swap.target_response = 'accepted'
        swap.updated_at      = datetime.now(UTC)
        db.session.commit()
        return jsonify({'ok': True, 'msg': 'وافقتَ على التبديل. بانتظار موافقة المدير.'})
    else:
        swap.status          = 'rejected'
        swap.target_response = 'declined'
        swap.admin_notes     = 'رفض الموظف المستهدف'
        swap.updated_at      = datetime.now(UTC)
        db.session.commit()
        return jsonify({'ok': True, 'msg': 'تم رفض طلب التبديل.'})


@employee_bp.route('/api/shifts/employee/<int:emp_id>/<int:month>/<int:year>')
@login_required
def api_employee_shifts(emp_id, month, year):
    schedules = ShiftSchedule.query.filter(
        ShiftSchedule.employee_id == emp_id,
        ShiftSchedule.status == 'confirmed',
        extract('month', ShiftSchedule.scheduled_date) == month,
        extract('year',  ShiftSchedule.scheduled_date) == year
    ).order_by(ShiftSchedule.scheduled_date).all()
    result = []
    for ss in schedules:
        st = ss.shift_type
        result.append({
            'id': ss.id,
            'date': ss.scheduled_date.strftime('%Y-%m-%d'),
            'date_ar': f"{ss.scheduled_date.day} {MONTH_NAMES[ss.scheduled_date.month-1]}",
            'shift_name': st.name if st else '?',
            'time_range': st.time_range if st else '',
            'color': st.color if st else '#64748b'
        })
    return jsonify({'schedules': result})


# ═══════════════════════════════════════════════════════════════════════════════
# ■ AREA 3 — NOTIFICATIONS AND PROFILE ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════


@employee_bp.route('/api/notifications')
@login_required
def get_notifications():
    today   = date.today()
    emp_id  = session['user_id']
    is_admin= session.get('role') == 'admin'
    notes   = []

    if is_admin:
        n = LeaveRequest.query.filter_by(status='pending').count()
        if n: notes.append({'type':'warning','msg':f'{n} طلب إجازة بانتظار المراجعة','url':'/admin/leaves'})
        viol = AttendanceLog.query.filter(
            AttendanceLog.log_date==today, AttendanceLog.is_inside_geofence==False,
            AttendanceLog.clock_out==None).count()
        if viol: notes.append({'type':'danger','msg':f'{viol} موظف خارج النطاق الآن','url':'/admin/attendance'})
        ns = ShiftSwapRequest.query.filter_by(status='target_approved').count()
        if ns: notes.append({'type':'info','msg':f'{ns} طلب تبديل بانتظار موافقة الإدارة','url':'/admin/shifts/swaps'})

        from sqlalchemy import func as sqlfunc
        for st in ShiftType.query.filter_by(is_active=True).all():
            cnt = ShiftSchedule.query.filter_by(shift_type_id=st.id,
                scheduled_date=today, status='confirmed').count()
            if cnt < st.min_staff:
                notes.append({'type':'warning','msg':f'مناوبة {st.name} اليوم: {cnt}/{st.min_staff}','url':'/admin/shifts'})

        deficit_count = 0
        for day_offset in range(7):
            d = today + timedelta(days=day_offset)
            for dept in Department.query.filter_by(is_active=True).all():
                emp_ids = [e.id for e in Employee.query.filter_by(department_id=dept.id, role='employee', is_active=True).all()]
                if not emp_ids: continue
                for s in ShiftType.query.filter_by(is_active=True).all():
                    cnt = ShiftSchedule.query.filter(
                        ShiftSchedule.employee_id.in_(emp_ids),
                        ShiftSchedule.scheduled_date == d,
                        ShiftSchedule.shift_type_id == s.id,
                        ShiftSchedule.status == 'confirmed'
                    ).count()
                    if cnt < dept.min_staff_required:
                        deficit_count += 1
        if deficit_count:
            notes.append({'type':'warning','msg':f'🧠 AI: {deficit_count} نقص في المناوبات خلال 7 أيام','url':'/admin/ai-predictor'})

        expiring = EmployeeDocument.query.filter(
            EmployeeDocument.expiry_date.isnot(None),
            EmployeeDocument.expiry_date <= today + timedelta(days=30),
        ).all()
        for doc in expiring:
            emp = Employee.query.get(doc.employee_id)
            name = emp.full_name if emp else 'موظف'
            if doc.expiry_date < today:
                notes.append({'type':'danger','msg':f'❌ مستند منتهي: {doc.doc_name} — {name}','url':'/admin/document-vault'})
            elif doc.days_until_expiry <= 30:
                notes.append({'type':'warning','msg':f'⚠️ {doc.doc_name} لـ {name} تنتهي بعد {doc.days_until_expiry} يوم','url':'/admin/document-vault'})
    else:
        my_docs = EmployeeDocument.query.filter(
            EmployeeDocument.employee_id == emp_id,
            EmployeeDocument.expiry_date.isnot(None),
            EmployeeDocument.expiry_date <= today + timedelta(days=30),
        ).all()
        for doc in my_docs:
            if doc.expiry_date < today:
                notes.append({'type':'danger','msg':f'❌ مستندك {doc.doc_name} منتهي الصلاحية!','url':'/employee'})
            elif doc.days_until_expiry <= 30:
                notes.append({'type':'warning','msg':f'⚠️ مستندك {doc.doc_name} سينتهي بعد {doc.days_until_expiry} يوم','url':'/employee'})
        n = ShiftSwapRequest.query.filter_by(target_id=emp_id, status='pending').count()
        if n: notes.append({'type':'info','msg':f'لديك {n} طلب تبديل مناوبة','url':'/employee/shifts'})
        ns = ShiftSchedule.query.filter(
            ShiftSchedule.employee_id==emp_id,
            ShiftSchedule.scheduled_date>=today,
            ShiftSchedule.scheduled_date<=today+timedelta(days=1),
            ShiftSchedule.status=='confirmed'
        ).first()
        if ns and ns.shift_type:
            notes.append({'type':'info','msg':f'مناوبتك القادمة: {ns.shift_type.name} — {ns.shift_type.time_range}','url':'/employee/shifts'})
        now = datetime.now()
        upcoming = ShiftSchedule.query.filter(
            ShiftSchedule.employee_id==emp_id,
            ShiftSchedule.scheduled_date==today,
            ShiftSchedule.status=='confirmed'
        ).first()
        if upcoming and upcoming.shift_type:
            shift_start = datetime.combine(today, datetime.min.time()) + timedelta(
                hours=upcoming.shift_type.start_hour, minutes=upcoming.shift_type.start_min)
            diff = (shift_start - now).total_seconds()
            if 0 < diff <= 3600:
                notes.append({'type':'warning','msg':f'⏰ مناوبتك بعد {int(diff//60)} دقيقة','url':'/employee/shifts'})
        log_today = AttendanceLog.query.filter_by(employee_id=emp_id, log_date=today).first()
        late_cutoff = now.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE + LATE_GRACE_MINUTES, second=0)
        if not log_today and now > late_cutoff and now.hour < WORK_START_HOUR + 4:
            notes.append({'type':'danger','msg':'⚠️ أنت متأخر! لم تسجل حضورك اليوم.','url':'/employee'})
        if not log_today:
            last_gps = GPSLog.query.filter_by(employee_id=emp_id)\
                .order_by(GPSLog.created_at.desc()).first()
            if last_gps:
                inside, _ = ClockService.check_geofence(last_gps.latitude, last_gps.longitude)
                if inside and (datetime.now(UTC) - last_gps.created_at).total_seconds() < 300:
                    notes.append({'type':'info','msg':'📍 أنت في موقع العمل — يرجى تسجيل الحضور','url':'/employee'})
    return jsonify({'notifications': notes, 'count': len(notes)})


@employee_bp.route('/api/notifications/history')
@login_required
def notification_history():
    emp_id = session['user_id']
    notes = Notification.query.filter(
        db.or_(Notification.employee_id == emp_id, Notification.is_global == True)
    ).order_by(Notification.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': n.id,
        'title': html.escape(n.title or ''),
        'message': html.escape(n.message or ''),
        'ntype': n.ntype, 'icon': n.icon, 'url': n.url,
        'is_read': n.is_read, 'created_at': n.created_at.isoformat()
    } for n in notes])


@employee_bp.route('/api/notifications/read/<int:nid>', methods=['POST'])
@login_required
def mark_notification_read(nid):
    n = Notification.query.get_or_404(nid)
    if n.employee_id and n.employee_id != session['user_id']:
        return jsonify({'ok': False})
    n.is_read = True
    db.session.commit()
    return jsonify({'ok': True})


@employee_bp.route('/api/notifications/unread-count')
@login_required
def unread_notification_count():
    emp_id = session['user_id']
    count = Notification.query.filter(
        db.or_(Notification.employee_id == emp_id, Notification.is_global == True),
        Notification.is_read == False
    ).count()
    return jsonify({'count': count})


# ─── GPS TRACKING ───────────────────────────────────────────────────────────────


@employee_bp.route('/employee/gps/log', methods=['POST'])
@login_required
def gps_log():
    last_gps = session.get('gps_last_time')
    if last_gps:
        elapsed = (datetime.now(UTC) - datetime.fromisoformat(last_gps)).total_seconds()
        if elapsed < 60:
            return jsonify({'ok': False, 'msg': 'يرجى الانتظار 60 ثانية بين كل تحديث.'}), 429
    d = request.get_json() or {}
    lat = d.get('lat'); lng = d.get('lng')
    if not validate_coordinates(lat, lng):
        return jsonify({'ok': False, 'msg': 'إحداثيات GPS غير صالحة.'})
    gps = GPSLog(employee_id=session['user_id'],
                 accuracy=d.get('accuracy', 0),
                 battery=d.get('battery'),
                 source=d.get('source', 'app'))
    gps.set_coords(lat, lng)
    db.session.add(gps)
    db.session.commit()
    session['gps_last_time'] = datetime.now(UTC).isoformat()
    return jsonify({'ok': True})


# ─── MOBILE BIOMETRICS ─────────────────────────────────────────────────────────


@employee_bp.route('/employee/biometrics/register', methods=['POST'])
@login_required
def register_biometric():
    d = request.get_json() or {}
    existing = BiometricCredential.query.filter_by(employee_id=session['user_id']).first()
    if existing:
        existing.credential_id = d['credential_id']
        existing.public_key = d.get('public_key', '')
        existing.device_info = d.get('device_info', '')
        existing.biometric_type = d.get('biometric_type', 'fingerprint')
    else:
        bc = BiometricCredential(employee_id=session['user_id'],
             credential_id=d['credential_id'], public_key=d.get('public_key', ''),
             device_info=d.get('device_info', ''), biometric_type=d.get('biometric_type', 'fingerprint'))
        db.session.add(bc)
    db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم تسجيل البصمة/الوجه بنجاح.'})


@employee_bp.route('/employee/biometrics/verify', methods=['POST'])
@login_required
def verify_biometric():
    allowed, remaining = check_rate_limit('biometric_verify', 5, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    d = request.get_json() or {}
    bc = BiometricCredential.query.filter_by(employee_id=session['user_id'], is_active=True).first()
    if not bc: return jsonify({'ok': False, 'msg': 'لم تسجل بيانات حيوية بعد.'})
    if bc.credential_id != d.get('credential_id', ''):
        return jsonify({'ok': False, 'msg': 'البيانات الحيوية غير متطابقة.'})
    bc.last_used = datetime.now(UTC)
    db.session.commit()
    session['biometric_verified'] = True
    return jsonify({'ok': True, 'msg': '✓ تم التحقق من البيانات الحيوية.'})
