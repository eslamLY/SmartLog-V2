"""
services/prediction_service.py — Prediction generation service.
Orchestrates all ML models to generate daily predictions, custom rules,
and department-specific forecasts.
"""

import numpy as np
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Optional, List, Dict, Any
import json

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.employee_enhanced import (
    EmployeeLeaveRequest, LeaveType, EmployeePerformance,
    EmployeePromotion, EmployeeDisciplinaryAction,
    EmployeeExtended,
)
from models.predictions import (
    ModelRegistry, ModelPerformanceLog, PredictionResult,
    CustomRule, HolidayCalendar, AnomalyLog,
)
from services.ml_models import (
    MLModelRegistry, LeavePredictionModel, AbsencePredictionModel,
    TurnoverPredictionModel, TimeSeriesForecastModel,
    AnomalyDetectionModel, EmployeeSegmentationModel,
    CorrelationAnalyzer, DepartmentSpecificModel, HolidayImpactModel,
    get_model,
)
from services.data_preprocessing import DataPreprocessor
from services.recommendation_engine import RecommendationEngine


class PredictionService:

    @staticmethod
    def generate_daily_predictions(target_date: Optional[date] = None) -> Dict:
        target_date = target_date or date.today()
        employees = Employee.query.filter_by(is_active=True).all()
        results = {
            'date': target_date,
            'date_str': target_date.isoformat(),
            'generated_at': datetime.utcnow().isoformat(),
            'total_employees': len(employees),
            'leave_predictions': [],
            'absence_predictions': [],
            'turnover_predictions': [],
            'shortage_warnings': [],
            'anomalies': [],
        }
        leave_model = MLModelRegistry.get_model('leave_prediction')
        absence_model = MLModelRegistry.get_model('absence_prediction')
        turnover_model = MLModelRegistry.get_model('turnover_prediction')
        for emp in employees:
            try:
                if leave_model is not None:
                    prob = leave_model.predict_proba(emp, [target_date])[0]
                else:
                    prob = 0.0
                if prob > 0.2:
                    results['leave_predictions'].append({
                        'employee_id': emp.id,
                        'employee_name': emp.full_name,
                        'department': emp.department,
                        'probability': round(prob, 3),
                        'risk_level': 'high' if prob > 0.7 else 'medium' if prob > 0.4 else 'low',
                    })
            except Exception:
                pass
            try:
                if absence_model is not None:
                    prob = absence_model.predict_proba(emp, target_date)
                else:
                    prob = 0.0
                if prob > 0.2:
                    results['absence_predictions'].append({
                        'employee_id': emp.id,
                        'employee_name': emp.full_name,
                        'department': emp.department,
                        'risk_score': round(prob, 3),
                        'risk_level': 'high' if prob > 0.6 else 'medium' if prob > 0.35 else 'low',
                    })
            except Exception:
                pass
            try:
                if turnover_model is not None:
                    prob = turnover_model.predict_proba(emp)
                else:
                    prob = 0.0
                if prob > 0.3:
                    results['turnover_predictions'].append({
                        'employee_id': emp.id,
                        'employee_name': emp.full_name,
                        'department': emp.department,
                        'risk_score': round(prob, 3),
                        'risk_level': 'high' if prob > 0.7 else 'medium' if prob > 0.4 else 'low',
                    })
            except Exception:
                pass
        results['leave_predictions'].sort(key=lambda x: x['probability'], reverse=True)
        results['absence_predictions'].sort(key=lambda x: x['risk_score'], reverse=True)
        results['turnover_predictions'].sort(key=lambda x: x['risk_score'], reverse=True)
        shortage = PredictionService._detect_shortages(target_date)
        results['shortage_warnings'] = shortage
        anomalies = PredictionService._detect_anomalies(target_date)
        results['anomalies'] = anomalies
        PredictionService._store_predictions(results)
        return results

    @staticmethod
    def _detect_shortages(target_date: date) -> List[Dict]:
        shortages = []
        departments = db.session.query(Employee.department, db.func.count(Employee.id)).filter(
            Employee.is_active == True, Employee.department.isnot(None)
        ).group_by(Employee.department).all()
        for dept_name, total_staff in departments:
            on_leave = EmployeeLeaveRequest.query.filter(
                EmployeeLeaveRequest.status == 'approved',
                EmployeeLeaveRequest.start_date <= target_date,
                EmployeeLeaveRequest.end_date >= target_date,
            ).join(Employee, EmployeeLeaveRequest.employee_id == Employee.id).filter(
                Employee.department == dept_name
            ).count()
            absent = AttendanceLog.query.filter(
                AttendanceLog.log_date == target_date,
                AttendanceLog.status == 'absent',
            ).join(Employee, AttendanceLog.employee_id == Employee.id).filter(
                Employee.department == dept_name
            ).count()
            unavailable = on_leave + absent
            available = total_staff - unavailable
            min_required = max(1, int(total_staff * 0.6))
            if available < min_required:
                shortages.append({
                    'department': dept_name,
                    'total_staff': total_staff,
                    'available': available,
                    'min_required': min_required,
                    'gap': available - min_required,
                    'severity': 'critical' if available < min_required - 1 else 'warning',
                })
        return shortages

    @staticmethod
    def _detect_anomalies(target_date: date) -> List[Dict]:
        anomalies = []
        cutoff_30 = target_date - timedelta(days=30)
        cutoff_90 = target_date - timedelta(days=90)
        recent_logs_all = AttendanceLog.query.filter(
            AttendanceLog.log_date >= cutoff_30,
            AttendanceLog.log_date <= target_date,
        ).with_entities(
            AttendanceLog.employee_id, AttendanceLog.status,
            AttendanceLog.late_minutes, AttendanceLog.log_date,
        ).all()
        prev_logs_all = AttendanceLog.query.filter(
            AttendanceLog.log_date >= cutoff_90,
            AttendanceLog.log_date < cutoff_30,
        ).with_entities(
            AttendanceLog.employee_id, AttendanceLog.status,
        ).all()
        recent_by_emp = defaultdict(list)
        for r in recent_logs_all:
            recent_by_emp[r.employee_id].append(r)
        prev_by_emp = defaultdict(list)
        for p in prev_logs_all:
            prev_by_emp[p.employee_id].append(p)
        employees = Employee.query.filter_by(is_active=True).with_entities(
            Employee.id, Employee.full_name, Employee.department,
        ).all()
        emp_map = {e.id: e for e in employees}
        for emp_id, recent_logs in recent_by_emp.items():
            emp = emp_map.get(emp_id)
            if not emp or len(recent_logs) < 5:
                continue
            late_count = sum(1 for l in recent_logs if (l.late_minutes or 0) > 30)
            absent_count = sum(1 for l in recent_logs if l.status == 'absent')
            prev_logs = prev_by_emp.get(emp_id, [])
            prev_absent_rate = sum(1 for l in prev_logs if l.status == 'absent') / max(len(prev_logs), 1)
            recent_absent_rate = absent_count / max(len(recent_logs), 1)
            sudden_absence_increase = (
                recent_absent_rate > prev_absent_rate * 2 and recent_absent_rate > 0.3
            )
            if sudden_absence_increase or late_count > 10 or absent_count > 5:
                anomaly_type = 'غياب متكرر' if absent_count > 5 else 'تأخير متكرر'
                anomalies.append({
                    'employee_id': emp_id,
                    'employee_name': emp.full_name,
                    'department': emp.department,
                    'type': anomaly_type,
                    'severity': 'high' if (absent_count > 5 or late_count > 15) else 'medium',
                    'detail': f'{absent_count} غياب, {late_count} تأخير في آخر 30 يوم',
                    'score': round(min((absent_count * 0.2 + late_count * 0.1), 1.0), 3),
                })
        return anomalies

    @staticmethod
    def _store_predictions(results: Dict):
        pred_date = results['date']
        for p in results.get('leave_predictions', []):
            existing = PredictionResult.query.filter_by(
                employee_id=p['employee_id'],
                prediction_type='leave',
                prediction_date=pred_date,
            ).first()
            if not existing:
                db.session.add(PredictionResult(
                    employee_id=p['employee_id'],
                    prediction_type='leave',
                    prediction_date=pred_date,
                    probability=p['probability'],
                    risk_level=p['risk_level'],
                    metadata_json=json.dumps({'department': p['department']}),
                ))
        for p in results.get('absence_predictions', []):
            existing = PredictionResult.query.filter_by(
                employee_id=p['employee_id'],
                prediction_type='absence',
                prediction_date=pred_date,
            ).first()
            if not existing:
                db.session.add(PredictionResult(
                    employee_id=p['employee_id'],
                    prediction_type='absence',
                    prediction_date=pred_date,
                    probability=p['risk_score'],
                    risk_level=p['risk_level'],
                    metadata_json=json.dumps({'department': p['department']}),
                ))
        for p in results.get('turnover_predictions', []):
            existing = PredictionResult.query.filter_by(
                employee_id=p['employee_id'],
                prediction_type='turnover',
                prediction_date=pred_date,
            ).first()
            if not existing:
                db.session.add(PredictionResult(
                    employee_id=p['employee_id'],
                    prediction_type='turnover',
                    prediction_date=pred_date,
                    probability=p['risk_score'],
                    risk_level=p['risk_level'],
                    metadata_json=json.dumps({'department': p['department']}),
                ))
        db.session.commit()

    @staticmethod
    def evaluate_custom_rules() -> List[Dict]:
        alerts = []
        rules = CustomRule.query.filter_by(is_active=True).all()
        for rule in rules:
            try:
                params = json.loads(rule.rule_params or '{}')
                employees = Employee.query.filter_by(is_active=True)
                if params.get('department'):
                    employees = employees.filter_by(department=params['department'])
                employees = employees.all()
                for emp in employees:
                    triggered = PredictionService._evaluate_rule(emp, rule, params)
                    if triggered:
                        alerts.append({
                            'rule_id': rule.id,
                            'rule_name': rule.rule_name,
                            'employee_id': emp.id,
                            'employee_name': emp.full_name,
                            'department': emp.department,
                            'message': rule.alert_message or f'قاعدة {rule.rule_name} نشطة',
                            'severity': rule.severity or 'warning',
                        })
            except Exception as e:
                pass
        return alerts

    @staticmethod
    def _evaluate_rule(emp: Employee, rule: CustomRule, params: dict) -> bool:
        if rule.metric == 'absence_risk':
            from services.ai_forecasting import AIForecastingEngine
            risk = AIForecastingEngine._calculate_absence_risk(emp)
            threshold = params.get('threshold', 0.5)
            return risk > threshold
        elif rule.metric == 'leave_probability':
            from services.ai_forecasting import AIForecastingEngine
            prob = AIForecastingEngine._predict_leave_probability(emp, date.today(), date.today() + timedelta(days=30))
            threshold = params.get('threshold', 0.5)
            return prob > threshold
        elif rule.metric == 'turnover_risk':
            from services.ai_forecasting import AIForecastingEngine
            risk = AIForecastingEngine._calculate_flight_risk(emp)
            threshold = params.get('threshold', 0.6)
            return risk > threshold
        elif rule.metric == 'staffing_below':
            dept = emp.department
            total = Employee.query.filter_by(department=dept, is_active=True).count()
            on_leave = EmployeeLeaveRequest.query.filter(
                EmployeeLeaveRequest.status == 'approved',
                EmployeeLeaveRequest.start_date <= date.today(),
                EmployeeLeaveRequest.end_date >= date.today(),
            ).join(Employee, EmployeeLeaveRequest.employee_id == Employee.id).filter(
                Employee.department == dept
            ).count()
            available = total - on_leave
            pct = params.get('percentage', 60)
            return (available / max(total, 1)) * 100 < pct
        return False

    @staticmethod
    def get_department_forecast(department: str, days: int = 30) -> Dict:
        model = DepartmentSpecificModel(department)
        patterns = model.analyze_patterns()
        date_from = date.today()
        date_to = date_from + timedelta(days=days)
        employees = Employee.query.filter_by(department=department, is_active=True).all()
        leave_model = LeavePredictionModel()
        abs_model = AbsencePredictionModel()
        daily_forecast = []
        for d in DataPreprocessor.sample_dates(date_from, date_to, max_samples=days):
            leave_count = 0
            abs_count = 0
            for emp in employees:
                try:
                    feats = leave_model._extract_features(emp, d)
                    if float(np.mean(feats)) > 0.4:
                        leave_count += 1
                    abs_feats = abs_model._extract_features(emp, d)
                    if float(np.mean(abs_feats)) > 0.35:
                        abs_count += 1
                except Exception:
                    pass
            daily_forecast.append({
                'date': d.isoformat(),
                'predicted_leaves': leave_count,
                'predicted_absences': abs_count,
                'total_available': len(employees) - leave_count - abs_count,
            })
        return {
            'department': department,
            'patterns': patterns,
            'forecast': daily_forecast,
        }

    @staticmethod
    def get_holiday_impact_forecast(year: int) -> Dict:
        return HolidayImpactModel.predict_holiday_impact(year)

    @staticmethod
    def get_correlation_analysis() -> Dict:
        leave_factors = CorrelationAnalyzer.analyze_leave_factors()
        turnover_factors = CorrelationAnalyzer.analyze_turnover_factors()
        return {
            'leave_factors': leave_factors,
            'turnover_factors': turnover_factors,
        }

    @staticmethod
    def get_segmentation() -> Dict:
        model = EmployeeSegmentationModel()
        X, ids = model.build_all_features()
        if len(X) < 4:
            return {'error': 'Not enough data for segmentation'}
        metrics = model.train_kmeans(X, n_clusters=min(4, len(X) // 2))
        labels = model.get_cluster_labels()
        employees = []
        for i, emp_id in enumerate(ids):
            emp = Employee.query.get(emp_id)
            if emp:
                employees.append({
                    'employee_id': emp.id,
                    'employee_name': emp.full_name,
                    'department': emp.department,
                    'cluster': int(labels.get(i, -1)),
                })
        return {
            'metrics': metrics,
            'employees': employees,
            'n_clusters': metrics.get('n_clusters', 0),
        }

    @staticmethod
    def get_recommendations() -> List[Dict]:
        engine = RecommendationEngine()
        return engine.generate_all()
