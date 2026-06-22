from datetime import datetime, date, timedelta, UTC
from collections import defaultdict
import json, math

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.misc import LeaveRequest, EmployeeDocument
from models.shifts import ShiftType, ShiftSchedule
from models.biotime_device import BioTimeDevice


class ReportCorrection(db.Model):
    __tablename__ = 'report_corrections'
    id              = db.Column(db.Integer, primary_key=True)
    employee_id     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    log_date        = db.Column(db.Date, nullable=False)
    correction_type = db.Column(db.String(30), nullable=False)
    original_value  = db.Column(db.String(50), nullable=True)
    corrected_value = db.Column(db.String(50), nullable=True)
    reason          = db.Column(db.Text, nullable=False)
    document_path   = db.Column(db.String(300), nullable=True)
    status          = db.Column(db.String(20), default='pending')
    reviewed_by     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    reviewed_at     = db.Column(db.DateTime, nullable=True)
    review_notes    = db.Column(db.Text, nullable=True)
    created_by      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee        = db.relationship('Employee', foreign_keys=[employee_id], backref='corrections')
    reviewer        = db.relationship('Employee', foreign_keys=[reviewed_by])
    creator         = db.relationship('Employee', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else '',
            'log_date': self.log_date.isoformat() if self.log_date else None,
            'correction_type': self.correction_type,
            'original_value': self.original_value,
            'corrected_value': self.corrected_value,
            'reason': self.reason,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScheduledReport(db.Model):
    __tablename__ = 'scheduled_reports'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    frequency       = db.Column(db.String(20), nullable=False)
    day_of_month    = db.Column(db.Integer, nullable=True)
    day_of_week     = db.Column(db.Integer, nullable=True)
    time_hour       = db.Column(db.Integer, nullable=False)
    time_minute     = db.Column(db.Integer, nullable=False)
    format_type     = db.Column(db.String(20), default='pdf')
    recipients_json = db.Column(db.Text, nullable=True)
    department_ids  = db.Column(db.Text, nullable=True)
    is_active       = db.Column(db.Boolean, default=True)
    last_run_at     = db.Column(db.DateTime, nullable=True)
    last_status     = db.Column(db.String(20), nullable=True)
    next_run_at     = db.Column(db.DateTime, nullable=True)
    created_by      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    creator         = db.relationship('Employee', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'frequency': self.frequency,
            'time': f'{self.time_hour:02d}:{self.time_minute:02d}',
            'format_type': self.format_type,
            'is_active': self.is_active,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'last_status': self.last_status,
            'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
        }


class ReportDataService:
    @staticmethod
    def get_working_days(year, month):
        import calendar
        total = 0
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            d = date(year, month, day)
            if d.weekday() < 5:
                total += 1
        return total

    @staticmethod
    def get_employee_expected_days(emp, year, month, working_days=None):
        if working_days is None:
            working_days = ReportDataService.get_working_days(year, month)
        if emp.hire_date:
            month_start = date(year, month, 1)
            if emp.hire_date > month_start:
                hired_day = emp.hire_date.day
                expected = 0
                import calendar
                for day in range(hired_day, calendar.monthrange(year, month)[1] + 1):
                    d = date(year, month, day)
                    if d.weekday() < 5:
                        expected += 1
                return expected
        return working_days

    @staticmethod
    def calculate_report(year, month, dept_id=None, employee_id=None, emp_type=None, shift_id=None):
        from services.payroll_service import PayrollService
        import calendar
        today = date.today()
        qry = Employee.query.filter_by(is_active=True, deleted_at=None)
        if dept_id:
            qry = qry.filter_by(department_id=int(dept_id))
        if employee_id:
            qry = qry.filter_by(id=int(employee_id))
        if emp_type:
            qry = qry.filter_by(employment_type=emp_type)
        if shift_id:
            qry = qry.join(ShiftType).filter(ShiftType.id == int(shift_id))
        employees = qry.order_by(Employee.department, Employee.full_name).all()
        emp_ids = [e.id for e in employees]
        all_logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id.in_(emp_ids) if emp_ids else False,
            db.extract('month', AttendanceLog.log_date) == month,
            db.extract('year', AttendanceLog.log_date) == year,
        ).all() if emp_ids else []
        logs_by_emp = defaultdict(list)
        for l in all_logs:
            logs_by_emp[l.employee_id].append(l)
        all_leaves = LeaveRequest.query.filter(
            LeaveRequest.employee_id.in_(emp_ids) if emp_ids else False,
            LeaveRequest.status == 'approved',
        ).all() if emp_ids else []
        leaves_by_emp = defaultdict(list)
        for lv in all_leaves:
            leaves_by_emp[lv.employee_id].append(lv)
        working_days = ReportDataService.get_working_days(year, month)
        month_days = calendar.monthrange(year, month)[1]
        rows = []
        for emp in employees:
            logs = logs_by_emp.get(emp.id, [])
            leaves = leaves_by_emp.get(emp.id, [])
            present = sum(1 for l in logs if l.status in ('present', 'late'))
            late_count = sum(1 for l in logs if l.status == 'late')
            absent = sum(1 for l in logs if l.status == 'absent')
            late_minutes_total = sum(l.late_minutes or 0 for l in logs)
            expected_days = ReportDataService.get_employee_expected_days(emp, year, month, working_days)
            total_work_seconds = 0
            for l in logs:
                if l.clock_in and l.clock_out:
                    total_work_seconds += (l.clock_out - l.clock_in).total_seconds()
            total_work_hours = total_work_seconds / 3600
            work_hours_str = f'{int(total_work_hours)}س {int((total_work_seconds % 3600) / 60)}د'
            leave_days = 0
            for lv in leaves:
                if lv.start_date and lv.end_date:
                    delta = (lv.end_date - lv.start_date).days + 1
                    leave_days += delta
            overtime_minutes = 0
            for l in logs:
                if l.clock_in and l.clock_out:
                    worked = (l.clock_out - l.clock_in).total_seconds() / 3600
                    if worked > 8:
                        overtime_minutes += (worked - 8) * 60
            base_salary = emp.base_salary or 0
            late_deduction = PayrollService.calculate_deduction(base_salary, late_minutes_total) if late_minutes_total > 0 else 0
            absence_deduction = PayrollService.calculate_deduction(base_salary, absent * 8 * 60) if absent > 0 else 0
            total_deduction = round(late_deduction + absence_deduction, 2)
            overtime_pay = 0
            if overtime_minutes > 0:
                hourly_rate = base_salary / 30 / 8
                overtime_pay = round(hourly_rate * (overtime_minutes / 60) * (emp.overtime_multiplier or 1.5), 2)
            allowances = (emp.housing_allowance or 0) + (emp.transport_allowance or 0)
            net_salary = round(base_salary + allowances + overtime_pay - total_deduction, 2)
            attendance_pct = round((present / expected_days) * 100, 1) if expected_days > 0 else 0
            if attendance_pct >= 95:
                overall_status = 'excellent'
                status_label = 'ممتاز'
            elif attendance_pct >= 85:
                overall_status = 'good'
                status_label = 'جيد'
            elif attendance_pct >= 75:
                overall_status = 'acceptable'
                status_label = 'مقبول'
            else:
                overall_status = 'poor'
                status_label = 'ضعيف'
            day_details = []
            import calendar
            for day_num in range(1, month_days + 1):
                d = date(year, month, day_num)
                day_logs = [l for l in logs if l.log_date == d]
                day_status = 'absent'
                day_clock_in = None
                day_clock_out = None
                if day_logs:
                    day_log = day_logs[0]
                    day_status = day_log.status or 'absent'
                    day_clock_in = day_log.clock_in
                    day_clock_out = day_log.clock_out
                is_leave = False
                for lv in leaves:
                    if lv.start_date and lv.end_date and lv.start_date <= d <= lv.end_date:
                        is_leave = True
                        day_status = 'leave'
                        break
                if d.weekday() >= 5:
                    day_status = 'weekend'
                day_details.append({
                    'day': day_num,
                    'date': d.isoformat(),
                    'status': day_status,
                    'clock_in': day_clock_in.strftime('%H:%M') if day_clock_in else None,
                    'clock_out': day_clock_out.strftime('%H:%M') if day_clock_out else None,
                })
            rows.append({
                'employee': emp,
                'emp_id': emp.id,
                'emp_name': emp.full_name,
                'emp_code': emp.username,
                'department': emp.department,
                'department_id': emp.department_id,
                'employment_type': emp.employment_type or 'full_time',
                'present': present,
                'late_count': late_count,
                'absent': absent,
                'late_minutes': late_minutes_total,
                'expected_days': expected_days,
                'total_work_hours': round(total_work_hours, 1),
                'total_work_hours_str': work_hours_str,
                'leave_days': leave_days,
                'overtime_minutes': round(overtime_minutes),
                'overtime_pay': overtime_pay,
                'bonus': 0,
                'late_deduction': late_deduction,
                'absence_deduction': absence_deduction,
                'total_deduction': total_deduction,
                'base_salary': base_salary,
                'allowances': allowances,
                'net_salary': net_salary,
                'attendance_pct': attendance_pct,
                'overall_status': overall_status,
                'status_label': status_label,
                'day_details': day_details,
                'profile_photo': emp.profile_photo,
            })
        total_present = sum(r['present'] for r in rows)
        total_absent = sum(r['absent'] for r in rows)
        total_late_m = sum(r['late_minutes'] for r in rows)
        total_deductions = sum(r['total_deduction'] for r in rows)
        total_employees = len(rows)
        total_expected = sum(r['expected_days'] for r in rows)
        overall_pct = round((total_present / total_expected) * 100, 1) if total_expected > 0 else 0
        summary = {
            'working_days': working_days,
            'total_employees': total_employees,
            'total_present': total_present,
            'total_absent': total_absent,
            'total_late_minutes': total_late_m,
            'total_deductions': total_deductions,
            'overall_pct': overall_pct,
            'total_expected': total_expected,
        }
        return {'rows': rows, 'summary': summary, 'year': year, 'month': month}
