import json, csv, io, os, re
from datetime import datetime, UTC, date
from uuid import uuid4

from flask import Blueprint, render_template, request, session, jsonify, send_file
from werkzeug.security import generate_password_hash

from models import db, BioTimeDevice, DeviceEventLog, DeviceHealthSnapshot, \
    Employee, Department, AttendanceLog, AuditLog, Branch
from utils.decorators import admin_required
from services.biotime_service import (
    test_connection, get_device_info, push_employee, restart_device,
    clear_device_logs, pull_attendance_logs, scan_network
)

admin_devices_bp = Blueprint('admin_devices', __name__)
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



DEVICE_MODELS = [
    {'value': 'zkteco_k40', 'label': 'ZKTeco K40'},
    {'value': 'zkteco_f22', 'label': 'ZKTeco F22'},
    {'value': 'zkteco_mb360', 'label': 'ZKTeco MB360'},
    {'value': 'speedface_v5', 'label': 'SpeedFace V5'},
    {'value': 'proface_x', 'label': 'ProFace X'},
    {'value': 'inbio_260', 'label': 'inBio 260'},
    {'value': 'zkteco_k30', 'label': 'ZKTeco K30'},
    {'value': 'zkteco_sf100', 'label': 'ZKTeco SF100'},
    {'value': 'custom', 'label': 'أخرى (Custom)'},
]


def _add_device_event(device_id, event_type, message=None, error_code=None):
    log = DeviceEventLog(device_id=device_id, event_type=event_type,
                         message=message, error_code=error_code)
    db.session.add(log)


def _add_health_snapshot(device):
    snap = DeviceHealthSnapshot(
        device_id=device.id,
        is_online=device.is_online,
        fp_enrolled=device.fp_enrolled or 0,
        face_enrolled=device.face_enrolled or 0,
        txlog_used=device.txlog_used or 0,
    )
    db.session.add(snap)


def _validate_mac(mac):
    return bool(re.match(r'^([0-9A-Fa-f]{2}[:]){5}[0-9A-Fa-f]{2}$', mac))


def _validate_ip(ip):
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for p in parts:
        try:
            n = int(p)
            if n < 0 or n > 255:
                return False
        except ValueError:
            return False
    return True


# ─── PAGE: DEVICES LIST ─────────────────────────────────────

@admin_devices_bp.route('/admin/devices')
@admin_required
def admin_devices():
    devices = BioTimeDevice.query.order_by(BioTimeDevice.created_at.desc()).all()
    depts = Department.query.filter_by(is_active=True).all()
    branches = Branch.query.filter_by(is_active=True).all()
    employees = Employee.query.filter_by(is_active=True, deleted_at=None).order_by(Employee.full_name).all()
    return render_template('admin/devices.html',
        devices=devices, departments=depts, branches=branches,
        employees=employees, device_models=DEVICE_MODELS)


# ─── API: GET DEVICE ─────────────────────────────────────────

@admin_devices_bp.route('/api/admin/devices/<int:did>')
@safe_api
@admin_required
def get_device_api(did):
    dev = BioTimeDevice.query.get_or_404(did)
    return jsonify({'ok': True, 'device': dev.to_dict()})


# ─── API: TEST CONNECTION ────────────────────────────────────

@admin_devices_bp.route('/admin/devices/test-connection', methods=['POST'])
@admin_required
def test_device_connection():
    d = request.get_json() or {}
    ip = d.get('ip', '').strip()
    port = int(d.get('port', 4370))
    if not ip:
        return jsonify({'ok': False, 'msg': 'عنوان IP مطلوب.'})
    result = test_connection(ip, port)
    return jsonify({
        'ok': result.get('online', False),
        'online': result.get('online', False),
        'ping_ms': result.get('ping_ms'),
        'error': result.get('error'),
        'note': result.get('note'),
    })


# ─── API: GET DEVICE INFO ────────────────────────────────────

@admin_devices_bp.route('/admin/devices/fetch-info', methods=['POST'])
@admin_required
def fetch_device_info():
    d = request.get_json() or {}
    ip = d.get('ip', '').strip()
    port = int(d.get('port', 4370))
    password = d.get('password', '')
    if not ip:
        return jsonify({'ok': False, 'msg': 'عنوان IP مطلوب.'})
    info = get_device_info(ip, port, password)
    if info.get('error'):
        return jsonify({'ok': False, 'msg': info['error']})
    return jsonify({'ok': True, 'info': info})


# ─── API: SCAN NETWORK ───────────────────────────────────────

@admin_devices_bp.route('/admin/devices/scan-network', methods=['POST'])
@admin_required
def scan_network_for_devices():
    d = request.get_json() or {}
    subnet = d.get('subnet', '192.168.1')
    import re
    if not re.match(r'^\d{1,3}(\.\d{1,3}){0,2}$', subnet):
        return jsonify({'ok': False, 'msg': 'subnet غير صالح'})
    found = scan_network(subnet)
    return jsonify({'ok': True, 'devices': found})


# ─── API: ADD DEVICE ─────────────────────────────────────────

@admin_devices_bp.route('/admin/devices/add', methods=['POST'])
@admin_required
def add_device():
    d = request.get_json() or {}
    serial = d.get('serial_no', '').strip()
    if not serial:
        return jsonify({'ok': False, 'msg': 'الرقم التسلسلي مطلوب.'})
    if BioTimeDevice.query.filter_by(serial_no=serial).first():
        return jsonify({'ok': False, 'msg': 'الجهاز موجود مسبقاً.'})
    ip = d.get('ip_address', '').strip()
    if ip and not _validate_ip(ip):
        return jsonify({'ok': False, 'msg': 'صيغة IP غير صالحة.'})
    mac = d.get('mac_address', '').strip()
    if mac and not _validate_mac(mac):
        return jsonify({'ok': False, 'msg': 'صيغة MAC غير صالحة (XX:XX:XX:XX:XX:XX).'})
    if ip:
        dup_ip = BioTimeDevice.query.filter_by(ip_address=ip, is_active=True).first()
        if dup_ip:
            return jsonify({'ok': False, 'msg': f'IP {ip} مستخدم بالفعل للجهاز {dup_ip.name}.'})
    dev = BioTimeDevice(
        serial_no=serial,
        name=d.get('name', '').strip(),
        device_type=d.get('device_type', 'biometric'),
        location=d.get('location', '').strip(),
        ip_address=ip or None,
        mac_address=mac or None,
        port=int(d.get('port', 4370)),
        comm_password=d.get('comm_password', '').strip() or None,
        protocol=d.get('protocol', 'tcp_ip'),
        device_model=d.get('device_model'),
        firmware_ver=d.get('firmware_ver', '').strip() or None,
        manufacture_date=datetime.strptime(d['manufacture_date'], '%Y-%m-%d').date() if d.get('manufacture_date') else None,
        warranty_expiry=datetime.strptime(d['warranty_expiry'], '%Y-%m-%d').date() if d.get('warranty_expiry') else None,
        fp_capacity=int(d.get('fp_capacity', 0)),
        fp_enrolled=int(d.get('fp_enrolled', 0)),
        face_capacity=int(d.get('face_capacity', 0)),
        face_enrolled=int(d.get('face_enrolled', 0)),
        card_capacity=int(d.get('card_capacity', 0)),
        card_enrolled=int(d.get('card_enrolled', 0)),
        txlog_capacity=int(d.get('txlog_capacity', 0)),
        txlog_used=int(d.get('txlog_used', 0)),
        access_mode=d.get('access_mode', 'fingerprint'),
        door_relay_enabled=d.get('door_relay_enabled', False),
        anti_passback_enabled=d.get('anti_passback_enabled', False),
        auto_sync_enabled=d.get('auto_sync_enabled', True),
        sync_interval=int(d.get('sync_interval', 5)),
        sync_window_start=d.get('sync_window_start'),
        sync_window_end=d.get('sync_window_end'),
        api_key=d.get('api_key') or uuid4().hex[:16],
    )
    assigned_depts = d.get('assigned_departments', [])
    if assigned_depts:
        dev.assigned_department_list = assigned_depts
    assigned_emps = d.get('assigned_employees', [])
    if assigned_emps:
        dev.assigned_employee_list = assigned_emps
    db.session.add(dev)
    db.session.flush()
    _add_device_event(dev.id, 'create', f'تم إضافة الجهاز {dev.name}')
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم إضافة الجهاز {dev.name}.', 'id': dev.id})


# ─── API: UPDATE DEVICE ──────────────────────────────────────

@admin_devices_bp.route('/admin/devices/<int:did>/edit', methods=['POST'])
@admin_required
def edit_device(did):
    dev = BioTimeDevice.query.get_or_404(did)
    d = request.get_json() or {}
    changed = []
    fields_map = {
        'name': 'name', 'serial_no': 'serial_no', 'device_type': 'device_type',
        'location': 'location', 'ip_address': 'ip_address', 'mac_address': 'mac_address',
        'port': 'port', 'comm_password': 'comm_password', 'protocol': 'protocol',
        'device_model': 'device_model', 'firmware_ver': 'firmware_ver',
        'fp_capacity': 'fp_capacity', 'face_capacity': 'face_capacity',
        'card_capacity': 'card_capacity', 'txlog_capacity': 'txlog_capacity',
        'access_mode': 'access_mode', 'sync_interval': 'sync_interval',
        'auto_sync_enabled': 'auto_sync_enabled',
        'door_relay_enabled': 'door_relay_enabled',
        'anti_passback_enabled': 'anti_passback_enabled',
        'sync_window_start': 'sync_window_start',
        'sync_window_end': 'sync_window_end',
    }
    for field, col in fields_map.items():
        if field in d:
            setattr(dev, col, d[field])
            changed.append(field)
    if 'manufacture_date' in d:
        dev.manufacture_date = datetime.strptime(d['manufacture_date'], '%Y-%m-%d').date() if d.get('manufacture_date') else None
        changed.append('manufacture_date')
    if 'warranty_expiry' in d:
        dev.warranty_expiry = datetime.strptime(d['warranty_expiry'], '%Y-%m-%d').date() if d.get('warranty_expiry') else None
        changed.append('warranty_expiry')
    if 'assigned_departments' in d:
        dev.assigned_department_list = d['assigned_departments']
        changed.append('assigned_departments')
    if 'assigned_employees' in d:
        dev.assigned_employee_list = d['assigned_employees']
        changed.append('assigned_employees')
    if changed:
        _add_device_event(dev.id, 'edit', f'تحديث الحقول: {", ".join(changed)}')
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم تحديث الجهاز.'})


# ─── API: TOGGLE DEVICE ──────────────────────────────────────

@admin_devices_bp.route('/admin/devices/<int:did>/toggle', methods=['POST'])
@admin_required
def toggle_device(did):
    dev = BioTimeDevice.query.get_or_404(did)
    dev.is_active = not dev.is_active
    status = 'تفعيل' if dev.is_active else 'تعطيل'
    _add_device_event(dev.id, 'toggle', f'{status} الجهاز')
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم {status} الجهاز.'})


# ─── API: DELETE DEVICE ──────────────────────────────────────

@admin_devices_bp.route('/admin/devices/<int:did>/delete', methods=['POST'])
@admin_required
def delete_device(did):
    dev = BioTimeDevice.query.get_or_404(did)
    d = request.get_json() or {}
    action = d.get('attendance_action', 'keep')
    _add_device_event(dev.id, 'delete', f'حذف الجهاز. التعامل مع سجلات الحضور: {action}')
    if action == 'delete':
        AttendanceLog.query.filter_by(device_serial=dev.serial_no).delete()
    DeviceEventLog.query.filter_by(device_id=dev.id).delete()
    DeviceHealthSnapshot.query.filter_by(device_id=dev.id).delete()
    db.session.delete(dev)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف الجهاز.'})


# ─── API: SYNC DEVICE ────────────────────────────────────────

@admin_devices_bp.route('/admin/devices/<int:did>/sync', methods=['POST'])
@admin_required
def sync_device(did):
    dev = BioTimeDevice.query.get_or_404(did)
    if not dev.ip_address:
        return jsonify({'ok': False, 'msg': 'الجهاز ليس لديه IP.'})
    conn = test_connection(dev.ip_address, dev.port or 4370)
    if not conn.get('online'):
        dev.is_online = False
        dev.last_online_at = datetime.now(UTC)
        _add_device_event(dev.id, 'sync_failed', 'فشل الاتصال بالجهاز', error_code='OFFLINE')
        _add_health_snapshot(dev)
        db.session.commit()
        return jsonify({'ok': False, 'msg': 'الجهاز غير متصل.'})
    dev.is_online = True
    dev.last_online_at = datetime.now(UTC)
    try:
        logs = pull_attendance_logs(dev.ip_address, dev.port or 4370, dev.comm_password)
        count = len(logs)
        imported = 0
        for log_entry in logs:
            emp_uid = log_entry.get('uid', log_entry.get('employee_id', ''))
            punch_time = log_entry.get('time', log_entry.get('punch_time'))
            if emp_uid and punch_time:
                emp = Employee.query.filter_by(username=str(emp_uid).upper()).first()
                if not emp:
                    try:
                        emp = Employee.query.get(int(emp_uid))
                    except (ValueError, TypeError):
                        pass
                if emp:
                    try:
                        pt = datetime.fromisoformat(punch_time) if isinstance(punch_time, str) else datetime.now(UTC)
                    except Exception:
                        pt = datetime.now(UTC)
                    log_date = pt.date()
                    att = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=log_date).first()
                    if not att:
                        att = AttendanceLog(
                            employee_id=emp.id, log_date=log_date,
                            clock_in=pt, status='present',
                            is_inside_geofence=True,
                            device_serial=dev.serial_no,
                        )
                        db.session.add(att)
                        imported += 1
        dev.records_pulled = (dev.records_pulled or 0) + imported
        dev.last_sync = datetime.now(UTC)
        _add_device_event(dev.id, 'sync_success', f'تم استيراد {imported} سجل جديد')
        _add_health_snapshot(dev)
        db.session.commit()
        return jsonify({'ok': True, 'msg': f'تمت المزامنة. {imported} سجل جديد.', 'imported': imported, 'total': count})
    except Exception as e:
        dev.is_online = False
        _add_device_event(dev.id, 'sync_failed', str(e), error_code='SYNC_ERR')
        errors = dev.sync_error_list
        errors.append({'time': datetime.now(UTC).isoformat(), 'error': str(e)})
        if len(errors) > 5:
            errors = errors[-5:]
        dev.sync_error_list = errors
        db.session.commit()
        return jsonify({'ok': False, 'msg': f'فشلت المزامنة: {str(e)}'})


# ─── API: BULK SYNC ALL DEVICES ──────────────────────────────

@admin_devices_bp.route('/admin/devices/bulk-sync', methods=['POST'])
@admin_required
def bulk_sync_devices():
    devices = BioTimeDevice.query.filter_by(is_active=True).all()
    results = []
    for dev in devices:
        if not dev.ip_address:
            results.append({'id': dev.id, 'name': dev.name, 'status': 'skipped', 'msg': 'لا يوجد IP'})
            continue
        try:
            conn = test_connection(dev.ip_address, dev.port or 4370)
            if not conn.get('online'):
                results.append({'id': dev.id, 'name': dev.name, 'status': 'failed', 'msg': 'غير متصل'})
                continue
            logs = pull_attendance_logs(dev.ip_address, dev.port or 4370, dev.comm_password)
            results.append({'id': dev.id, 'name': dev.name, 'status': 'synced', 'count': len(logs)})
            dev.last_sync = datetime.now(UTC)
        except Exception as e:
            results.append({'id': dev.id, 'name': dev.name, 'status': 'error', 'msg': str(e)})
    db.session.commit()
    return jsonify({'ok': True, 'results': results})


# ─── API: DEVICE HEALTH / STATUS ────────────────────────────

@admin_devices_bp.route('/admin/devices/<int:did>/health')
@admin_required
def device_health(did):
    dev = BioTimeDevice.query.get_or_404(did)
    snapshots = DeviceHealthSnapshot.query.filter_by(device_id=did)\
        .order_by(DeviceHealthSnapshot.created_at.desc()).limit(288).all()
    events = DeviceEventLog.query.filter_by(device_id=did)\
        .order_by(DeviceEventLog.created_at.desc()).limit(20).all()
    # Calculate uptime from snapshots
    total_snapshots = len(snapshots)
    online_snapshots = sum(1 for s in snapshots if s.is_online)
    uptime = round(online_snapshots / total_snapshots * 100, 1) if total_snapshots else 100.0
    dev.uptime_percent_24h = uptime
    db.session.commit()
    return jsonify({
        'ok': True,
        'device': dev.to_dict(),
        'uptime_24h': uptime,
        'snapshots': [{
            'time': s.created_at.isoformat(),
            'online': s.is_online,
            'ping_ms': s.ping_ms,
            'fp_enrolled': s.fp_enrolled,
            'face_enrolled': s.face_enrolled,
            'txlog_used': s.txlog_used,
        } for s in snapshots[:96]],
        'events': [{
            'id': e.id,
            'type': e.event_type,
            'message': e.message,
            'error_code': e.error_code,
            'created_at': e.created_at.isoformat() if e.created_at else None,
        } for e in events],
    })


# ─── API: RESTART DEVICE ─────────────────────────────────────

@admin_devices_bp.route('/admin/devices/<int:did>/restart', methods=['POST'])
@admin_required
def restart_device_api(did):
    dev = BioTimeDevice.query.get_or_404(did)
    if not dev.ip_address:
        return jsonify({'ok': False, 'msg': 'الجهاز ليس لديه IP.'})
    ok = restart_device(dev.ip_address, dev.port or 4370, dev.comm_password)
    if ok:
        _add_device_event(dev.id, 'restart', 'تم إعادة تشغيل الجهاز')
        db.session.commit()
        return jsonify({'ok': True, 'msg': 'تم إرسال أمر إعادة التشغيل.'})
    return jsonify({'ok': False, 'msg': 'فشل إعادة تشغيل الجهاز.'})


# ─── API: CLEAR DEVICE LOGS ──────────────────────────────────

@admin_devices_bp.route('/admin/devices/<int:did>/clear-logs', methods=['POST'])
@admin_required
def clear_device_logs_api(did):
    dev = BioTimeDevice.query.get_or_404(did)
    if not dev.ip_address:
        return jsonify({'ok': False, 'msg': 'الجهاز ليس لديه IP.'})
    ok = clear_device_logs(dev.ip_address, dev.port or 4370, dev.comm_password)
    if ok:
        _add_device_event(dev.id, 'clear_logs', 'تم مسح سجلات الجهاز')
        db.session.commit()
        return jsonify({'ok': True, 'msg': 'تم مسح سجلات الجهاز.'})
    return jsonify({'ok': False, 'msg': 'فشل مسح السجلات.'})


# ─── API: EXPORT DEVICES ─────────────────────────────────────

@admin_devices_bp.route('/admin/devices/export')
@admin_required
def export_devices():
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    import io
    wb = Workbook()
    ws = wb.active
    ws.title = "Devices"
    ws.append(["Serial No", "Name", "Type", "Location", "IP", "MAC", "Model"])
    devices = BioTimeDevice.query.all()
    for dev in devices:
        ws.append([dev.serial_no, dev.name, dev.device_type, dev.location, dev.ip_address, dev.mac_address, dev.device_model])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='devices.xlsx')

