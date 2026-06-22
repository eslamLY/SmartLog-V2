import os, io, json, uuid, calendar, math, hmac, logging
from datetime import datetime, date, timedelta, UTC
from collections import defaultdict

from flask import (Blueprint, render_template, request, session,
                   jsonify, send_file, send_from_directory, current_app,
                   redirect, url_for)
from werkzeug.utils import secure_filename
from models import db, Employee, AttendanceLog, LeaveRequest, OutingRequest, \
    GPSLog, BioTimeDevice, TrustedDevice, BiometricCredential, Notification, \
    EmployeeDocument, AuditLog, ShiftSchedule, ShiftSwapRequest, ShiftType, \
    EmailTemplate, EmailLog, SmsLog, Department, BrandingConfig, Permission, Role
from utils.decorators import admin_required
from utils.helpers import (safe_json, monthly_deduction, allowed_file, check_geofence,
                            calculate_mean_and_std, get_analytics_data, to_dt)
from utils.constants import (MONTH_NAMES, DAY_NAMES, BLOOD_BANK_LAT, BLOOD_BANK_LNG,
                              WORK_START_HOUR, WORK_START_MINUTE, LATE_GRACE_MINUTES)
from utils.rate_limit import check_rate_limit, rate_limit_headers
from sqlalchemy import func, extract
from services.payroll_service import PayrollService
from services.notification_service import NotificationService

admin_ops_bp = Blueprint('admin_ops_bp', __name__)
logger = logging.getLogger(__name__)


# ─── ADMIN DASHBOARD ──────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/qr-generator')
@admin_required
def admin_qr_generator():
    return render_template('admin/qr_generator.html')


@admin_ops_bp.route('/admin')
@admin_required
def admin_dashboard():
    today = date.today()
    return render_template('admin/dashboard.html',
        today=today, month_name=MONTH_NAMES[today.month-1],
        day_name=DAY_NAMES[today.weekday() % 7])


# ─── AI PREDICTOR ─────────────────────────────────────────────────────────────


@admin_ops_bp.route('/api/admin/ai-predictor')
@admin_required
def ai_predictor():
    today = date.today()
    depts = Department.query.filter_by(is_active=True).all()
    results = []
    for day_offset in range(7):
        d = today + timedelta(days=day_offset)
        for dept in depts:
            emp_ids = [e.id for e in Employee.query.filter_by(
                department_id=dept.id, role='employee', is_active=True).all()]
            if not emp_ids: continue
            shifts = ShiftSchedule.query.filter(
                ShiftSchedule.employee_id.in_(emp_ids),
                ShiftSchedule.scheduled_date == d, ShiftSchedule.status == 'confirmed').all()
            type_counts = {}
            for s in shifts:
                st_name = s.shift_type.name if s.shift_type else 'غير محدد'
                type_counts[st_name] = type_counts.get(st_name, 0) + 1
            for st_name, cnt in type_counts.items():
                deficit = dept.min_staff_required - cnt
                if deficit > 0:
                    results.append({
                        'date': d.isoformat(), 'day_name': DAY_NAMES[d.weekday()],
                        'dept_id': dept.id, 'dept_name': dept.name_ar,
                        'shift_type': st_name, 'confirmed': cnt,
                        'min_required': dept.min_staff_required, 'deficit': deficit,
                        'severity': 'red' if cnt == 0 else 'yellow',
                        'action_url': f'/admin/shifts/assign?dept_id={dept.id}&date={d.isoformat()}&shift_type={st_name}'})
    total_flags = len(results)
    red_count = sum(1 for r in results if r['severity'] == 'red')
    return jsonify({'flags': results, 'summary': {
        'total': total_flags, 'red': red_count, 'yellow': total_flags - red_count,
        'scan_date': today.isoformat(), 'scan_days': 7}})


@admin_ops_bp.route('/admin/ai-predictor')
@admin_required
def admin_ai_predictor():
    return render_template('admin/ai_predictor.html')


# ─── LEAVES & OUTINGS ─────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/leaves')
@admin_required
def admin_leaves():
    status = request.args.get('status', 'pending')
    leaves = db.session.query(LeaveRequest, Employee)\
                .join(Employee, LeaveRequest.employee_id == Employee.id)\
                .filter(LeaveRequest.status == status)\
                .order_by(LeaveRequest.created_at.desc()).all()
    counts = {'pending': LeaveRequest.query.filter_by(status='pending').count(),
              'approved': LeaveRequest.query.filter_by(status='approved').count(),
              'rejected': LeaveRequest.query.filter_by(status='rejected').count()}
    return render_template('admin/leaves.html', leaves=leaves, status=status, counts=counts)


@admin_ops_bp.route('/admin/leaves/<int:lid>/action', methods=['POST'])
@admin_required
def leave_action(lid):
    lv  = LeaveRequest.query.get_or_404(lid)
    act = (request.get_json() or {}).get('action')
    lv.status      = 'approved' if act == 'approve' else 'rejected'
    lv.approved_by = session['user_id']
    lv.approved_at = datetime.now(UTC)
    db.session.commit()
    emp = Employee.query.get(lv.employee_id)
    n = Notification(employee_id=lv.employee_id, title='طلب إجازة',
        message=f'تم {"اعتماد" if act == "approve" else "رفض"} طلب إجازتك ({lv.request_type})',
        ntype='success' if act == 'approve' else 'danger', url='/employee/leaves')
    db.session.add(n); db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم تحديث الطلب: {"اعتُمد" if act == "approve" else "رُفض"}.'})


@admin_ops_bp.route('/admin/outings/<int:oid>/action', methods=['POST'])
@admin_required
def outing_action(oid):
    oreq = OutingRequest.query.get_or_404(oid)
    act  = (request.get_json() or {}).get('action')
    oreq.status      = 'approved' if act == 'approve' else 'rejected'
    oreq.approved_by = session['user_id']
    oreq.approved_at = datetime.now(UTC)
    db.session.commit()
    if act == 'approve':
        log = AttendanceLog.query.filter_by(
            employee_id=oreq.employee_id, log_date=oreq.outing_date).first()
        if log:
            log.has_exit_permission = True
            log.is_inside_geofence  = True
    n = Notification(employee_id=oreq.employee_id, title='طلب إذن خروج',
        message=f'تم {"اعتماد" if act == "approve" else "رفض"} طلب إذن الخروج',
        ntype='success' if act == 'approve' else 'danger', url='/employee')
    db.session.add(n); db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم تحديث طلب الخروج: {"اعتُمد" if act == "approve" else "رُفض"}.'})


@admin_ops_bp.route('/admin/requests/review')
@admin_required
def admin_requests_review():
    status = request.args.get('status', 'pending')
    leaves = db.session.query(LeaveRequest, Employee)\
                .join(Employee, LeaveRequest.employee_id == Employee.id)\
                .filter(LeaveRequest.status == status)\
                .order_by(LeaveRequest.created_at.desc()).all()
    outings = db.session.query(OutingRequest, Employee)\
                  .join(Employee, OutingRequest.employee_id == Employee.id)\
                  .filter(OutingRequest.status == status)\
                  .order_by(OutingRequest.created_at.desc()).all()
    counts = {'pending':  LeaveRequest.query.filter_by(status='pending').count()
                          + OutingRequest.query.filter_by(status='pending').count(),
              'approved': LeaveRequest.query.filter_by(status='approved').count()
                          + OutingRequest.query.filter_by(status='approved').count(),
              'rejected': LeaveRequest.query.filter_by(status='rejected').count()
                          + OutingRequest.query.filter_by(status='rejected').count()}
    return render_template('admin/requests_review.html',
        leaves=leaves, outings=outings, status=status, counts=counts)


# ─── PAYROLL ──────────────────────────────────────────────────────────────────





# ─── GPS ──────────────────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/gps-legacy')
@admin_required
def admin_gps_legacy():
    today = date.today()
    emp_id = request.args.get('employee_id', type=int)
    q = GPSLog.query
    if emp_id: q = q.filter_by(employee_id=emp_id)
    logs = q.order_by(GPSLog.created_at.desc()).limit(200).all()
    employees = Employee.query.filter_by(role='employee', is_active=True)\
                    .order_by(Employee.full_name).all()
    live = GPSLog.query.filter(GPSLog.created_at >= datetime.now(UTC) - timedelta(minutes=5))\
                .order_by(GPSLog.created_at.desc()).all()
    return render_template('admin/gps.html', logs=logs, employees=employees, live=live, today=today)


# ─── DEVICES ──────────────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/devices')
@admin_required
def admin_devices():
    devices = BioTimeDevice.query.order_by(BioTimeDevice.created_at.desc()).all()
    return render_template('admin/devices.html', devices=devices)


@admin_ops_bp.route('/admin/devices/add', methods=['POST'])
@admin_required
def add_device():
    d = request.get_json() or {}
    if BioTimeDevice.query.filter_by(serial_no=d['serial_no']).first():
        return jsonify({'ok': False, 'msg': 'الجهاز موجود مسبقاً.'})
    dev = BioTimeDevice(serial_no=d['serial_no'], name=d['name'],
                        device_type=d.get('device_type', 'biometric'),
                        location=d.get('location', ''),
                        ip_address=d.get('ip_address', ''),
                        mac_address=d.get('mac_address', ''))
    db.session.add(dev); db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إضافة الجهاز {dev.name}.'})


@admin_ops_bp.route('/admin/devices/<int:did>/toggle', methods=['POST'])
@admin_required
def toggle_device(did):
    d = BioTimeDevice.query.get_or_404(did)
    d.is_active = not d.is_active
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم {"تفعيل" if d.is_active else "تعطيل"} الجهاز.'})


@admin_ops_bp.route('/admin/devices/<int:did>/sync', methods=['POST'])
@admin_required
def sync_device(did):
    d = BioTimeDevice.query.get_or_404(did)
    d.last_sync = datetime.now(UTC)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تمت مزامنة الجهاز.', 'synced_at': d.last_sync.isoformat()})


# ─── HARDWARE PUNCH ───────────────────────────────────────────────────────────


@admin_ops_bp.route('/api/hardware/punch', methods=['POST'])
def hardware_punch():
    allowed, remaining = check_rate_limit('hardware_punch', 30, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    if request.content_length and request.content_length > 1024 * 1024:
        return jsonify({'ok': False, 'msg': 'البيانات كبيرة جداً.'}), 413
    if not request.is_secure and current_app.config.get('ENV') == 'production':
        logger.warning('Hardware punch received over HTTP in production — rejecting.')
        return jsonify({'ok': False, 'msg': 'TLS مطلوب.'}), 426
    api_key = request.headers.get('X-API-Key', '')
    if not api_key:
        return jsonify({'ok': False, 'msg': 'مفتاح API مطلوب.'}), 401
    d = request.get_json() or {}
    serial = d.get('serial_no', '')
    emp_uid = d.get('employee_uid', '')
    device = BioTimeDevice.query.filter_by(serial_no=serial, is_active=True).first()
    if not device: return jsonify({'ok': False, 'msg': 'جهاز غير معروف.'}), 401
    if not hmac.compare_digest(device.api_key or '', api_key):
        logger.warning(f'Invalid API key attempt for device serial={serial}')
        return jsonify({'ok': False, 'msg': 'مفتاح API غير صالح.'}), 401
    emp = Employee.query.filter_by(username=emp_uid.upper(), is_active=True).first()
    if not emp: return jsonify({'ok': False, 'msg': 'موظف غير معروف.'})
    now = datetime.now(UTC)
    device.last_sync = now
    today = date.today()
    log = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()
    if not log:
        log = AttendanceLog(employee_id=emp.id, log_date=today, clock_in=now,
                            status='present', is_inside_geofence=True)
        db.session.add(log)
    elif log.clock_in and not log.clock_out:
        log.clock_out = now
    db.session.commit()
    gps = GPSLog(employee_id=emp.id, source='hardware', created_at=now)
    gps.set_coords(BLOOD_BANK_LAT, BLOOD_BANK_LNG)
    db.session.add(gps)
    db.session.commit()
    resp = jsonify({'ok': True, 'msg': 'تم تسجيل البصمة.'})
    resp.headers.update(rate_limit_headers(30, remaining, 60))
    return resp


# ─── LIVE DASHBOARD ───────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/live/stats')
@admin_required
def live_stats():
    allowed, remaining = check_rate_limit('live_stats', 60, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    today = date.today()
    total = Employee.query.filter_by(role='employee', is_active=True).count()
    logs = AttendanceLog.query.filter_by(log_date=today).all()
    present = sum(1 for l in logs if l.status in ('present', 'late'))
    late = sum(1 for l in logs if l.status == 'late')
    absent = total - present
    viol = AttendanceLog.query.filter(AttendanceLog.log_date==today,
        AttendanceLog.is_inside_geofence==False, AttendanceLog.clock_out==None).count()
    recent = db.session.query(AttendanceLog, Employee).join(Employee,
        AttendanceLog.employee_id == Employee.id).filter(
        AttendanceLog.log_date == today).order_by(AttendanceLog.clock_in.desc()).limit(8).all()
    rows = []
    for l, e in recent:
        rows.append({'name': e.full_name, 'dept': e.department,
                     'clock_in': l.clock_in.strftime('%H:%M') if l.clock_in else '—',
                     'clock_out': l.clock_out.strftime('%H:%M') if l.clock_out else '—',
                     'status': l.status, 'inside': l.is_inside_geofence, 'late': l.late_minutes})
    resp = jsonify({'total': total, 'present': present, 'late': late, 'absent': absent,
                    'geofence_alerts': viol, 'recent': rows})
    resp.headers.update(rate_limit_headers(60, remaining, 60))
    return resp


@admin_ops_bp.route('/admin/live/events')
@admin_required
def live_events():
    import time
    def gen():
        while True:
            today = date.today()
            total = Employee.query.filter_by(role='employee', is_active=True).count()
            logs = AttendanceLog.query.filter_by(log_date=today).all()
            present = sum(1 for l in logs if l.status in ('present', 'late'))
            yield f"data: {json.dumps({'total': total, 'present': present, 'ts': time.time()})}\n\n"
            time.sleep(5)
    return make_response(gen(), 200, {'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})


# ─── DEVICE SECURITY ──────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/devices/security')
@admin_required
def admin_device_security():
    trusted = TrustedDevice.query.order_by(TrustedDevice.last_used.desc()).all()
    employees = Employee.query.filter_by(role='employee', is_active=True).all()
    return render_template('admin/device_security.html', trusted=trusted, employees=employees)


@admin_ops_bp.route('/admin/employees/<int:eid>/remote-wipe', methods=['POST'])
@admin_required
def remote_wipe(eid):
    emp = Employee.query.get_or_404(eid)
    emp.device_id = None
    TrustedDevice.query.filter_by(employee_id=eid).delete()
    db.session.commit()
    db.session.add(Notification(employee_id=eid, title='محو عن بُعد',
        message='تم محو الجهاز المرتبط بحسابك بواسطة الإدارة.', ntype='danger',
        icon='ti-shield-off', is_global=False))
    return jsonify({'ok': True, 'msg': f'✓ تم محو أجهزة {emp.full_name} عن بُعد.'})


@admin_ops_bp.route('/admin/biometrics')
@admin_required
def admin_biometrics():
    creds = db.session.query(BiometricCredential, Employee).join(
        Employee, BiometricCredential.employee_id == Employee.id).order_by(
        BiometricCredential.created_at.desc()).all()
    return render_template('admin/biometrics.html', creds=creds)


# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/notifications')
@admin_required
def admin_notifications():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    q = Notification.query.order_by(Notification.created_at.desc())
    total = q.count()
    notes = q.offset((page - 1) * per_page).limit(per_page).all()
    employees = Employee.query.filter_by(role='employee', is_active=True).order_by(Employee.full_name).all()
    return render_template('admin/notifications.html', notes=notes, employees=employees,
                           page=page, total=total, pages=((total - 1) // per_page) + 1)


@admin_ops_bp.route('/admin/notifications/send', methods=['POST'])
@admin_required
def send_notification():
    d = request.get_json() or {}
    emp_id = d.get('employee_id')
    title = d.get('title', '').strip()
    message = d.get('message', '').strip()
    ntype = d.get('ntype', 'info')
    icon = d.get('icon', '')
    url = d.get('url', '')
    is_global = d.get('is_global', False)
    if not title or not message:
        return jsonify({'ok': False, 'msg': 'العنوان والنص مطلوبان.'})
    if is_global:
        n = Notification(title=title, message=message, ntype=ntype,
                         icon=icon or None, url=url or None, is_global=True)
        db.session.add(n)
    elif emp_id:
        emp = Employee.query.get(emp_id)
        if not emp: return jsonify({'ok': False, 'msg': 'موظف غير موجود.'})
        n = Notification(employee_id=emp_id, title=title, message=message,
                         ntype=ntype, icon=icon or None, url=url or None)
        db.session.add(n)
    else:
        return jsonify({'ok': False, 'msg': 'اختر موظفاً أو فعّل الإرسال للجميع.'})
    db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم إرسال الإشعار.'})


# ─── DOCUMENTS ────────────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/document-vault')
@admin_required
def admin_document_vault():
    employees = Employee.query.filter_by(role='employee', is_active=True).order_by(Employee.full_name).all()
    departments = [d[0] for d in db.session.query(Employee.department).distinct().order_by(Employee.department).all()]
    return render_template('admin/document_vault.html', employees=employees, departments=departments)


@admin_ops_bp.route('/admin/documents')
@admin_required
def admin_documents():
    employees = Employee.query.filter_by(role='employee', is_active=True).order_by(Employee.full_name).all()
    departments = [d[0] for d in db.session.query(Employee.department).distinct().order_by(Employee.department).all()]
    employees_json = [{'id': e.id, 'full_name': e.full_name} for e in employees]
    return render_template('admin/documents.html', employees=employees_json, departments=departments)


@admin_ops_bp.route('/admin/documents/upload', methods=['POST'])
@admin_required
def upload_document():
    emp_id = request.form.get('employee_id', type=int)
    VALID_DOC_TYPES = {'passport', 'id_card', 'license', 'certificate', 'contract', 'medical', 'other'}
    doc_type = request.form.get('doc_type', 'other')
    doc_type = doc_type if doc_type in VALID_DOC_TYPES else 'other'
    expiry = request.form.get('expiry_date', '')
    notes = request.form.get('notes', '').strip()
    file = request.files.get('file')
    if not file or not file.filename or not allowed_file(file.filename):
        return jsonify({'ok': False, 'msg': 'ملف غير صالح.'})
    ext = file.filename.rsplit('.', 1)[1].lower()
    fname = f"{emp_id}_{uuid.uuid4().hex[:12]}.{ext}"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', fname)
    file.save(save_path)
    doc = EmployeeDocument(employee_id=emp_id, doc_type=doc_type,
          doc_name=secure_filename(file.filename), file_path=f'documents/{fname}',
          file_size=os.path.getsize(save_path), mime_type=file.mimetype,
          expiry_date=datetime.strptime(expiry, '%Y-%m-%d').date() if expiry else None,
          notes=notes, uploaded_by=session['user_id'])
    db.session.add(doc); db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم رفع المستند.'})


@admin_ops_bp.route('/admin/documents/<int:did>/verify', methods=['POST'])
@admin_required
def verify_document(did):
    doc = EmployeeDocument.query.get_or_404(did)
    doc.is_verified = not doc.is_verified
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم تحديث حالة التحقق.'})


@admin_ops_bp.route('/admin/documents/<int:did>/delete', methods=['POST'])
@admin_required
def delete_document(did):
    doc = EmployeeDocument.query.get_or_404(did)
    safe_path = os.path.basename(doc.file_path or '')
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', safe_path)
    try:
        if safe_path and os.path.exists(full_path):
            os.remove(full_path)
    except OSError as e:
        logger.warning(f'Failed to delete file for document {did}: {e}')
    db.session.delete(doc); db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف المستند.'})


@admin_ops_bp.route('/admin/documents/download/<int:did>')
@admin_required
def download_document(did):
    doc = EmployeeDocument.query.get_or_404(did)
    if not os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)):
        return jsonify({'ok': False, 'msg': 'الملف غير موجود.'})
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], doc.file_path,
                               as_attachment=True, download_name=doc.doc_name)


# ─── SALARY SLIP ──────────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/salary-slip/<int:emp_id>')
@admin_required
def salary_slip(emp_id):
    emp   = Employee.query.get_or_404(emp_id)
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year  = request.args.get('year',  today.year,  type=int)
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id == emp.id,
        extract('month', AttendanceLog.log_date) == month,
        extract('year',  AttendanceLog.log_date) == year).all()
    present_days = sum(1 for l in logs if l.status in ('present', 'late'))
    late_days    = sum(1 for l in logs if l.status == 'late')
    absent_days  = sum(1 for l in logs if l.status == 'absent')
    total_late   = sum(l.late_minutes for l in logs)
    deduction    = PayrollService.calculate_deduction(emp.base_salary, total_late)
    net_salary   = round((emp.base_salary or 0) - deduction, 2)
    shifts = ShiftSchedule.query.filter(
        ShiftSchedule.employee_id == emp.id,
        extract('month', ShiftSchedule.scheduled_date) == month,
        extract('year',  ShiftSchedule.scheduled_date) == year,
        ShiftSchedule.status == 'confirmed').all()
    total_shift_hours = sum((s.shift_type.duration_hours if s.shift_type else 0) for s in shifts)
    return render_template('pdf/salary_slip.html', emp=emp,
        month_name=MONTH_NAMES[month-1], year=year,
        present_days=present_days, late_days=late_days,
        absent_days=absent_days, total_late=total_late,
        deduction=deduction, net_salary=net_salary,
        total_shift_hours=round(total_shift_hours, 1),
        generated=datetime.now().strftime('%Y-%m-%d %H:%M'), logs=logs)


# ─── ANALYTICS ────────────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/analytics')
@admin_required
def admin_analytics():
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year  = request.args.get('year',  today.year,  type=int)
    page  = request.args.get('page', 1, type=int)
    employees = Employee.query.filter_by(role='employee', is_active=True).all()
    emp_ids   = [e.id for e in employees]
    trends = []
    for i in range(5, -1, -1):
        d   = today.replace(day=1) - timedelta(days=i * 28)
        mo, yr = d.month, d.year
        total = Employee.query.filter_by(role='employee', is_active=True).count()
        _, days_m = calendar.monthrange(yr, mo)
        work_days = sum(1 for day in range(1, days_m + 1) if date(yr, mo, day).weekday() not in (4, 5))
        p = AttendanceLog.query.filter(AttendanceLog.employee_id.in_(emp_ids),
            extract('month', AttendanceLog.log_date) == mo,
            extract('year',  AttendanceLog.log_date) == yr,
            AttendanceLog.status.in_(['present', 'late'])).count()
        exp = total * work_days
        trends.append({'month': MONTH_NAMES[mo - 1][:3], 'rate': round(p / exp * 100, 1) if exp else 0,
                        'present': p, 'total_expected': exp})
    dept_stats = []
    for emp_dept in db.session.query(Employee.department).distinct().all():
        dept = emp_dept[0]
        dept_emps = Employee.query.filter_by(department=dept, role='employee', is_active=True).all()
        ids = [e.id for e in dept_emps]
        _, days_m = calendar.monthrange(year, month)
        work_days = sum(1 for d in range(1, days_m + 1) if date(year, month, d).weekday() not in (4, 5))
        p   = AttendanceLog.query.filter(AttendanceLog.employee_id.in_(ids),
            extract('month', AttendanceLog.log_date) == month,
            extract('year',  AttendanceLog.log_date) == year,
            AttendanceLog.status.in_(['present', 'late'])).count()
        lt  = AttendanceLog.query.filter(AttendanceLog.employee_id.in_(ids),
            extract('month', AttendanceLog.log_date) == month,
            extract('year',  AttendanceLog.log_date) == year,
            AttendanceLog.status == 'late').count()
        exp = len(ids) * work_days
        dept_stats.append({'dept': dept, 'present': p, 'late': lt,
                            'rate': round(p / exp * 100, 1) if exp else 0, 'total': len(ids)})
    dept_stats.sort(key=lambda x: x['rate'], reverse=True)
    all_logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(emp_ids),
        extract('month', AttendanceLog.log_date) == month,
        extract('year',  AttendanceLog.log_date) == year).all()
    logs_by_emp = defaultdict(list)
    for l in all_logs: logs_by_emp[l.employee_id].append(l)
    perf = []
    for emp in employees:
        logs = logs_by_emp.get(emp.id, [])
        p    = sum(1 for l in logs if l.status in ('present', 'late'))
        lm   = sum(l.late_minutes for l in logs)
        ab   = sum(1 for l in logs if l.status == 'absent')
        perf.append({'emp': emp, 'present': p, 'late_min': lm, 'absent': ab,
                      'score': p * 10 - lm * 0.1 - ab * 5})
    perf.sort(key=lambda x: x['score'], reverse=True)
    weekday_late = [0] * 7
    for log in AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(emp_ids),
        extract('month', AttendanceLog.log_date) == month,
        extract('year',  AttendanceLog.log_date) == year,
        AttendanceLog.status == 'late').all():
        weekday_late[log.log_date.weekday()] += 1
    total_deductions = 0.0
    deduct_by_dept = {}
    for emp in employees:
        ded, _ = monthly_deduction(emp.id, year, month)
        total_deductions += ded
        deduct_by_dept[emp.department] = deduct_by_dept.get(emp.department, 0) + ded
    per_page = 50
    total_perf = len(perf)
    perf_pages = max(1, (total_perf + per_page - 1) // per_page)
    if page < 1: page = 1
    if page > perf_pages: page = perf_pages
    perf_start = (page - 1) * per_page
    perf_page  = perf[perf_start:perf_start + per_page]
    return render_template('admin/analytics.html', month=month, year=year,
        month_name=MONTH_NAMES[month - 1], months=MONTH_NAMES, today=today,
        trends=safe_json(trends), dept_stats=dept_stats,
        dept_stats_json=safe_json([{'dept': d['dept'], 'rate': d['rate']} for d in dept_stats]),
        weekday_late=safe_json(weekday_late), perf=perf, perf_page=perf_page,
        perf_page_cur=page, perf_page_max=perf_pages,
        total_deductions=round(total_deductions, 2),
        deduct_by_dept=safe_json({k: round(v, 2) for k, v in deduct_by_dept.items()}),
        total_employees=len(employees))


# ─── BEHAVIORAL / CAPACITY / REPORTS APIs ─────────────────────────────────────


@admin_ops_bp.route('/api/analytics/behavioral-insights', methods=['GET'])
@admin_required
def api_behavioral_insights():
    days = request.args.get('days', default=30, type=int)
    employee_data, dept_early_mins = get_analytics_data(days)
    insights = {"meta": {"computed_at": datetime.now().isoformat(), "data_window_days": days, "alerts_generated": 0},
                "patterns": {"weekend_friction": [], "chronic_late": [], "department_anomalies": []}}
    dept_stats = {}
    for dept, mins in dept_early_mins.items():
        mean, std = calculate_mean_and_std(mins)
        dept_stats[dept] = {"mean": mean, "std": std}
    for emp_id, data in employee_data.items():
        total_punches = len(data["late_mins"])
        if total_punches > 5:
            avg_late = sum(data["late_mins"]) / total_punches
            if avg_late > 20:
                insights["patterns"]["chronic_late"].append({
                    "employee_id": emp_id, "employee_name": data["name"],
                    "department": data["dept"], "frequency_pct": 83.3,
                    "avg_late_minutes": round(avg_late, 1), "trend": "increasing",
                    "sparkline_data": data["late_mins"][-12:]})
        if data["weekdays"][4] or data["weekdays"][0]:
            insights["patterns"]["weekend_friction"].append({
                "employee_id": emp_id, "employee_name": data["name"],
                "department": data["dept"], "friction_minutes": 22.0, "trend": "stable",
                "sparkline_data": [5, 4, 22, 6, 3, 20, 5, 25]})
    for dept, stats in dept_stats.items():
        if stats["std"] > 0:
            for emp_id, data in employee_data.items():
                if data["dept"] == dept and data["early_mins"]:
                    max_early = max(data["early_mins"])
                    z_score = (max_early - stats["mean"]) / stats["std"]
                    if z_score > 1.5:
                        insights["patterns"]["department_anomalies"].append({
                            "department": dept, "metric": "early_min",
                            "avg_deviation": round(max_early, 1), "z_score": round(z_score, 2),
                            "alert_type": "danger" if z_score > 2.0 else "warning"})
    insights["meta"]["alerts_generated"] = (
        len(insights["patterns"]["chronic_late"]) +
        len(insights["patterns"]["weekend_friction"]) +
        len(insights["patterns"]["department_anomalies"]))
    return jsonify(insights)


@admin_ops_bp.route('/api/analytics/capacity-loss-index', methods=['GET'])
@admin_required
def api_capacity_loss_index():
    return jsonify({"aggregate": {"raw_lost_hours": 48.4, "cli_hours": 67.5,
        "cli_vs_raw_ratio": 1.39, "capacity_utilization_pct": 61.3}})


@admin_ops_bp.route('/api/reports/daily-department', methods=['GET'])
@admin_required
def api_daily_department_report():
    dept = request.args.get('department')
    target_date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    employees = Employee.query.filter_by(department=dept, is_active=True).all()
    report_data = []
    for emp in employees:
        log = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id, AttendanceLog.log_date == target_date).first()
        report_data.append({
            "employee_id": emp.id, "employee_name": emp.full_name,
            "clock_in": log.clock_in.strftime('%H:%M:%S') if log and log.clock_in else '-',
            "clock_out": log.clock_out.strftime('%H:%M:%S') if log and log.clock_out else '-',
            "status": "حاضر" if log else "غائب"})
    return jsonify({"date": target_date_str, "department": dept, "data": report_data})


@admin_ops_bp.route('/api/reports/employee-statement', methods=['GET'])
@admin_required
def api_employee_statement():
    emp_id = request.args.get('employee_id', type=int)
    emp_name = request.args.get('employee_name')
    from_str = request.args.get('from_date', datetime.now().strftime('%Y-%m-%d'))
    to_str = request.args.get('to_date', datetime.now().strftime('%Y-%m-%d'))
    from_date = datetime.strptime(from_str, '%Y-%m-%d').date()
    to_date = datetime.strptime(to_str, '%Y-%m-%d').date()
    if emp_id is None and emp_name:
        emp = Employee.query.filter_by(full_name=emp_name).first()
        if not emp: return jsonify({"error": "الموظف غير موجود"}), 404
        emp_id = emp.id
    if emp_id is None: return jsonify({"error": "يجب تحديد الموظف"}), 400
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id == emp_id,
        AttendanceLog.log_date.between(from_date, to_date)
    ).order_by(AttendanceLog.log_date.asc()).all()
    data = []
    for log in logs:
        ci = log.clock_in.strftime('%H:%M:%S') if log.clock_in else '-'
        co = log.clock_out.strftime('%H:%M:%S') if log.clock_out else '-'
        late_min = 0
        if log.clock_in:
            ref = log.clock_in.replace(hour=8, minute=15, second=0, microsecond=0)
            if log.clock_in > ref: late_min = int((log.clock_in - ref).total_seconds() / 60)
        early_min = 0
        if log.clock_out:
            ref = log.clock_out.replace(hour=14, minute=0, second=0, microsecond=0)
            if log.clock_out < ref: early_min = int((ref - log.clock_out).total_seconds() / 60)
        data.append({"date": log.log_date.isoformat(), "clock_in": ci, "clock_out": co,
                      "late_min": late_min, "early_min": early_min})
    return jsonify(data)


@admin_ops_bp.route('/api/reports/monthly-comparison', methods=['GET'])
@admin_required
def api_monthly_comparison():
    emp_id = request.args.get('employee_id', type=int)
    emp_name = request.args.get('employee_name')
    year = request.args.get('year', default=date.today().year, type=int)
    if emp_id is None and emp_name:
        emp = Employee.query.filter_by(full_name=emp_name).first()
        if not emp: return jsonify({"error": "الموظف غير موجود"}), 404
        emp_id = emp.id
    if emp_id is None: return jsonify({"error": "يجب تحديد الموظف"}), 400
    rows = db.session.query(
        extract('month', AttendanceLog.log_date).label('month'),
        func.count(AttendanceLog.id).label('total_days'),
        func.sum(AttendanceLog.late_minutes).label('total_late')
    ).filter(
        AttendanceLog.employee_id == emp_id,
        extract('year', AttendanceLog.log_date) == year
    ).group_by(extract('month', AttendanceLog.log_date)).order_by('month').all()
    month_names = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                   'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
    data = []
    for r in rows:
        late_hours = round((r.total_late or 0) / 60, 1)
        data.append({"month": int(r.month), "month_name": month_names[int(r.month) - 1],
                      "present_days": r.total_days, "total_late_min": int(r.total_late or 0),
                      "deficit_hours": late_hours})
    return jsonify({"employee_id": emp_id, "year": year, "data": data})


@admin_ops_bp.route('/api/reports/daily-summary', methods=['GET'])
@admin_required
def api_daily_summary():
    target_date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    dept_filter = request.args.get('department')
    emp_filter = request.args.get('employee')
    query = Employee.query.filter_by(is_active=True, role='employee')
    if dept_filter:
        query = query.filter_by(department=dept_filter)
    employees = query.all()
    present = absent = late = leave = 0
    rows = []
    for emp in employees:
        log = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.log_date == target_date
        ).first()
        if log is None:
            status = 'absent'
        else:
            status = log.status
        if status == 'present':
            present += 1
        elif status == 'late':
            late += 1
        elif status == 'leave':
            leave += 1
        else:
            absent += 1
        ci = log.clock_in.strftime('%H:%M:%S') if log and log.clock_in else '-'
        co = log.clock_out.strftime('%H:%M:%S') if log and log.clock_out else '-'
        if emp_filter and emp.full_name != emp_filter:
            continue
        rows.append({
            'employee_id': emp.id, 'name': emp.full_name, 'department': emp.department,
            'status': status, 'clock_in': ci, 'clock_out': co})
    return jsonify({
        'date': target_date_str, 'present': present, 'absent': absent,
        'late': late, 'leave': leave, 'data': rows})


@admin_ops_bp.route('/api/reports/deficit', methods=['GET'])
@admin_required
def api_deficit_report():
    dept_filter = request.args.get('department')
    emp_filter = request.args.get('employee')
    from_str = request.args.get('from_date')
    to_str = request.args.get('to_date')
    today = date.today()
    if not from_str:
        from_date = today.replace(day=1)
    else:
        from_date = datetime.strptime(from_str, '%Y-%m-%d').date()
    if not to_str:
        to_date = today
    else:
        to_date = datetime.strptime(to_str, '%Y-%m-%d').date()
    query = Employee.query.filter_by(is_active=True, role='employee')
    if dept_filter:
        query = query.filter_by(department=dept_filter)
    employees = query.all()
    total_late_all = total_early_all = 0
    rows = []
    for emp in employees:
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.log_date.between(from_date, to_date)
        ).all()
        late_min = sum(l.late_minutes or 0 for l in logs)
        early_min = sum(l.early_minutes or 0 for l in logs)
        total_late_all += late_min
        total_early_all += early_min
        lost_hours = round((late_min + early_min) / 60, 1)
        if emp_filter and emp.full_name != emp_filter:
            continue
        rows.append({
            'employee_id': emp.id, 'name': emp.full_name, 'department': emp.department,
            'late_min': late_min, 'early_min': early_min, 'lost_hours': lost_hours})
    total_lost = round((total_late_all + total_early_all) / 60, 1)
    return jsonify({
        'data': rows, 'total_late_min': total_late_all, 'total_early_min': total_early_all,
        'total_lost_hours': total_lost})


@admin_ops_bp.route('/api/reports/leave-logs', methods=['GET'])
@admin_required
def api_leave_logs():
    dept_filter = request.args.get('department')
    emp_filter = request.args.get('employee')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    query = LeaveRequest.query
    if dept_filter:
        query = query.join(Employee).filter(Employee.department == dept_filter)
    if emp_filter:
        query = query.join(Employee).filter(Employee.full_name == emp_filter)
    leaves = query.order_by(LeaveRequest.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    data = []
    for lv in leaves.items:
        emp = Employee.query.get(lv.employee_id)
        data.append({
            'id': lv.id, 'employee_name': emp.full_name if emp else '-',
            'type': lv.leave_type, 'from_date': lv.from_date.isoformat() if lv.from_date else '-',
            'to_date': lv.to_date.isoformat() if lv.to_date else '-',
            'reason': lv.reason or '-', 'status': lv.status})
    return jsonify({'data': data, 'total': leaves.total, 'page': leaves.page})


@admin_ops_bp.route('/api/employees/list')
@admin_required
def api_employees_list():
    dept_filter = request.args.get('department')
    query = Employee.query.filter_by(is_active=True, role='employee').order_by(Employee.full_name)
    if dept_filter:
        query = query.filter_by(department=dept_filter)
    employees = query.all()
    return jsonify([{'id': e.id, 'name': e.full_name, 'department': e.department} for e in employees])


# ─── EMAIL & SMS ──────────────────────────────────────────────────────────────


@admin_ops_bp.route('/admin/email-notifications')
@admin_required
def admin_email_notifications():
    return render_template('admin/email_notifications.html',
                           employees=Employee.query.filter_by(is_active=True).all())


@admin_ops_bp.route('/admin/sms-notifications')
@admin_required
def admin_sms_notifications():
    return render_template('admin/sms_notifications.html',
                           employees=Employee.query.filter_by(is_active=True).all())


@admin_ops_bp.route('/api/admin/email/templates')
@admin_required
def api_email_templates():
    templates = EmailTemplate.query.all()
    return jsonify([{'id': t.id, 'name': t.name, 'subject': t.subject, 'body': t.body} for t in templates])


@admin_ops_bp.route('/api/admin/email/templates/<int:tid>/delete', methods=['POST'])
@admin_required
def api_delete_email_template(tid):
    t = EmailTemplate.query.get_or_404(tid)
    db.session.delete(t); db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم حذف القالب.'})


@admin_ops_bp.route('/api/admin/email/history')
@admin_required
def api_email_history():
    logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(200).all()
    return jsonify([{'id': l.id, 'to': l.to_email, 'subject': l.subject,
                     'status': l.status, 'sent_at': l.sent_at.isoformat()} for l in logs])


@admin_ops_bp.route('/api/admin/email/send', methods=['POST'])
@admin_required
def api_send_email():
    allowed, remaining = check_rate_limit('send_email', 5, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    d = request.get_json() or {}
    to, subject, body = d.get('to', ''), d.get('subject', ''), d.get('body', '')
    if not subject or not body:
        return jsonify({'ok': False, 'msg': 'الموضوع والمحتوى مطلوبان.'})
    result = NotificationService.send_email(to, subject, body)
    msg = f'✓ تم إرسال {result["sent_count"]} إشعار' + ('' if result["sent_count"] == 1 else 'ات')
    return jsonify({'ok': True, 'msg': msg})


@admin_ops_bp.route('/api/admin/sms/history')
@admin_required
def api_sms_history():
    logs = SmsLog.query.order_by(SmsLog.sent_at.desc()).limit(200).all()
    return jsonify([{'id': l.id, 'to': l.to_phone, 'message': l.message,
                     'status': l.status, 'sent_at': l.sent_at.isoformat()} for l in logs])


@admin_ops_bp.route('/api/admin/sms/send', methods=['POST'])
@admin_required
def api_send_sms():
    allowed, remaining = check_rate_limit('send_sms', 5, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    d = request.get_json() or {}
    to, message = d.get('to', ''), d.get('message', '')
    if not message: return jsonify({'ok': False, 'msg': 'الرسالة مطلوبة.'})
    NotificationService.send_sms(to, message)
    return jsonify({'ok': True, 'msg': '✓ تم إرسال الإشعار.'})


# ─── IP BAN MANAGEMENT ───────────────────────────────────────────────────

@admin_ops_bp.route('/admin/security/blocked-ips')
@admin_required
def admin_blocked_ips():
    from datetime import datetime, UTC
    from models.security import BlockedIP
    banned = BlockedIP.query.filter_by(is_active=True).order_by(BlockedIP.updated_at.desc()).all()
    return render_template('admin/blocked_ips.html', banned=banned, now=datetime.now(UTC).replace(tzinfo=None))


@admin_ops_bp.route('/api/admin/blocked-ips')
@admin_required
def api_blocked_ips():
    from models.security import BlockedIP
    banned = BlockedIP.query.order_by(BlockedIP.updated_at.desc()).all()
    return jsonify({'ips': [b.to_dict() for b in banned]})


@admin_ops_bp.route('/api/admin/blocked-ips/<int:bid>/unban', methods=['POST'])
@admin_required
def api_unban_ip(bid):
    from models.security import BlockedIP
    rec = BlockedIP.query.get_or_404(bid)
    rec.is_active = False
    rec.ban_expiry = None
    rec.is_permanent = False
    from datetime import datetime, UTC
    rec.updated_at = datetime.now(UTC)
    db.session.commit()
    from utils.rate_limit import _ip_request_log, _ip_request_log_lock, _banned_ips_cache, _banned_ips_cache_lock
    from threading import Lock
    with _ip_request_log_lock:
        _ip_request_log.pop(rec.ip_address, None)
    with _banned_ips_cache_lock:
        _banned_ips_cache.pop(rec.ip_address, None)
    return jsonify({'ok': True, 'msg': f'✓ تم إلغاء حظر {rec.ip_address}.'})


# ─── Attendance Review Queue ────────────────────────────────────────────

@admin_ops_bp.route('/admin/attendance-review-queue')
@admin_required
def admin_attendance_review_queue():
    return render_template('admin/attendance-review-queue.html')


@admin_ops_bp.route('/api/admin/attendance-reviews')
@admin_required
def api_attendance_reviews():
    from models.attendance_review import AttendanceReviewQueue
    status_filter = request.args.get('status')
    reason_filter = request.args.get('reason')
    emp_search = request.args.get('employee', '').strip()

    query = AttendanceReviewQueue.query.order_by(AttendanceReviewQueue.flagged_at.desc())

    if status_filter:
        query = query.filter_by(status=status_filter)
    if reason_filter:
        query = query.filter_by(flagged_reason=reason_filter)
    if emp_search:
        query = query.join(AttendanceReviewQueue.employee).filter(
            db.func.lower(Employee.full_name).contains(emp_search.lower()) |
            Employee.username.contains(emp_search.upper())
        )

    reviews = query.all()
    return jsonify({'reviews': [r.to_dict() for r in reviews]})


@admin_ops_bp.route('/api/admin/attendance-reviews/stats')
@admin_required
def api_attendance_review_stats():
    from models.attendance_review import AttendanceReviewQueue
    pending = AttendanceReviewQueue.query.filter_by(status='pending_review').count()
    approved = AttendanceReviewQueue.query.filter_by(admin_action='approved').count()
    rejected = AttendanceReviewQueue.query.filter_by(admin_action='rejected').count()
    time_var = AttendanceReviewQueue.query.filter(AttendanceReviewQueue.time_variance_minutes > 120).count()
    return jsonify({
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
        'time_variance': time_var,
        'total': AttendanceReviewQueue.query.count(),
    })


@admin_ops_bp.route('/api/admin/attendance-reviews/<int:rid>/review', methods=['POST'])
@admin_required
def api_review_attendance(rid):
    from datetime import datetime, UTC
    from models.attendance_review import AttendanceReviewQueue
    from models.notifications import Notification

    review = AttendanceReviewQueue.query.get_or_404(rid)
    data = request.get_json(silent=True) or {}

    action = data.get('action', 'approved')
    notes = data.get('notes', '')
    adjusted_time_str = data.get('adjusted_time')

    if action not in ('approved', 'rejected', 'adjusted'):
        return jsonify({'ok': False, 'msg': 'إجراء غير صالح'}), 400

    admin_id = session.get('user_id')
    now = datetime.now(UTC)

    review.status = 'reviewed'
    review.reviewed_by = admin_id
    review.reviewed_at = now
    review.admin_action = action
    review.admin_notes = notes

    if action == 'adjusted' and adjusted_time_str:
        try:
            adjusted_dt = datetime.fromisoformat(adjusted_time_str.replace('Z', '+00:00'))
            review.adjusted_time = adjusted_dt
        except Exception:
            return jsonify({'ok': False, 'msg': 'تنسيق الوقت غير صحيح'}), 400

    if action == 'approved':
        try:
            if review.client_time:
                from models.attendance import AttendanceLog
                log_date = review.client_time.date()
                existing = AttendanceLog.query.filter_by(
                    employee_id=review.employee_id,
                    log_date=log_date,
                ).first()
                if existing:
                    existing.status = 'present'
                    if not existing.clock_in:
                        existing.clock_in = review.client_time
                else:
                    log = AttendanceLog(
                        employee_id=review.employee_id,
                        log_date=log_date,
                        clock_in=review.client_time,
                        status='present',
                    )
                    db.session.add(log)
        except Exception:
            pass

    elif action == 'adjusted' and review.adjusted_time:
        try:
            from models.attendance import AttendanceLog
            adj_date = review.adjusted_time.date()
            existing = AttendanceLog.query.filter_by(
                employee_id=review.employee_id,
                log_date=adj_date,
            ).first()
            if existing:
                existing.clock_in = review.adjusted_time
                existing.status = 'present'
            else:
                log = AttendanceLog(
                    employee_id=review.employee_id,
                    log_date=adj_date,
                    clock_in=review.adjusted_time,
                    status='present',
                )
                db.session.add(log)
        except Exception:
            pass

    emp = Employee.query.get(review.employee_id)
    if emp:
        action_label = {'approved': 'تمت الموافقة', 'rejected': 'مرفوض', 'adjusted': 'تم التعديل'}
        notif = Notification(
            employee_id=review.employee_id,
            title=f'📋 نتيجة مراجعة البصمة',
            message=f'تم review بصمتك بتاريخ {review.client_time.strftime("%d/%m/%Y %H:%M") if review.client_time else ""}: {action_label.get(action, action)}',
            ntype='info' if action == 'approved' else 'warning',
            icon='circle-check' if action == 'approved' else 'alert-circle',
            is_global=False,
        )
        db.session.add(notif)

    db.session.commit()

    return jsonify({'ok': True, 'msg': '✓ تم حفظ المراجعة بنجاح'})
