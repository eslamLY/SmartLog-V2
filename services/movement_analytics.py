import json
import logging
from datetime import datetime, timedelta, date, UTC
from collections import defaultdict

from models import db
from models.gps import GeofenceEvent, AlertLog, GeofenceZone
from models.employee import Employee
from models.misc import GPSLog
from sqlalchemy import func, extract

logger = logging.getLogger(__name__)


class MovementAnalyticsService:

    def get_movement_summary(self, employee_id=None, period='week'):
        if period == 'day':
            start = datetime.now(UTC) - timedelta(days=1)
            group_fmt = '%Y-%m-%d %H:00'
        elif period == 'week':
            start = datetime.now(UTC) - timedelta(weeks=1)
            group_fmt = '%Y-%m-%d'
        elif period == 'month':
            start = datetime.now(UTC) - timedelta(days=30)
            group_fmt = '%Y-%m-%d'
        elif period == 'year':
            start = datetime.now(UTC) - timedelta(days=365)
            group_fmt = '%Y-%m'
        else:
            start = datetime.now(UTC) - timedelta(weeks=1)
            group_fmt = '%Y-%m-%d'

        query = GPSLog.query.filter(GPSLog.created_at >= start)
        if employee_id:
            query = query.filter(GPSLog.employee_id == employee_id)

        logs = query.order_by(GPSLog.created_at.asc()).all()

        total_points = len(logs)
        total_distance = 0.0
        daily_points = defaultdict(int)
        hourly_distribution = defaultdict(int)
        employee_points = defaultdict(int)
        last_pos = {}

        for log in logs:
            lat = log.decrypted_lat
            lng = log.decrypted_lng
            if lat is None or lng is None:
                continue
            day_key = log.created_at.strftime(group_fmt)
            daily_points[day_key] += 1
            hour_key = log.created_at.strftime('%H')
            hourly_distribution[hour_key] += 1
            emp_key = log.employee_id
            employee_points[emp_key] += 1
            prev = last_pos.get(log.employee_id)
            if prev:
                from utils.helpers import haversine
                dist = haversine(prev[0], prev[1], lat, lng)
                total_distance += dist
            last_pos[log.employee_id] = (lat, lng)

        sorted_daily = [{'date': k, 'count': v}
                        for k, v in sorted(daily_points.items())]
        sorted_hourly = [{'hour': k, 'count': v}
                         for k, v in sorted(hourly_distribution.items())]

        avg_points_per_day = (total_points / len(daily_points)
                              if daily_points else 0)

        employee_details = []
        for emp_id, count in sorted(employee_points.items(),
                                     key=lambda x: x[1], reverse=True)[:20]:
            emp = Employee.query.get(emp_id)
            employee_details.append({
                'employee_id': emp_id,
                'employee_name': emp.full_name if emp else '',
                'points': count,
                'percentage': round(count / total_points * 100, 1) if total_points else 0
            })

        return {
            'period': period,
            'total_points': total_points,
            'total_distance_km': round(total_distance / 1000, 2),
            'unique_employees': len(employee_points),
            'avg_points_per_day': round(avg_points_per_day, 1),
            'daily_breakdown': sorted_daily,
            'hourly_distribution': sorted_hourly,
            'employee_breakdown': employee_details
        }

    def get_system_stats(self, period='week'):
        if period == 'day':
            start = datetime.now(UTC) - timedelta(days=1)
        elif period == 'week':
            start = datetime.now(UTC) - timedelta(weeks=1)
        elif period == 'month':
            start = datetime.now(UTC) - timedelta(days=30)
        else:
            start = datetime.now(UTC) - timedelta(weeks=1)

        total_logs = GPSLog.query.filter(GPSLog.created_at >= start).count()
        unique_employees = (db.session.query(GPSLog.employee_id)
                            .filter(GPSLog.created_at >= start)
                            .distinct().count())

        avg_accuracy = (db.session.query(func.avg(GPSLog.accuracy))
                        .filter(GPSLog.created_at >= start,
                                GPSLog.accuracy.isnot(None))
                        .scalar()) or 0

        total_alerts = AlertLog.query.filter(
            AlertLog.created_at >= start).count()
        unacknowledged_alerts = AlertLog.query.filter(
            AlertLog.created_at >= start,
            AlertLog.acknowledged_at.is_(None)).count()
        critical_alerts = AlertLog.query.filter(
            AlertLog.created_at >= start,
            AlertLog.is_critical == True).count()

        zone_entries = (db.session.query(
            GeofenceZone.name, func.count(GeofenceEvent.id))
            .join(GeofenceEvent, GeofenceZone.id == GeofenceEvent.zone_id)
            .filter(GeofenceEvent.created_at >= start,
                    GeofenceEvent.event_type == 'entry')
            .group_by(GeofenceZone.name)
            .order_by(func.count(GeofenceEvent.id).desc())
            .limit(10)
            .all())

        source_counts = (db.session.query(
            GPSLog.source, func.count(GPSLog.id))
            .filter(GPSLog.created_at >= start)
            .group_by(GPSLog.source)
            .all())

        hourly_activity_raw = (db.session.query(
            extract('hour', GPSLog.created_at).label('hour'),
            func.count(GPSLog.id))
            .filter(GPSLog.created_at >= start)
            .group_by('hour')
            .order_by('hour')
            .all())

        hourly_activity = [{'hour': f'{int(h):02d}', 'count': c}
                           for h, c in hourly_activity_raw]

        return {
            'period': period,
            'total_logs': total_logs,
            'unique_employees': unique_employees,
            'avg_accuracy_m': round(float(avg_accuracy), 1),
            'total_alerts': total_alerts,
            'unacknowledged_alerts': unacknowledged_alerts,
            'critical_alerts': critical_alerts,
            'top_zones': [{'name': n, 'entries': c} for n, c in zone_entries],
            'source_breakdown': {s: c for s, c in source_counts},
            'hourly_activity': hourly_activity
        }

    def get_employee_heatmap_data(self, employee_id, start_date=None, end_date=None):
        query = GPSLog.query.filter(GPSLog.employee_id == employee_id)
        if start_date:
            query = query.filter(GPSLog.created_at >= start_date)
        if end_date:
            query = query.filter(GPSLog.created_at <= end_date +
                                 timedelta(days=1))
        logs = query.order_by(GPSLog.created_at.asc()).all()
        points = []
        for log in logs:
            lat = log.decrypted_lat
            lng = log.decrypted_lng
            if lat and lng:
                points.append({
                    'lat': lat,
                    'lng': lng,
                    'weight': 1,
                    'time': log.created_at.strftime('%H:%M'),
                    'date': log.created_at.strftime('%Y-%m-%d'),
                    'accuracy': log.accuracy,
                    'source': log.source
                })
        return points

    def get_zone_occupancy(self, zone_id, start_date=None, end_date=None):
        if not start_date:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(UTC)
        entries = (GeofenceEvent.query
                   .filter(GeofenceEvent.zone_id == zone_id,
                           GeofenceEvent.event_type == 'entry',
                           GeofenceEvent.created_at >= start_date,
                           GeofenceEvent.created_at <= end_date)
                   .order_by(GeofenceEvent.created_at.asc())
                   .all())
        exits = (GeofenceEvent.query
                 .filter(GeofenceEvent.zone_id == zone_id,
                         GeofenceEvent.event_type == 'exit',
                         GeofenceEvent.created_at >= start_date,
                         GeofenceEvent.created_at <= end_date)
                 .order_by(GeofenceEvent.created_at.asc())
                 .all())
        daily_entries = defaultdict(int)
        for e in entries:
            day_key = e.created_at.strftime('%Y-%m-%d')
            daily_entries[day_key] += 1
        daily_exits = defaultdict(int)
        for e in exits:
            day_key = e.created_at.strftime('%Y-%m-%d')
            daily_exits[day_key] += 1
        all_days = sorted(set(list(daily_entries.keys()) +
                              list(daily_exits.keys())))
        occupancy = []
        for day in all_days:
            occupancy.append({
                'date': day,
                'entries': daily_entries.get(day, 0),
                'exits': daily_exits.get(day, 0)
            })
        total_seconds = 0.0
        active_periods = []
        for e in entries:
            matching_exit = None
            for ex in exits:
                if (ex.created_at > e.created_at and
                        ex.employee_id == e.employee_id):
                    matching_exit = ex
                    break
            if matching_exit:
                duration = (matching_exit.created_at -
                            e.created_at).total_seconds()
                total_seconds += duration
                active_periods.append({
                    'employee_id': e.employee_id,
                    'entry_time': e.created_at.isoformat(),
                    'exit_time': matching_exit.created_at.isoformat(),
                    'duration_minutes': round(duration / 60, 1)
                })
        return {
            'zone_id': zone_id,
            'total_entries': len(entries),
            'total_exits': len(exits),
            'avg_duration_minutes': round(
                total_seconds / len(active_periods) / 60, 1
            ) if active_periods else 0,
            'total_duration_hours': round(total_seconds / 3600, 1),
            'daily_breakdown': occupancy,
            'active_periods': active_periods[:50]
        }

    def get_employee_ranking(self, metric='points', period='week'):
        if period == 'day':
            start = datetime.now(UTC) - timedelta(days=1)
        elif period == 'week':
            start = datetime.now(UTC) - timedelta(weeks=1)
        elif period == 'month':
            start = datetime.now(UTC) - timedelta(days=30)
        else:
            start = datetime.now(UTC) - timedelta(weeks=1)
        point_counts = (db.session.query(
            GPSLog.employee_id, func.count(GPSLog.id))
            .filter(GPSLog.created_at >= start)
            .group_by(GPSLog.employee_id)
            .all())
        ranking = []
        for emp_id, count in point_counts:
            emp = Employee.query.get(emp_id)
            if not emp:
                continue
            ranking.append({
                'employee_id': emp_id,
                'employee_name': emp.full_name,
                'department': emp.department or '',
                'points': count
            })
        ranking.sort(key=lambda x: x['points'], reverse=True)
        for i, r in enumerate(ranking, 1):
            r['rank'] = i
        return ranking[:50]
