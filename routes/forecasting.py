"""
routes/forecasting.py — All API endpoints for the AI forecasting system.
Covers predictions, models, rules, holidays, anomalies, segmentation, reports.
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, request, session, jsonify, Response
from models import db
from models.employee import Employee
from models.predictions import CustomRule, HolidayCalendar, AnomalyLog, PredictionResult
from services.prediction_service import PredictionService
from services.anomaly_detection import AnomalyDetector
from services.ml_models import (
    HolidayImpactModel, CorrelationAnalyzer, EmployeeSegmentationModel,
    DepartmentSpecificModel, get_model,
)
from services.recommendation_engine import RecommendationEngine
from models.ml_performance import MLPerformanceTracker
from utils.decorators import admin_required
import logging
from functools import wraps

forecast_bp = Blueprint('forecast', __name__)

LOGGER = logging.getLogger(__name__)


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper


@forecast_bp.route('/admin/forecasting')
@admin_required
def forecasting_page():
    return render_template('admin/forecasting_dashboard.html')


# ─── PREDICTIONS ────────────────────────────────────────────

@forecast_bp.route('/api/forecast/generate', methods=['POST'])
@admin_required
@safe_api
def generate_predictions():
    data = request.get_json(force=True) or {}
    target = data.get('date')
    target_date = date.fromisoformat(target) if target else date.today()
    results = PredictionService.generate_daily_predictions(target_date)
    return jsonify(results)


@forecast_bp.route('/api/forecast/daily')
@admin_required
@safe_api
def get_daily_forecast():
    target = request.args.get('date')
    target_date = date.fromisoformat(target) if target else date.today()
    results = PredictionService.generate_daily_predictions(target_date)
    return jsonify(results)


@forecast_bp.route('/api/forecast/department/<dept>')
@admin_required
@safe_api
def department_forecast(dept):
    days = request.args.get('days', 30, type=int)
    return jsonify(PredictionService.get_department_forecast(dept, days))


@forecast_bp.route('/api/forecast/holiday-impact')
@admin_required
@safe_api
def holiday_impact():
    year = request.args.get('year', type=int) or date.today().year
    return jsonify(PredictionService.get_holiday_impact_forecast(year))


@forecast_bp.route('/api/forecast/correlation')
@admin_required
@safe_api
def correlation_analysis():
    return jsonify(PredictionService.get_correlation_analysis())


@forecast_bp.route('/api/forecast/segmentation')
@admin_required
@safe_api
def employee_segmentation():
    return jsonify(PredictionService.get_segmentation())


@forecast_bp.route('/api/forecast/recommendations')
@admin_required
@safe_api
def get_recommendations():
    return jsonify({'recommendations': PredictionService.get_recommendations()})


# ─── CUSTOM RULES ───────────────────────────────────────────

@forecast_bp.route('/api/forecast/rules', methods=['GET'])
@admin_required
@safe_api
def list_rules():
    rules = CustomRule.query.order_by(CustomRule.created_at.desc()).all()
    return jsonify([{
        'id': r.id, 'name': r.rule_name, 'description': r.rule_description,
        'metric': r.metric, 'threshold': r.threshold, 'severity': r.severity,
        'is_active': r.is_active, 'alert_message': r.alert_message,
    } for r in rules])


@forecast_bp.route('/api/forecast/rules', methods=['POST'])
@admin_required
@safe_api
def create_rule():
    data = request.get_json(force=True) or {}
    rule = CustomRule(
        rule_name=data.get('rule_name', 'قاعدة جديدة'),
        rule_description=data.get('description', ''),
        metric=data.get('metric', 'absence_risk'),
        condition=data.get('condition', 'greater_than'),
        threshold=data.get('threshold', 0.5),
        rule_params=data.get('params', '{}'),
        alert_message=data.get('alert_message', ''),
        severity=data.get('severity', 'warning'),
        is_active=data.get('is_active', True),
        created_by=session.get('user_id'),
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify({'success': True, 'id': rule.id})


@forecast_bp.route('/api/forecast/rules/<int:rule_id>', methods=['PUT'])
@admin_required
@safe_api
def update_rule(rule_id):
    rule = CustomRule.query.get_or_404(rule_id)
    data = request.get_json(force=True) or {}
    for field in ('rule_name', 'metric', 'condition', 'alert_message', 'severity', 'is_active'):
        if field in data:
            setattr(rule, field, data[field])
    if 'threshold' in data:
        rule.threshold = float(data['threshold'])
    if 'description' in data:
        rule.rule_description = data['description']
    db.session.commit()
    return jsonify({'success': True})


@forecast_bp.route('/api/forecast/rules/<int:rule_id>', methods=['DELETE'])
@admin_required
@safe_api
def delete_rule(rule_id):
    rule = CustomRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    return jsonify({'success': True})


@forecast_bp.route('/api/forecast/rules/evaluate')
@admin_required
@safe_api
def evaluate_rules():
    return jsonify({'alerts': PredictionService.evaluate_custom_rules()})


# ─── HOLIDAYS ──────────────────────────────────────────────

@forecast_bp.route('/api/forecast/holidays', methods=['GET'])
@admin_required
@safe_api
def list_holidays():
    year = request.args.get('year', type=int) or date.today().year
    holidays = HolidayCalendar.query.filter(
        HolidayCalendar.date >= date(year, 1, 1),
        HolidayCalendar.date <= date(year, 12, 31),
    ).order_by(HolidayCalendar.date).all()
    return jsonify([{
        'id': h.id, 'name': h.name, 'date': h.date.isoformat(),
        'type': h.type, 'is_recurring': h.is_recurring,
    } for h in holidays])


@forecast_bp.route('/api/forecast/holidays', methods=['POST'])
@admin_required
@safe_api
def add_holiday():
    data = request.get_json(force=True) or {}
    holiday = HolidayCalendar(
        name=data['name'],
        date=date.fromisoformat(data['date']),
        type=data.get('type', 'national'),
        is_recurring=data.get('is_recurring', False),
    )
    db.session.add(holiday)
    db.session.commit()
    return jsonify({'success': True, 'id': holiday.id})


@forecast_bp.route('/api/forecast/holidays/<int:holiday_id>', methods=['DELETE'])
@admin_required
@safe_api
def delete_holiday(holiday_id):
    h = HolidayCalendar.query.get_or_404(holiday_id)
    db.session.delete(h)
    db.session.commit()
    return jsonify({'success': True})


# ─── ANOMALIES ──────────────────────────────────────────────

@forecast_bp.route('/api/forecast/anomalies/scan', methods=['POST'])
@admin_required
@safe_api
def scan_anomalies():
    results = AnomalyDetector.run_full_scan()
    return jsonify(results)


@forecast_bp.route('/api/forecast/anomalies')
@admin_required
@safe_api
def list_anomalies():
    days = request.args.get('days', 7, type=int)
    return jsonify({'anomalies': AnomalyDetector.get_recent_anomalies(days)})


@forecast_bp.route('/api/forecast/anomalies/employee/<int:emp_id>')
@admin_required
@safe_api
def employee_anomalies(emp_id):
    return jsonify({'anomalies': AnomalyDetector.get_employee_anomaly_history(emp_id)})


@forecast_bp.route('/api/forecast/anomalies/<int:anomaly_id>/resolve', methods=['POST'])
@admin_required
@safe_api
def resolve_anomaly(anomaly_id):
    success = AnomalyDetector.resolve_anomaly(anomaly_id)
    return jsonify({'success': success})


# ─── MODEL PERFORMANCE ──────────────────────────────────────

@forecast_bp.route('/api/forecast/models')
@admin_required
@safe_api
def list_models():
    return jsonify({'models': MLPerformanceTracker.get_registered_models()})


@forecast_bp.route('/api/forecast/models/performance')
@admin_required
@safe_api
def model_performance():
    days = request.args.get('days', 30, type=int)
    return jsonify({'performance': MLPerformanceTracker.get_model_performance_summary(days)})


@forecast_bp.route('/api/forecast/models/<model_key>/trend')
@admin_required
@safe_api
def model_trend(model_key):
    days = request.args.get('days', 90, type=int)
    return jsonify({'trend': MLPerformanceTracker.get_accuracy_trend(model_key, days)})


@forecast_bp.route('/api/forecast/models/compute-accuracy', methods=['POST'])
@admin_required
@safe_api
def compute_accuracy():
    data = request.get_json(force=True) or {}
    model_key = data.get('model_key', 'leave_prediction')
    target = data.get('date')
    target_date = date.fromisoformat(target) if target else date.today()
    return jsonify(MLPerformanceTracker.compute_daily_accuracy(model_key, target_date))


# ─── DEPARTMENT PATTERNS ────────────────────────────────────

@forecast_bp.route('/api/forecast/departments/patterns')
@admin_required
@safe_api
def department_patterns():
    departments = db.session.query(Employee.department).filter(
        Employee.department.isnot(None), Employee.is_active == True
    ).distinct().all()
    results = []
    for (dept,) in departments:
        model = DepartmentSpecificModel(dept)
        results.append(model.analyze_patterns())
    return jsonify({'departments': results})


# ─── PREDICTION HISTORY ──────────────────────────────────

@forecast_bp.route('/api/forecast/history')
@admin_required
@safe_api
def prediction_history():
    days = request.args.get('days', 7, type=int)
    pred_type = request.args.get('type')
    cutoff = date.today() - timedelta(days=days)
    query = PredictionResult.query.filter(
        PredictionResult.prediction_date >= cutoff,
    )
    if pred_type:
        query = query.filter(PredictionResult.prediction_type == pred_type)
    results = query.order_by(PredictionResult.prediction_date.desc()).limit(200).all()
    return jsonify([{
        'id': r.id, 'employee_id': r.employee_id,
        'type': r.prediction_type, 'date': r.prediction_date.isoformat(),
        'probability': r.probability, 'risk_level': r.risk_level,
        'was_correct': r.was_correct,
    } for r in results])
