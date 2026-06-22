"""
services/data_preprocessing.py — Data cleaning, transformation and feature engineering
for the AI forecasting system. Handles all feature extraction pipelines.
"""

import numpy as np
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import List, Optional

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.employee_enhanced import (
    EmployeeLeaveRequest, LeaveType, EmployeePerformance,
    EmployeePromotion, EmployeeDisciplinaryAction,
    EmployeeGrade, EmployeeExtended,
)
from models.shifts import ShiftSchedule


class DataPreprocessor:

    @staticmethod
    def sample_dates(date_from: date, date_to: date, max_samples: int = 60) -> List[date]:
        total_days = (date_to - date_from).days
        if total_days <= max_samples:
            return [date_from + timedelta(days=i) for i in range(total_days + 1)]
        step = max(1, total_days // max_samples)
        return [date_from + timedelta(days=i) for i in range(0, total_days + 1, step)][:max_samples]

    @staticmethod
    def get_employee_base_features(emp: Employee, target_date: date) -> List[float]:
        features = []
        if emp.hire_date:
            tenure_days = (target_date - emp.hire_date).days
            features.append(min(tenure_days / 3650, 1.0))
            features.append(1.0 if tenure_days < 365 else 0.0)
        else:
            features.extend([0.0, 0.0])
        age = 0
        if emp.date_of_birth:
            age = (target_date - emp.date_of_birth).days / 365
        features.append(min(age / 70, 1.0))
        shift_val = {'صباحي': 0.0, 'مسائي': 0.5, 'دوام كامل': 1.0}
        features.append(shift_val.get(emp.shift_type, 0.0))
        features.append(1.0 if emp.gender == 'أنثى' else 0.0)
        extended = emp.extended
        if extended:
            features.append(min((extended.years_of_experience or 0) / 30, 1.0))
            features.append(1.0 if extended.has_transportation else 0.0)
            features.append(1.0 if extended.emergency_contact_name else 0.0)
        else:
            features.extend([0.0, 0.0, 0.0])
        return features

    @staticmethod
    def get_leave_history_features(emp: Employee, target_date: date) -> List[float]:
        lookback = target_date - timedelta(days=365)
        leaves = EmployeeLeaveRequest.query.filter(
            EmployeeLeaveRequest.employee_id == emp.id,
            EmployeeLeaveRequest.status == 'approved',
            EmployeeLeaveRequest.start_date >= lookback,
            EmployeeLeaveRequest.start_date <= target_date,
        ).all()
        total_leaves = len(leaves)
        total_days = sum(lv.total_days or 1 for lv in leaves)
        months_with_leaves = len(set(lv.start_date.month for lv in leaves))
        features = [
            min(total_leaves / 20, 1.0),
            min(total_days / 60, 1.0),
            min(months_with_leaves / 12, 1.0),
        ]
        sick_lt = LeaveType.query.filter_by(code='sick').first()
        sick_count = sum(1 for lv in leaves if lv.leave_type_id == sick_lt.id) if sick_lt else 0
        annual_lt = LeaveType.query.filter_by(code='annual').first()
        annual_count = sum(1 for lv in leaves if lv.leave_type_id == annual_lt.id) if annual_lt else 0
        features.append(min(sick_count / 10, 1.0))
        features.append(min(annual_count / 15, 1.0))
        last_leave = leaves[-1] if leaves else None
        if last_leave:
            days_since = (target_date - last_leave.end_date).days
            features.append(min(days_since / 180, 1.0))
        else:
            features.append(1.0)
        return features

    @staticmethod
    def get_absence_history_features(emp: Employee, target_date: date) -> List[float]:
        lookback = target_date - timedelta(days=180)
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.log_date >= lookback,
            AttendanceLog.log_date <= target_date,
        ).all()
        total_days = len(logs)
        absent_days = sum(1 for l in logs if l.status == 'absent')
        late_days = sum(1 for l in logs if (l.late_minutes or 0) > 15)
        features = [
            min(absent_days / max(total_days, 1), 1.0),
            min(late_days / max(total_days, 1), 1.0),
            min(total_days / 180, 1.0),
        ]
        current_streak = 0
        for l in sorted(logs, key=lambda x: x.log_date, reverse=True):
            if l.status == 'absent':
                current_streak += 1
            else:
                break
        features.append(min(current_streak / 10, 1.0))
        return features

    @staticmethod
    def get_calendar_features(target_date: date) -> List[float]:
        return [
            target_date.month / 12.0,
            target_date.weekday() / 6.0,
            1.0 if target_date.month in (6, 7, 8) else 0.0,
            1.0 if target_date.weekday() in (0, 4) else 0.0,
            1.0 if target_date.weekday() >= 5 else 0.0,
        ]

    @staticmethod
    def get_department_features(department: str, target_date: date) -> List[float]:
        dept_total = Employee.query.filter_by(department=department, is_active=True).count()
        dept_leaves_today = EmployeeLeaveRequest.query.filter(
            EmployeeLeaveRequest.status == 'approved',
            EmployeeLeaveRequest.start_date <= target_date,
            EmployeeLeaveRequest.end_date >= target_date,
        ).join(Employee, EmployeeLeaveRequest.employee_id == Employee.id).filter(
            Employee.department == department
        ).count()
        return [
            min(dept_total / 50, 1.0),
            min(dept_leaves_today / max(dept_total, 1), 1.0),
        ]

    @staticmethod
    def get_attendance_pattern_features(emp: Employee, target_date: date) -> List[float]:
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.log_date >= (target_date - timedelta(days=30)),
            AttendanceLog.log_date <= target_date,
        ).all()
        if not logs:
            return [0.0, 0.0, 0.0, 0.0]
        late_minutes_avg = np.mean([l.late_minutes or 0 for l in logs])
        has_early = sum(1 for l in logs if l.clock_out and l.clock_in and
                        (l.clock_out - l.clock_in).total_seconds() < 25200)
        clock_times = []
        for l in logs:
            if l.clock_in:
                clock_times.append(l.clock_in.hour * 60 + l.clock_in.minute)
        time_std = np.std(clock_times) if len(clock_times) > 1 else 0
        return [
            min(late_minutes_avg / 60, 1.0),
            min(has_early / max(len(logs), 1), 1.0),
            min(time_std / 120, 1.0),
            min(len(logs) / 30, 1.0),
        ]

    @staticmethod
    def get_performance_features(emp: Employee) -> List[float]:
        last_eval = EmployeePerformance.query.filter_by(
            employee_id=emp.id, status='completed'
        ).order_by(EmployeePerformance.created_at.desc()).first()
        score = last_eval.score if last_eval and last_eval.score else 50
        promo = EmployeePromotion.query.filter_by(employee_id=emp.id, status='completed').count()
        last_promo = EmployeePromotion.query.filter_by(employee_id=emp.id, status='completed').order_by(
            EmployeePromotion.effective_date.desc()).first()
        years_since_promo = 5
        if last_promo and last_promo.effective_date:
            years_since_promo = (date.today() - last_promo.effective_date).days / 365
        discipline = EmployeeDisciplinaryAction.query.filter_by(employee_id=emp.id, status='active').count()
        return [
            score / 100.0,
            min(promo / 5, 1.0),
            min(years_since_promo / 10, 1.0),
            min(discipline / 5, 1.0),
        ]

    @staticmethod
    def get_turnover_features(emp: Employee) -> List[float]:
        extended = emp.extended
        has_extended = 1.0 if extended else 0.0
        has_grade = 1.0 if (extended and extended.grade_id) else 0.0
        no_end_date = 1.0 if emp.no_end_date else 0.0
        if emp.hire_date:
            tenure = (date.today() - emp.hire_date).days / 365
        else:
            tenure = 0
        if emp.contract_end_date:
            contract_remaining = (emp.contract_end_date - date.today()).days / 365
        else:
            contract_remaining = 5.0
        return [
            has_extended, has_grade, no_end_date,
            min(tenure / 20, 1.0), min(max(contract_remaining, 0) / 5, 1.0),
        ]

    @staticmethod
    def get_financial_features(emp: Employee) -> List[float]:
        extended = emp.extended
        if not emp.base_salary:
            return [0.0, 0.0, 0.0]
        salary_norm = min(float(emp.base_salary) / 10000, 1.0)
        if extended and extended.grade and extended.grade.base_salary:
            ratio = float(emp.base_salary) / float(extended.grade.base_salary)
        else:
            ratio = 1.0
        has_housing = 1.0 if (emp.housing_allowance or 0) > 0 else 0.0
        return [salary_norm, min(ratio, 2.0), has_housing]

    @staticmethod
    def clean_attendance_data() -> dict:
        stats = {'total_processed': 0, 'fixed_anomalies': 0}
        logs = AttendanceLog.query.filter(
            AttendanceLog.log_date >= (date.today() - timedelta(days=7))
        ).all()
        for log in logs:
            if log.clock_in and log.clock_out:
                duration = (log.clock_out - log.clock_in).total_seconds() / 3600
                if duration > 16:
                    log.clock_out = log.clock_in + timedelta(hours=8)
                    stats['fixed_anomalies'] += 1
                elif duration < 2 and log.status == 'present':
                    log.status = 'partial'
                    stats['fixed_anomalies'] += 1
            stats['total_processed'] += 1
        db.session.commit()
        return stats

    @staticmethod
    def build_department_weekly_pattern(dept: str) -> dict:
        employees = Employee.query.filter_by(department=dept, is_active=True).all()
        emp_ids = [e.id for e in employees]
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id.in_(emp_ids),
            AttendanceLog.log_date >= (date.today() - timedelta(days=84)),
        ).all()
        weekday_absent = defaultdict(int)
        weekday_total = defaultdict(int)
        for log in logs:
            wd = log.log_date.weekday()
            weekday_total[wd] += 1
            if log.status == 'absent':
                weekday_absent[wd] += 1
        pattern = {}
        for wd in range(7):
            total = weekday_total.get(wd, 0)
            absent = weekday_absent.get(wd, 0)
            pattern[str(wd)] = {
                'total': total, 'absent': absent,
                'rate': round(absent / max(total, 1), 3),
            }
        return {'department': dept, 'weekly_pattern': pattern}
