import json
import logging
from datetime import datetime, UTC

from flask import Blueprint, request, jsonify, current_app
from models import db
from models.misc import GPSLog
from models.gps import GeofenceZone, GPSTrackingSession, AlertLog
from models.employee import Employee
from utils.decorators import login_required
from utils.helpers import validate_coordinates
from services.geofence_service import GeofenceService

gps_api_bp = Blueprint('gps_api_bp', __name__, url_prefix='/api/gps')
logger = logging.getLogger(__name__)


@gps_api_bp.route('/ping', methods=['POST'])
def api_gps_ping():
    """Receive a GPS location ping from a mobile device or web client."""
    body = request.get_json(silent=True)
    if not body:
        body = request.form.to_dict()

    employee_id = body.get('employee_id') or body.get('user_id')
    lat = body.get('lat') or body.get('latitude')
    lng = body.get('lng') or body.get('longitude')
    accuracy = body.get('accuracy', 0)
    battery = body.get('battery')
    source = body.get('source', 'app')
    device_id = body.get('device_id')
    speed = body.get('speed')
    heading = body.get('heading')
    altitude = body.get('altitude')

    if not employee_id or lat is None or lng is None:
        return jsonify({'ok': False, 'msg': 'employee_id, lat, lng are required'}), 400

    try:
        employee_id = int(employee_id)
        lat = float(lat)
        lng = float(lng)
        if accuracy:
            accuracy = float(accuracy)
        if battery:
            battery = float(battery)
    except (TypeError, ValueError) as e:
        return jsonify({'ok': False, 'msg': f'Invalid parameter: {str(e)}'}), 400

    if not validate_coordinates(lat, lng):
        return jsonify({'ok': False, 'msg': 'Invalid coordinates'}), 400

    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({'ok': False, 'msg': 'Employee not found'}), 404

    if not employee.is_active:
        return jsonify({'ok': False, 'msg': 'Employee is inactive'}), 403

    log = GPSLog(employee_id=employee_id, accuracy=accuracy,
                 battery=battery, source=source)
    log.set_coords(lat, lng)
    db.session.add(log)

    session_record = GPSTrackingSession.query.filter_by(
        employee_id=employee_id, is_active=True).first()
    if session_record:
        session_record.last_ping_at = datetime.now(UTC)
        session_record.total_updates = (session_record.total_updates or 0) + 1
    else:
        session_record = GPSTrackingSession(
            employee_id=employee_id,
            device_id=device_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:300],
            total_updates=1
        )
        db.session.add(session_record)

    db.session.commit()

    geofence_results = []
    try:
        service = GeofenceService()
        geofence_results = service.check_all_zones(lat, lng, accuracy)
        for result in geofence_results:
            if result.get('is_restricted') and result.get('inside'):
                pass
    except Exception as e:
        logger.error(f'Geofence check error: {e}')

    return jsonify({
        'ok': True,
        'msg': 'Location received',
        'log_id': log.id,
        'geofence': geofence_results
    })


@gps_api_bp.route('/batch', methods=['POST'])
def api_gps_batch():
    """Receive a batch of GPS location pings."""
    body = request.get_json(silent=True)
    if not body or not isinstance(body, list):
        body = (request.get_json(silent=True) or {}).get('points', [])

    if not body:
        return jsonify({'ok': False, 'msg': 'No points provided'}), 400

    results = {'received': 0, 'errors': 0, 'error_details': []}
    for point in body:
        try:
            employee_id = int(point.get('employee_id') or point.get('user_id', 0))
            lat = float(point.get('lat') or point.get('latitude', 0))
            lng = float(point.get('lng') or point.get('longitude', 0))
            accuracy = float(point.get('accuracy', 0))
            battery = point.get('battery')
            source = point.get('source', 'app')

            if not employee_id or not validate_coordinates(lat, lng):
                results['errors'] += 1
                results['error_details'].append('Invalid coordinates or employee_id')
                continue

            employee = Employee.query.get(employee_id)
            if not employee or not employee.is_active:
                results['errors'] += 1
                continue

            log = GPSLog(employee_id=employee_id, accuracy=accuracy,
                         battery=float(battery) if battery else None,
                         source=source)
            log.set_coords(lat, lng)
            db.session.add(log)
            results['received'] += 1

        except (TypeError, ValueError, KeyError) as e:
            results['errors'] += 1
            results['error_details'].append(str(e))

    db.session.commit()
    return jsonify({'ok': True, **results})


@gps_api_bp.route('/session/start', methods=['POST'])
def api_start_session():
    """Start a GPS tracking session."""
    body = request.get_json(silent=True) or {}
    employee_id = body.get('employee_id') or body.get('user_id')
    device_id = body.get('device_id')

    if not employee_id:
        return jsonify({'ok': False, 'msg': 'employee_id required'}), 400

    employee = Employee.query.get(int(employee_id))
    if not employee:
        return jsonify({'ok': False, 'msg': 'Employee not found'}), 404

    existing = GPSTrackingSession.query.filter_by(
        employee_id=employee.id, is_active=True).first()
    if existing:
        existing.last_ping_at = datetime.now(UTC)
        db.session.commit()
        return jsonify({'ok': True, 'session_id': existing.id, 'resumed': True})

    session = GPSTrackingSession(
        employee_id=employee.id,
        device_id=device_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:300]
    )
    db.session.add(session)
    db.session.commit()
    return jsonify({'ok': True, 'session_id': session.id, 'resumed': False})


@gps_api_bp.route('/session/end', methods=['POST'])
def api_end_session():
    """End a GPS tracking session."""
    body = request.get_json(silent=True) or {}
    employee_id = body.get('employee_id') or body.get('user_id')
    if not employee_id:
        return jsonify({'ok': False, 'msg': 'employee_id required'}), 400

    session = GPSTrackingSession.query.filter_by(
        employee_id=int(employee_id), is_active=True).first()
    if session:
        session.is_active = False
        session.ended_at = datetime.now(UTC)
        db.session.commit()
        return jsonify({'ok': True, 'msg': 'Session ended'})

    return jsonify({'ok': False, 'msg': 'No active session found'}), 404


@gps_api_bp.route('/zones', methods=['GET'])
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

    return jsonify({'ok': True, 'zones': data})


@gps_api_bp.route('/alerts', methods=['GET'])
def api_get_alerts():
    """Get alerts for a specific employee."""
    employee_id = request.args.get('employee_id', type=int)
    if not employee_id:
        return jsonify({'ok': False, 'msg': 'employee_id required'}), 400
    alerts = (AlertLog.query
              .filter(AlertLog.employee_id == employee_id,
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
    return jsonify({'ok': True, 'alerts': data})


@gps_api_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def api_acknowledge_alert(alert_id):
    """Acknowledge an alert from the mobile client."""
    alert = AlertLog.query.get_or_404(alert_id)
    body = request.get_json(silent=True) or {}
    alert.acknowledged_at = datetime.now(UTC)
    alert.acknowledged_by = alert.employee_id
    alert.acknowledged_by_name = body.get('acknowledged_by_name')
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'Alert acknowledged'})


@gps_api_bp.route('/health', methods=['GET'])
def api_health():
    """Health check endpoint for the GPS API."""
    return jsonify({
        'ok': True,
        'service': 'gps_tracking',
        'timestamp': datetime.now(UTC).isoformat()
    })
