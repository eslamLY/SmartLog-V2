import json
import logging
from datetime import datetime, UTC

from models import db
from models.gps import GeofenceZone, GeofenceEvent, AlertLog
from models.employee import Employee
from utils.helpers import haversine

logger = logging.getLogger(__name__)


class GeofenceService:

    def check_all_zones(self, lat, lng, accuracy=0.0):
        results = []
        zones = GeofenceZone.query.filter_by(is_active=True).all()
        for zone in zones:
            inside, distance = zone.contains(lat, lng)
            results.append({
                'zone_id': zone.id,
                'zone_name': zone.name,
                'zone_type': zone.zone_type,
                'color': zone.color,
                'inside': inside,
                'distance': distance,
                'is_restricted': zone.is_restricted,
                'is_trusted': zone.is_trusted,
                'alert_on_entry': zone.alert_on_entry,
                'alert_on_exit': zone.alert_on_exit
            })
        return results

    def process_location_update(self, employee_id, lat, lng, accuracy=0.0, source='app'):
        zones = GeofenceZone.query.filter_by(is_active=True).all()
        events = []
        employee = Employee.query.get(employee_id)
        employee_name = employee.full_name if employee else ''
        for zone in zones:
            inside, distance = zone.contains(lat, lng)
            last_event = (GeofenceEvent.query
                          .filter(GeofenceEvent.employee_id == employee_id,
                                  GeofenceEvent.zone_id == zone.id)
                          .order_by(GeofenceEvent.created_at.desc())
                          .first())
            if inside:
                if not last_event or last_event.event_type != 'entry':
                    event = GeofenceEvent(
                        employee_id=employee_id,
                        zone_id=zone.id,
                        event_type='entry',
                        lat=lat, lng=lng, accuracy=accuracy
                    )
                    db.session.add(event)
                    events.append(event)
                    if zone.alert_on_entry:
                        self._create_alert(
                            alert_type='geofence_entry',
                            severity='info',
                            employee_id=employee_id,
                            employee_name=employee_name,
                            description=f'دخول {employee_name} إلى منطقة {zone.name}',
                            details=json.dumps({
                                'zone_id': zone.id, 'zone_name': zone.name,
                                'lat': lat, 'lng': lng, 'distance': distance
                            }),
                            lat=lat, lng=lng
                        )
            else:
                if last_event and last_event.event_type == 'entry':
                    event = GeofenceEvent(
                        employee_id=employee_id,
                        zone_id=zone.id,
                        event_type='exit',
                        lat=lat, lng=lng, accuracy=accuracy
                    )
                    db.session.add(event)
                    events.append(event)
                    if zone.alert_on_exit:
                        self._create_alert(
                            alert_type='geofence_exit',
                            severity='info',
                            employee_id=employee_id,
                            employee_name=employee_name,
                            description=f'خروج {employee_name} من منطقة {zone.name}',
                            details=json.dumps({
                                'zone_id': zone.id, 'zone_name': zone.name,
                                'lat': lat, 'lng': lng, 'distance': distance
                            }),
                            lat=lat, lng=lng
                        )
                if zone.is_restricted and (not last_event or last_event.event_type != 'restricted_alert'):
                    if last_event and last_event.event_type == 'restricted_alert':
                        continue
                    dist_text = f'على بعد {int(distance)} متر' if distance else ''
                    event = GeofenceEvent(
                        employee_id=employee_id,
                        zone_id=zone.id,
                        event_type='restricted_alert',
                        lat=lat, lng=lng, accuracy=accuracy
                    )
                    db.session.add(event)
                    events.append(event)
                    self._create_alert(
                        alert_type='restricted_area',
                        severity='critical',
                        is_critical=True,
                        employee_id=employee_id,
                        employee_name=employee_name,
                        description=f'⚠️ موظف في منطقة محظورة: {employee_name} في {zone.name} {dist_text}',
                        details=json.dumps({
                            'zone_id': zone.id, 'zone_name': zone.name,
                            'lat': lat, 'lng': lng, 'distance': distance
                        }),
                        lat=lat, lng=lng
                    )
        db.session.commit()
        return events

    def _create_alert(self, alert_type, severity, employee_id, employee_name,
                      description, details=None, lat=None, lng=None,
                      is_critical=False):
        alert = AlertLog(
            alert_type=alert_type,
            severity=severity,
            is_critical=is_critical,
            employee_id=employee_id,
            employee_name=employee_name,
            description=description,
            details=details,
            lat=lat,
            lng=lng
        )
        db.session.add(alert)
        return alert

    def get_zone_stats(self, zone_id):
        zone = GeofenceZone.query.get(zone_id)
        if not zone:
            return None
        total_entries = GeofenceEvent.query.filter_by(
            zone_id=zone_id, event_type='entry').count()
        total_exits = GeofenceEvent.query.filter_by(
            zone_id=zone_id, event_type='exit').count()
        unique_employees = (db.session.query(GeofenceEvent.employee_id)
                            .filter(GeofenceEvent.zone_id == zone_id)
                            .distinct().count())
        today = datetime.now(UTC).date()
        today_entries = GeofenceEvent.query.filter(
            GeofenceEvent.zone_id == zone_id,
            GeofenceEvent.event_type == 'entry',
            GeofenceEvent.created_at >= today
        ).count()
        return {
            'zone_id': zone.id,
            'zone_name': zone.name,
            'total_entries': total_entries,
            'total_exits': total_exits,
            'unique_employees': unique_employees,
            'today_entries': today_entries,
            'is_active': zone.is_active,
            'zone_type': zone.zone_type,
            'radius': zone.radius
        }

    def get_nearby_zones(self, lat, lng, max_distance=500):
        results = []
        zones = GeofenceZone.query.filter_by(is_active=True).all()
        for zone in zones:
            if zone.zone_type == 'circle' and zone.center_lat and zone.center_lng:
                dist = haversine(lat, lng, zone.center_lat, zone.center_lng)
                if dist <= max_distance + (zone.radius or 0):
                    results.append({
                        'zone_id': zone.id,
                        'zone_name': zone.name,
                        'distance': dist,
                        'inside': dist <= (zone.radius or 0),
                        'color': zone.color
                    })
            elif zone.zone_type in ('polygon', 'rectangle'):
                inside, dist = zone.contains(lat, lng)
                if inside or (dist is not None and dist <= max_distance):
                    results.append({
                        'zone_id': zone.id,
                        'zone_name': zone.name,
                        'distance': dist or 0,
                        'inside': inside,
                        'color': zone.color
                    })
        results.sort(key=lambda x: x['distance'])
        return results
