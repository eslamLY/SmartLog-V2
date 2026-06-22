from datetime import datetime, date, timedelta, UTC
from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.shifts import ShiftSchedule
from models.misc import LeaveRequest
from sqlalchemy import extract
from collections import defaultdict


class SalaryCalculator:
    WORK_HOURS_PER_DAY = 8
    WORK_DAYS_PER_MONTH = 30

    @staticmethod
    def get_month_range(month, year):
        if month == 12:
            return date(year, month, 1), date(year, month, 31)
        return date(year, month, 1), date(year, month + 1, 1) - timedelta(days=1)

    @staticmethod
    def daily_rate(base_salary):
        return base_salary / SalaryCalculator.WORK_DAYS_PER_MONTH

    @staticmethod
    def hourly_rate(base_salary):
        return base_salary / (SalaryCalculator.WORK_DAYS_PER_MONTH * SalaryCalculator.WORK_HOURS_PER_DAY)

    @staticmethod
    def minute_rate(base_salary):
        return base_salary / (SalaryCalculator.WORK_DAYS_PER_MONTH * SalaryCalculator.WORK_HOURS_PER_DAY * 60)

    @staticmethod
    def calculate_overtime_pay(base_salary, overtime_hours, multiplier=1.5):
        hr = SalaryCalculator.hourly_rate(base_salary)
        return round(overtime_hours * hr * multiplier, 2)

    @staticmethod
    def calculate_late_deduction(base_salary, late_minutes):
        if not base_salary or not late_minutes:
            return 0.0
        mr = SalaryCalculator.minute_rate(base_salary)
        return round(late_minutes * mr, 2)

    @staticmethod
    def calculate_absence_deduction(base_salary, absent_days):
        if not base_salary or not absent_days:
            return 0.0
        dr = SalaryCalculator.daily_rate(base_salary)
        return round(absent_days * dr, 2)

    @staticmethod
    def get_employee_attendance(emp_id, month, year):
        start_date, end_date = SalaryCalculator.get_month_range(month, year)
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp_id,
            AttendanceLog.log_date >= start_date,
            AttendanceLog.log_date <= end_date,
        ).order_by(AttendanceLog.log_date).all()
        return logs

    @staticmethod
    def get_employee_overtime(emp_id, month, year):
        start_date, end_date = SalaryCalculator.get_month_range(month, year)
        shifts = ShiftSchedule.query.filter(
            ShiftSchedule.employee_id == emp_id,
            ShiftSchedule.scheduled_date >= start_date,
            ShiftSchedule.scheduled_date <= end_date,
            ShiftSchedule.status == 'confirmed',
        ).all()
        return shifts

    @staticmethod
    def get_employee_leaves(emp_id, month, year):
        start_date, end_date = SalaryCalculator.get_month_range(month, year)
        leaves = LeaveRequest.query.filter(
            LeaveRequest.employee_id == emp_id,
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        ).all()
        return leaves

    @staticmethod
    def compute_employee_salary(emp, month, year, logs=None, shifts=None, leaves=None):
        if logs is None:
            logs = SalaryCalculator.get_employee_attendance(emp.id, month, year)
        if shifts is None:
            shifts = SalaryCalculator.get_employee_overtime(emp.id, month, year)
        if leaves is None:
            leaves = SalaryCalculator.get_employee_leaves(emp.id, month, year)
        base = emp.base_salary
        housing = emp.housing_allowance or 0
        transport = emp.transport_allowance or 0
        others = emp.other_allowances_list
        other_total = sum(a.get('amount', 0) for a in others)
        total_allowances = housing + transport + other_total
        mult = emp.overtime_multiplier or 1.5
        total_late_m = sum(l.late_minutes or 0 for l in logs)
        absent_days = sum(1 for l in logs if l.status == 'absent')
        total_ot_hours = sum(s.overtime_hours or 0 for s in shifts)
        overtime_pay = SalaryCalculator.calculate_overtime_pay(base, total_ot_hours, mult)
        late_deduction = SalaryCalculator.calculate_late_deduction(base, total_late_m)
        absent_deduction = SalaryCalculator.calculate_absence_deduction(base, absent_days)
        total_deductions = round(late_deduction + absent_deduction, 2)
        gross = round(base + total_allowances + overtime_pay, 2)
        start_date, end_date = SalaryCalculator.get_month_range(month, year)
        work_days_count = 0
        d = start_date
        while d <= end_date:
            if d.weekday() < 5:
                work_days_count += 1
            d += timedelta(days=1)
        present_days = sum(1 for l in logs if l.status in ('present', 'late'))
        return {
            'base': base,
            'housing_allowance': housing,
            'transport_allowance': transport,
            'other_allowances': others,
            'other_total': other_total,
            'total_allowances': total_allowances,
            'overtime_hours': total_ot_hours,
            'overtime_pay': overtime_pay,
            'gross': gross,
            'late_minutes': total_late_m,
            'late_deduction': late_deduction,
            'absent_days': absent_days,
            'absent_deduction': absent_deduction,
            'total_deductions': total_deductions,
            'present_days': present_days,
            'work_days': work_days_count,
        }

    @staticmethod
    def compute_all_employees(month, year, dept=None):
        qry = Employee.query.filter_by(role='employee', is_active=True)
        if dept:
            qry = qry.filter_by(department=dept)
        employees = qry.all()
        emp_ids = [e.id for e in employees]
        start_date, end_date = SalaryCalculator.get_month_range(month, year)
        all_logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id.in_(emp_ids),
            AttendanceLog.log_date >= start_date,
            AttendanceLog.log_date <= end_date,
        ).all()
        logs_by_emp = defaultdict(list)
        for l in all_logs:
            logs_by_emp[l.employee_id].append(l)
        all_shifts = ShiftSchedule.query.filter(
            ShiftSchedule.employee_id.in_(emp_ids),
            ShiftSchedule.scheduled_date >= start_date,
            ShiftSchedule.scheduled_date <= end_date,
            ShiftSchedule.status == 'confirmed',
        ).all()
        shifts_by_emp = defaultdict(list)
        for s in all_shifts:
            shifts_by_emp[s.employee_id].append(s)
        results = []
        for emp in employees:
            comp = SalaryCalculator.compute_employee_salary(
                emp, month, year,
                logs=logs_by_emp.get(emp.id, []),
                shifts=shifts_by_emp.get(emp.id, []),
            )
            results.append({'emp': emp, 'comp': comp})
        return results

    @staticmethod
    def apply_salary_adjustment(employees, adjustment_type, value):
        results = []
        for emp in employees:
            old = emp.base_salary
            new = old
            if adjustment_type == 'percentage':
                new = round(old * (1 + value / 100), 2)
            elif adjustment_type == 'fixed':
                new = round(old + value, 2)
            elif adjustment_type == 'range_floor':
                if old < value:
                    new = value
            results.append({
                'emp_id': emp.id,
                'emp_name': emp.full_name,
                'old_salary': old,
                'new_salary': new,
                'change': round(new - old, 2),
                'change_pct': round((new - old) / old * 100, 2) if old else 0,
            })
        return results

    @staticmethod
    def preview_adjustment(month, year, dept=None, adj_type='percentage', value=0):
        employees = Employee.query.filter_by(role='employee', is_active=True)
        if dept:
            employees = employees.filter_by(department=dept)
        employees = employees.all()
        return SalaryCalculator.apply_salary_adjustment(employees, adj_type, value)
