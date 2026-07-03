import json
import logging
from datetime import datetime, UTC, date
from functools import wraps

from flask import Blueprint, request, jsonify, current_app
from models import db, Company, BiometricDevice, DeviceSyncLog, Employee, AttendanceLog
from services.company_service import set_company_context

device_api_bp = Blueprint('device_api', __name__)
log = logging.getLogger(__name__)


def authenticate_device(f):
    @wraps(f)
    def deco(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        license_key = None
        if auth_header.startswith('Bearer '):
            license_key = auth_header[7:]
        if not license_key:
            license_key = request.args.get('license_key')

        if not license_key:
            return jsonify({'ok': False, 'msg': 'Missing license_key'}), 401

        device = BiometricDevice.query.filter_by(license_key=license_key, is_active=True, deleted_at=None).first()
        if not device:
            return jsonify({'ok': False, 'msg': 'Invalid license_key'}), 401

        company = Company.query.get(device.company_id)
        if not company or not company.is_active:
            return jsonify({'ok': False, 'msg': 'Company inactive'}), 403

        kwargs['device'] = device
        kwargs['company'] = company
        return f(*args, **kwargs)
    return deco


def log_sync(company_id, device_id, event_type, status='received', payload=None, error_msg=None):
    ip = request.remote_addr or 'unknown'
    log_entry = DeviceSyncLog(
        company_id=company_id,
        device_id=device_id,
        event_type=event_type,
        direction='push',
        payload=json.dumps(payload) if payload else None,
        status=status,
        error_msg=error_msg,
        ip_address=ip,
    )
    db.session.add(log_entry)


@device_api_bp.route('/api/device/handshake', methods=['POST'])
@authenticate_device
def device_handshake(**kwargs):
    device = kwargs['device']
    company = kwargs['company']
    data = request.get_json() or {}

    device.is_online = True
    device.last_online_at = datetime.now(UTC)
    device.firmware_ver = data.get('firmware_ver', device.firmware_ver)
    device.fp_enrolled = data.get('fp_enrolled', device.fp_enrolled)
    device.face_enrolled = data.get('face_enrolled', device.face_enrolled)
    device.txlog_used = data.get('txlog_used', device.txlog_used)

    log_sync(company.id, device.id, 'handshake', status='success')

    db.session.commit()

    return jsonify({
        'ok': True,
        'server_time': datetime.now(UTC).isoformat(),
        'sync_interval': 60,
        'company_name': company.name_ar,
    })


@device_api_bp.route('/api/device/sync/data', methods=['POST'])
@authenticate_device
def device_sync_data(**kwargs):
    device = kwargs['device']
    company = kwargs['company']
    data = request.get_json() or {}

    records = data.get('records', data.get('attendance_logs', []))
    imported = 0
    errors = []

    for rec in records:
        try:
            emp_uid = rec.get('uid') or rec.get('employee_id') or rec.get('employee_code')
            punch_time_str = rec.get('timestamp') or rec.get('punch_time') or rec.get('time')
            if not emp_uid or not punch_time_str:
                errors.append({'uid': emp_uid, 'error': 'missing uid or time'})
                continue

            emp = Employee.query.filter_by(
                company_id=company.id,
                username=str(emp_uid).upper()
            ).first()

            if not emp:
                try:
                    emp = Employee.query.filter_by(
                        company_id=company.id,
                        biotime_emp_id=int(emp_uid)
                    ).first()
                except (ValueError, TypeError):
                    pass

            if not emp:
                emp = Employee.query.filter_by(
                    company_id=company.id,
                    device_id=str(emp_uid)
                ).first()

            if not emp:
                errors.append({'uid': emp_uid, 'error': 'employee not found'})
                continue

            try:
                pt = datetime.fromisoformat(punch_time_str)
            except Exception:
                try:
                    pt = datetime.strptime(punch_time_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    pt = datetime.now(UTC)

            log_date = pt.date()

            att = AttendanceLog.query.filter_by(
                employee_id=emp.id,
                company_id=company.id,
                log_date=log_date
            ).first()

            if not att:
                att = AttendanceLog(
                    employee_id=emp.id,
                    company_id=company.id,
                    device_id=device.id,
                    log_date=log_date,
                    clock_in=pt,
                    status='present',
                    is_inside_geofence=True,
                    device_serial=device.serial_no,
                )
                db.session.add(att)
                imported += 1
            elif not att.clock_in:
                att.clock_in = pt
                att.status = 'present'
                imported += 1
            elif att.clock_in and not att.clock_out and pt > att.clock_in:
                att.clock_out = pt
                att.status = 'present'
                imported += 1

        except Exception as e:
            errors.append({'uid': rec.get('uid'), 'error': str(e)})

    device.is_online = True
    device.last_online_at = datetime.now(UTC)
    device.last_sync = datetime.now(UTC)
    device.records_pulled = (device.records_pulled or 0) + imported

    log_sync(company.id, device.id, 'sync_data',
             status='partial' if errors else 'success',
             payload={'imported': imported, 'total': len(records)})

    db.session.commit()

    return jsonify({
        'ok': True,
        'imported': imported,
        'total': len(records),
        'errors': errors[:20],
    })


@device_api_bp.route('/api/device/config/download', methods=['GET'])
@authenticate_device
def device_config_download(**kwargs):
    device = kwargs['device']
    company = kwargs['company']

    log_sync(company.id, device.id, 'config_download', status='success')
    db.session.commit()

    employees = Employee.query.filter_by(
        company_id=company.id,
        deleted_at=None,
        is_active=True
    ).all()

    return jsonify({
        'ok': True,
        'config': {
            'company_name': company.name_ar,
            'server_time': datetime.now(UTC).isoformat(),
            'sync_interval': 60,
        },
        'employees': [{
            'uid': e.username,
            'name': e.full_name,
            'employee_id': e.biotime_emp_id or e.id,
        } for e in employees],
    })


@device_api_bp.route('/api/device/command/execute', methods=['POST'])
@authenticate_device
def device_command_execute(**kwargs):
    device = kwargs['device']
    company = kwargs['company']
    data = request.get_json() or {}
    command = data.get('command', '')

    valid_commands = ['restart', 'clear_logs', 'sync_now', 'update_firmware']
    if command not in valid_commands:
        return jsonify({'ok': False, 'msg': f'Unknown command: {command}'}), 400

    log_sync(company.id, device.id, f'command/{command}', status='queued',
             payload={'command': command})

    db.session.commit()

    return jsonify({
        'ok': True,
        'command': command,
        'status': 'queued',
        'message': f'Command {command} queued for device',
    })


@device_api_bp.route('/api/device/sync/status', methods=['GET'])
@authenticate_device
def device_sync_status(**kwargs):
    device = kwargs['device']
    company = kwargs['company']

    from models import DeviceSyncLog
    recent = DeviceSyncLog.query.filter_by(
        device_id=device.id
    ).order_by(DeviceSyncLog.created_at.desc()).limit(20).all()

    return jsonify({
        'ok': True,
        'device_id': device.id,
        'serial_no': device.serial_no,
        'is_online': device.is_online,
        'last_online_at': device.last_online_at.isoformat() if device.last_online_at else None,
        'last_sync': device.last_sync.isoformat() if device.last_sync else None,
        'records_pulled': device.records_pulled or 0,
        'events': [s.to_dict() for s in recent],
    })
