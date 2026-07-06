import os
import logging
from datetime import datetime, UTC
from uuid import uuid4
from functools import wraps

from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for

from models import db, BiometricDevice
from routes.company_auth import company_login_required
from services.company_service import get_current_company

company_devices_bp = Blueprint('company_devices', __name__)
log = logging.getLogger(__name__)


@company_devices_bp.route('/company/devices')
@company_login_required
def company_device_list():
    company = get_current_company()
    if not company:
        return redirect(url_for('company_auth.company_login'))
    return render_template('company/devices.html', company=company)


@company_devices_bp.route('/api/company/devices/list')
@company_login_required
def company_device_list_api():
    company = get_current_company()
    if not company:
        return jsonify({'ok': False, 'msg': 'unauthorized'}), 403

    devices = BiometricDevice.query.filter_by(
        company_id=company.id,
        deleted_at=None
    ).order_by(BiometricDevice.created_at.desc()).all()

    return jsonify({
        'ok': True,
        'devices': [dev.to_dict() for dev in devices],
    })


@company_devices_bp.route('/api/company/devices/generate-key', methods=['POST'])
@company_login_required
def company_device_generate_key():
    company = get_current_company()
    if not company:
        return jsonify({'ok': False, 'msg': 'unauthorized'}), 403

    if not company.can_add_device():
        return jsonify({'ok': False, 'msg': 'لقد تجاوزت الحد الأقصى للأجهزة في باقتك'}), 400

    data = request.get_json() or {}
    serial_no = data.get('serial_no', '').strip()
    name = data.get('name', '').strip()
    ip_address = data.get('ip_address', '').strip()

    if not serial_no or not name:
        return jsonify({'ok': False, 'msg': 'الرقم التسلسلي واسم الجهاز مطلوبان'})

    if BiometricDevice.query.filter_by(serial_no=serial_no).first():
        return jsonify({'ok': False, 'msg': 'الجهاز موجود مسبقاً'})

    license_key = uuid4().hex[:24].upper()
    api_key = uuid4().hex[:32]
    secret_key = os.urandom(32).hex()

    device = BiometricDevice(
        company_id=company.id,
        serial_no=serial_no,
        name=name,
        device_model=data.get('device_model', ''),
        location=data.get('location', ''),
        ip_address=ip_address or None,
        port=int(data.get('port', 4370)),
        license_key=license_key,
        api_key=api_key,
        secret_key=secret_key,
        is_active=True,
    )
    db.session.add(device)
    db.session.commit()

    return jsonify({
        'ok': True,
        'msg': f'تم إضافة الجهاز {name}',
        'device': device.to_dict(),
        'license_key': license_key,
        'api_key': api_key,
        'secret_key': secret_key,
    })


@company_devices_bp.route('/api/company/devices/<int:did>/regenerate-key', methods=['POST'])
@company_login_required
def company_device_regenerate_key(did):
    company = get_current_company()
    device = BiometricDevice.query.filter_by(id=did, company_id=company.id, deleted_at=None).first()
    if not device:
        return jsonify({'ok': False, 'msg': 'الجهاز غير موجود'}), 404

    device.license_key = uuid4().hex[:24].upper()
    device.api_key = uuid4().hex[:32]
    device.secret_key = os.urandom(32).hex()
    db.session.commit()

    return jsonify({
        'ok': True,
        'msg': 'تم تجديد مفاتيح الجهاز',
        'license_key': device.license_key,
        'api_key': device.api_key,
        'secret_key': device.secret_key,
    })


@company_devices_bp.route('/api/company/devices/<int:did>/toggle', methods=['POST'])
@company_login_required
def company_device_toggle(did):
    company = get_current_company()
    device = BiometricDevice.query.filter_by(id=did, company_id=company.id, deleted_at=None).first()
    if not device:
        return jsonify({'ok': False, 'msg': 'الجهاز غير موجود'}), 404
    device.is_active = not device.is_active
    db.session.commit()
    status = 'تفعيل' if device.is_active else 'تعطيل'
    return jsonify({'ok': True, 'msg': f'تم {status} الجهاز'})


@company_devices_bp.route('/api/company/devices/<int:did>/delete', methods=['POST'])
@company_login_required
def company_device_delete(did):
    company = get_current_company()
    device = BiometricDevice.query.filter_by(id=did, company_id=company.id, deleted_at=None).first()
    if not device:
        return jsonify({'ok': False, 'msg': 'الجهاز غير موجود'}), 404
    device.deleted_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف الجهاز'})


@company_devices_bp.route('/api/company/devices/sync-status')
@company_login_required
def company_device_sync_status():
    company = get_current_company()
    if not company:
        return jsonify({'ok': False, 'msg': 'unauthorized'}), 403

    from models import DeviceSyncLog
    thirty_min_ago = datetime.now(UTC) - __import__('datetime').timedelta(minutes=30)

    devices = BiometricDevice.query.filter_by(
        company_id=company.id,
        deleted_at=None
    ).all()

    result = []
    for dev in devices:
        recent_syncs = DeviceSyncLog.query.filter(
            DeviceSyncLog.device_id == dev.id,
            DeviceSyncLog.created_at >= thirty_min_ago
        ).order_by(DeviceSyncLog.created_at.desc()).limit(5).all()

        last_sync = DeviceSyncLog.query.filter_by(
            device_id=dev.id, status='success'
        ).order_by(DeviceSyncLog.created_at.desc()).first()

        result.append({
            'device_id': dev.id,
            'device_name': dev.name,
            'is_online': dev.is_online,
            'last_online_at': dev.last_online_at.isoformat() if dev.last_online_at else None,
            'last_sync': dev.last_sync.isoformat() if dev.last_sync else None,
            'records_pulled': dev.records_pulled or 0,
            'recent_events': [s.to_dict() for s in recent_syncs],
        })

    return jsonify({'ok': True, 'devices': result, 'count': len(result)})
