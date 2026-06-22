import json, io, calendar, math, hashlib
from datetime import datetime, date, timedelta, UTC
from collections import defaultdict, Counter

from flask import Blueprint, request, jsonify, render_template, session, send_file
from sqlalchemy import func, extract, case, and_
from sqlalchemy.orm import joinedload

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.misc import LeaveRequest
from models.shifts import ShiftType, ShiftSchedule
from models.department import Department
from utils.decorators import admin_required

reports_attendance_bp = Blueprint('reports_attendance', __name__, url_prefix='/admin/reports/attendance')

MONTH_NAMES = ['', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
               'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
DAY_NAMES = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']

def get_date_range(year, month, preset=None, start_date=None, end_date=None):
    today = date.today()
    if preset == 'current_month':
        return date(today.year, today.month, 1), today
    if preset == 'last_7':
        return today - timedelta(days=7), today
    if preset == 'last_30':
        return today - timedelta(days=30), today
    if start_date and end_date:
        try:
            sd = datetime.strptime(start_date, '%Y-%m-%d').date()
            ed = datetime.strptime(end_date, '%Y-%m-%d').date()
            return sd, ed
        except:
            pass
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return first, date(year, month, last_day)

def get_work_days(start, end):
    count = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count

def get_expected_hours(start, end):
    return get_work_days(start, end) * 8

def get_employee_query(filters):
    query = Employee.query.filter(Employee.is_active == True)
    if filters.get('department_id'):
        query = query.filter(Employee.department_id == filters['department_id'])
    if filters.get('employee_ids'):
        query = query.filter(Employee.id.in_(filters['employee_ids']))
    if filters.get('new_employees'):
        thirty_days_ago = date.today() - timedelta(days=30)
        query = query.filter(Employee.hire_date >= thirty_days_ago)
    if filters.get('employment_type'):
        query = query.filter(Employee.employment_type == filters['employment_type'])
    return query.order_by(Employee.full_name).all()

def calc_attendance_stats(employee, start, end, status_filters=None):
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id == employee.id,
        AttendanceLog.log_date >= start,
        AttendanceLog.log_date <= end,
    ).order_by(AttendanceLog.log_date).all()

    log_map = {l.log_date: l for l in logs}
    total_days = (end - start).days + 1
    work_days = get_work_days(start, end)
    present_days = 0
    late_days = 0
    absent_days = 0
    leave_days = 0
    total_late_minutes = 0
    total_work_hours = 0.0
    total_clock_hours = 0.0
    daily_records = []
    clock_in_times = []
    clock_out_times = []
    anomaly_flags = []

    leaves = LeaveRequest.query.filter(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= end,
        LeaveRequest.end_date >= start,
    ).all()
    leave_dates = set()
    for lv in leaves:
        d = max(lv.start_date, start)
        ed = min(lv.end_date, end)
        while d <= ed:
            leave_dates.add(d)
            d += timedelta(days=1)

    d = start
    while d <= end:
        log = log_map.get(d)
        is_leave = d in leave_dates
        is_weekend = d.weekday() >= 5
        status = 'absent'
        clock_in_time = None
        clock_out_time = None
        late_mins = 0
        work_hours = 0.0
        note = ''

        if log:
            status = log.status or 'present'
            clock_in_time = log.clock_in
            clock_out_time = log.clock_out
            late_mins = log.late_minutes or 0
            if clock_in_time and clock_out_time:
                work_hours = (clock_out_time - clock_in_time).total_seconds() / 3600
            elif clock_in_time:
                work_hours = 0
            if status == 'present' or status == 'late':
                if late_mins > 0:
                    present_days += 1
                    late_days += 1
                    total_late_minutes += late_mins
                else:
                    present_days += 1
            elif status == 'late':
                present_days += 1
                late_days += 1
                total_late_minutes += late_mins
            if clock_in_time:
                clock_in_times.append(clock_in_time.hour * 60 + clock_in_time.minute)
            if clock_out_time:
                clock_out_times.append(clock_out_time.hour * 60 + clock_out_time.minute)
            total_clock_hours += work_hours
        elif is_leave:
            status = 'leave'
            leave_days += 1
        elif is_weekend:
            status = 'off'
        else:
            absent_days += 1

        if d.weekday() < 5:
            total_work_hours += 8

        if status_filters and status not in status_filters:
            d += timedelta(days=1)
            continue

        daily_records.append({
            'date': d.isoformat(),
            'day_name': DAY_NAMES[d.weekday()],
            'day': d.day,
            'is_weekend': is_weekend,
            'status': status,
            'clock_in': clock_in_time.strftime('%H:%M') if clock_in_time else None,
            'clock_out': clock_out_time.strftime('%H:%M') if clock_out_time else None,
            'late_minutes': late_mins,
            'work_hours': round(work_hours, 1),
            'note': note,
        })
        d += timedelta(days=1)

    present_excluding_absent = max(work_days - absent_days, 0)
    attendance_pct = round((present_days / work_days * 100), 1) if work_days > 0 else 0
    punctuality_score = 0
    if late_days > 0 and present_days > 0:
        punctuality_score = max(0, 100 - (total_late_minutes / present_days / 5))
    elif present_days > 0:
        punctuality_score = 100
    consistency = 100 - min(100, absent_days * 10)
    overall_score = (attendance_pct / 100) * 4 + (punctuality_score / 100) * 1
    overall_rating = min(5, round(overall_score, 1))

    avg_clock_in = None
    avg_clock_out = None
    if clock_in_times:
        avg_min = int(sum(clock_in_times) / len(clock_in_times))
        avg_clock_in = f'{avg_min // 60:02d}:{avg_min % 60:02d}'
    if clock_out_times:
        avg_min = int(sum(clock_out_times) / len(clock_out_times))
        avg_clock_out = f'{avg_min // 60:02d}:{avg_min % 60:02d}'

    return {
        'employee_id': employee.id,
        'employee_username': employee.username,
        'employee_name': employee.full_name,
        'department': employee.department,
        'department_id': employee.department_id,
        'total_work_days': work_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'leave_days': leave_days,
        'total_late_minutes': total_late_minutes,
        'total_work_hours': total_work_hours,
        'total_clock_hours': round(total_clock_hours, 1),
        'attendance_pct': attendance_pct,
        'punctuality_score': round(punctuality_score, 1),
        'consistency': consistency,
        'overall_rating': overall_rating,
        'avg_clock_in': avg_clock_in,
        'avg_clock_out': avg_clock_out,
        'daily_records': daily_records,
        'anomaly_flags': anomaly_flags,
    }

@reports_attendance_bp.route('')
@admin_required
def reports_page():
    today = date.today()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar).all()
    shifts = ShiftType.query.filter_by(is_active=True).all()
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.full_name).all()
    months = [{'value': i, 'label': f'{i:02d}', 'selected': i == today.month} for i in range(1, 13)]
    years = list(range(today.year - 2, today.year + 3))
    return render_template('admin/reports_attendance.html',
        departments=departments,
        shifts=shifts,
        employees=employees,
        months=months,
        years=years,
        now=today,
    )

@reports_attendance_bp.route('/api/filters')
@admin_required
def api_filters():
    departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar).all()
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.full_name).all()
    shifts = ShiftType.query.filter_by(is_active=True).all()
    return jsonify({
        'departments': [{'id': d.id, 'name': d.name_ar or d.name_en} for d in departments],
        'employees': [{'id': e.id, 'name': e.full_name, 'username': e.username, 'department': e.department} for e in employees],
        'shifts': [{'id': s.id, 'name': s.name} for s in shifts],
        'months': [{'value': i, 'label': f'{i:02d}'} for i in range(1, 13)],
        'years': list(range(date.today().year - 2, date.today().year + 3)),
        'employment_types': ['full_time', 'part_time', 'contractor', 'intern'],
    })

@reports_attendance_bp.route('/api/summary')
@admin_required
def api_summary():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    preset = request.args.get('preset')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    status_filter = request.args.getlist('status[]')

    start, end = get_date_range(year, month, preset, start_str, end_str)
    work_days = get_work_days(start, end)
    expected_hours = work_days * 8

    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    if employee_id:
        filters['employee_ids'] = [employee_id]
    employees = get_employee_query(filters)

    total_employees = len(employees)
    total_present = 0
    total_absent = 0
    total_late = 0
    total_late_minutes = 0
    total_work_hours = 0.0
    total_clock_hours = 0.0
    regular_count = 0
    needs_followup_count = 0
    all_clock_in = []
    all_clock_out = []
    dept_stats = defaultdict(lambda: {'present': 0, 'absent': 0, 'late': 0, 'count': 0})

    employee_results = []
    for emp in employees:
        stats = calc_attendance_stats(emp, start, end)
        employee_results.append(stats)
        total_present += stats['present_days']
        total_absent += stats['absent_days']
        total_late += stats['late_days']
        total_late_minutes += stats['total_late_minutes']
        total_clock_hours += stats['total_clock_hours']
        total_work_hours += stats['total_work_hours']
        if stats['absent_days'] == 0 and stats['late_days'] <= 2:
            regular_count += 1
        if stats['absent_days'] >= 3 or stats['late_days'] >= 5:
            needs_followup_count += 1
        if stats['avg_clock_in']:
            parts = stats['avg_clock_in'].split(':')
            all_clock_in.append(int(parts[0]) * 60 + int(parts[1]))
        if stats['avg_clock_out']:
            parts = stats['avg_clock_out'].split(':')
            all_clock_out.append(int(parts[0]) * 60 + int(parts[1]))
        dept = stats['department'] or 'غير محدد'
        dept_stats[dept]['present'] += stats['present_days']
        dept_stats[dept]['absent'] += stats['absent_days']
        dept_stats[dept]['late'] += stats['late_days']
        dept_stats[dept]['count'] += 1

    total_possible = total_employees * work_days
    overall_attendance_pct = round((total_present / total_possible * 100), 1) if total_possible > 0 else 0
    overall_absent_pct = round((total_absent / total_possible * 100), 1) if total_possible > 0 else 0
    overall_late_pct = round((total_late / total_possible * 100), 1) if total_possible > 0 else 0

    avg_clock_in_val = None
    avg_clock_out_val = None
    if all_clock_in:
        m = int(sum(all_clock_in) / len(all_clock_in))
        avg_clock_in_val = f'{m // 60:02d}:{m % 60:02d}'
    if all_clock_out:
        m = int(sum(all_clock_out) / len(all_clock_out))
        avg_clock_out_val = f'{m // 60:02d}:{m % 60:02d}'

    avg_hours_per_employee = round(total_clock_hours / total_employees, 1) if total_employees > 0 else 0
    avg_hours_minutes = f'{int(avg_hours_per_employee)}h {int((avg_hours_per_employee % 1) * 60)}m'

    summary = {
        'total_employees': total_employees,
        'overall_attendance_pct': overall_attendance_pct,
        'overall_absent_pct': overall_absent_pct,
        'overall_late_pct': overall_late_pct,
        'total_present_days': total_present,
        'total_absent_days': total_absent,
        'total_late_count': total_late,
        'total_late_minutes': total_late_minutes,
        'total_clock_hours': round(total_clock_hours, 1),
        'total_work_hours': total_work_hours,
        'work_days': work_days,
        'expected_hours': expected_hours,
        'regular_employees': regular_count,
        'needs_followup': needs_followup_count,
        'avg_clock_in': avg_clock_in_val,
        'avg_clock_out': avg_clock_out_val,
        'avg_hours_per_employee': avg_hours_per_employee,
        'avg_hours_label': avg_hours_minutes,
        'month': month,
        'year': year,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'month_name': MONTH_NAMES[month],
    }
    return jsonify(summary)

@reports_attendance_bp.route('/api/charts')
@admin_required
def api_charts():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    preset = request.args.get('preset')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)
    chart_type = request.args.get('chart_type', 'trend')

    start, end = get_date_range(year, month, preset, start_str, end_str)
    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    employees = get_employee_query(filters)
    emp_ids = [e.id for e in employees]

    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(emp_ids),
        AttendanceLog.log_date >= start,
        AttendanceLog.log_date <= end,
    ).all()

    if chart_type == 'trend':
        daily_stats = defaultdict(lambda: {'present': 0, 'absent': 0, 'late': 0, 'total': 0})
        for log in logs:
            ds = daily_stats[log.log_date.isoformat()]
            ds['total'] += 1
            if log.status in ('present', 'late'):
                ds['present'] += 1
            else:
                ds['absent'] += 1
            if log.late_minutes and log.late_minutes > 0:
                ds['late'] += 1
        trend_data = []
        d = start
        while d <= end:
            iso = d.isoformat()
            ds = daily_stats.get(iso, {'present': 0, 'absent': 0, 'late': 0, 'total': 0})
            total_emps = len(employees)
            trend_data.append({
                'date': iso,
                'day_name': DAY_NAMES[d.weekday()],
                'day': d.day,
                'present': ds['present'],
                'absent': ds['absent'],
                'late': ds['late'],
                'attendance_pct': round(ds['present'] / total_emps * 100, 1) if total_emps > 0 else 0,
            })
            d += timedelta(days=1)
        return jsonify({'type': 'trend', 'data': trend_data})

    if chart_type == 'punctuality':
        buckets = {'ontime': 0, '1_15': 0, '15_30': 0, 'over_30': 0}
        for log in logs:
            if log.clock_in:
                late_m = log.late_minutes or 0
                if late_m == 0:
                    buckets['ontime'] += 1
                elif late_m <= 15:
                    buckets['1_15'] += 1
                elif late_m <= 30:
                    buckets['15_30'] += 1
                else:
                    buckets['over_30'] += 1
        total = sum(buckets.values())
        dist = [
            {'label': 'في الموعد', 'value': buckets['ontime'], 'pct': round(buckets['ontime'] / total * 100, 1) if total else 0, 'color': '#22c55e'},
            {'label': '1-15 دقيقة', 'value': buckets['1_15'], 'pct': round(buckets['1_15'] / total * 100, 1) if total else 0, 'color': '#eab308'},
            {'label': '15-30 دقيقة', 'value': buckets['15_30'], 'pct': round(buckets['15_30'] / total * 100, 1) if total else 0, 'color': '#f97316'},
            {'label': '> 30 دقيقة', 'value': buckets['over_30'], 'pct': round(buckets['over_30'] / total * 100, 1) if total else 0, 'color': '#ef4444'},
        ]
        return jsonify({'type': 'punctuality', 'data': dist})

    if chart_type == 'department_compare':
        all_emps = Employee.query.filter(Employee.id.in_(emp_ids)).all()
        dept_groups = defaultdict(list)
        for emp in all_emps:
            dept_groups[emp.department or 'غير محدد'].append(emp.id)
        result = []
        for dept_name, eids in dept_groups.items():
            dept_logs = [l for l in logs if l.employee_id in eids]
            total = len(dept_logs)
            present = sum(1 for l in dept_logs if l.status in ('present', 'late'))
            absent = sum(1 for l in dept_logs if l.status == 'absent')
            late = sum(1 for l in dept_logs if l.late_minutes and l.late_minutes > 0)
            result.append({
                'department': dept_name,
                'employee_count': len(eids),
                'present_pct': round(present / total * 100, 1) if total else 0,
                'absent_pct': round(absent / total * 100, 1) if total else 0,
                'late_pct': round(late / total * 100, 1) if total else 0,
            })
        result.sort(key=lambda x: x['present_pct'], reverse=True)
        return jsonify({'type': 'department_compare', 'data': result})

    if chart_type == 'heatmap':
        heatmap = {}
        for log in logs:
            if log.clock_in:
                dow = log.log_date.weekday()
                hour = log.clock_in.hour
                key = f'{dow}_{hour}'
                heatmap[key] = heatmap.get(key, 0) + 1
        rows = []
        for dow in range(7):
            row = {'day': DAY_NAMES[dow], 'hours': []}
            for h in range(6, 22):
                key = f'{dow}_{h}'
                row['hours'].append(heatmap.get(key, 0))
            rows.append(row)
        return jsonify({'type': 'heatmap', 'data': rows})

    if chart_type == 'pie':
        status_counts = Counter()
        for log in logs:
            s = log.status or 'absent'
            status_counts[s] += 1
        pie_data = []
        colors = {'present': '#22c55e', 'late': '#eab308', 'absent': '#ef4444', 'leave': '#3b82f6'}
        labels = {'present': 'حاضر', 'late': 'متأخر', 'absent': 'غائب', 'leave': 'إجازة'}
        for s in ['present', 'late', 'absent', 'leave']:
            v = status_counts.get(s, 0)
            if v > 0:
                pie_data.append({'label': labels.get(s, s), 'value': v, 'color': colors.get(s, '#888')})
        return jsonify({'type': 'pie', 'data': pie_data})

    if chart_type == 'hourly':
        hourly = defaultdict(int)
        for log in logs:
            if log.clock_in:
                hourly[log.clock_in.hour] += 1
        hourly_data = [{'hour': h, 'count': hourly.get(h, 0)} for h in range(6, 22)]
        return jsonify({'type': 'hourly', 'data': hourly_data})

    return jsonify({'type': 'error', 'message': 'نوع الرسم البياني غير معروف'})

@reports_attendance_bp.route('/api/table')
@admin_required
def api_table():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    preset = request.args.get('preset')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    sort_by = request.args.get('sort_by', 'employee_name')
    sort_dir = request.args.get('sort_dir', 'asc')
    search = request.args.get('search', '').strip()

    start, end = get_date_range(year, month, preset, start_str, end_str)
    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    if employee_id:
        filters['employee_ids'] = [employee_id]
    employees = get_employee_query(filters)

    if search:
        employees = [e for e in employees if search.lower() in e.full_name.lower() or search.lower() in e.username.lower()]

    employee_results = []
    for emp in employees:
        stats = calc_attendance_stats(emp, start, end)
        employee_results.append(stats)

    sort_keys = {
        'employee_name': lambda x: x['employee_name'],
        'department': lambda x: x['department'] or '',
        'attendance_pct': lambda x: x['attendance_pct'],
        'absent_days': lambda x: x['absent_days'],
        'late_days': lambda x: x['late_days'],
        'total_clock_hours': lambda x: x['total_clock_hours'],
        'overall_rating': lambda x: x['overall_rating'],
        'total_late_minutes': lambda x: x['total_late_minutes'],
    }
    key_fn = sort_keys.get(sort_by, sort_keys['employee_name'])
    reverse = sort_dir == 'desc'
    employee_results.sort(key=key_fn, reverse=reverse)

    total = len(employee_results)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page
    page_results = employee_results[start_idx:start_idx + per_page]

    return jsonify({
        'employees': page_results,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
    })

@reports_attendance_bp.route('/api/employee/<int:eid>/detail')
@admin_required
def api_employee_detail(eid):
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    preset = request.args.get('preset')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start, end = get_date_range(year, month, preset, start_str, end_str)
    emp = Employee.query.get_or_404(eid)
    stats = calc_attendance_stats(emp, start, end)

    shift_schedules = ShiftSchedule.query.filter(
        ShiftSchedule.employee_id == emp.id,
        ShiftSchedule.scheduled_date >= start,
        ShiftSchedule.scheduled_date <= end,
    ).all()
    schedule_map = {}
    for s in shift_schedules:
        schedule_map[s.scheduled_date.isoformat()] = {
            'shift_name': s.shift_type.name if s.shift_type else 'بدون',
            'start': s.shift_type.time_range if s.shift_type else '',
        }

    for rec in stats['daily_records']:
        sched = schedule_map.get(rec['date'])
        if sched:
            rec['scheduled_shift'] = sched['shift_name']
            rec['scheduled_range'] = sched['start']

    return jsonify(stats)

@reports_attendance_bp.route('/api/stats')
@admin_required
def api_statistics():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    preset = request.args.get('preset')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)

    start, end = get_date_range(year, month, preset, start_str, end_str)
    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    employees = get_employee_query(filters)

    all_attendance_pcts = []
    all_late_minutes = []
    all_clock_hours = []
    all_clock_in_times = []
    day_absent_count = Counter()
    day_late_count = Counter()
    day_present_count = Counter()

    for emp in employees:
        stats = calc_attendance_stats(emp, start, end)
        all_attendance_pcts.append(stats['attendance_pct'])
        all_late_minutes.append(stats['total_late_minutes'])
        all_clock_hours.append(stats['total_clock_hours'])
        if stats['avg_clock_in']:
            parts = stats['avg_clock_in'].split(':')
            all_clock_in_times.append(int(parts[0]) * 60 + int(parts[1]))
        for rec in stats['daily_records']:
            dow = datetime.strptime(rec['date'], '%Y-%m-%d').weekday()
            if rec['status'] == 'absent':
                day_absent_count[dow] += 1
            elif rec['status'] == 'late':
                day_late_count[dow] += 1
            if rec['status'] in ('present', 'late'):
                day_present_count[dow] += 1

    sorted_pcts = sorted(all_attendance_pcts)
    n = len(sorted_pcts)
    median_attendance = round(sorted_pcts[n // 2], 1) if n else 0
    mean_attendance = round(sum(sorted_pcts) / n, 1) if n else 0
    variance = sum((x - mean_attendance) ** 2 for x in sorted_pcts) / n if n else 0
    std_dev = round(math.sqrt(variance), 1)

    q1 = round(sorted_pcts[n // 4], 1) if n else 0
    q3 = round(sorted_pcts[3 * n // 4], 1) if n else 0

    mode_clock_in = None
    if all_clock_in_times:
        counter = Counter(all_clock_in_times)
        mode_val = counter.most_common(1)[0][0]
        mode_clock_in = f'{mode_val // 60:02d}:{mode_val % 60:02d}'

    peak_absent_day = None
    if day_absent_count:
        peak_dow = day_absent_count.most_common(1)[0][0]
        peak_absent_day = DAY_NAMES[peak_dow]
    peak_late_day = None
    if day_late_count:
        peak_dow_l = day_late_count.most_common(1)[0][0]
        peak_late_day = DAY_NAMES[peak_dow_l]

    consistency_score = 'عالية جداً' if std_dev < 5 else 'عالية' if std_dev < 10 else 'متوسطة' if std_dev < 15 else 'منخفضة'
    predictability = 'متوقع جداً' if std_dev < 5 else 'متوقع' if std_dev < 10 else 'متفاوت' if std_dev < 15 else 'غير متوقع'

    return jsonify({
        'mean_attendance': mean_attendance,
        'median_attendance': median_attendance,
        'std_deviation': std_dev,
        'q1': q1,
        'q3': q3,
        'mode_clock_in': mode_clock_in,
        'peak_absent_day': peak_absent_day,
        'peak_late_day': peak_late_day,
        'consistency_score': consistency_score,
        'predictability': predictability,
        'total_employees_analyzed': n,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
    })

@reports_attendance_bp.route('/api/anomalies')
@admin_required
def api_anomalies():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    dept_id = request.args.get('department_id', type=int)

    start, end = get_date_range(year, month)
    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    employees = get_employee_query(filters)

    anomalies = []
    for emp in employees:
        stats = calc_attendance_stats(emp, start, end)
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.log_date >= start,
            AttendanceLog.log_date <= end,
        ).order_by(AttendanceLog.log_date).all()

        weekday_counts = Counter()
        absent_streak = 0
        max_absent_streak = 0
        monday_late = 0
        monday_count = 0

        for log in logs:
            dow = log.log_date.weekday()
            weekday_counts[dow] += 1
            if log.status == 'absent':
                absent_streak += 1
                max_absent_streak = max(max_absent_streak, absent_streak)
            else:
                absent_streak = 0
            if dow == 0 and log.late_minutes and log.late_minutes > 0:
                monday_late += 1
                monday_count += 1
            elif dow == 0:
                monday_count += 1

        weekend_work = [l for l in logs if l.log_date.weekday() >= 5 and l.clock_in]
        if weekend_work:
            for wl in weekend_work[:3]:
                anomalies.append({
                    'employee_name': emp.full_name,
                    'employee_id': emp.id,
                    'department': emp.department,
                    'type': 'weekend_work',
                    'severity': 'info',
                    'title': 'حضر في يوم غير معتاد',
                    'detail': f'{emp.full_name}: حضر يوم {DAY_NAMES[wl.log_date.weekday()]} ({wl.log_date.strftime("%Y-%m-%d")})',
                    'date': wl.log_date.isoformat(),
                })

        if max_absent_streak >= 3:
            anomalies.append({
                'employee_name': emp.full_name,
                'employee_id': emp.id,
                'department': emp.department,
                'type': 'absence_streak',
                'severity': 'danger',
                'title': 'غياب متكرر',
                'detail': f'{emp.full_name}: غياب لمدة {max_absent_streak} أيام متتالية',
                'date': start.isoformat(),
            })

        if monday_count > 0 and monday_late / monday_count >= 0.5:
            anomalies.append({
                'employee_name': emp.full_name,
                'employee_id': emp.id,
                'department': emp.department,
                'type': 'monday_late',
                'severity': 'warning',
                'title': 'تأخير يوم الاثنين',
                'detail': f'{emp.full_name}: متأخر {monday_late} من أصل {monday_count} أيام الاثنين',
                'date': start.isoformat(),
            })

        if stats['absent_days'] == 0 and stats['late_days'] <= 1 and stats['attendance_pct'] > 95:
            anomalies.append({
                'employee_name': emp.full_name,
                'employee_id': emp.id,
                'department': emp.department,
                'type': 'excellent',
                'severity': 'success',
                'title': 'أداء متميز',
                'detail': f'{emp.full_name}: حضور كامل بنسبة {stats["attendance_pct"]}%',
                'date': start.isoformat(),
            })

    anomalies.sort(key=lambda x: {'danger': 0, 'warning': 1, 'success': 2, 'info': 3}.get(x['severity'], 4))
    return jsonify({'anomalies': anomalies[:50]})

@reports_attendance_bp.route('/api/insights')
@admin_required
def api_insights():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    dept_id = request.args.get('department_id', type=int)

    start, end = get_date_range(year, month)
    prev_start = start - timedelta(days=(end - start).days + 1)
    prev_end = start - timedelta(days=1)

    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    employees = get_employee_query(filters)
    emp_ids = [e.id for e in employees]

    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id.in_(emp_ids),
        AttendanceLog.log_date >= prev_start,
        AttendanceLog.log_date <= end,
    ).all()

    current_logs = [l for l in logs if start <= l.log_date <= end]
    prev_logs = [l for l in logs if prev_start <= l.log_date <= prev_end]

    current_present = sum(1 for l in current_logs if l.status in ('present', 'late'))
    prev_present = sum(1 for l in prev_logs if l.status in ('present', 'late'))
    current_total = len(employees) * get_work_days(start, end)
    prev_total = len(employees) * get_work_days(prev_start, prev_end)

    current_pct = round(current_present / current_total * 100, 1) if current_total else 0
    prev_pct = round(prev_present / prev_total * 100, 1) if prev_total else 0
    change = round(current_pct - prev_pct, 1)

    dept_pcts = []
    dept_groups = defaultdict(list)
    for emp in employees:
        dept_groups[emp.department or 'غير محدد'].append(emp.id)
    for dept_name, eids in dept_groups.items():
        dept_current = sum(1 for l in current_logs if l.employee_id in eids and l.status in ('present', 'late'))
        dept_total = len(eids) * get_work_days(start, end)
        dept_pcts.append((dept_name, round(dept_current / dept_total * 100, 1) if dept_total else 0))
    dept_pcts.sort(key=lambda x: x[1], reverse=True)

    day_pcts = defaultdict(lambda: {'present': 0, 'total': 0})
    for l in current_logs:
        dow = l.log_date.weekday()
        day_pcts[dow]['total'] += 1
        if l.status in ('present', 'late'):
            day_pcts[dow]['present'] += 1
    day_stats = []
    for d in range(7):
        if day_pcts[d]['total'] > 0:
            day_stats.append({
                'day': DAY_NAMES[d],
                'pct': round(day_pcts[d]['present'] / day_pcts[d]['total'] * 100, 1),
                'count': day_pcts[d]['total'],
            })
    day_stats.sort(key=lambda x: x['pct'])

    new_emp_ids = [e.id for e in employees if e.hire_date and e.hire_date >= date.today() - timedelta(days=90)]
    new_logs = [l for l in current_logs if l.employee_id in new_emp_ids]
    new_late = sum(1 for l in new_logs if l.late_minutes and l.late_minutes > 0)
    new_late_avg = round(new_late / len(new_logs) * 100, 1) if new_logs else 0

    regular_logs = [l for l in current_logs if l.employee_id not in new_emp_ids]
    regular_late = sum(1 for l in regular_logs if l.late_minutes and l.late_minutes > 0)
    regular_late_avg = round(regular_late / len(regular_logs) * 100, 1) if regular_logs else 0
    late_diff = round(new_late_avg - regular_late_avg, 1)

    insights = []
    if change > 0:
        insights.append({
            'type': 'positive',
            'icon': '📈',
            'title': 'معدل الحضور في ارتفاع',
            'detail': f'ارتفع معدل الحضور بنسبة {change}% مقارنة بالفترة السابقة',
        })
    elif change < 0:
        insights.append({
            'type': 'negative',
            'icon': '📉',
            'title': 'معدل الحضور في انخفاض',
            'detail': f'انخفض معدل الحضور بنسبة {abs(change)}% مقارنة بالفترة السابقة',
        })

    best_dept = dept_pcts[0] if dept_pcts else None
    worst_dept = dept_pcts[-1] if dept_pcts and len(dept_pcts) > 1 else None
    if best_dept:
        insights.append({
            'type': 'positive',
            'icon': '🏆',
            'title': f'أفضل قسم: {best_dept[0]}',
            'detail': f'نسبة حضور {best_dept[1]}% — قدوة لبقية الأقسام',
        })
    if worst_dept and worst_dept[1] < 85:
        insights.append({
            'type': 'negative',
            'icon': '⚠️',
            'title': f'القسم الأقل حضوراً: {worst_dept[0]}',
            'detail': f'نسبة حضور {worst_dept[1]}% — يحتاج متابعة واهتمام',
        })

    if day_stats:
        best_day = day_stats[-1]
        worst_day = day_stats[0]
        insights.append({
            'type': 'info',
            'icon': '📅',
            'title': f'أفضل يوم: {best_day["day"]}',
            'detail': f'نسبة حضور {best_day["pct"]}% — الموظفون أكثر التزاماً',
        })
        insights.append({
            'type': 'info',
            'icon': '📅',
            'title': f'أسوأ يوم: {worst_day["day"]}',
            'detail': f'نسبة حضور {worst_day["pct"]}% — قد يحتاج تعديل في المناوبات',
        })

    if late_diff > 3:
        insights.append({
            'type': 'warning',
            'icon': '🆕',
            'title': 'الموظفون الجدد أكثر تأخيراً',
            'detail': f'الموظفون الجدد يتأخرون بنسبة {late_diff}% أكثر من الموظفين القدامى',
        })

    employees_at_risk = []
    for emp in employees:
        stats = calc_attendance_stats(emp, start, end)
        projected = stats['attendance_pct']
        if projected < 80:
            employees_at_risk.append({
                'name': emp.full_name,
                'id': emp.id,
                'current_pct': projected,
            })

    if employees_at_risk:
        insights.append({
            'type': 'danger',
            'icon': '🎯',
            'title': f'{len(employees_at_risk)} موظفين قد لا يحققون 80%',
            'detail': 'التدخل المبكر قد يساعد في تحسين أدائهم',
            'employees': employees_at_risk[:5],
        })

    return jsonify({'insights': insights})

@reports_attendance_bp.route('/api/compare')
@admin_required
def api_compare():
    compare_type = request.args.get('type', 'periods')
    dept_id = request.args.get('department_id', type=int)

    if compare_type == 'periods':
        year = request.args.get('year', type=int) or date.today().year
        month = request.args.get('month', type=int) or date.today().month
        start, end = get_date_range(year, month)
        prev_start = start - timedelta(days=(end - start).days + 1)
        prev_end = start - timedelta(days=1)

        filters = {}
        if dept_id:
            filters['department_id'] = dept_id
        employees = get_employee_query(filters)

        current_stats = {'present': 0, 'absent': 0, 'late': 0, 'total_hours': 0, 'late_minutes': 0}
        prev_stats = {'present': 0, 'absent': 0, 'late': 0, 'total_hours': 0, 'late_minutes': 0}
        current_emps = len(employees)
        current_work_days = get_work_days(start, end)
        prev_work_days = get_work_days(prev_start, prev_end)

        for emp in employees:
            cs = calc_attendance_stats(emp, start, end)
            ps = calc_attendance_stats(emp, prev_start, prev_end)
            current_stats['present'] += cs['present_days']
            current_stats['absent'] += cs['absent_days']
            current_stats['late'] += cs['late_days']
            current_stats['total_hours'] += cs['total_clock_hours']
            current_stats['late_minutes'] += cs['total_late_minutes']
            prev_stats['present'] += ps['present_days']
            prev_stats['absent'] += ps['absent_days']
            prev_stats['late'] += ps['late_days']
            prev_stats['total_hours'] += ps['total_clock_hours']
            prev_stats['late_minutes'] += ps['total_late_minutes']

        current_total = current_emps * current_work_days
        prev_total = current_emps * prev_work_days
        current_att_pct = round(current_stats['present'] / current_total * 100, 1) if current_total else 0
        prev_att_pct = round(prev_stats['present'] / prev_total * 100, 1) if prev_total else 0

        return jsonify({
            'compare_type': 'periods',
            'period1': {'label': f'{MONTH_NAMES[prev_start.month]} {prev_start.year}', 'start': prev_start.isoformat(), 'end': prev_end.isoformat(), 'attendance_pct': prev_att_pct, 'absent': prev_stats['absent'], 'late': prev_stats['late'], 'total_hours': round(prev_stats['total_hours'], 1)},
            'period2': {'label': f'{MONTH_NAMES[start.month]} {start.year}', 'start': start.isoformat(), 'end': end.isoformat(), 'attendance_pct': current_att_pct, 'absent': current_stats['absent'], 'late': current_stats['late'], 'total_hours': round(current_stats['total_hours'], 1)},
            'change': round(current_att_pct - prev_att_pct, 1),
        })

    if compare_type == 'departments':
        dept1_id = request.args.get('dept1_id', type=int)
        dept2_id = request.args.get('dept2_id', type=int)
        year = request.args.get('year', type=int) or date.today().year
        month = request.args.get('month', type=int) or date.today().month
        start, end = get_date_range(year, month)

        depts_data = []
        for did in [dept1_id, dept2_id]:
            if not did:
                continue
            dept = Department.query.get(did)
            emp_list = Employee.query.filter_by(department_id=did, is_active=True).all()
            total_present = 0
            total_absent = 0
            total_late = 0
            for emp in emp_list:
                stats = calc_attendance_stats(emp, start, end)
                total_present += stats['present_days']
                total_absent += stats['absent_days']
                total_late += stats['late_days']
            total_possible = len(emp_list) * get_work_days(start, end)
            att_pct = round(total_present / total_possible * 100, 1) if total_possible else 0
            depts_data.append({
                'name': dept.name_ar or dept.name_en if dept else f'قسم #{did}',
                'employee_count': len(emp_list),
                'attendance_pct': att_pct,
                'absent': total_absent,
                'late': total_late,
            })
        return jsonify({'compare_type': 'departments', 'departments': depts_data})

    return jsonify({'error': 'نوع المقارنة غير معروف'})

@reports_attendance_bp.route('/api/export')
@admin_required
def api_export():
    export_type = request.args.get('type', 'json')
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    preset = request.args.get('preset')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)

    start, end = get_date_range(year, month, preset, start_str, end_str)
    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    employees = get_employee_query(filters)

    rows = []
    for emp in employees:
        stats = calc_attendance_stats(emp, start, end)
        rows.append({
            'employee_name': stats['employee_name'],
            'employee_id': stats['employee_username'],
            'department': stats['department'],
            'attendance_pct': stats['attendance_pct'],
            'present_days': stats['present_days'],
            'absent_days': stats['absent_days'],
            'late_days': stats['late_days'],
            'total_late_minutes': stats['total_late_minutes'],
            'total_work_hours': stats['total_clock_hours'],
            'avg_clock_in': stats['avg_clock_in'],
            'avg_clock_out': stats['avg_clock_out'],
            'overall_rating': stats['overall_rating'],
        })

    if export_type == 'json':
        return jsonify({'data': rows, 'generated_at': datetime.now(UTC).isoformat()})

    if export_type == 'csv':
        import csv
        si = io.StringIO()
        writer = csv.DictWriter(si, fieldnames=rows[0].keys() if rows else [])
        writer.writeheader()
        writer.writerows(rows)
        output = si.getvalue().encode('utf-8-sig')
        return send_file(
            io.BytesIO(output),
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name=f'attendance_report_{start.isoformat()}_{end.isoformat()}.csv',
        )

    return jsonify({'error': 'نوع التصدير غير مدعوم'})

@reports_attendance_bp.route('/api/recommendations')
@admin_required
def api_recommendations():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    dept_id = request.args.get('department_id', type=int)

    start, end = get_date_range(year, month)
    filters = {}
    if dept_id:
        filters['department_id'] = dept_id
    employees = get_employee_query(filters)

    recommendations = []
    for emp in employees:
        stats = calc_attendance_stats(emp, start, end)
        if stats['absent_days'] >= 3 and stats['late_days'] >= 5:
            recommendations.append({
                'employee_name': emp.full_name,
                'department': emp.department,
                'type': 'critical',
                'title': 'موظف يحتاج تدخل عاجل',
                'detail': f'{emp.full_name}: {stats["absent_days"]} غيابات و {stats["late_days"]} تأخيرات — نسبة الحضور {stats["attendance_pct"]}%',
                'action': 'عقد جلسة مع الموظف لفهم الأسباب',
            })
        elif stats['attendance_pct'] >= 95 and stats['late_days'] <= 2:
            recommendations.append({
                'employee_name': emp.full_name,
                'department': emp.department,
                'type': 'praise',
                'title': 'موظف يستحق التكريم',
                'detail': f'{emp.full_name}: نسبة حضور {stats["attendance_pct"]}% و {stats["late_days"]} تأخيرات فقط',
                'action': 'تكريم الموظف في اجتماع القسم الشهري',
            })

    if len(recommendations) > 10:
        recommendations = recommendations[:10]

    return jsonify({'recommendations': recommendations})
