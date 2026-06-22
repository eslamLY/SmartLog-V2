import json, math, re
from datetime import datetime, timedelta, date
from sqlalchemy import extract

from models import db, Employee, AttendanceLog, BrandingConfig
from utils.constants import (BLOOD_BANK_LAT, BLOOD_BANK_LNG, GEOFENCE_RADIUS_M, ALLOWED_EXTENSIONS,
                              WORK_START_HOUR, WORK_START_MINUTE, LATE_GRACE_MINUTES)
from services.payroll_service import PayrollService

def validate_password_strength(password):
    if not password or len(password) < 8:
        return False, 'كلمة المرور يجب أن تكون 8 أحرف على الأقل.'
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_upper and has_lower and has_digit):
        return False, 'كلمة المرور يجب أن تحتوي على أحرف كبيرة وصغيرة ورقم واحد على الأقل.'
    return True, ''

def validate_latitude(val):
    try: v = float(val); return -90 <= v <= 90
    except (TypeError, ValueError): return False

def validate_longitude(val):
    try: v = float(val); return -180 <= v <= 180
    except (TypeError, ValueError): return False

def validate_coordinates(lat, lng):
    return validate_latitude(lat) and validate_longitude(lng)

def validate_employee_id(val):
    if not val: return False
    s = str(val).strip()
    return s.isdigit() and 3 <= len(s) <= 10

def validate_date_iso(val):
    if not val: return False
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$', str(val)))

def validate_string_length(val, max_len=100, allow_empty=False):
    if not val and allow_empty: return True
    if not val: return False
    return len(str(val).strip()) <= max_len

_JS_ESC_TRANS = str.maketrans({'<': '\\u003c', '>': '\\u003e', '&': '\\u0026', "'": "\\u0027"})

def safe_json(obj):
    return json.dumps(obj, ensure_ascii=False).translate(_JS_ESC_TRANS)

def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return round(2 * R * math.asin(math.sqrt(a)))

def get_geofence_config():
    cfg = BrandingConfig.query.first()
    if cfg and cfg.company_lat and cfg.company_lng:
        return cfg.company_lat, cfg.company_lng, cfg.allowed_radius_meters or 200
    return BLOOD_BANK_LAT, BLOOD_BANK_LNG, GEOFENCE_RADIUS_M

def check_geofence(lat, lng):
    clat, clng, radius = get_geofence_config()
    dist = haversine(float(lat), float(lng), clat, clng)
    return dist <= radius, dist

def calc_late_minutes(ci: datetime):
    start = ci.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0)
    grace = start + timedelta(minutes=LATE_GRACE_MINUTES)
    if ci > grace:
        return int((ci - start).total_seconds() / 60)
    return 0

def monthly_deduction(emp_id, year, month):
    emp = Employee.query.get(emp_id)
    if not emp or not emp.base_salary:
        return 0.0, 0
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id == emp_id,
        extract('year',  AttendanceLog.log_date) == year,
        extract('month', AttendanceLog.log_date) == month
    ).all()
    total_late = sum(l.late_minutes for l in logs)
    return PayrollService.calculate_deduction(emp.base_salary, total_late), total_late

def work_hours_str(log):
    if log and log.clock_in and log.clock_out:
        diff = log.clock_out - log.clock_in
        h, rem = divmod(int(diff.total_seconds()), 3600)
        m = rem // 60
        return f"{h}س {m}د"
    return "—"


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def coverage_status(scheduled, min_staff):
    if scheduled == 0:    return 'empty',    '#ef4444'
    if scheduled < min_staff: return 'low',  '#f59e0b'
    return 'ok', '#22c55e'


def check_conflict(emp_id, sched_date, exclude_id=None):
    from models import ShiftSchedule, LeaveRequest, OutingRequest
    q = ShiftSchedule.query.filter_by(
        employee_id=emp_id, scheduled_date=sched_date, status='confirmed')
    if exclude_id:
        q = q.filter(ShiftSchedule.id != exclude_id)
    if q.count() > 0:
        return True
    leave = LeaveRequest.query.filter(
        LeaveRequest.employee_id == emp_id,
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= sched_date,
        db.or_(LeaveRequest.end_date.is_(None), LeaveRequest.end_date >= sched_date)
    ).first()
    if leave:
        return True
    outing = OutingRequest.query.filter_by(
        employee_id=emp_id, outing_date=sched_date, status='approved'
    ).first()
    if outing:
        return True
    return False


def calculate_mean_and_std(values):
    n = len(values)
    if n < 2:
        return 0.0, 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance)


def get_analytics_data(days_limit=30):
    from collections import defaultdict
    from models import Employee, AttendanceLog
    start_date = datetime.now() - timedelta(days=days_limit)
    logs = db.session.query(
        AttendanceLog.employee_id, Employee.full_name, Employee.department,
        AttendanceLog.clock_in, AttendanceLog.clock_out, AttendanceLog.late_minutes
    ).join(Employee, AttendanceLog.employee_id == Employee.id)\
     .filter(AttendanceLog.log_date >= start_date.date()).all()
    employee_data = defaultdict(lambda: {"late_mins": [], "early_mins": [],
                                          "weekdays": defaultdict(list),
                                          "name": "", "dept": ""})
    dept_early_mins = defaultdict(list)
    for emp_id, name, dept, clock_in, clock_out, late_min in logs:
        employee_data[emp_id]["name"] = name
        employee_data[emp_id]["dept"] = dept
        if clock_in:
            day_of_week = clock_in.weekday()
            base_time = clock_in.replace(hour=8, minute=0, second=0, microsecond=0)
            diff = (clock_in - base_time).total_seconds() / 60
            if diff > 15:
                employee_data[emp_id]["late_mins"].append(diff)
                employee_data[emp_id]["weekdays"][day_of_week].append(diff)
        if clock_out:
            end_time = clock_out.replace(hour=14, minute=0, second=0, microsecond=0)
            if clock_out < end_time:
                diff = (end_time - clock_out).total_seconds() / 60
                employee_data[emp_id]["early_mins"].append(diff)
                dept_early_mins[dept].append(diff)
    return employee_data, dept_early_mins


def to_dt(tpl):
    try:
        if isinstance(tpl, (tuple, list)) and len(tpl) == 3:
            return date(int(tpl[0]), int(tpl[1]), int(tpl[2]))
    except:
        pass
    return None
