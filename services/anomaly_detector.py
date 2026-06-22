import math, json, logging
from datetime import datetime, date, timedelta, UTC
from collections import defaultdict

from sqlalchemy import func

from models import db
from models.anomaly import AttendanceAnomaly, EmployeePattern

logger = logging.getLogger(__name__)

ANOMALY_SEVERITY_CRITICAL = 'critical'
ANOMALY_SEVERITY_WARNING = 'warning'
ANOMALY_SEVERITY_INFO = 'info'


def minutes_since_midnight(dt):
    if dt is None: return None
    return dt.hour * 60 + dt.minute


def analyze_clock_in(employee_id, log_date, clock_in_dt, device_serial, pattern):
    anomalies = []
    if not clock_in_dt or not pattern:
        return anomalies
    ci_minutes = minutes_since_midnight(clock_in_dt)
    avg_ci = pattern.avg_clock_in_minutes
    std_ci = pattern.std_clock_in_minutes
    if avg_ci is None or std_ci is None or std_ci < 5:
        return anomalies
    diff = ci_minutes - avg_ci
    z_score = diff / std_ci if std_ci > 0 else 0
    if z_score > 2:
        expected = f"{int(avg_ci)//60:02d}:{int(avg_ci)%60:02d}"
        actual = f"{clock_in_dt.hour:02d}:{clock_in_dt.minute:02d}"
        log_minutes = ci_minutes
        anomalies.append({
            'anomaly_type': 'late_clock_in',
            'severity': ANOMALY_SEVERITY_WARNING if z_score < 3 else ANOMALY_SEVERITY_CRITICAL,
            'description': f'تأخر {int(diff)} دقيقة عن المعتاد ({expected})',
            'expected_value': expected,
            'actual_value': actual,
        })
    elif z_score < -2:
        expected = f"{int(avg_ci)//60:02d}:{int(avg_ci)%60:02d}"
        actual = f"{clock_in_dt.hour:02d}:{clock_in_dt.minute:02d}"
        anomalies.append({
            'anomaly_type': 'early_clock_in',
            'severity': ANOMALY_SEVERITY_WARNING,
            'description': f'حضور مبكر {int(abs(diff))} دقيقة عن المعتاد ({expected})',
            'expected_value': expected,
            'actual_value': actual,
        })
    if device_serial and pattern.usual_device_list:
        if device_serial not in pattern.usual_device_list:
            anomalies.append({
                'anomaly_type': 'unexpected_device',
                'severity': ANOMALY_SEVERITY_CRITICAL,
                'description': f'حضور من جهاز غير معتاد: {device_serial}',
                'expected_value': ', '.join(pattern.usual_device_list),
                'actual_value': device_serial,
            })
    return anomalies


def analyze_clock_out(employee_id, log_date, clock_in_dt, clock_out_dt, pattern):
    anomalies = []
    if not clock_out_dt or not clock_in_dt or not pattern:
        return anomalies
    co_minutes = minutes_since_midnight(clock_out_dt)
    avg_co = pattern.avg_clock_out_minutes
    std_co = pattern.std_clock_out_minutes
    if avg_co is None or std_co is None or std_co < 5:
        return anomalies
    diff = co_minutes - avg_co
    z_score = diff / std_co if std_co > 0 else 0
    if z_score < -2:
        expected = f"{int(avg_co)//60:02d}:{int(avg_co)%60:02d}"
        actual = f"{clock_out_dt.hour:02d}:{clock_out_dt.minute:02d}"
        anomalies.append({
            'anomaly_type': 'early_clock_out',
            'severity': ANOMALY_SEVERITY_WARNING,
            'description': f'انصراف مبكر {int(abs(diff))} دقيقة عن المعتاد ({expected})',
            'expected_value': expected,
            'actual_value': actual,
        })
    elif z_score > 2:
        expected = f"{int(avg_co)//60:02d}:{int(avg_co)%60:02d}"
        actual = f"{clock_out_dt.hour:02d}:{clock_out_dt.minute:02d}"
        anomalies.append({
            'anomaly_type': 'late_clock_out',
            'severity': ANOMALY_SEVERITY_INFO,
            'description': f'انصراف متأخر {int(diff)} دقيقة عن المعتاد ({expected})',
            'expected_value': expected,
            'actual_value': actual,
        })
    worked_minutes = (clock_out_dt - clock_in_dt).total_seconds() / 60
    if worked_minutes < 15:
        ci_str = f"{clock_in_dt.hour:02d}:{clock_in_dt.minute:02d}"
        co_str = f"{clock_out_dt.hour:02d}:{clock_out_dt.minute:02d}"
        anomalies.append({
            'anomaly_type': 'ghost_attendance',
            'severity': ANOMALY_SEVERITY_CRITICAL,
            'description': f'فترة حضور قصيرة جداً ({int(worked_minutes)} دقائق) — بصمة دخول {ci_str} وخروج {co_str}',
            'expected_value': '> 60 دقيقة',
            'actual_value': f'{int(worked_minutes)} دقيقة',
        })
    avg_break = pattern.avg_break_minutes
    std_break = pattern.std_break_minutes
    if avg_break and std_break:
        from models import AttendanceLog
        breaks = AttendanceLog.query.filter(
            AttendanceLog.employee_id == employee_id,
            AttendanceLog.log_date == log_date,
            AttendanceLog.break_start.isnot(None),
            AttendanceLog.break_end.isnot(None),
        ).all()
        total_break = 0
        for b in breaks:
            if b.break_start and b.break_end:
                total_break += (b.break_end - b.break_start).total_seconds() / 60
        if total_break > avg_break + 2 * std_break:
            anomalies.append({
                'anomaly_type': 'long_break',
                'severity': ANOMALY_SEVERITY_WARNING,
                'description': f'استراحة طويلة ({int(total_break)} دقيقة)',
                'expected_value': f'{int(avg_break)} دقيقة',
                'actual_value': f'{int(total_break)} دقيقة',
            })
    return anomalies


def check_duplicate_punch(employee_id, clock_in_dt, device_serial):
    anomalies = []
    if not clock_in_dt:
        return anomalies
    recent = AttendanceAnomaly.query.filter(
        AttendanceAnomaly.employee_id == employee_id,
        AttendanceAnomaly.anomaly_type == 'duplicate_punch',
        AttendanceAnomaly.created_at >= clock_in_dt - timedelta(seconds=60),
    ).first()
    if recent:
        anomalies.append({
            'anomaly_type': 'duplicate_punch',
            'severity': ANOMALY_SEVERITY_WARNING,
            'description': 'بصمة مكررة خلال 60 ثانية — عطل جهاز أو محاولة تلاعب',
            'expected_value': 'مرة واحدة',
            'actual_value': 'محاولتين خلال 60 ثانية',
        })
    return anomalies


def check_off_hours_access(employee_id, clock_in_dt, pattern):
    anomalies = []
    if not clock_in_dt:
        return anomalies
    hour = clock_in_dt.hour
    if hour < 5 or hour >= 22:
        anomalies.append({
            'anomaly_type': 'off_hours_access',
            'severity': ANOMALY_SEVERITY_INFO,
            'description': f'دخول خارج ساعات العمل: {clock_in_dt.strftime("%H:%M")}',
            'expected_value': '05:00 - 22:00',
            'actual_value': clock_in_dt.strftime('%H:%M'),
        })
    return anomalies


def run_anomaly_detection_for_employee(employee_id, log_date=None):
    from models import AttendanceLog, Employee
    if log_date is None:
        log_date = date.today()
    employee = Employee.query.get(employee_id)
    if not employee:
        return []
    logs = AttendanceLog.query.filter_by(employee_id=employee_id, log_date=log_date).all()
    if not logs:
        return []
    pattern = EmployeePattern.query.filter_by(employee_id=employee_id).first()
    if not pattern or pattern.total_samples < 5:
        return []
    all_anomalies = []
    for log in logs:
        if log.clock_in:
            all_anomalies.extend(analyze_clock_in(employee_id, log_date, log.clock_in, log.device_serial, pattern))
            all_anomalies.extend(check_duplicate_punch(employee_id, log.clock_in, log.device_serial))
            all_anomalies.extend(check_off_hours_access(employee_id, log.clock_in, pattern))
        if log.clock_out:
            all_anomalies.extend(analyze_clock_out(employee_id, log_date, log.clock_in, log.clock_out, pattern))
    saved = []
    for anom in all_anomalies:
        existing = AttendanceAnomaly.query.filter_by(
            employee_id=employee_id, log_date=log_date,
            anomaly_type=anom['anomaly_type']
        ).first()
        if existing:
            continue
        a = AttendanceAnomaly(
            employee_id=employee_id,
            log_date=log_date,
            anomaly_type=anom['anomaly_type'],
            severity=anom['severity'],
            description=anom['description'],
            expected_value=anom.get('expected_value'),
            actual_value=anom.get('actual_value'),
        )
        db.session.add(a)
        db.session.flush()
        saved.append(a)
    if saved:
        db.session.commit()
    return saved


def run_anomaly_detection_for_all(log_date=None):
    from models import Employee, AttendanceLog
    if log_date is None:
        log_date = date.today()
    employees = Employee.query.filter_by(is_active=True, deleted_at=None).all()
    total_anomalies = 0
    for emp in employees:
        try:
            saved = run_anomaly_detection_for_employee(emp.id, log_date)
            total_anomalies += len(saved)
        except Exception as e:
            logger.error(f'Anomaly detection failed for employee {emp.id}: {e}')
    logger.info(f'Anomaly detection complete for {len(employees)} employees. {total_anomalies} anomalies found.')
    return total_anomalies


def generate_anomaly_report(employee_id=None, days=7):
    query = AttendanceAnomaly.query
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    cutoff = date.today() - timedelta(days=days)
    query = query.filter(AttendanceAnomaly.log_date >= cutoff)
    query = query.order_by(AttendanceAnomaly.severity.desc(), AttendanceAnomaly.created_at.desc())
    return query.all()


def update_attendance_patterns():
    from models import Employee, AttendanceLog
    employees = Employee.query.filter_by(is_active=True, deleted_at=None).all()
    thirty_days_ago = date.today() - timedelta(days=30)
    for emp in employees:
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.log_date >= thirty_days_ago,
            AttendanceLog.clock_in.isnot(None),
        ).all()
        if len(logs) < 3:
            continue
        clock_in_times = []
        clock_out_times = []
        work_durations = []
        device_ids = set()
        for log in logs:
            if log.clock_in:
                clock_in_times.append(minutes_since_midnight(log.clock_in))
            if log.clock_out:
                clock_out_times.append(minutes_since_midnight(log.clock_out))
            if log.clock_in and log.clock_out:
                dur = (log.clock_out - log.clock_in).total_seconds() / 3600
                work_durations.append(dur)
            if log.device_serial:
                device_ids.add(log.device_serial)
        if not clock_in_times:
            continue
        avg_ci = sum(clock_in_times) / len(clock_in_times)
        std_ci = math.sqrt(sum((x - avg_ci)**2 for x in clock_in_times) / len(clock_in_times)) if len(clock_in_times) > 1 else 0
        avg_co = sum(clock_out_times) / len(clock_out_times) if clock_out_times else None
        std_co = math.sqrt(sum((x - avg_co)**2 for x in clock_out_times) / len(clock_out_times)) if clock_out_times and len(clock_out_times) > 1 else 0
        avg_hours = sum(work_durations) / len(work_durations) if work_durations else None
        std_hours = math.sqrt(sum((x - avg_hours)**2 for x in work_durations) / len(work_durations)) if work_durations and len(work_durations) > 1 else 0
        pattern = EmployeePattern.query.filter_by(employee_id=emp.id).first()
        if not pattern:
            pattern = EmployeePattern(employee_id=emp.id)
            db.session.add(pattern)
        pattern.avg_clock_in_minutes = round(avg_ci, 1)
        pattern.std_clock_in_minutes = round(std_ci, 1)
        pattern.avg_clock_out_minutes = round(avg_co, 1) if avg_co else None
        pattern.std_clock_out_minutes = round(std_co, 1) if std_co else None
        pattern.avg_hours_worked = round(avg_hours, 2) if avg_hours else None
        pattern.std_hours_worked = round(std_hours, 2) if std_hours else None
        pattern.total_samples = len(logs)
        pattern.usual_device_list = list(device_ids)
        pattern.last_updated = datetime.now(UTC)
    db.session.commit()
    logger.info(f'Updated attendance patterns for {len(employees)} employees.')
