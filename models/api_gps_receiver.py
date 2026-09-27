import logging
from datetime import datetime, UTC

from flask import Blueprint, request, jsonify, session
from models import db
from models.misc import GPSLog
from models.gps import GeofenceZone, GPSTrackingSession, AlertLog
from models.employee import Employee
from utils.decorators import login_required
from utils.api_response import error_response, log_exception
from utils.helpers import validate_coordinates
from services.geofence_service import GeofenceService

gps_api_bp = Blueprint('gps_api_bp', __name__, url_prefix='/api/gps')
logger = logging.getLogger(__name__)

_MAX_BATCH_POINTS = 500


def _resolve_actor(body, requested_employee_id):
    """Resolve the acting employee, enforcing ownership for non-admins.

    Returns ``(employee, error_response_tuple)``.  ``employee`` is ``None``
    when an error tuple is returned.  Non-admin sessions may only act on
    their own data — this closes the IDOR that allowed anonymous or
    cross-employee GPS log injection and alert acknowledgement.
    """
    uid = session.get('user_id')
    if not uid:
        return None, error_response(code='UNAUTHORIZED', status=401)

    actor = Employee.query.get(uid)
    if not actor or not actor.is_active:
        return None, error_response('الجلسة غير صالحة. سجل دخول مجدداً.', status=401, code='UNAUTHORIZED')

    target = requested_employee_id
    if target is None or str(target) == '':
        target = uid
    else:
        try:
            target = int(target)
        except (TypeError, ValueError):
            return None, error_response('employee_id يجب أن يكون رقمًا صحيحًا.', status=400, code='VALIDATION_ERROR')

    if target != uid and session.get('role') != 'admin':
        return None, error_response('لا يمكنك الوصول إلى بيانات موظف آخر.', status=403, code='FORBIDDEN')

    target_emp = actor if target == uid else Employee.query.get(target)
    if not target_emp or not target_emp.is_active:
        return None, error_response('الموظف غير موجود أو غير نشط.', status=404, code='NOT_FOUND')

    return target_emp, None


@gps_api_bp.route('/ping', methods=['POST'])
@login_required
def api_gps_ping():
    """Receive a GPS location ping from a mobile device or web client."""
    body = request.get_json(silent=True)
    if not body:
        body = request.form.to_dict()

    lat = body.get('lat') or body.get('latitude')
    lng = body.get('lng') or body.get('longitude')
    accuracy = body.get('accuracy', 0)
    battery = body.get('battery')
    source = body.get('source', 'app')
    device_id = body.get('device_id')

    if lat is None or lng is None:
        return error_response('employee_id, lat, lng مطلوبة.', status=400, code='VALIDATION_ERROR')

    employee, err = _resolve_actor(body, body.get('employee_id') or body.get('user_id'))
    if err:
        return err

    try:
        lat = float(lat)
        lng = float(lng)
        if accuracy:
            accuracy = float(accuracy)
        if battery:
            battery = float(battery)
    except (TypeError, ValueError):
        return error_response('قيم الإحداثيات أو الدقة غير صالحة.', status=400, code='VALIDATION_ERROR')

    if not validate_coordinates(lat, lng):
        return error_response('بيانات الموقع الجغرافي غير صالحة.', status=400, code='VALIDATION_ERROR')

    try:
        log = GPSLog(employee_id=employee.id, accuracy=accuracy,
                     battery=battery, source=source)
        log.set_coords(lat, lng)
        db.session.add(log)

        session_record = GPSTrackingSession.query.filter_by(
            employee_id=employee.id, is_active=True).first()
        if session_record:
            session_record.last_ping_at = datetime.now(UTC)
            session_record.total_updates = (session_record.total_updates or 0) + 1
        else:
            session_record = GPSTrackingSession(
                employee_id=employee.id,
                device_id=device_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:300],
                total_updates=1
            )
            db.session.add(session_record)

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        log_exception('api_gps_ping', exc)
        return error_response(code='INTERNAL_ERROR', status=500)

    geofence_results = []
    try:
        service = GeofenceService()
        geofence_results = service.check_all_zones(lat, lng, accuracy)
        for result in geofence_results:
            if result.get('is_restricted') and result.get('inside'):
                pass
    except Exception as e:
        logger.error('Geofence check error: %s', e)

    return jsonify({
        'success': True,
        'ok': True,
        'msg': 'تم استلام الموقع',
        'log_id': log.id,
        'geofence': geofence_results
    })


@gps_api_bp.route('/batch', methods=['POST'])
@login_required
def api_gps_batch():
    """Receive a batch of GPS location pings."""
    raw = request.get_json(silent=True)
    if isinstance(raw, dict):
        body = raw.get('points') or []
    elif isinstance(raw, list):
        body = raw
    else:
        body = []

    if not body:
        return error_response('لم يتم إرسال أي نقاط.', status=400, code='VALIDATION_ERROR')
    if not isinstance(body, list):
        return error_response('صيغة النقاط غير صالحة.', status=400, code='VALIDATION_ERROR')
    if len(body) > _MAX_BATCH_POINTS:
        return error_response(
            f'الحد الأقصى {_MAX_BATCH_POINTS} نقطة لكل طلب.', status=400, code='VALIDATION_ERROR')

    results = {'received': 0, 'errors': 0, 'error_details': []}
    for point in body:
        try:
            if not isinstance(point, dict):
                results['errors'] += 1
                results['error_details'].append('نقطة غير صالحة')
                continue

            employee, err = _resolve_actor(point, point.get('employee_id') or point.get('user_id'))
            if err:
                results['errors'] += 1
                results['error_details'].append('غير مصرح')
                continue

            lat = float(point.get('lat') if point.get('lat') is not None else point.get('latitude'))
            lng = float(point.get('lng') if point.get('lng') is not None else point.get('longitude'))
            accuracy = float(point.get('accuracy') or 0)
            battery = point.get('battery')

            if not validate_coordinates(lat, lng):
                results['errors'] += 1
                results['error_details'].append('إحداثيات غير صالحة')
                continue

            log = GPSLog(employee_id=employee.id, accuracy=accuracy,
                         battery=float(battery) if battery else None,
                         source=point.get('source', 'app'))
            log.set_coords(lat, lng)
            db.session.add(log)
            results['received'] += 1

        except (TypeError, ValueError, KeyError):
            results['errors'] += 1
            results['error_details'].append('قيم غير صالحة')

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        log_exception('api_gps_batch', exc)
        return error_response(code='INTERNAL_ERROR', status=500)

    return jsonify({'success': True, 'ok': True, **results})


@gps_api_bp.route('/session/start', methods=['POST'])
@login_required
def api_start_session():
    """Start a GPS tracking session."""
    body = request.get_json(silent=True) or {}
    device_id = body.get('device_id')

    employee, err = _resolve_actor(body, body.get('employee_id') or body.get('user_id'))
    if err:
        return err

    try:
        existing = GPSTrackingSession.query.filter_by(
            employee_id=employee.id, is_active=True).first()
        if existing:
            existing.last_ping_at = datetime.now(UTC)
            db.session.commit()
            return jsonify({'success': True, 'ok': True, 'session_id': existing.id, 'resumed': True})

        session = GPSTrackingSession(
            employee_id=employee.id,
            device_id=device_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:300]
        )
        db.session.add(session)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        log_exception('api_start_session', exc)
        return error_response(code='INTERNAL_ERROR', status=500)

    return jsonify({'success': True, 'ok': True, 'session_id': session.id, 'resumed': False})


@gps_api_bp.route('/session/end', methods=['POST'])
@login_required
def api_end_session():
    """End a GPS tracking session."""
    body = request.get_json(silent=True) or {}

    employee, err = _resolve_actor(body, body.get('employee_id') or body.get('user_id'))
    if err:
        return err

    try:
        session = GPSTrackingSession.query.filter_by(
            employee_id=employee.id, is_active=True).first()
        if session:
            session.is_active = False
            session.ended_at = datetime.now(UTC)
            db.session.commit()
            return jsonify({'success': True, 'ok': True, 'msg': 'تم إنهاء الجلسة'})

        return error_response('لا توجد جلسة نشطة.', status=404, code='NOT_FOUND')
    except Exception as exc:
        db.session.rollback()
        log_exception('api_end_session', exc)
        return error_response(code='INTERNAL_ERROR', status=500)


@gps_api_bp.route('/zones', methods=['GET'])
@login_required
def api_get_zones():
    """Get active geofence zones for the client."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    zones = GeofenceZone.query.filter_by(is_active=True).all()
    data = []
    for z in zones:
        zone_data = {
            'id': z.id,
            'name': z.name,
            'name_en': z.name_en,
            'zone_type': z.zone_type,
            'center_lat': z.center_lat,
            'center_lng': z.center_lng,
            'radius': z.radius,
            'color': z.color,
            'is_restricted': z.is_restricted,
            'is_trusted': z.is_trusted,
            'work_hours_start': z.work_hours_start,
            'work_hours_end': z.work_hours_end,
            'work_days': z.get_work_days()
        }
        if z.zone_type in ('polygon', 'rectangle'):
            zone_data['coordinates'] = z.get_coordinates()
        if lat is not None and lng is not None:
            inside, dist = z.contains(lat, lng)
            zone_data['inside'] = inside
            zone_data['distance'] = dist
        data.append(zone_data)

    return jsonify({'success': True, 'ok': True, 'zones': data})


@gps_api_bp.route('/alerts', methods=['GET'])
@login_required
def api_get_alerts():
    """Get alerts for a specific employee."""
    employee, err = _resolve_actor({}, request.args.get('employee_id'))
    if err:
        return err
    alerts = (AlertLog.query
              .filter(AlertLog.employee_id == employee.id,
                      AlertLog.acknowledged_at.is_(None))
              .order_by(AlertLog.created_at.desc())
              .limit(20)
              .all())
    data = []
    for a in alerts:
        data.append({
            'id': a.id,
            'alert_type': a.alert_type,
            'severity': a.severity,
            'is_critical': a.is_critical,
            'description': a.description,
            'created_at': a.created_at.isoformat()
        })
    return jsonify({'success': True, 'ok': True, 'alerts': data})


@gps_api_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@login_required
def api_acknowledge_alert(alert_id):
    """Acknowledge an alert from the mobile client."""
    actor = Employee.query.get(session.get('user_id'))
    if not actor or not actor.is_active:
        return error_response('الجلسة غير صالحة. سجل دخول مجدداً.', status=401, code='UNAUTHORIZED')

    alert = AlertLog.query.get_or_404(alert_id)
    # IDOR guard: non-admins may only acknowledge their own alerts.
    if alert.employee_id != actor.id and session.get('role') != 'admin':
        return error_response('لا يمكنك الوصول إلى بيانات موظف آخر.', status=403, code='FORBIDDEN')

    body = request.get_json(silent=True) or {}
    name = body.get('acknowledged_by_name')
    try:
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by = actor.id
        alert.acknowledged_by_name = (str(name).strip()[:120] if name else actor.full_name)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        log_exception('api_acknowledge_alert', exc)
        return error_response(code='INTERNAL_ERROR', status=500)
    return jsonify({'success': True, 'ok': True, 'msg': 'تم تأكيد التنبيه'})


@gps_api_bp.route('/health', methods=['GET'])
def api_health():
    """Health check endpoint for the GPS API."""
    return jsonify({
        'success': True,
        'ok': True,
        'service': 'gps_tracking',
        'timestamp': datetime.now(UTC).isoformat()
    })
