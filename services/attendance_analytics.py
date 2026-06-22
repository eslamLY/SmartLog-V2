import math, calendar
from datetime import datetime, date, timedelta, UTC
from collections import defaultdict, Counter, OrderedDict

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.misc import LeaveRequest
from models.shifts import ShiftType, ShiftSchedule
from models.department import Department

MONTH_NAMES = ['', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
               'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
DAY_NAMES = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']


class AttendanceAnalytics:

    def __init__(self, start_date=None, end_date=None, department_id=None,
                 employee_ids=None, status_filters=None):
        self.start_date = start_date or date.today().replace(day=1)
        self.end_date = end_date or date.today()
        self.department_id = department_id
        self.employee_ids = employee_ids
        self.status_filters = status_filters
        self._cache = {}

    def get_employees(self):
        query = Employee.query.filter(Employee.is_active == True)
        if self.department_id:
            query = query.filter(Employee.department_id == self.department_id)
        if self.employee_ids:
            query = query.filter(Employee.id.in_(self.employee_ids))
        return query.order_by(Employee.full_name).all()

    def get_work_days(self):
        count = 0
        d = self.start_date
        while d <= self.end_date:
            if d.weekday() < 5:
                count += 1
            d += timedelta(days=1)
        return count

    def get_expected_hours(self):
        return self.get_work_days() * 8

    def get_all_logs(self, employee_ids=None):
        q = AttendanceLog.query.filter(
            AttendanceLog.log_date >= self.start_date,
            AttendanceLog.log_date <= self.end_date,
        )
        if employee_ids:
            q = q.filter(AttendanceLog.employee_id.in_(employee_ids))
        return q.order_by(AttendanceLog.employee_id, AttendanceLog.log_date).all()

    def get_approved_leaves(self, employee_ids=None):
        q = LeaveRequest.query.filter(
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= self.end_date,
            LeaveRequest.end_date >= self.start_date,
        )
        if employee_ids:
            q = q.filter(LeaveRequest.employee_id.in_(employee_ids))
        return q.all()

    def build_leave_date_set(self, leaves):
        result = set()
        for lv in leaves:
            d = max(lv.start_date, self.start_date)
            ed = min(lv.end_date, self.end_date)
            while d <= ed:
                result.add((lv.employee_id, d))
                d += timedelta(days=1)
        return result

    def employee_attendance_detail(self, employee):
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == employee.id,
            AttendanceLog.log_date >= self.start_date,
            AttendanceLog.log_date <= self.end_date,
        ).order_by(AttendanceLog.log_date).all()

        log_map = {l.log_date: l for l in logs}
        work_days = self.get_work_days()
        leaves = self.get_approved_leaves([employee.id])
        leave_set = set()
        for lv in leaves:
            d = max(lv.start_date, self.start_date)
            ed = min(lv.end_date, self.end_date)
            while d <= ed:
                leave_set.add(d)
                d += timedelta(days=1)

        present_days = 0
        late_days = 0
        absent_days = 0
        leave_days = 0
        total_late_minutes = 0
        total_clock_hours = 0.0
        daily_records = []
        clock_in_times = []
        clock_out_times = []
        anomaly_flags = []

        d = self.start_date
        while d <= self.end_date:
            log = log_map.get(d)
            is_leave = d in leave_set
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
                if status in ('present', 'late'):
                    present_days += 1
                    if late_mins > 0:
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

            daily_records.append({
                'date': d.isoformat(),
                'day_name': DAY_NAMES[d.weekday()],
                'day': d.day,
                'month': d.month,
                'year': d.year,
                'is_weekend': is_weekend,
                'status': status,
                'clock_in': clock_in_time.strftime('%H:%M') if clock_in_time else None,
                'clock_out': clock_out_time.strftime('%H:%M') if clock_out_time else None,
                'late_minutes': late_mins,
                'work_hours': round(work_hours, 1),
                'note': note,
            })
            d += timedelta(days=1)

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

    def organization_summary(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        total_employees = len(employees)
        work_days = self.get_work_days()
        logs = self.get_all_logs(emp_ids)
        leaves = self.get_approved_leaves(emp_ids)
        leave_set = self.build_leave_date_set(leaves)
        log_map = defaultdict(list)
        for l in logs:
            log_map[l.employee_id].append(l)

        total_present = 0
        total_absent = 0
        total_late = 0
        total_late_minutes = 0
        total_clock_hours = 0.0
        regular_count = 0
        needs_followup_count = 0
        dept_data = defaultdict(lambda: {
            'present': 0, 'absent': 0, 'late': 0, 'count': 0, 'late_minutes': 0, 'clock_hours': 0.0
        })

        for emp in employees:
            elogs = log_map.get(emp.id, [])
            elog_map = {l.log_date: l for l in elogs}
            emp_present = 0
            emp_absent = 0
            emp_late = 0
            emp_late_min = 0
            emp_hours = 0.0
            emp_clock_in = []

            d = self.start_date
            while d <= self.end_date:
                log = elog_map.get(d)
                is_leave = (emp.id, d) in leave_set
                is_weekend = d.weekday() >= 5
                if log:
                    status = log.status or 'present'
                    if status in ('present', 'late'):
                        emp_present += 1
                        if log.late_minutes and log.late_minutes > 0:
                            emp_late += 1
                            emp_late_min += log.late_minutes
                    if log.clock_in and log.clock_out:
                        emp_hours += (log.clock_out - log.clock_in).total_seconds() / 3600
                    if log.clock_in:
                        emp_clock_in.append(log.clock_in.hour * 60 + log.clock_in.minute)
                elif is_leave:
                    pass
                elif not is_weekend:
                    emp_absent += 1
                d += timedelta(days=1)

            if emp_absent == 0 and emp_late <= 2:
                regular_count += 1
            if emp_absent >= 3 or emp_late >= 5:
                needs_followup_count += 1

            total_present += emp_present
            total_absent += emp_absent
            total_late += emp_late
            total_late_minutes += emp_late_min
            total_clock_hours += emp_hours

            dept = emp.department or 'غير محدد'
            dept_data[dept]['present'] += emp_present
            dept_data[dept]['absent'] += emp_absent
            dept_data[dept]['late'] += emp_late
            dept_data[dept]['count'] += 1
            dept_data[dept]['late_minutes'] += emp_late_min
            dept_data[dept]['clock_hours'] += emp_hours

        total_possible = total_employees * work_days
        overall_attendance_pct = round((total_present / total_possible * 100), 1) if total_possible else 0
        overall_absent_pct = round((total_absent / total_possible * 100), 1) if total_possible else 0
        overall_late_pct = round((total_late / total_possible * 100), 1) if total_possible else 0

        return {
            'total_employees': total_employees,
            'work_days': work_days,
            'overall_attendance_pct': overall_attendance_pct,
            'overall_absent_pct': overall_absent_pct,
            'overall_late_pct': overall_late_pct,
            'total_present_days': total_present,
            'total_absent_days': total_absent,
            'total_late_count': total_late,
            'total_late_minutes': total_late_minutes,
            'total_clock_hours': round(total_clock_hours, 1),
            'regular_employees': regular_count,
            'needs_followup': needs_followup_count,
            'departments': dict(dept_data),
        }

    def daily_trend(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        total_emps = len(employees)
        logs = self.get_all_logs(emp_ids)
        log_map = defaultdict(list)
        for l in logs:
            log_map[l.log_date.isoformat()].append(l)

        trend = []
        d = self.start_date
        while d <= self.end_date:
            iso = d.isoformat()
            day_logs = log_map.get(iso, [])
            present = sum(1 for l in day_logs if l.status in ('present', 'late'))
            absent = total_emps - present
            late = sum(1 for l in day_logs if l.late_minutes and l.late_minutes > 0)
            trend.append({
                'date': iso,
                'day_name': DAY_NAMES[d.weekday()],
                'day': d.day,
                'present': present,
                'absent': absent,
                'late': late,
                'attendance_pct': round(present / total_emps * 100, 1) if total_emps > 0 else 0,
            })
            d += timedelta(days=1)
        return trend

    def punctuality_distribution(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        logs = self.get_all_logs(emp_ids)
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
        return [
            {'label': 'في الموعد', 'value': buckets['ontime'], 'pct': round(buckets['ontime'] / total * 100, 1) if total else 0, 'color': '#22c55e'},
            {'label': '1-15 دقيقة', 'value': buckets['1_15'], 'pct': round(buckets['1_15'] / total * 100, 1) if total else 0, 'color': '#eab308'},
            {'label': '15-30 دقيقة', 'value': buckets['15_30'], 'pct': round(buckets['15_30'] / total * 100, 1) if total else 0, 'color': '#f97316'},
            {'label': '> 30 دقيقة', 'value': buckets['over_30'], 'pct': round(buckets['over_30'] / total * 100, 1) if total else 0, 'color': '#ef4444'},
        ]

    def department_comparison(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        logs = self.get_all_logs(emp_ids)
        log_map = defaultdict(list)
        for l in logs:
            log_map[l.employee_id].append(l)
        dept_groups = defaultdict(list)
        for emp in employees:
            dept_groups[emp.department or 'غير محدد'].append(emp.id)
        result = []
        for dept_name, eids in dept_groups.items():
            dept_logs = []
            for eid in eids:
                dept_logs.extend(log_map.get(eid, []))
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
        return result

    def attendance_heatmap(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        logs = self.get_all_logs(emp_ids)
        heatmap = {}
        for log in logs:
            if log.clock_in:
                dow = log.log_date.weekday()
                hour = log.clock_in.hour
                key = f'{dow}_{hour}'
                heatmap[key] = heatmap.get(key, 0) + 1
        rows = []
        max_val = max(heatmap.values()) if heatmap else 1
        for dow in range(7):
            row = {'day': DAY_NAMES[dow], 'hours': []}
            for h in range(6, 22):
                key = f'{dow}_{h}'
                val = heatmap.get(key, 0)
                intensity = round(val / max_val * 100) if max_val > 0 else 0
                row['hours'].append({'hour': h, 'count': val, 'intensity': intensity})
            rows.append(row)
        return rows

    def status_pie(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        logs = self.get_all_logs(emp_ids)
        status_counts = Counter()
        for log in logs:
            s = log.status or 'absent'
            status_counts[s] += 1
        colors = {'present': '#22c55e', 'late': '#eab308', 'absent': '#ef4444', 'leave': '#3b82f6'}
        labels = {'present': 'حاضر', 'late': 'متأخر', 'absent': 'غائب', 'leave': 'إجازة'}
        result = []
        for s in ['present', 'late', 'absent', 'leave']:
            v = status_counts.get(s, 0)
            if v > 0:
                result.append({'label': labels.get(s, s), 'value': v, 'color': colors.get(s, '#888')})
        return result

    def hourly_distribution(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        logs = self.get_all_logs(emp_ids)
        hourly = defaultdict(int)
        for log in logs:
            if log.clock_in:
                hourly[log.clock_in.hour] += 1
        return [{'hour': h, 'count': hourly.get(h, 0)} for h in range(6, 22)]

    def statistical_summary(self):
        employees = self.get_employees()
        all_pcts = []
        all_late_mins = []
        all_hours = []
        all_clock_in = []
        day_absent = Counter()
        day_late = Counter()

        for emp in employees:
            detail = self.employee_attendance_detail(emp)
            all_pcts.append(detail['attendance_pct'])
            all_late_mins.append(detail['total_late_minutes'])
            all_hours.append(detail['total_clock_hours'])
            if detail['avg_clock_in']:
                parts = detail['avg_clock_in'].split(':')
                all_clock_in.append(int(parts[0]) * 60 + int(parts[1]))
            for rec in detail['daily_records']:
                dt = datetime.strptime(rec['date'], '%Y-%m-%d')
                dow = dt.weekday()
                if rec['status'] == 'absent':
                    day_absent[dow] += 1
                elif rec['status'] == 'late':
                    day_late[dow] += 1

        n = len(all_pcts)
        sorted_pcts = sorted(all_pcts)
        mean_att = round(sum(sorted_pcts) / n, 1) if n else 0
        median_att = round(sorted_pcts[n // 2], 1) if n else 0
        variance = sum((x - mean_att) ** 2 for x in sorted_pcts) / n if n else 0
        std_dev = round(math.sqrt(variance), 1)
        q1 = round(sorted_pcts[n // 4], 1) if n else 0
        q3 = round(sorted_pcts[3 * n // 4], 1) if n else 0
        iqr = round(q3 - q1, 1)

        mode_in = None
        if all_clock_in:
            counter = Counter(all_clock_in)
            mode_val = counter.most_common(1)[0][0]
            mode_in = f'{mode_val // 60:02d}:{mode_val % 60:02d}'

        peak_absent = DAY_NAMES[day_absent.most_common(1)[0][0]] if day_absent else None
        peak_late = DAY_NAMES[day_late.most_common(1)[0][0]] if day_late else None

        consistency = 'عالية جداً' if std_dev < 5 else 'عالية' if std_dev < 10 else 'متوسطة' if std_dev < 15 else 'منخفضة'
        predictability = 'متوقع جداً' if std_dev < 5 else 'متوقع' if std_dev < 10 else 'متفاوت' if std_dev < 15 else 'غير متوقع'

        return {
            'mean': mean_att,
            'median': median_att,
            'std_deviation': std_dev,
            'variance': round(variance, 1),
            'q1': q1,
            'q3': q3,
            'iqr': iqr,
            'mode_clock_in': mode_in,
            'peak_absent_day': peak_absent,
            'peak_late_day': peak_late,
            'consistency_score': consistency,
            'predictability': predictability,
            'sample_size': n,
        }

    def detect_anomalies(self, max_results=50):
        employees = self.get_employees()
        anomalies = []
        for emp in employees:
            detail = self.employee_attendance_detail(emp)
            logs = AttendanceLog.query.filter(
                AttendanceLog.employee_id == emp.id,
                AttendanceLog.log_date >= self.start_date,
                AttendanceLog.log_date <= self.end_date,
            ).order_by(AttendanceLog.log_date).all()

            weekday_counts = Counter()
            absent_streak = 0
            max_streak = 0
            monday_late_count = 0
            monday_total = 0

            for log in logs:
                dow = log.log_date.weekday()
                weekday_counts[dow] += 1
                if log.status == 'absent':
                    absent_streak += 1
                    max_streak = max(max_streak, absent_streak)
                else:
                    absent_streak = 0
                if dow == 0:
                    monday_total += 1
                    if log.late_minutes and log.late_minutes > 0:
                        monday_late_count += 1

            weekend_logs = [l for l in logs if l.log_date.weekday() >= 5 and l.clock_in]
            for wl in weekend_logs[:2]:
                anomalies.append({
                    'employee_name': emp.full_name,
                    'employee_id': emp.id,
                    'department': emp.department,
                    'type': 'weekend_work',
                    'severity': 'info',
                    'title': 'حضور في يوم عطلة',
                    'detail': f'{emp.full_name}: حضر يوم {DAY_NAMES[wl.log_date.weekday()]} {wl.log_date.strftime("%Y-%m-%d")}',
                })

            if max_streak >= 3:
                anomalies.append({
                    'employee_name': emp.full_name,
                    'employee_id': emp.id,
                    'department': emp.department,
                    'type': 'absence_streak',
                    'severity': 'danger',
                    'title': 'غياب متكرر',
                    'detail': f'{emp.full_name}: غياب {max_streak} أيام متتالية',
                })

            if monday_total > 0 and monday_late_count / monday_total >= 0.4:
                anomalies.append({
                    'employee_name': emp.full_name,
                    'employee_id': emp.id,
                    'department': emp.department,
                    'type': 'monday_late',
                    'severity': 'warning',
                    'title': 'تأخير يوم الاثنين',
                    'detail': f'{emp.full_name}: متأخر {monday_late_count}/{monday_total} أيام الاثنين',
                })

            if detail['absent_days'] == 0 and detail['late_days'] <= 1 and detail['attendance_pct'] >= 95:
                anomalies.append({
                    'employee_name': emp.full_name,
                    'employee_id': emp.id,
                    'department': emp.department,
                    'type': 'excellent',
                    'severity': 'success',
                    'title': 'أداء متميز',
                    'detail': f'{emp.full_name}: حضور {detail["attendance_pct"]}% بدون غياب',
                })

        severity_order = {'danger': 0, 'warning': 1, 'success': 2, 'info': 3}
        anomalies.sort(key=lambda x: severity_order.get(x['severity'], 4))
        return anomalies[:max_results]

    def generate_insights(self):
        employees = self.get_employees()
        emp_ids = [e.id for e in employees]
        total_emps = len(employees)
        work_days = self.get_work_days()

        prev_end = self.start_date - timedelta(days=1)
        prev_start = self.start_date - timedelta(days=work_days + 1)

        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id.in_(emp_ids),
            AttendanceLog.log_date >= prev_start,
            AttendanceLog.log_date <= self.end_date,
        ).all()

        current_logs = [l for l in logs if self.start_date <= l.log_date <= self.end_date]
        prev_logs = [l for l in logs if prev_start <= l.log_date <= prev_end]

        cur_present = sum(1 for l in current_logs if l.status in ('present', 'late'))
        prev_present = sum(1 for l in prev_logs if l.status in ('present', 'late'))
        cur_total = total_emps * work_days
        prev_total = total_emps * get_work_days_count(prev_start, prev_end)
        cur_pct = round(cur_present / cur_total * 100, 1) if cur_total else 0
        prev_pct = round(prev_present / prev_total * 100, 1) if prev_total else 0
        change = round(cur_pct - prev_pct, 1)

        dept_pcts = []
        dept_groups = defaultdict(list)
        for emp in employees:
            dept_groups[emp.department or 'غير محدد'].append(emp.id)
        for dept_name, eids in dept_groups.items():
            d_present = sum(1 for l in current_logs if l.employee_id in eids and l.status in ('present', 'late'))
            d_total = len(eids) * work_days
            dept_pcts.append((dept_name, round(d_present / d_total * 100, 1) if d_total else 0))
        dept_pcts.sort(key=lambda x: x[1], reverse=True)

        day_pcts = defaultdict(lambda: {'present': 0, 'total': 0})
        for l in current_logs:
            dow = l.log_date.weekday()
            day_pcts[dow]['total'] += 1
            if l.status in ('present', 'late'):
                day_pcts[dow]['present'] += 1
        day_list = []
        for d in range(7):
            if day_pcts[d]['total']:
                day_list.append({'day': DAY_NAMES[d], 'pct': round(day_pcts[d]['present'] / day_pcts[d]['total'] * 100, 1)})
        day_list.sort(key=lambda x: x['pct'])

        insights = []
        if change > 0:
            insights.append({'type': 'positive', 'icon': '📈', 'title': 'معدل الحضور في ارتفاع', 'detail': f'ارتفع {change}% مقارنة بالفترة السابقة'})
        elif change < 0:
            insights.append({'type': 'negative', 'icon': '📉', 'title': 'معدل الحضور في انخفاض', 'detail': f'انخفض {abs(change)}% مقارنة بالفترة السابقة'})

        if dept_pcts:
            best = dept_pcts[0]
            insights.append({'type': 'positive', 'icon': '🏆', 'title': f'أفضل قسم: {best[0]}', 'detail': f'نسبة حضور {best[1]}%'})
            if len(dept_pcts) > 1 and dept_pcts[-1][1] < 85:
                worst = dept_pcts[-1]
                insights.append({'type': 'negative', 'icon': '⚠️', 'title': f'القسم الأقل حضوراً: {worst[0]}', 'detail': f'نسبة حضور {worst[1]}%'})

        if day_list:
            insights.append({'type': 'info', 'icon': '📅', 'title': f'أفضل يوم: {day_list[-1]["day"]}', 'detail': f'نسبة حضور {day_list[-1]["pct"]}%'})
            insights.append({'type': 'info', 'icon': '📅', 'title': f'أسوأ يوم: {day_list[0]["day"]}', 'detail': f'نسبة حضور {day_list[0]["pct"]}%'})

        new_threshold = date.today() - timedelta(days=90)
        new_emp_ids = [e.id for e in employees if e.hire_date and e.hire_date >= new_threshold]
        if new_emp_ids:
            new_late = sum(1 for l in current_logs if l.employee_id in new_emp_ids and l.late_minutes and l.late_minutes > 0)
            new_total = sum(1 for l in current_logs if l.employee_id in new_emp_ids)
            reg_ids = [e.id for e in employees if e.id not in new_emp_ids]
            reg_late = sum(1 for l in current_logs if l.employee_id in reg_ids and l.late_minutes and l.late_minutes > 0)
            reg_total = sum(1 for l in current_logs if l.employee_id in reg_ids)
            new_pct = round(new_late / new_total * 100, 1) if new_total else 0
            reg_pct = round(reg_late / reg_total * 100, 1) if reg_total else 0
            if new_pct > reg_pct + 3:
                insights.append({'type': 'warning', 'icon': '🆕', 'title': 'الموظفون الجدد أكثر تأخيراً', 'detail': f'{new_pct}% مقابل {reg_pct}% للقدماء'})

        at_risk = []
        for emp in employees:
            detail = self.employee_attendance_detail(emp)
            if detail['attendance_pct'] < 80:
                at_risk.append({'name': emp.full_name, 'id': emp.id, 'pct': detail['attendance_pct']})
        if at_risk:
            insights.append({'type': 'danger', 'icon': '🎯', 'title': f'{len(at_risk)} موظفين قد لا يحققون 80%', 'detail': 'التدخل المبكر قد يساعد', 'employees': at_risk[:5]})

        return insights

    def compare_periods(self, other_start, other_end):
        current = AttendanceAnalytics(
            start_date=self.start_date, end_date=self.end_date,
            department_id=self.department_id, employee_ids=self.employee_ids
        )
        previous = AttendanceAnalytics(
            start_date=other_start, end_date=other_end,
            department_id=self.department_id, employee_ids=self.employee_ids
        )
        cs = current.organization_summary()
        ps = previous.organization_summary()
        return {
            'current': cs,
            'previous': ps,
            'change': round(cs['overall_attendance_pct'] - ps['overall_attendance_pct'], 1),
        }

    def department_detail(self, department_id):
        dept = Department.query.get(department_id)
        if not dept:
            return None
        ana = AttendanceAnalytics(
            start_date=self.start_date, end_date=self.end_date,
            department_id=department_id
        )
        employees = ana.get_employees()
        emp_details = [ana.employee_attendance_detail(e) for e in employees]
        summary = ana.organization_summary()
        return {
            'department': dept.name_ar or dept.name_en if dept else '',
            'employees': emp_details,
            'summary': summary,
        }


def get_work_days_count(start, end):
    count = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count
