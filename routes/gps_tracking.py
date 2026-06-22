import json
from datetime import datetime, date, timedelta, UTC
from collections import defaultdict

from flask import Blueprint, render_template, request, session, jsonify
from sqlalchemy import func, extract

from models import db, Employee, GPSLog
from models.gps import (GeofenceZone, GeofenceEvent, AlertLog,
                         TrustedLocation, LocationAuditLog, TrackingPolicy,
                         PhotoVerification)
from utils.decorators import admin_required
from utils.helpers import safe_json, haversine
from utils.constants import MONTH_NAMES, DAY_NAMES
from services.geofence_service import GeofenceService
from services.location_alerts import LocationAlertService
from services.movement_analytics import MovementAnalyticsService

gps_bp = Blueprint('gps_bp', __name__)


@gps_bp.route('/admin/gps')
@admin_required
def gps_tracking():
    today = date.today()
    employees_raw = Employee.query.filter_by(is_active=True, role='employee').all()
    employees = [{'id': e.id, 'full_name': e.full_name, 'username': e.username,
                  'department': e.department, 'phone': e.secure_phone, 'is_active': e.is_active}
                 for e in employees_raw]
    live_logs_raw = (db.session.query(GPSLog)
                     .filter(GPSLog.created_at >= datetime.now(UTC) - timedelta(minutes=5))
                     .order_by(GPSLog.created_at.desc())
                     .all())
    live_logs = [{'id': l.id, 'employee_id': l.employee_id, 'lat': l.decrypted_lat,
                  'lng': l.decrypted_lng, 'accuracy': l.accuracy, 'battery': l.battery,
                  'source': l.source, 'created_at': l.created_at.isoformat() if l.created_at else None}
                 for l in live_logs_raw]
    recent_logs = (GPSLog.query
                   .order_by(GPSLog.created_at.desc())
                   .limit(100)
                   .all())
    geofence_zones_raw = GeofenceZone.query.filter_by(is_active=True).all()
    geofence_zones = [{'id': z.id, 'name': z.name, 'zone_type': z.zone_type,
                       'center_lat': z.center_lat, 'center_lng': z.center_lng,
                       'radius': z.radius, 'color': z.color, 'is_restricted': z.is_restricted}
                      for z in geofence_zones_raw]
    alerts = (AlertLog.query
              .order_by(AlertLog.created_at.desc())
              .limit(50)
              .all())
    zone_map = {z.id: z.name for z in geofence_zones_raw}
    return render_template('admin/gps_tracking.html',
        today=today, month_name=MONTH_NAMES[today.month-1],
        day_name=DAY_NAMES[today.weekday() % 7],
        employees=employees, live_logs=live_logs,
        recent_logs=recent_logs, geofence_zones=geofence_zones,
        alerts=alerts, zone_map=zone_map)


@gps_bp.route('/admin/geofence')
@admin_required
def geofence_management():
    zones_raw = GeofenceZone.query.order_by(GeofenceZone.created_at.desc()).all()
    zones = [{'id': z.id, 'name': z.name, 'name_en': z.name_en, 'zone_type': z.zone_type,
              'center_lat': z.center_lat, 'center_lng': z.center_lng, 'radius': z.radius,
              'color': z.color, 'address': z.address, 'purpose': z.purpose,
              'is_active': z.is_active, 'is_restricted': z.is_restricted,
              'is_trusted': z.is_trusted, 'alert_on_entry': z.alert_on_entry,
              'alert_on_exit': z.alert_on_exit,
              'coordinates': z.get_coordinates(),
              'work_hours_start': z.work_hours_start, 'work_hours_end': z.work_hours_end,
              'work_days': z.get_work_days(),
              'assigned_employee_ids': z.get_assigned_employee_ids()}
             for z in zones_raw]
    employees_raw = Employee.query.filter_by(is_active=True, role='employee').all()
    employees = [{'id': e.id, 'full_name': e.full_name, 'username': e.username,
                  'department': e.department}
                 for e in employees_raw]
    return render_template('admin/geofence_management.html',
        zones=zones, employees=employees,
        month_name=MONTH_NAMES[date.today().month-1])


@gps_bp.route('/admin/location-analytics')
@admin_required
def location_analytics():
    today = date.today()
    employees_raw = Employee.query.filter_by(is_active=True, role='employee').all()
    employees = [{'id': e.id, 'full_name': e.full_name, 'username': e.username,
                  'department': e.department}
                 for e in employees_raw]
    zones_raw = GeofenceZone.query.filter_by(is_active=True).all()
    zones = [{'id': z.id, 'name': z.name, 'zone_type': z.zone_type,
              'center_lat': z.center_lat, 'center_lng': z.center_lng,
              'radius': z.radius, 'color': z.color, 'is_restricted': z.is_restricted,
              'coordinates': z.get_coordinates()}
             for z in zones_raw]
    return render_template('admin/location_analytics.html',
        today=today, employees=employees, zones=zones,
        month_name=MONTH_NAMES[today.month-1])


@gps_bp.route('/api/admin/gps/live')
@admin_required
def api_gps_live():
    since = request.args.get('since', type=int, default=0)
    employee_id = request.args.get('employee_id', type=int)
    query = (db.session.query(GPSLog)
             .filter(GPSLog.created_at >= datetime.now(UTC) - timedelta(minutes=5)))
    if employee_id:
        query = query.filter(GPSLog.employee_id == employee_id)
    logs = query.order_by(GPSLog.created_at.desc()).all()
    data = []
    for l in logs:
        data.append({
            'id': l.id,
            'employee_id': l.employee_id,
            'employee_name': l.employee.full_name if l.employee else '',
            'lat': l.decrypted_lat,
            'lng': l.decrypted_lng,
            'accuracy': l.accuracy,
            'battery': l.battery,
            'source': l.source,
            'created_at': l.created_at.isoformat(),
            'ts': int(l.created_at.timestamp() * 1000)
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/gps/history')
@admin_required
def api_gps_history():
    employee_id = request.args.get('employee_id', type=int)
    date_str = request.args.get('date')
    if not employee_id or not date_str:
        return jsonify({'ok': False, 'msg': 'employee_id and date required'}), 400
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'ok': False, 'msg': 'Invalid date format'}), 400
    logs = (GPSLog.query
            .filter(GPSLog.employee_id == employee_id,
                    func.date(GPSLog.created_at) == dt)
            .order_by(GPSLog.created_at.asc())
            .all())
    data = []
    for l in logs:
        data.append({
            'id': l.id,
            'lat': l.decrypted_lat,
            'lng': l.decrypted_lng,
            'accuracy': l.accuracy,
            'battery': l.battery,
            'source': l.source,
            'created_at': l.created_at.isoformat()
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/geofence/zones')
@admin_required
def api_geofence_zones():
    zones = GeofenceZone.query.order_by(GeofenceZone.created_at.desc()).all()
    data = []
    for z in zones:
        assigned = z.get_assigned_employee_ids()
        assigned_names = []
        if assigned:
            emps = Employee.query.filter(Employee.id.in_(assigned)).all()
            emp_map = {e.id: e.full_name for e in emps}
            assigned_names = [emp_map.get(eid, '') for eid in assigned]
        data.append({
            'id': z.id,
            'name': z.name,
            'name_en': z.name_en,
            'zone_type': z.zone_type,
            'coordinates': z.get_coordinates(),
            'center_lat': z.center_lat,
            'center_lng': z.center_lng,
            'radius': z.radius,
            'color': z.color,
            'address': z.address,
            'purpose': z.purpose,
            'work_hours_start': z.work_hours_start,
            'work_hours_end': z.work_hours_end,
            'work_days': z.get_work_days(),
            'is_active': z.is_active,
            'is_restricted': z.is_restricted,
            'is_trusted': z.is_trusted,
            'alert_on_entry': z.alert_on_entry,
            'alert_on_exit': z.alert_on_exit,
            'assigned_employee_ids': assigned,
            'assigned_employee_names': assigned_names,
            'created_at': z.created_at.isoformat() if z.created_at else None
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/geofence/zones', methods=['POST'])
@admin_required
def api_create_geofence_zone():
    body = request.get_json(silent=True) or {}
    errors = []
    if not body.get('name'):
        errors.append('اسم المنطقة مطلوب')
    if body.get('zone_type') == 'circle':
        if body.get('center_lat') is None or body.get('center_lng') is None:
            errors.append('خط الطول والعرض مطلوبان للمنطقة الدائرية')
        if not body.get('radius') or float(body.get('radius', 0)) <= 0:
            errors.append('نصف القطر مطلوب للمنطقة الدائرية')
    if errors:
        return jsonify({'ok': False, 'msg': ' '.join(errors)}), 400
    zone = GeofenceZone()
    zone.name = body.get('name', '')
    zone.name_en = body.get('name_en', '')
    zone.zone_type = body.get('zone_type', 'circle')
    zone.center_lat = body.get('center_lat', type=float)
    zone.center_lng = body.get('center_lng', type=float)
    zone.radius = body.get('radius', type=float, default=200.0)
    zone.color = body.get('color', '#22c55e')
    zone.address = body.get('address', '')
    zone.purpose = body.get('purpose', '')
    zone.work_hours_start = body.get('work_hours_start', '08:00')
    zone.work_hours_end = body.get('work_hours_end', '17:00')
    zone.is_restricted = body.get('is_restricted', False)
    zone.is_trusted = body.get('is_trusted', False)
    zone.alert_on_entry = body.get('alert_on_entry', True)
    zone.alert_on_exit = body.get('alert_on_exit', True)
    coords = body.get('coordinates')
    if coords:
        zone.set_coordinates(coords)
    work_days = body.get('work_days')
    if work_days:
        zone.set_work_days(work_days)
    assigned = body.get('assigned_employee_ids')
    if assigned:
        zone.set_assigned_employee_ids(assigned)
    db.session.add(zone)
    db.session.commit()
    db.session.add(LocationAuditLog(
        user_id=session['user_id'],
        user_name=session.get('full_name', ''),
        action='create_geofence_zone',
        target_name=zone.name,
        details=json.dumps({'zone_id': zone.id, 'zone_type': zone.zone_type}),
        ip_address=request.remote_addr
    ))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إنشاء المنطقة الجغرافية بنجاح', 'zone_id': zone.id})


@gps_bp.route('/api/admin/geofence/zones/<int:zone_id>', methods=['PUT'])
@admin_required
def api_update_geofence_zone(zone_id):
    zone = GeofenceZone.query.get_or_404(zone_id)
    body = request.get_json(silent=True) or {}
    if 'name' in body:
        zone.name = body['name']
    if 'name_en' in body:
        zone.name_en = body.get('name_en', '')
    if 'zone_type' in body:
        zone.zone_type = body['zone_type']
    if 'center_lat' in body:
        zone.center_lat = body.get('center_lat', type=float)
    if 'center_lng' in body:
        zone.center_lng = body.get('center_lng', type=float)
    if 'radius' in body:
        zone.radius = body.get('radius', type=float)
    if 'color' in body:
        zone.color = body['color']
    if 'address' in body:
        zone.address = body['address']
    if 'purpose' in body:
        zone.purpose = body['purpose']
    if 'work_hours_start' in body:
        zone.work_hours_start = body['work_hours_start']
    if 'work_hours_end' in body:
        zone.work_hours_end = body['work_hours_end']
    if 'is_active' in body:
        zone.is_active = body['is_active']
    if 'is_restricted' in body:
        zone.is_restricted = body['is_restricted']
    if 'is_trusted' in body:
        zone.is_trusted = body['is_trusted']
    if 'alert_on_entry' in body:
        zone.alert_on_entry = body['alert_on_entry']
    if 'alert_on_exit' in body:
        zone.alert_on_exit = body['alert_on_exit']
    if 'coordinates' in body:
        zone.set_coordinates(body['coordinates'])
    if 'work_days' in body:
        zone.set_work_days(body['work_days'])
    if 'assigned_employee_ids' in body:
        zone.set_assigned_employee_ids(body['assigned_employee_ids'])
    db.session.commit()
    db.session.add(LocationAuditLog(
        user_id=session['user_id'],
        user_name=session.get('full_name', ''),
        action='update_geofence_zone',
        target_name=zone.name,
        details=json.dumps({'zone_id': zone.id}),
        ip_address=request.remote_addr
    ))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم تحديث المنطقة الجغرافية بنجاح'})


@gps_bp.route('/api/admin/geofence/zones/<int:zone_id>', methods=['DELETE'])
@admin_required
def api_delete_geofence_zone(zone_id):
    zone = GeofenceZone.query.get_or_404(zone_id)
    name = zone.name
    db.session.delete(zone)
    db.session.commit()
    db.session.add(LocationAuditLog(
        user_id=session['user_id'],
        user_name=session.get('full_name', ''),
        action='delete_geofence_zone',
        target_name=name,
        ip_address=request.remote_addr
    ))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف المنطقة الجغرافية بنجاح'})


@gps_bp.route('/api/admin/geofence/events')
@admin_required
def api_geofence_events():
    zone_id = request.args.get('zone_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    limit = request.args.get('limit', type=int, default=100)
    query = GeofenceEvent.query
    if zone_id:
        query = query.filter(GeofenceEvent.zone_id == zone_id)
    if employee_id:
        query = query.filter(GeofenceEvent.employee_id == employee_id)
    events = query.order_by(GeofenceEvent.created_at.desc()).limit(limit).all()
    data = []
    for e in events:
        data.append({
            'id': e.id,
            'employee_id': e.employee_id,
            'employee_name': e.employee.full_name if e.employee else '',
            'zone_id': e.zone_id,
            'zone_name': e.zone.name if e.zone else '',
            'event_type': e.event_type,
            'lat': e.lat,
            'lng': e.lng,
            'accuracy': e.accuracy,
            'created_at': e.created_at.isoformat() if e.created_at else None
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/alerts')
@admin_required
def api_alerts():
    alert_type = request.args.get('alert_type')
    severity = request.args.get('severity')
    limit = request.args.get('limit', type=int, default=100)
    acknowledged = request.args.get('acknowledged')
    query = AlertLog.query
    if alert_type:
        query = query.filter(AlertLog.alert_type == alert_type)
    if severity:
        query = query.filter(AlertLog.severity == severity)
    if acknowledged == 'false':
        query = query.filter(AlertLog.acknowledged_at.is_(None))
    elif acknowledged == 'true':
        query = query.filter(AlertLog.acknowledged_at.isnot(None))
    alerts = query.order_by(AlertLog.created_at.desc()).limit(limit).all()
    data = []
    for a in alerts:
        data.append({
            'id': a.id,
            'alert_type': a.alert_type,
            'severity': a.severity,
            'is_critical': a.is_critical,
            'employee_id': a.employee_id,
            'employee_name': a.employee_name,
            'description': a.description,
            'details': a.details,
            'lat': a.lat,
            'lng': a.lng,
            'acknowledged_at': a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            'acknowledged_by': a.acknowledged_by,
            'acknowledged_by_name': a.acknowledged_by_name,
            'snoozed_until': a.snoozed_until.isoformat() if a.snoozed_until else None,
            'notes': a.notes,
            'created_at': a.created_at.isoformat() if a.created_at else None
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@admin_required
def api_acknowledge_alert(alert_id):
    alert = AlertLog.query.get_or_404(alert_id)
    body = request.get_json(silent=True) or {}
    alert.acknowledged_at = datetime.now(UTC)
    alert.acknowledged_by = session['user_id']
    alert.acknowledged_by_name = session.get('full_name', '')
    alert.notes = body.get('notes', alert.notes)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم تأكيد التنبيه'})


@gps_bp.route('/api/admin/alerts/<int:alert_id>/snooze', methods=['POST'])
@admin_required
def api_snooze_alert(alert_id):
    alert = AlertLog.query.get_or_404(alert_id)
    body = request.get_json(silent=True) or {}
    minutes = body.get('minutes', 30)
    alert.snoozed_until = datetime.now(UTC) + timedelta(minutes=minutes)
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم تأجيل التنبيه لمدة {minutes} دقيقة'})


@gps_bp.route('/api/admin/analytics/movement')
@admin_required
def api_movement_analytics():
    employee_id = request.args.get('employee_id', type=int)
    period = request.args.get('period', 'week')
    service = MovementAnalyticsService()
    result = service.get_movement_summary(employee_id, period)
    return jsonify({'ok': True, 'data': result})


@gps_bp.route('/api/admin/analytics/heatmap')
@admin_required
def api_heatmap_data():
    date_str = request.args.get('date')
    employee_id = request.args.get('employee_id', type=int)
    if date_str:
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'ok': False, 'msg': 'Invalid date'}), 400
    else:
        dt = date.today()
    query = GPSLog.query.filter(func.date(GPSLog.created_at) == dt)
    if employee_id:
        query = query.filter(GPSLog.employee_id == employee_id)
    logs = query.all()
    points = []
    for l in logs:
        lat = l.decrypted_lat
        lng = l.decrypted_lng
        if lat and lng:
            points.append({
                'lat': lat,
                'lng': lng,
                'weight': 1,
                'employee_name': l.employee.full_name if l.employee else '',
                'time': l.created_at.strftime('%H:%M')
            })
    return jsonify({'ok': True, 'points': points})


@gps_bp.route('/api/admin/analytics/stats')
@admin_required
def api_analytics_stats():
    period = request.args.get('period', 'week')
    service = MovementAnalyticsService()
    stats = service.get_system_stats(period)
    return jsonify({'ok': True, 'data': stats})


@gps_bp.route('/api/admin/gps/audit-log')
@admin_required
def api_gps_audit_log():
    limit = request.args.get('limit', type=int, default=100)
    logs = (LocationAuditLog.query
            .order_by(LocationAuditLog.created_at.desc())
            .limit(limit)
            .all())
    data = []
    for l in logs:
        data.append({
            'id': l.id,
            'user_id': l.user_id,
            'user_name': l.user_name,
            'action': l.action,
            'target_employee_id': l.target_employee_id,
            'target_name': l.target_name,
            'ip_address': l.ip_address,
            'details': l.details,
            'created_at': l.created_at.isoformat() if l.created_at else None
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/gps/trusted-locations')
@admin_required
def api_trusted_locations():
    employee_id = request.args.get('employee_id', type=int)
    query = TrustedLocation.query.filter_by(is_active=True)
    if employee_id:
        query = query.filter(TrustedLocation.employee_id == employee_id)
    locations = query.all()
    data = []
    for loc in locations:
        data.append({
            'id': loc.id,
            'employee_id': loc.employee_id,
            'employee_name': loc.employee.full_name if loc.employee else '',
            'name': loc.name,
            'lat': loc.lat,
            'lng': loc.lng,
            'radius': loc.radius,
            'address': loc.address,
            'created_at': loc.created_at.isoformat() if loc.created_at else None
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/gps/trusted-locations', methods=['POST'])
@admin_required
def api_create_trusted_location():
    body = request.get_json(silent=True) or {}
    if not body.get('name') or not body.get('lat') or not body.get('lng'):
        return jsonify({'ok': False, 'msg': 'الاسم والإحداثيات مطلوبة'}), 400
    loc = TrustedLocation(
        employee_id=body.get('employee_id') or session['user_id'],
        name=body['name'],
        lat=float(body['lat']),
        lng=float(body['lng']),
        radius=float(body.get('radius', 100)),
        address=body.get('address', '')
    )
    db.session.add(loc)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إضافة الموقع الموثوق'})


@gps_bp.route('/api/admin/gps/trusted-locations/<int:loc_id>', methods=['DELETE'])
@admin_required
def api_delete_trusted_location(loc_id):
    loc = TrustedLocation.query.get_or_404(loc_id)
    db.session.delete(loc)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم حذف الموقع الموثوق'})


@gps_bp.route('/api/admin/gps/policies')
@admin_required
def api_tracking_policies():
    policies = TrackingPolicy.query.order_by(TrackingPolicy.created_at.desc()).all()
    data = []
    for p in policies:
        data.append({
            'id': p.id,
            'employee_id': p.employee_id,
            'employee_name': p.employee.full_name if p.employee else '',
            'policy_type': p.policy_type,
            'tracking_enabled': p.tracking_enabled,
            'work_hours_only': p.work_hours_only,
            'allow_opt_out': p.allow_opt_out,
            'opted_out': p.opted_out,
            'data_retention_days': p.data_retention_days,
            'notify_on_entry': p.notify_on_entry,
            'notify_on_exit': p.notify_on_exit
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/gps/policies', methods=['POST'])
@admin_required
def api_create_tracking_policy():
    body = request.get_json(silent=True) or {}
    policy = TrackingPolicy(
        employee_id=body.get('employee_id'),
        policy_type=body.get('policy_type', 'work_hours_only'),
        tracking_enabled=body.get('tracking_enabled', True),
        work_hours_only=body.get('work_hours_only', True),
        allow_opt_out=body.get('allow_opt_out', True),
        opted_out=body.get('opted_out', False),
        data_retention_days=body.get('data_retention_days', 90),
        notify_on_entry=body.get('notify_on_entry', True),
        notify_on_exit=body.get('notify_on_exit', True)
    )
    db.session.add(policy)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إنشاء سياسة التتبع'})


@gps_bp.route('/api/admin/gps/policies/<int:policy_id>', methods=['PUT'])
@admin_required
def api_update_tracking_policy(policy_id):
    policy = TrackingPolicy.query.get_or_404(policy_id)
    body = request.get_json(silent=True) or {}
    for field in ('tracking_enabled', 'work_hours_only', 'allow_opt_out',
                  'opted_out', 'notify_on_entry', 'notify_on_exit'):
        if field in body:
            setattr(policy, field, body[field])
    if 'policy_type' in body:
        policy.policy_type = body['policy_type']
    if 'data_retention_days' in body:
        policy.data_retention_days = body['data_retention_days']
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم تحديث سياسة التتبع'})


@gps_bp.route('/api/admin/gps/check-geofence', methods=['POST'])
@admin_required
def api_check_geofence():
    body = request.get_json(silent=True) or {}
    lat = body.get('lat')
    lng = body.get('lng')
    if lat is None or lng is None:
        return jsonify({'ok': False, 'msg': 'الإحداثيات مطلوبة'}), 400
    service = GeofenceService()
    results = service.check_all_zones(float(lat), float(lng))
    return jsonify({'ok': True, 'results': results})


@gps_bp.route('/api/admin/gps/photo-verifications')
@admin_required
def api_photo_verifications():
    limit = request.args.get('limit', type=int, default=50)
    pending_only = request.args.get('pending', type=bool, default=False)
    query = PhotoVerification.query
    if pending_only:
        query = query.filter(PhotoVerification.verified == False)
    photos = query.order_by(PhotoVerification.created_at.desc()).limit(limit).all()
    data = []
    for p in photos:
        data.append({
            'id': p.id,
            'employee_id': p.employee_id,
            'employee_name': p.employee.full_name if p.employee else '',
            'photo_path': p.photo_path,
            'lat': p.lat,
            'lng': p.lng,
            'accuracy': p.accuracy,
            'verified': p.verified,
            'verified_by': p.verified_by,
            'notes': p.notes,
            'created_at': p.created_at.isoformat() if p.created_at else None
        })
    return jsonify({'ok': True, 'data': data})


@gps_bp.route('/api/admin/gps/photo-verifications/<int:photo_id>/verify', methods=['POST'])
@admin_required
def api_verify_photo(photo_id):
    photo = PhotoVerification.query.get_or_404(photo_id)
    body = request.get_json(silent=True) or {}
    photo.verified = True
    photo.verified_by = session['user_id']
    photo.notes = body.get('notes', photo.notes)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم التحقق من الصورة'})


@gps_bp.route('/api/admin/gps/batch-delete', methods=['POST'])
@admin_required
def api_batch_delete_logs():
    body = request.get_json(silent=True) or {}
    ids = body.get('ids', [])
    if not ids:
        return jsonify({'ok': False, 'msg': 'لا توجد سجلات للحذف'}), 400
    count = GPSLog.query.filter(GPSLog.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    db.session.add(LocationAuditLog(
        user_id=session['user_id'],
        user_name=session.get('full_name', ''),
        action='batch_delete_gps_logs',
        details=json.dumps({'count': count, 'ids': ids}),
        ip_address=request.remote_addr
    ))
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم حذف {count} سجل'})
