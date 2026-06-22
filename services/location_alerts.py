import json
import logging
from datetime import datetime, timedelta, UTC
from collections import defaultdict

from models import db
from models.gps import AlertLog, LocationAuditLog
from models.employee import Employee
from utils.helpers import haversine

logger = logging.getLogger(__name__)


class LocationAlertService:

    SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    ALERT_RETENTION_DAYS = 90
    MAX_UNACKNOWLEDGED_CRITICAL = 50

    def get_active_alerts(self, limit=100, include_acknowledged=False):
        query = AlertLog.query
        if not include_acknowledged:
            query = query.filter(
                AlertLog.acknowledged_at.is_(None),
                (AlertLog.snoozed_until.is_(None) |
                 (AlertLog.snoozed_until < datetime.now(UTC)))
            )
        return query.order_by(
            AlertLog.is_critical.desc(),
            AlertLog.created_at.desc()
        ).limit(limit).all()

    def get_alerts_by_severity(self, severity, limit=50):
        return (AlertLog.query
                .filter(AlertLog.severity == severity)
                .order_by(AlertLog.created_at.desc())
                .limit(limit)
                .all())

    def get_unacknowledged_count(self):
        return AlertLog.query.filter(
            AlertLog.acknowledged_at.is_(None),
            (AlertLog.snoozed_until.is_(None) |
             (AlertLog.snoozed_until < datetime.now(UTC)))
        ).count()

    def get_critical_unacknowledged_count(self):
        return AlertLog.query.filter(
            AlertLog.is_critical == True,
            AlertLog.acknowledged_at.is_(None),
            (AlertLog.snoozed_until.is_(None) |
             (AlertLog.snoozed_until < datetime.now(UTC)))
        ).count()

    def acknowledge_alert(self, alert_id, user_id, user_name, notes=None):
        alert = AlertLog.query.get(alert_id)
        if not alert:
            return False
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by = user_id
        alert.acknowledged_by_name = user_name
        if notes:
            alert.notes = notes
        db.session.commit()
        return True

    def acknowledge_all(self, user_id, user_name):
        now = datetime.now(UTC)
        count = (AlertLog.query
                 .filter(AlertLog.acknowledged_at.is_(None))
                 .update({
                     AlertLog.acknowledged_at: now,
                     AlertLog.acknowledged_by: user_id,
                     AlertLog.acknowledged_by_name: user_name
                 }, synchronize_session=False))
        db.session.commit()
        return count

    def snooze_alert(self, alert_id, minutes=30):
        alert = AlertLog.query.get(alert_id)
        if not alert:
            return False
        alert.snoozed_until = datetime.now(UTC) + timedelta(minutes=minutes)
        db.session.commit()
        return True

    def create_alert(self, alert_type, severity, description, employee_id=None,
                     employee_name=None, details=None, lat=None, lng=None,
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
        db.session.commit()
        return alert

    def purge_old_alerts(self, days=None):
        if days is None:
            days = self.ALERT_RETENTION_DAYS
        cutoff = datetime.now(UTC) - timedelta(days=days)
        count = AlertLog.query.filter(
            AlertLog.created_at < cutoff,
            AlertLog.acknowledged_at.isnot(None)
        ).delete(synchronize_session=False)
        db.session.commit()
        return count

    def get_alert_summary(self):
        total = AlertLog.query.count()
        unacknowledged = self.get_unacknowledged_count()
        critical = self.get_critical_unacknowledged_count()
        by_severity = {}
        for sev in ('critical', 'high', 'medium', 'low', 'info'):
            by_severity[sev] = AlertLog.query.filter(
                AlertLog.severity == sev,
                AlertLog.acknowledged_at.is_(None)
            ).count()
        by_type = {}
        type_counts = (db.session.query(
            AlertLog.alert_type, db.func.count(AlertLog.id))
            .filter(AlertLog.acknowledged_at.is_(None))
            .group_by(AlertLog.alert_type)
            .all())
        for t, c in type_counts:
            by_type[t] = c
        return {
            'total': total,
            'unacknowledged': unacknowledged,
            'critical_unacknowledged': critical,
            'by_severity': by_severity,
            'by_type': by_type
        }

    def get_alert_timeline(self, hours=24):
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        alerts = (AlertLog.query
                  .filter(AlertLog.created_at >= cutoff)
                  .order_by(AlertLog.created_at.asc())
                  .all())
        buckets = defaultdict(int)
        for a in alerts:
            key = a.created_at.strftime('%Y-%m-%d %H:00')
            buckets[key] += 1
        timeline = [{'hour': k, 'count': v} for k, v in sorted(buckets.items())]
        return timeline

    def get_employee_alert_history(self, employee_id, limit=50):
        return (AlertLog.query
                .filter(AlertLog.employee_id == employee_id)
                .order_by(AlertLog.created_at.desc())
                .limit(limit)
                .all())

    def check_proximity_alert(self, employee_id, lat, lng, proximity_radius=50):
        employee = Employee.query.get(employee_id)
        if not employee:
            return None
        recent_alerts = (AlertLog.query
                         .filter(AlertLog.employee_id == employee_id,
                                 AlertLog.alert_type == 'proximity',
                                 AlertLog.created_at >= datetime.now(UTC) - timedelta(minutes=30))
                         .count())
        if recent_alerts > 3:
            return None
        from models.gps import TrustedLocation
        trusted = TrustedLocation.query.filter_by(
            employee_id=employee_id, is_active=True).all()
        for loc in trusted:
            dist = haversine(lat, lng, loc.lat, loc.lng)
            if dist <= loc.radius + proximity_radius:
                alert = self.create_alert(
                    alert_type='proximity',
                    severity='low',
                    description=f'اقتراب الموظف {employee.full_name} من موقع موثوق {loc.name}',
                    details=json.dumps({
                        'trusted_location_id': loc.id,
                        'trusted_location_name': loc.name,
                        'distance': dist
                    }),
                    employee_id=employee_id,
                    employee_name=employee.full_name,
                    lat=lat, lng=lng
                )
                return alert
        return None
