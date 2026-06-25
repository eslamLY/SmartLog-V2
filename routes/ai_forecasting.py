from datetime import date, timedelta
from flask import Blueprint, render_template, request, session, jsonify, Response
from models import db, Employee
from models.employee_enhanced import EmployeeLeaveRequest, EmployeePerformance, EmployeePromotion
from services.ai_forecasting import AIForecastingEngine
from utils.decorators import admin_required
import logging
from functools import wraps

LOGGER = logging.getLogger(__name__)
ai_forecast_bp = Blueprint('ai_forecast', __name__)

def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper



@ai_forecast_bp.route('/admin/ai-forecast')
@admin_required
def ai_forecast_page():
    now = date.today()
    return render_template('admin/ai_forecasting.html',
                           current_year=now.year,
                           current_month=now.month,
                           current_day=now.day)


# ─── MASTER ──────────────────────────────────────────────────

@ai_forecast_bp.route('/api/ai/master-forecast')
@safe_api
@admin_required
def master_forecast():
    forecast = AIForecastingEngine.get_master_forecast()
    forecast['recommendations'] = AIForecastingEngine.get_recommendations()
    return jsonify(forecast)


# ─── CORE FORECASTS ──────────────────────────────────────────

@ai_forecast_bp.route('/api/ai/leave-forecast')
@safe_api
@admin_required
def leave_forecast():
    days = request.args.get('days', 30, type=int)
    dept = request.args.get('department')
    date_from = date.today()
    date_to = date_from + timedelta(days=days)
    return jsonify(AIForecastingEngine.get_leave_forecast_summary(date_from, date_to))


@ai_forecast_bp.route('/api/ai/absence-forecast')
@safe_api
@admin_required
def absence_forecast():
    days = request.args.get('days', 14, type=int)
    dept = request.args.get('department')
    date_from = date.today()
    date_to = date_from + timedelta(days=days)
    return jsonify(AIForecastingEngine.get_absence_forecast_summary(date_from, date_to))


@ai_forecast_bp.route('/api/ai/shortage-forecast')
@safe_api
@admin_required
def shortage_forecast():
    days = request.args.get('days', 30, type=int)
    date_from = date.today()
    date_to = date_from + timedelta(days=days)
    return jsonify(AIForecastingEngine.predict_shortages(date_from, date_to))


@ai_forecast_bp.route('/api/ai/turnover-forecast')
@safe_api
@admin_required
def turnover_forecast():
    return jsonify(AIForecastingEngine.get_turnover_summary())


@ai_forecast_bp.route('/api/ai/hiring-forecast')
@safe_api
@admin_required
def hiring_forecast():
    months = request.args.get('months', 6, type=int)
    return jsonify(AIForecastingEngine.predict_hiring_needs(months))


@ai_forecast_bp.route('/api/ai/daily-forecast')
@safe_api
@admin_required
def daily_forecast():
    target = request.args.get('date')
    if target:
        try:
            target_date = date.fromisoformat(target)
        except (ValueError, TypeError):
            target_date = date.today()
    else:
        target_date = date.today()
    return jsonify(AIForecastingEngine.get_daily_forecast(target_date))


@ai_forecast_bp.route('/api/ai/calendar')
@safe_api
@admin_required
def calendar_forecast():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    return jsonify(AIForecastingEngine.generate_calendar(year, month))


@ai_forecast_bp.route('/api/ai/recommendations')
@safe_api
@admin_required
def recommendations():
    return jsonify({'recommendations': AIForecastingEngine.get_recommendations()})


# ─── PHASE 4: ADVANCED PREDICTION DETAILS ────────────────────

@ai_forecast_bp.route('/api/ai/employee/<int:emp_id>/leave-detail')
@safe_api
@admin_required
def employee_leave_detail(emp_id):
    return jsonify(AIForecastingEngine.get_employee_leave_detail(emp_id))


@ai_forecast_bp.route('/api/ai/employee/<int:emp_id>/absence-detail')
@safe_api
@admin_required
def employee_absence_detail(emp_id):
    return jsonify(AIForecastingEngine.get_employee_absence_detail(emp_id))


@ai_forecast_bp.route('/api/ai/employee/<int:emp_id>/turnover-detail')
@safe_api
@admin_required
def employee_turnover_detail(emp_id):
    return jsonify(AIForecastingEngine.get_employee_turnover_detail(emp_id))


# ─── PHASE 5: WHAT-IF SCENARIO ANALYSIS ────────────────────

@ai_forecast_bp.route('/api/ai/simulate', methods=['POST'])
@safe_api
@admin_required
def simulate_scenario():
    data = request.get_json(force=True) or {}
    scenario_type = data.get('scenario_type', 'employee_departure')
    params = data.get('params', {})
    return jsonify(AIForecastingEngine.simulate_scenario(scenario_type, params))


# ─── PHASE 6: SMART RECOMMENDATIONS ───────────────────────

@ai_forecast_bp.route('/api/ai/smart-recommendations')
@safe_api
@admin_required
def smart_recommendations():
    return jsonify({'recommendations': AIForecastingEngine.get_smart_recommendations()})


# ─── PHASE 7: HISTORICAL TRENDS ───────────────────────────

@ai_forecast_bp.route('/api/ai/trends/leave')
@safe_api
@admin_required
def leave_trends():
    months = request.args.get('months', 12, type=int)
    return jsonify(AIForecastingEngine.get_leave_trends(months))


@ai_forecast_bp.route('/api/ai/trends/absence')
@safe_api
@admin_required
def absence_trends():
    months = request.args.get('months', 6, type=int)
    return jsonify(AIForecastingEngine.get_absence_trends(months))


@ai_forecast_bp.route('/api/ai/trends/turnover')
@safe_api
@admin_required
def turnover_trends():
    months = request.args.get('months', 12, type=int)
    return jsonify(AIForecastingEngine.get_turnover_trends(months))


@ai_forecast_bp.route('/api/ai/trends/staffing')
@safe_api
@admin_required
def staffing_trends():
    months = request.args.get('months', 6, type=int)
    return jsonify(AIForecastingEngine.get_staffing_trends(months))


# ─── PHASE 8: REAL-TIME MONITORING ─────────────────────────

@ai_forecast_bp.route('/api/ai/live-status')
@safe_api
@admin_required
def live_status():
    return jsonify(AIForecastingEngine.get_live_status())


# ─── PHASE 9: EXPORT & REPORTING ─────────────────────────

@ai_forecast_bp.route('/api/ai/report/csv')
@safe_api
@admin_required
def report_csv():
    report_type = request.args.get('type', 'executive_summary')
    emp_id = request.args.get('employee_id', type=int)
    csv_data = AIForecastingEngine.generate_csv_report(report_type, employee_id=emp_id)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=ai_report_{report_type}_{date.today().isoformat()}.csv'},
    )


@ai_forecast_bp.route('/api/ai/report/data')
@safe_api
@admin_required
def report_data():
    report_type = request.args.get('type', 'executive_summary')
    emp_id = request.args.get('employee_id', type=int)
    return jsonify(AIForecastingEngine.generate_report_data(report_type, employee_id=emp_id))


# ─── PHASE 10: ML ACCURACY ─────────────────────────────────

@ai_forecast_bp.route('/api/ai/model-performance')
@safe_api
@admin_required
def model_performance():
    return jsonify(AIForecastingEngine.get_model_performance())
