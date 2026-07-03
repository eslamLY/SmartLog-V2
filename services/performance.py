"""
SmartLog V2 — Performance Optimization Layer
=============================================
Provides:
  1. BatchLoader — Eager-load relationship data to eliminate N+1
  2. SQL Aggregation helpers — Move counting/summing to DB
  3. CachedQuery — Simple in-memory cache with TTL per query key
  4. FastJSON — Optimized JSON serialization
  5. Query profiler — Log slow queries
"""
import json
import time
import logging
import functools
from threading import Lock
from datetime import datetime, timedelta, UTC
from collections import defaultdict, OrderedDict

from models import db
from sqlalchemy import func, text, Integer

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 1. BATCH LOADER — Eliminate N+1 queries
# ═══════════════════════════════════════════════════════════════════════════

class BatchLoader:
    """Batch-load related objects to avoid N+1 query patterns.

    Usage:
        logs = AttendanceLog.query.filter(...).all()
        # BEFORE (N+1):
        for log in logs:
            emp = Employee.query.get(log.employee_id)

        # AFTER:
        employees = BatchLoader.load_employees([l.employee_id for l in logs])
        for log in logs:
            emp = employees[log.employee_id]
    """

    @staticmethod
    def load_employees(employee_ids):
        """Load all employees by IDs in one query, return {id: employee}."""
        from models import Employee
        unique = list(set(eid for eid in employee_ids if eid))
        if not unique:
            return {}
        employees = Employee.query.filter(Employee.id.in_(unique)).all()
        return {e.id: e for e in employees}

    @staticmethod
    def load_departments(department_ids):
        """Load all departments by IDs in one query."""
        from models.department import Department
        unique = list(set(did for did in department_ids if did))
        if not unique:
            return {}
        depts = Department.query.filter(Department.id.in_(unique)).all()
        return {d.id: d for d in depts}

    @staticmethod
    def load_devices_by_serial(serials):
        """Load biometric devices by serial number."""
        from models.biometric_device import BiometricDevice
        unique = list(set(s for s in serials if s))
        if not unique:
            return {}
        devices = BiometricDevice.query.filter(BiometricDevice.serial_no.in_(unique)).all()
        return {d.serial_no: d for d in devices}

    @staticmethod
    def load_attendance_logs(employee_ids, start_date, end_date):
        """Load all attendance for given employees and date range, return {emp_id: [logs]}."""
        from models.attendance import AttendanceLog
        if not employee_ids:
            return {}
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id.in_(employee_ids),
            AttendanceLog.log_date >= start_date,
            AttendanceLog.log_date <= end_date,
        ).order_by(AttendanceLog.employee_id, AttendanceLog.log_date).all()
        by_emp = defaultdict(list)
        for log in logs:
            by_emp[log.employee_id].append(log)
        return dict(by_emp)

    @staticmethod
    def get_today_logs_by_employee():
        """Get all today's attendance logs indexed by employee_id in one query."""
        from models.attendance import AttendanceLog
        from datetime import date
        today = date.today()
        logs = AttendanceLog.query.filter(AttendanceLog.log_date == today).all()
        return {log.employee_id: log for log in logs}

    @staticmethod
    def get_active_employees_by_department():
        """Return {dept_id: [employee]} for all active employees."""
        from models import Employee
        employees = Employee.query.filter(
            Employee.is_active == True,
            Employee.deleted_at.is_(None)
        ).all()
        by_dept = defaultdict(list)
        for emp in employees:
            by_dept[emp.department_id].append(emp)
        return dict(by_dept)


# ═══════════════════════════════════════════════════════════════════════════
# 2. SQL AGGREGATION HELPERS — Push work to the database
# ═══════════════════════════════════════════════════════════════════════════

class DBAggregator:
    """Aggregate data using SQL so we don't load rows into Python memory."""

    @staticmethod
    def attendance_summary(log_date):
        """Return {present, late, absent, total} counts for a date using SQL."""
        from models.attendance import AttendanceLog
        from models import Employee
        total = Employee.query.filter(
            Employee.is_active == True,
            Employee.deleted_at.is_(None),
            Employee.role == 'employee'
        ).count()
        stats = db.session.query(
            AttendanceLog.status,
            func.count(AttendanceLog.id)
        ).filter(
            AttendanceLog.log_date == log_date
        ).group_by(AttendanceLog.status).all()
        counts = {'present': 0, 'late': 0, 'absent': 0, 'on_leave': 0}
        for status, count in stats:
            if status in counts:
                counts[status] = count
        counts['total'] = total
        counts['no_record'] = total - sum(counts.get(s, 0) for s in ('present', 'late', 'absent'))
        return counts

    @staticmethod
    def attendance_range_summary(start_date, end_date, department_id=None):
        """Get aggregated stats over a date range, optionally filtered by department."""
        from models.attendance import AttendanceLog
        from models import Employee
        query = db.session.query(
            AttendanceLog.log_date,
            AttendanceLog.status,
            func.count(AttendanceLog.id).label('count')
        ).filter(
            AttendanceLog.log_date >= start_date,
            AttendanceLog.log_date <= end_date,
        )
        if department_id:
            query = query.join(Employee, AttendanceLog.employee_id == Employee.id)
            query = query.filter(Employee.department_id == department_id)
        rows = query.group_by(AttendanceLog.log_date, AttendanceLog.status).all()
        result = {}
        for log_date, status, count in rows:
            if log_date not in result:
                result[log_date] = {'present': 0, 'late': 0, 'absent': 0}
            if status in result[log_date]:
                result[log_date][status] = count
        return result

    @staticmethod
    def late_minutes_total(employee_id, year, month):
        """Get total late minutes for an employee in a month using SQL SUM."""
        from models.attendance import AttendanceLog
        from sqlalchemy import extract
        result = db.session.query(
            func.coalesce(func.sum(AttendanceLog.late_minutes), 0)
        ).filter(
            AttendanceLog.employee_id == employee_id,
            extract('year', AttendanceLog.log_date) == year,
            extract('month', AttendanceLog.log_date) == month,
        ).scalar()
        return int(result) if result else 0

    @staticmethod
    def top_late_employees(limit=10, start_date=None, end_date=None):
        """Get employees with most late minutes in a period using SQL."""
        from models.attendance import AttendanceLog
        from models import Employee
        from datetime import date
        start = start_date or date.today().replace(day=1)
        end = end_date or date.today()
        rows = db.session.query(
            AttendanceLog.employee_id,
            func.sum(AttendanceLog.late_minutes).label('total_late')
        ).filter(
            AttendanceLog.log_date >= start,
            AttendanceLog.log_date <= end,
        ).group_by(AttendanceLog.employee_id).order_by(
            text('total_late DESC')
        ).limit(limit).all()
        emp_ids = [r[0] for r in rows]
        employees = BatchLoader.load_employees(emp_ids)
        return [{
            'employee_id': eid,
            'employee_name': employees.get(eid).full_name if employees.get(eid) else '?',
            'total_late': int(total),
        } for eid, total in rows]

    @staticmethod
    def department_attendance_pct(log_date):
        """Get attendance percentage per department using SQL."""
        from models.attendance import AttendanceLog
        from models import Employee
        from models.department import Department
        rows = db.session.query(
            Employee.department_id,
            func.count(AttendanceLog.id).label('present_count')
        ).outerjoin(
            AttendanceLog,
            db.and_(
                AttendanceLog.employee_id == Employee.id,
                AttendanceLog.log_date == log_date,
                AttendanceLog.status.in_(['present', 'late'])
            )
        ).filter(
            Employee.is_active == True,
            Employee.deleted_at.is_(None),
        ).group_by(Employee.department_id).all()
        dept_ids = [r[0] for r in rows if r[0]]
        depts = BatchLoader.load_departments(dept_ids)
        result = []
        for dept_id, present_count in rows:
            total = Employee.query.filter(
                Employee.department_id == dept_id,
                Employee.is_active == True,
                Employee.deleted_at.is_(None),
            ).count()
            dept = depts.get(dept_id) if dept_id else None
            result.append({
                'department_id': dept_id,
                'department_name': dept.name_ar if dept else '—',
                'present': present_count,
                'total': total,
                'pct': round(present_count / total * 100) if total else 0,
            })
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 3. SIMPLE IN-MEMORY CACHE (TTL-based)
# ═══════════════════════════════════════════════════════════════════════════

_cache = OrderedDict()
_cache_lock = Lock()
_CACHE_MAX_ITEMS = 200
_CACHE_DEFAULT_TTL = 60  # seconds


def cached(ttl_seconds=_CACHE_DEFAULT_TTL):
    """Decorator to cache function return values with a TTL.

    Cache key is derived from function name + stringified args/kwargs.
    Thread-safe with lock.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            key_parts = [f.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f'{k}={v}' for k, v in sorted(kwargs.items()))
            cache_key = '|'.join(key_parts)

            with _cache_lock:
                if cache_key in _cache:
                    entry = _cache[cache_key]
                    if entry['expires_at'] > datetime.now(UTC):
                        _cache.move_to_end(cache_key)
                        return entry['value']
                    del _cache[cache_key]

            value = f(*args, **kwargs)

            with _cache_lock:
                if len(_cache) >= _CACHE_MAX_ITEMS:
                    _cache.popitem(last=False)
                _cache[cache_key] = {
                    'value': value,
                    'expires_at': datetime.now(UTC) + timedelta(seconds=ttl_seconds),
                }
            return value
        return wrapper
    return decorator


def invalidate_cache(pattern=None):
    """Invalidate cache entries. If pattern is None, clear all."""
    with _cache_lock:
        if pattern is None:
            _cache.clear()
        else:
            keys = [k for k in _cache if pattern in k]
            for k in keys:
                del _cache[k]


# ═══════════════════════════════════════════════════════════════════════════
# 4. FAST JSON — Optimized serialization
# ═══════════════════════════════════════════════════════════════════════════

class FastJSON:
    """Optimized JSON encoder with pre-compiled templates for common objects."""

    _ISO_FMT = '%Y-%m-%d'
    _ISO_DT_FMT = '%Y-%m-%dT%H:%M:%S'

    @staticmethod
    def date_str(d):
        return d.isoformat() if d else None

    @staticmethod
    def time_str(dt):
        return dt.strftime('%H:%M') if dt else None

    @staticmethod
    def employee_brief(emp):
        return {
            'id': emp.id,
            'full_name': emp.full_name,
            'username': emp.username,
            'department': emp.department,
            'profile_photo': emp.profile_photo,
        }

    @staticmethod
    def attendance_log_brief(log):
        return {
            'id': log.id,
            'employee_id': log.employee_id,
            'log_date': FastJSON.date_str(log.log_date),
            'clock_in': FastJSON.time_str(log.clock_in),
            'clock_out': FastJSON.time_str(log.clock_out),
            'status': log.status or 'absent',
            'late_minutes': log.late_minutes or 0,
        }

    @staticmethod
    def attendance_log_detail(log, emp=None):
        return {
            'id': log.id,
            'employee_id': log.employee_id,
            'employee_name': emp.full_name if emp else None,
            'department': emp.department if emp else None,
            'log_date': FastJSON.date_str(log.log_date),
            'clock_in': FastJSON.time_str(log.clock_in),
            'clock_out': FastJSON.time_str(log.clock_out),
            'status': log.status or 'absent',
            'late_minutes': log.late_minutes or 0,
            'overtime_minutes': log.overtime_minutes or 0,
            'is_inside_geofence': log.is_inside_geofence,
        }

    @staticmethod
    def time_ago(dt):
        if not dt:
            return None
        delta = datetime.now(UTC) - dt
        seconds = delta.total_seconds()
        if seconds < 60: return f'{int(seconds)}ث'
        if seconds < 3600: return f'{int(seconds / 60)}د'
        if seconds < 86400: return f'{int(seconds / 3600)}س'
        return f'{int(seconds / 86400)}ي'


# ═══════════════════════════════════════════════════════════════════════════
# 5. QUERY PROFILER
# ═══════════════════════════════════════════════════════════════════════════

_SLOW_QUERY_THRESHOLD_MS = 500


class QueryProfiler:
    """Context manager to profile and log slow database queries."""

    def __init__(self, label, threshold_ms=_SLOW_QUERY_THRESHOLD_MS):
        self.label = label
        self.threshold_ms = threshold_ms
        self.start = None

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = (time.perf_counter() - self.start) * 1000
        if elapsed > self.threshold_ms:
            logger.warning('SLOW QUERY [%s]: %.0fms', self.label, elapsed)
        elif elapsed > 100:
            logger.info('QUERY [%s]: %.0fms', self.label, elapsed)


def profile_query(label=None):
    """Decorator to profile a function that does database queries."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            name = label or f.__name__
            start = time.perf_counter()
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                if elapsed > _SLOW_QUERY_THRESHOLD_MS:
                    logger.warning('SLOW [%s]: %.0fms', name, elapsed)
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════
# 6. BATCH ATTENDANCE STATS — Replace per-employee calc_attendance_stats
# ═══════════════════════════════════════════════════════════════════════════

def batch_attendance_stats(employees, start_date, end_date):
    """Calculate attendance stats for multiple employees in batch (2 queries total).

    Returns {emp_id: {present_days, absent_days, late_days, total_late_minutes, ...}}
    Replaces the N+1 pattern of calling calc_attendance_stats per employee.
    """
    from models.attendance import AttendanceLog
    from models.misc import LeaveRequest

    emp_ids = [e.id for e in employees]
    if not emp_ids:
        return {}

    # 1. Load ALL attendance logs for these employees in one query
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(emp_ids),
        AttendanceLog.log_date >= start_date,
        AttendanceLog.log_date <= end_date,
    ).order_by(AttendanceLog.employee_id, AttendanceLog.log_date).all()

    logs_by_emp = defaultdict(list)
    for log in logs:
        logs_by_emp[log.employee_id].append(log)

    # 2. Load ALL approved leaves for these employees in one query
    leaves = LeaveRequest.query.filter(
        LeaveRequest.employee_id.in_(emp_ids),
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= end_date,
        LeaveRequest.end_date >= start_date,
    ).all()

    leaves_by_emp = defaultdict(list)
    for lv in leaves:
        leaves_by_emp[lv.employee_id].append(lv)

    # 3. Pre-compute work days count (Python loop over dates, just once)
    work_days = 0
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:
            work_days += 1
        d += timedelta(days=1)

    result = {}
    for emp in employees:
        emp_logs = logs_by_emp.get(emp.id, [])
        log_map = {l.log_date: l for l in emp_logs}
        emp_leaves = leaves_by_emp.get(emp.id, [])
        leave_dates = set()
        for lv in emp_leaves:
            d = max(lv.start_date, start_date)
            ed = min(lv.end_date, end_date)
            while d <= ed:
                leave_dates.add(d)
                d += timedelta(days=1)

        present_days = absent_days = late_days = 0
        total_late_minutes = 0
        total_clock_hours = 0.0
        clock_in_times = []
        clock_out_times = []

        d = start_date
        while d <= end_date:
            log = log_map.get(d)
            is_leave = d in leave_dates
            is_weekend = d.weekday() >= 5

            if log and log.status in ('present', 'late'):
                present_days += 1
                if log.late_minutes:
                    late_days += 1
                    total_late_minutes += log.late_minutes
                if log.clock_in:
                    clock_in_times.append(log.clock_in.hour * 60 + log.clock_in.minute)
                if log.clock_out:
                    clock_out_times.append(log.clock_out.hour * 60 + log.clock_out.minute)
                if log.clock_in and log.clock_out:
                    total_clock_hours += (log.clock_out - log.clock_in).total_seconds() / 3600
            elif not is_leave and not is_weekend:
                absent_days += 1
            d += timedelta(days=1)

        avg_clock_in = None
        if clock_in_times:
            avg_min = sum(clock_in_times) // len(clock_in_times)
            avg_clock_in = f'{avg_min // 60:02d}:{avg_min % 60:02d}'
        avg_clock_out = None
        if clock_out_times:
            avg_min = sum(clock_out_times) // len(clock_out_times)
            avg_clock_out = f'{avg_min // 60:02d}:{avg_min % 60:02d}'
        late_pct = round((late_days / present_days) * 100) if present_days else 0
        attendance_pct = round((present_days / work_days) * 100) if work_days else 0

        result[emp.id] = {
            'emp_id': emp.id,
            'emp_name': emp.full_name,
            'emp_code': emp.username,
            'department': emp.department,
            'present_days': present_days,
            'absent_days': absent_days,
            'late_days': late_days,
            'leave_days': len(leave_dates),
            'total_late_minutes': total_late_minutes,
            'total_clock_hours': round(total_clock_hours, 1),
            'avg_clock_in': avg_clock_in,
            'avg_clock_out': avg_clock_out,
            'late_pct': late_pct,
            'attendance_pct': attendance_pct,
            'overall_status': 'excellent' if attendance_pct >= 95 else 'good' if attendance_pct >= 85 else 'acceptable' if attendance_pct >= 70 else 'poor',
            'work_days': work_days,
            'daily_records': [],
        }
    return result


def batch_work_days(start_date, end_date):
    """Count weekdays between two dates using arithmetic (no loop)."""
    if start_date > end_date:
        return 0
    total_days = (end_date - start_date).days + 1
    full_weeks = total_days // 7
    remainder = total_days % 7
    start_wd = start_date.weekday()
    weekdays = full_weeks * 5
    for i in range(remainder):
        if (start_wd + i) % 7 < 5:
            weekdays += 1
    return weekdays
