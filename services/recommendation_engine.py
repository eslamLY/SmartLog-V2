"""
services/recommendation_engine.py — AI recommendation engine.
Generates smart, context-aware recommendations based on all prediction models,
anomaly detection, custom rules, and historical trends.
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
from models.predictions import PredictionResult, CustomRule, AnomalyLog


class RecommendationEngine:

    def __init__(self):
        self.recommendations = []

    def generate_all(self) -> List[Dict]:
        self.recommendations = []
        self._check_staffing_shortages()
        self._check_turnover_risks()
        self._check_absence_patterns()
        self._check_leave_peaks()
        self._check_anomalies()
        self._check_hiring_needs()
        self._check_department_risks()
        self._check_holiday_impact()
        self._check_training_needs()
        self.recommendations.sort(key=lambda r: self._priority_score(r), reverse=True)
        return self.recommendations

    def _priority_score(self, rec: dict) -> float:
        scores = {'critical': 100, 'high': 70, 'medium': 40, 'low': 10}
        return scores.get(rec.get('severity', 'low'), 0) + (rec.get('confidence', 0) or 0)

    def _check_staffing_shortages(self):
        today = date.today()
        departments = db.session.query(Employee.department, db.func.count(Employee.id)).filter(
            Employee.is_active == True, Employee.department.isnot(None)
        ).group_by(Employee.department).all()
        for dept_name, total in departments:
            on_leave = EmployeeLeaveRequest.query.filter(
                EmployeeLeaveRequest.status == 'approved',
                EmployeeLeaveRequest.start_date <= today,
                EmployeeLeaveRequest.end_date >= today,
            ).join(Employee, EmployeeLeaveRequest.employee_id == Employee.id).filter(
                Employee.department == dept_name
            ).count()
            absent = AttendanceLog.query.filter(
                AttendanceLog.log_date == today,
                AttendanceLog.status == 'absent',
            ).join(Employee, AttendanceLog.employee_id == Employee.id).filter(
                Employee.department == dept_name
            ).count()
            available = total - on_leave - absent
            min_req = max(1, int(total * 0.6))
            if available < min_req:
                self.recommendations.append({
                    'category': 'توزيع الموظفين',
                    'title': f'نقص في {dept_name}: {available}/{min_req}',
                    'message': f'التوفر حالياً {available} من أصل {total} (الحد الأدنى {min_req})',
                    'severity': 'critical' if available < min_req - 1 else 'high',
                    'confidence': 92,
                    'action': 'إعادة توزيع',
                    'action_url': '/admin/shifts',
                    'icon': '⚠️',
                })

    def _check_turnover_risks(self):
        high_risk_preds = PredictionResult.query.filter(
            PredictionResult.prediction_type == 'turnover',
            PredictionResult.prediction_date == date.today(),
            PredictionResult.risk_level == 'high',
        ).all()
        for pred in high_risk_preds[:5]:
            emp = Employee.query.get(pred.employee_id)
            if not emp:
                continue
            self.recommendations.append({
                'category': 'الاحتفاظ بالموظفين',
                'title': f'{emp.full_name} — خطر رحيل مرتفع',
                'message': f'احتمالية {pred.probability*100:.0f}%. يوصى باتخاذ إجراءات فورية.',
                'severity': 'critical' if pred.probability > 0.8 else 'high',
                'confidence': round(min(0.5 + pred.probability * 0.5, 0.95) * 100),
                'action': 'خطة الاحتفاظ',
                'action_url': f'/admin/employees/{emp.id}/profile',
                'icon': '🔴',
            })

    def _check_absence_patterns(self):
        today = date.today()
        if today.weekday() == 0:
            emp_count = Employee.query.filter_by(is_active=True).count()
            high_risk_count = PredictionResult.query.filter(
                PredictionResult.prediction_type == 'absence',
                PredictionResult.prediction_date == today,
                PredictionResult.risk_level == 'high',
            ).count()
            if high_risk_count > max(1, emp_count * 0.15):
                self.recommendations.append({
                    'category': 'الموارد البشرية',
                    'title': 'تحذير: غياب متوقع مرتفع اليوم',
                    'message': f'{high_risk_count} موظف في خطر غياب مرتفع اليوم',
                    'severity': 'high',
                    'confidence': 85,
                    'action': 'عرض التفاصيل',
                    'action_url': '/admin/ai-forecast',
                    'icon': '📅',
                })

    def _check_leave_peaks(self):
        today = date.today()
        month_end = date(today.year, today.month + 1, 1) - timedelta(days=1) if today.month < 12 else date(today.year, 12, 31)
        predictions = PredictionResult.query.filter(
            PredictionResult.prediction_type == 'leave',
            PredictionResult.prediction_date >= today,
            PredictionResult.prediction_date <= month_end,
            PredictionResult.risk_level == 'high',
        ).all()
        by_date = defaultdict(int)
        for p in predictions:
            by_date[p.prediction_date] += 1
        for d, count in sorted(by_date.items(), key=lambda x: x[1], reverse=True)[:3]:
            if count > 2:
                self.recommendations.append({
                    'category': 'التخطيط للإجازات',
                    'title': f'ذروة إجازات متوقعة {d.isoformat()}',
                    'message': f'{count} موظف في إجازة في هذا التاريخ',
                    'severity': 'medium' if count < 5 else 'high',
                    'confidence': 82,
                    'action': 'إدارة الإجازات',
                    'action_url': '/admin/leaves',
                    'icon': '📊',
                })

    def _check_anomalies(self):
        recent = AnomalyLog.query.filter(
            AnomalyLog.detected_date >= (date.today() - timedelta(days=3)),
            AnomalyLog.resolved == False,
        ).order_by(AnomalyLog.score.desc()).limit(5).all()
        for a in recent:
            emp = Employee.query.get(a.employee_id) if a.employee_id else None
            name = emp.full_name if emp else a.anomaly_type
            self.recommendations.append({
                'category': 'المراقبة',
                'title': f'شذوذ: {a.anomaly_type}',
                'message': f'{name}: {a.description}',
                'severity': a.severity or 'medium',
                'confidence': 78,
                'action': 'حل',
                'action_url': f'/admin/ai-forecast?tab=anomalies',
                'icon': '🚨',
            })

    def _check_hiring_needs(self):
        total = Employee.query.filter_by(is_active=True).count()
        upcoming_retirements = EmployeeExtended.query.filter(
            EmployeeExtended.retirement_age.isnot(None),
        ).count()
        if upcoming_retirements > 0:
            self.recommendations.append({
                'category': 'التوظيف',
                'title': f'{upcoming_retirements} موظف يقترب من التقاعد',
                'message': 'يوصى ببدء عملية التوظيف للتعويض',
                'severity': 'medium',
                'confidence': 80,
                'action': 'خطة التوظيف',
                'action_url': '/admin/employee-analytics',
                'icon': '💼',
            })

    def _check_department_risks(self):
        departments = db.session.query(Employee.department, db.func.count(Employee.id)).filter(
            Employee.is_active == True, Employee.department.isnot(None)
        ).group_by(Employee.department).all()
        for dept_name, total in departments:
            if total < 2:
                continue
            high_risk = PredictionResult.query.filter(
                PredictionResult.prediction_type == 'turnover',
                PredictionResult.prediction_date == date.today(),
                PredictionResult.risk_level == 'high',
            ).join(Employee, PredictionResult.employee_id == Employee.id).filter(
                Employee.department == dept_name
            ).count()
            if high_risk > max(1, total * 0.3):
                self.recommendations.append({
                    'category': 'المخاطر',
                    'title': f'مخاطر تركز في {dept_name}',
                    'message': f'{high_risk} موظف في القسم معرضون لخطر الرحيل',
                    'severity': 'high',
                    'confidence': 75,
                    'action': 'تحليل القسم',
                    'action_url': '/admin/employee-analytics',
                    'icon': '📉',
                })

    def _check_holiday_impact(self):
        from services.ml_models import HolidayImpactModel
        impact = HolidayImpactModel.predict_holiday_impact(date.today().year)
        upcoming = [h for h in impact.get('holidays', []) if h.get('date', '') >= date.today().isoformat()][:3]
        for h in upcoming:
            if h.get('severity') == 'critical':
                self.recommendations.append({
                    'category': 'الإجازات الرسمية',
                    'title': f'تأثير {h["name"]} على الموارد',
                    'message': f'غياب متوقع {h["predicted_absent"]} موظف ({h["available"]} متاحون)',
                    'severity': 'high',
                    'confidence': 90,
                    'action': 'استعدادات',
                    'action_url': '/admin/shifts',
                    'icon': '🎉',
                })

    def _check_training_needs(self):
        low_perf = EmployeePerformance.query.filter(
            EmployeePerformance.status == 'completed',
            EmployeePerformance.score < 50,
        ).join(EmployeePerformance.employee).filter(
            Employee.is_active == True,
        ).count()
        if low_perf > 2:
            self.recommendations.append({
                'category': 'التطوير',
                'title': f'{low_perf} موظف يحتاجون تدريباً',
                'message': 'تقييم أداء منخفض — يوصى بخطة تدريبية',
                'severity': 'low',
                'confidence': 65,
                'action': 'برنامج تدريبي',
                'action_url': '/admin/employee-training',
                'icon': '📚',
            })
