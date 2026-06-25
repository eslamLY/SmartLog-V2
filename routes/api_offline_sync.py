import time
import secrets
from datetime import datetime, timedelta, UTC
from flask import Blueprint, request, jsonify, current_app
from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.notifications import Notification
from models.attendance_review import AttendanceReviewQueue

api_offline_sync_bp = Blueprint('api_offline_sync', __name__)
import logging
from functools import wraps

LOGGER = logging.getLogger(__name__)
from utils.rate_limit import check_rate_limit, rate_limit_headers


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper



API_TOKENS = {}

def generate_api_token(employee_id):
    token = secrets.token_urlsafe(48)
    expiry = datetime.now(UTC) + timedelta(days=30)
    API_TOKENS[token] = {
        'employee_id': employee_id,
        'expiry': expiry,
        'created_at': datetime.now(UTC),
    }
    return token

def validate_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth[7:]
    data = API_TOKENS.get(token)
    if not data:
        return None
    if data['expiry'] and data['expiry'] < datetime.now(UTC):
        API_TOKENS.pop(token, None)
        return None
    emp = Employee.query.get(data['employee_id'])
    if not emp or not emp.is_active:
        return None
    return emp

def validate_timestamp(client_timestamp, server_time=None):
    if server_time is None:
        server_time = datetime.now(UTC)
    client_dt = datetime.fromtimestamp(client_timestamp / 1000, tz=UTC)
    diff_minutes = abs((server_time - client_dt).total_seconds() / 60)
    result = {
        'valid': True,
        'flags': [],
        'client_time': client_dt.isoformat(),
        'server_time': server_time.isoformat(),
        'time_variance_minutes': round(diff_minutes, 1),
    }
    if client_timestamp > server_time.timestamp() * 1000:
        result['flags'].append('future_time')
        result['valid'] = False
    if diff_minutes > 1440:
        result['flags'].append('extreme_time_variance')
        result['valid'] = False
    elif diff_minutes > 120:
        result['flags'].append('time_mismatch')
        result['valid'] = False
    return result

def check_off_shift(employee_id, client_timestamp):
    try:
        client_dt = datetime.fromtimestamp(client_timestamp / 1000, tz=UTC)
        client_time_minutes = client_dt.hour * 60 + client_dt.minute
        from models.shifts import ShiftSchedule, ShiftType
        schedules = ShiftSchedule.query.filter_by(
            employee_id=employee_id,
            scheduled_date=client_dt.date()
        ).all()
        for sched in schedules:
            st = sched.shift_type
            if st:
                shift_start = st.start_hour * 60 + st.start_min
                shift_end = st.end_hour * 60 + st.end_min
                if shift_end <= shift_start:
                    shift_end += 1440
                grace_before = 30
                grace_after = 60
                adjusted_start = shift_start - grace_before
                adjusted_end = shift_end + grace_after
                if adjusted_start <= client_time_minutes <= adjusted_end:
                    return None
        if schedules:
            return 'off_shift'
    except Exception:
        pass
    return None

def check_duplicate(employee_id, client_timestamp, record_type):
    try:
        client_dt = datetime.fromtimestamp(client_timestamp / 1000, tz=UTC)
        window_start = client_dt - timedelta(seconds=60)
        window_end = client_dt + timedelta(seconds=60)
        existing = AttendanceLog.query.filter(
            AttendanceLog.employee_id == employee_id,
            AttendanceLog.log_date == client_dt.date(),
            AttendanceLog.clock_in >= window_start,
            AttendanceLog.clock_in <= window_end,
        ).first()
        if existing:
            return 'possible_duplicate'
    except Exception:
        pass
    return None

@api_offline_sync_bp.route('/api/attendance/offline-sync', methods=['POST'])
@safe_api
def offline_sync():
    now = datetime.now(UTC)
    emp = validate_token()
    if not emp:
        return jsonify({
            'status': 'error',
            'message': 'رمز التحقق غير صالح أو منتهي الصلاحية',
        }), 401

    data = request.get_json(silent=True) or {}
    records = data.get('records', [])
    if not records:
        return jsonify({
            'status': 'error',
            'message': 'لا توجد سجلات للمزامنة',
        }), 400

    if len(records) > 10:
        return jsonify({
            'status': 'error',
            'message': 'لا يمكن مزامنة أكثر من 10 سجلات في كل مرة',
        }), 400

    synced_records = []
    failed_records = []
    synced_count = 0
    failed_count = 0

    for rec in records:
        local_id = rec.get('id')
        raw_employee_id = rec.get('employee_id', emp.id)
        employee_id = emp.id
        if raw_employee_id and raw_employee_id != emp.id:
            target = Employee.query.filter(
                (Employee.username == str(raw_employee_id).upper()) |
                (Employee.id == raw_employee_id)
            ).first()
            if target:
                employee_id = target.id
        record_type = rec.get('record_type', 'check_in')
        client_timestamp = rec.get('client_timestamp')
        gps_location = rec.get('gps_location')
        device_id = rec.get('device_id')
        biometric_type = rec.get('biometric_type', 'gps')
        retry_count = rec.get('retry_count', 0)

        if not client_timestamp:
            failed_records.append({
                'local_id': local_id,
                'status': 'rejected',
                'reason': 'missing_timestamp',
                'message': 'الوقت غير موجود في السجل',
            })
            failed_count += 1
            continue

        if record_type not in ('check_in', 'check_out'):
            failed_records.append({
                'local_id': local_id,
                'status': 'rejected',
                'reason': 'invalid_type',
                'message': 'نوع التسجيل غير صالح',
            })
            failed_count += 1
            continue

        validation = validate_timestamp(client_timestamp, now)
        flags = list(validation['flags'])

        off_shift_flag = check_off_shift(employee_id, client_timestamp)
        if off_shift_flag:
            flags.append(off_shift_flag)

        dup_flag = check_duplicate(employee_id, client_timestamp, record_type)
        if dup_flag:
            flags.append(dup_flag)

        if flags:
            client_dt = datetime.fromtimestamp(client_timestamp / 1000, tz=UTC)
            review = AttendanceReviewQueue(
                employee_id=employee_id,
                record_id=None,
                flagged_reason=flags[0],
                client_time=client_dt,
                server_time=now,
                time_variance_minutes=validation['time_variance_minutes'],
                department=emp.department,
                status='pending_review',
                flagged_by='system',
                flagged_at=now,
            )
            db.session.add(review)
            db.session.flush()

            notif = Notification(
                employee_id=employee_id,
                title='⚠️ بصمة بحاجة للمراجعة',
                message=f'تم تسجيل بصمة {record_type} في غير وقت المناوبة أو بفارق زمني كبير. بحاجة لمراجعة إدارية.',
                ntype='warning',
                icon='alert-triangle',
                is_global=False,
            )
            db.session.add(notif)

            admins = Employee.query.filter_by(role='admin', is_active=True).all()
            for admin in admins:
                admin_notif = Notification(
                    employee_id=admin.id,
                    title='⚠️ بصمة بحاجة للمراجعة',
                    message=f'الموظف {emp.full_name} - بصمة {record_type} {client_dt.strftime("%H:%M")} بحاجة للمراجعة ({flags[0]})',
                    ntype='warning',
                    icon='alert-triangle',
                    url='/admin/attendance-review-queue',
                    is_global=False,
                )
                db.session.add(admin_notif)

            db.session.commit()

            if 'extreme_time_variance' in flags or 'future_time' in flags:
                failed_records.append({
                    'local_id': local_id,
                    'status': 'rejected',
                    'reason': flags[0],
                    'message': 'البصمة تحتاج مراجعة يدوية - تم تحويلها للإدارة',
                })
                failed_count += 1
                continue

            synced_records.append({
                'local_id': local_id,
                'server_id': None,
                'status': 'flagged',
                'reason': flags[0],
                'message': 'تم استلام البصمة وهي بحاجة لمراجعة إدارية',
            })
            synced_count += 1
            continue

        try:
            client_dt = datetime.fromtimestamp(client_timestamp / 1000, tz=UTC)
            log_date = client_dt.date()

            if record_type == 'check_in':
                existing_log = AttendanceLog.query.filter_by(
                    employee_id=employee_id,
                    log_date=log_date,
                ).first()

                if existing_log:
                    if existing_log.clock_in:
                        synced_records.append({
                            'local_id': local_id,
                            'server_id': existing_log.id,
                            'status': 'accepted',
                            'message': 'تم تسجيل الحضور مسبقاً',
                        })
                        synced_count += 1
                        continue
                    existing_log.clock_in = client_dt
                    existing_log.status = 'present'
                    if gps_location:
                        existing_log.set_clock_in_coords(
                            gps_location.get('latitude'),
                            gps_location.get('longitude')
                        )
                    db.session.commit()
                    synced_records.append({
                        'local_id': local_id,
                        'server_id': existing_log.id,
                        'status': 'accepted',
                        'message': 'تم حفظ البصمة بنجاح',
                    })
                    synced_count += 1
                    continue

                log = AttendanceLog(
                    employee_id=employee_id,
                    log_date=log_date,
                    clock_in=client_dt,
                    status='present',
                )
                if gps_location:
                    log.set_clock_in_coords(
                        gps_location.get('latitude'),
                        gps_location.get('longitude')
                    )
                db.session.add(log)
                db.session.flush()
                synced_records.append({
                    'local_id': local_id,
                    'server_id': log.id,
                    'status': 'accepted',
                    'message': 'تم حفظ البصمة بنجاح',
                })
                synced_count += 1

            elif record_type == 'check_out':
                existing_log = AttendanceLog.query.filter_by(
                    employee_id=employee_id,
                    log_date=log_date,
                ).first()

                if not existing_log or not existing_log.clock_in:
                    log = AttendanceLog(
                        employee_id=employee_id,
                        log_date=log_date,
                        clock_in=client_dt - timedelta(hours=8),
                        clock_out=client_dt,
                        status='present',
                    )
                    if gps_location:
                        log.set_clock_out_coords(
                            gps_location.get('latitude'),
                            gps_location.get('longitude')
                        )
                    db.session.add(log)
                    db.session.flush()
                    synced_records.append({
                        'local_id': local_id,
                        'server_id': log.id,
                        'status': 'accepted',
                        'message': 'تم حفظ الانصراف بنجاح',
                    })
                    synced_count += 1
                    continue

                if existing_log.clock_out:
                    synced_records.append({
                        'local_id': local_id,
                        'server_id': existing_log.id,
                        'status': 'accepted',
                        'message': 'تم تسجيل الانصراف مسبقاً',
                    })
                    synced_count += 1
                    continue

                existing_log.clock_out = client_dt
                if gps_location:
                    existing_log.set_clock_out_coords(
                        gps_location.get('latitude'),
                        gps_location.get('longitude')
                    )
                work_hours = (client_dt - existing_log.clock_in).total_seconds() / 3600
                if work_hours >= 8:
                    existing_log.status = 'present'
                db.session.commit()
                synced_records.append({
                    'local_id': local_id,
                    'server_id': existing_log.id,
                    'status': 'accepted',
                    'message': 'تم حفظ الانصراف بنجاح',
                })
                synced_count += 1

        except Exception as e:
            db.session.rollback()
            failed_records.append({
                'local_id': local_id,
                'status': 'rejected',
                'reason': 'server_error',
                'message': 'حدث خطأ في الخادم أثناء معالجة السجل',
            })
            failed_count += 1

    db.session.commit()

    if failed_count > 0 and synced_count > 0:
        status_code = 207
        status_text = 'partial_sync'
    elif failed_count > 0:
        status_code = 200
        status_text = 'partial_sync'
    else:
        status_code = 200
        status_text = 'success'

    response = {
        'status': status_text,
        'synced_count': synced_count,
        'failed_count': failed_count,
        'synced_records': synced_records,
        'failed_records': failed_records,
        'timestamp': int(now.timestamp() * 1000),
    }

    return jsonify(response), status_code


@api_offline_sync_bp.route('/api/auth/token', methods=['POST'])
@safe_api
def issue_token():
    allowed, remaining = check_rate_limit('api_token', 5, 60)
    if not allowed:
        return jsonify({'ok': False, 'msg': 'لقد تجاوزت الحد المسموح به. حاول بعد دقيقة.'}), 429
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip().upper()
    password = data.get('password', '').strip()
    device_id = data.get('device_id', '')

    from werkzeug.security import check_password_hash

    emp = Employee.query.filter_by(username=username, is_active=True).first()
    if not emp or not check_password_hash(emp.password_hash, password):
        return jsonify({'ok': False, 'msg': 'بيانات خاطئة'}), 401

    existing_tokens = [k for k, v in API_TOKENS.items() if v['employee_id'] == emp.id]
    for t in existing_tokens:
        API_TOKENS.pop(t, None)

    token = generate_api_token(emp.id)
    resp = jsonify({
        'ok': True,
        'token': token,
        'employee_id': emp.username,
        'employee_name': emp.full_name,
        'department': emp.department,
        'redirect': '/employee',
    })
    resp.headers.update(rate_limit_headers(5, remaining, 60))
    return resp


@api_offline_sync_bp.route('/api/auth/validate-token', methods=['GET'])
@safe_api
def check_token():
    emp = validate_token()
    if not emp:
        return jsonify({'ok': False, 'msg': 'رمز غير صالح'}), 401
    return jsonify({
        'ok': True,
        'employee_id': emp.username,
        'employee_name': emp.full_name,
        'department': emp.department,
        'token_expires_in_days': 30,
    })

