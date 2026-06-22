"""
services/anomaly_detection.py — Anomaly detection service.
Detects unusual employee behavior patterns, sudden changes, and potential issues.
"""

import numpy as np
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import List, Dict, Optional
import json

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.employee_enhanced import (
    EmployeeLeaveRequest, LeaveType, EmployeePerformance,
    EmployeePromotion, EmployeeDisciplinaryAction,
    EmployeeExtended,
)
from models.predictions import AnomalyLog
from services.ml_models import AnomalyDetectionModel
from services.data_preprocessing import DataPreprocessor


class AnomalyDetector:

    @staticmethod
    def run_full_scan(target_date: Optional[date] = None) -> Dict:
        target_date = target_date or date.today()
        results = {
            'scan_date': target_date.isoformat(),
            'anomalies': [],
            'stats': {'total_scanned': 0, 'anomalies_found': 0},
        }
        attendance = AnomalyDetector._scan_attendance_anomalies(target_date)
        results['anomalies'].extend(attendance)
        behavioral = AnomalyDetector._scan_behavioral_anomalies(target_date)
        results['anomalies'].extend(behavioral)
        pattern = AnomalyDetector._scan_pattern_anomalies(target_date)
        results['anomalies'].extend(pattern)
        department = AnomalyDetector._scan_department_anomalies(target_date)
        results['anomalies'].extend(department)
        results['stats']['anomalies_found'] = len(results['anomalies'])
        results['stats']['total_scanned'] = Employee.query.filter_by(is_active=True).count()
        AnomalyDetector._store_anomalies(results['anomalies'], target_date)
        return results

    @staticmethod
    def _scan_attendance_anomalies(target_date: date) -> List[Dict]:
        anomalies = []
        employees = Employee.query.filter_by(is_active=True).all()
        for emp in employees:
            logs = AttendanceLog.query.filter(
                AttendanceLog.employee_id == emp.id,
                AttendanceLog.log_date >= (target_date - timedelta(days=30)),
            ).order_by(AttendanceLog.log_date.desc()).all()
            if len(logs) < 5:
                continue
            late_minutes = [(l.late_minutes or 0) for l in logs]
            avg_late = np.mean(late_minutes)
            std_late = np.std(late_minutes) if len(late_minutes) > 1 else 0
            recent_late = late_minutes[:5] if len(late_minutes) >= 5 else late_minutes
            recent_avg = np.mean(recent_late)
            if std_late > 0 and recent_avg > avg_late + 2 * std_late and recent_avg > 30:
                anomalies.append({
                    'employee_id': emp.id,
                    'employee_name': emp.full_name,
                    'department': emp.department,
                    'type': 'تأخير مفاجئ',
                    'severity': 'high' if recent_avg > 60 else 'medium',
                    'score': round(min(recent_avg / 120, 1.0), 3),
                    'detail': f'متوسط التأخير قفز من {avg_late:.0f} إلى {recent_avg:.0f} دقيقة',
                    'recommended_action': 'استدعاء الموظف للتحقيق في أسباب التأخير',
                })
            absent_count = sum(1 for l in logs if l.status == 'absent')
            if absent_count >= 3:
                anomalies.append({
                    'employee_id': emp.id,
                    'employee_name': emp.full_name,
                    'department': emp.department,
                    'type': 'غياب متكرر',
                    'severity': 'high' if absent_count >= 5 else 'medium',
                    'score': round(absent_count / 10, 3),
                    'detail': f'{absent_count} أيام غياب في آخر 30 يوم',
                    'recommended_action': 'عقد اجتماع مع الموظف ومراجعة حالته',
                })
        return anomalies

    @staticmethod
    def _scan_behavioral_anomalies(target_date: date) -> List[Dict]:
        anomalies = []
        employees = Employee.query.filter_by(is_active=True).all()
        for emp in employees:
            extended = emp.extended
            if not extended:
                continue
            last_promo = EmployeePromotion.query.filter_by(
                employee_id=emp.id, status='completed'
            ).order_by(EmployeePromotion.effective_date.desc()).first()
            if last_promo and last_promo.effective_date:
                years_since = (target_date - last_promo.effective_date).days / 365
                if years_since > 4:
                    perf = EmployeePerformance.query.filter_by(
                        employee_id=emp.id, status='completed'
                    ).order_by(EmployeePerformance.created_at.desc()).first()
                    if perf and perf.score and perf.score < 60:
                        anomalies.append({
                            'employee_id': emp.id,
                            'employee_name': emp.full_name,
                            'department': emp.department,
                            'type': 'تدهور أداء بعد تأخر ترقية',
                            'severity': 'high',
                            'score': round(min(years_since / 8, 1.0), 3),
                            'detail': f'آخر ترقية منذ {years_since:.0f} سنة والأداء {perf.score}',
                            'recommended_action': 'مراجعة عاجلة للراتب والترقية',
                        })
            recent_leaves = EmployeeLeaveRequest.query.filter(
                EmployeeLeaveRequest.employee_id == emp.id,
                EmployeeLeaveRequest.status == 'approved',
                EmployeeLeaveRequest.start_date >= (target_date - timedelta(days=30)),
            ).count()
            sick_lt = LeaveType.query.filter_by(code='sick').first()
            if sick_lt:
                sick_leaves = EmployeeLeaveRequest.query.filter(
                    EmployeeLeaveRequest.employee_id == emp.id,
                    EmployeeLeaveRequest.leave_type_id == sick_lt.id,
                    EmployeeLeaveRequest.status == 'approved',
                    EmployeeLeaveRequest.start_date >= (target_date - timedelta(days=90)),
                ).count()
                if sick_leaves > 5:
                    anomalies.append({
                        'employee_id': emp.id,
                        'employee_name': emp.full_name,
                        'department': emp.department,
                        'type': 'إجازات مرضية مفرطة',
                        'severity': 'medium',
                        'score': round(sick_leaves / 15, 3),
                        'detail': f'{sick_leaves} إجازات مرضية في 3 أشهر',
                        'recommended_action': 'تحقيق في صحة الموظف',
                    })
        return anomalies

    @staticmethod
    def _scan_pattern_anomalies(target_date: date) -> List[Dict]:
        anomalies = []
        employees = Employee.query.filter_by(is_active=True).all()
        for emp in employees:
            logs = AttendanceLog.query.filter(
                AttendanceLog.employee_id == emp.id,
                AttendanceLog.log_date >= (target_date - timedelta(days=60)),
            ).order_by(AttendanceLog.log_date).all()
            if len(logs) < 10:
                continue
            monday_absences = sum(1 for l in logs if l.log_date.weekday() == 0 and l.status == 'absent')
            friday_absences = sum(1 for l in logs if l.log_date.weekday() == 4 and l.status == 'absent')
            total_mondays = sum(1 for l in logs if l.log_date.weekday() == 0)
            total_fridays = sum(1 for l in logs if l.log_date.weekday() == 4)
            monday_rate = monday_absences / max(total_mondays, 1)
            friday_rate = friday_absences / max(total_fridays, 1)
            if monday_rate > 0.4:
                anomalies.append({
                    'employee_id': emp.id,
                    'employee_name': emp.full_name,
                    'department': emp.department,
                    'type': 'نمط غياب الأحد',
                    'severity': 'medium',
                    'score': round(monday_rate, 3),
                    'detail': f'نسبة غياب يوم الأحد {monday_rate*100:.0f}%',
                    'recommended_action': 'مناقشة جدول العمل',
                })
            if friday_rate > 0.4:
                anomalies.append({
                    'employee_id': emp.id,
                    'employee_name': emp.full_name,
                    'department': emp.department,
                    'type': 'نمط غياب الخميس',
                    'severity': 'medium',
                    'score': round(friday_rate, 3),
                    'detail': f'نسبة غياب يوم الخميس {friday_rate*100:.0f}%',
                    'recommended_action': 'مناقشة جدول العمل',
                })
        return anomalies

    @staticmethod
    def _scan_department_anomalies(target_date: date) -> List[Dict]:
        anomalies = []
        departments = db.session.query(Employee.department, db.func.count(Employee.id)).filter(
            Employee.is_active == True, Employee.department.isnot(None)
        ).group_by(Employee.department).all()
        for dept_name, total in departments:
            if total < 2:
                continue
            absent_today = AttendanceLog.query.filter(
                AttendanceLog.log_date == target_date,
                AttendanceLog.status == 'absent',
            ).join(Employee, AttendanceLog.employee_id == Employee.id).filter(
                Employee.department == dept_name
            ).count()
            dept_avg_absent = db.session.query(db.func.avg(
                AttendanceLog.id
            )).filter(
                AttendanceLog.log_date >= (target_date - timedelta(days=30)),
                AttendanceLog.status == 'absent',
            ).join(Employee, AttendanceLog.employee_id == Employee.id).filter(
                Employee.department == dept_name
            ).scalar() or 0
            if absent_today > max(2, total * 0.4):
                anomalies.append({
                    'employee_id': None,
                    'employee_name': None,
                    'department': dept_name,
                    'type': 'نسبة غياب مرتفعة في القسم',
                    'severity': 'critical',
                    'score': round(absent_today / total, 3),
                    'detail': f'{absent_today}/{total} موظف غائب اليوم في {dept_name}',
                    'recommended_action': 'إعادة توزيع مؤقتة للموظفين',
                })
        return anomalies

    @staticmethod
    def _store_anomalies(anomalies: List[Dict], target_date: date):
        for a in anomalies:
            existing = AnomalyLog.query.filter_by(
                employee_id=a.get('employee_id'),
                anomaly_type=a['type'],
                detected_date=target_date,
            ).first()
            if not existing:
                log = AnomalyLog(
                    employee_id=a.get('employee_id'),
                    anomaly_type=a['type'],
                    severity=a['severity'],
                    score=a['score'],
                    description=a['detail'],
                    detected_date=target_date,
                    metadata_json=json.dumps({
                        'department': a.get('department'),
                        'recommended_action': a.get('recommended_action'),
                    }),
                )
                db.session.add(log)
        db.session.commit()

    @staticmethod
    def get_recent_anomalies(days: int = 7) -> List[Dict]:
        logs = AnomalyLog.query.filter(
            AnomalyLog.detected_date >= (date.today() - timedelta(days=days)),
        ).order_by(AnomalyLog.score.desc()).all()
        return [{
            'id': a.id,
            'employee_id': a.employee_id,
            'anomaly_type': a.anomaly_type,
            'severity': a.severity,
            'score': a.score,
            'description': a.description,
            'detected_date': a.detected_date.isoformat() if a.detected_date else None,
            'resolved': a.resolved,
        } for a in logs]

    @staticmethod
    def get_employee_anomaly_history(employee_id: int) -> List[Dict]:
        logs = AnomalyLog.query.filter_by(employee_id=employee_id).order_by(
            AnomalyLog.detected_date.desc()
        ).limit(20).all()
        return [{
            'id': a.id,
            'type': a.anomaly_type,
            'severity': a.severity,
            'score': a.score,
            'description': a.description,
            'date': a.detected_date.isoformat() if a.detected_date else None,
            'resolved': a.resolved,
        } for a in logs]

    @staticmethod
    def resolve_anomaly(anomaly_id: int) -> bool:
        log = AnomalyLog.query.get(anomaly_id)
        if not log:
            return False
        log.resolved = True
        log.resolved_at = datetime.utcnow()
        db.session.commit()
        return True
