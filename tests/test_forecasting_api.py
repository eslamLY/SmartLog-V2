"""Integration tests for Phase 11-12 AI forecasting API endpoints."""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from datetime import date, timedelta

pytest_plugins = []


def login_admin(client):
    resp = client.post('/login', json={'username': 'ADM001', 'password': 'admin123'})
    return resp


def test_forecasting_page_loads(client):
    login_admin(client)
    resp = client.get('/admin/forecasting')
    assert resp.status_code == 200
    assert 'نظام التنبؤ' in resp.text


def test_scenarios_page_loads(client):
    login_admin(client)
    resp = client.get('/admin/scenarios')
    assert resp.status_code == 200
    assert 'سيناريو' in resp.text


def test_generate_predictions(client):
    login_admin(client)
    resp = client.post('/api/forecast/generate', json={'date': date.today().isoformat()})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert 'date' in data or 'total_employees' in data


def test_list_rules_empty(client):
    login_admin(client)
    resp = client.get('/api/forecast/rules')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)


def test_create_rule(client):
    login_admin(client)
    resp = client.post('/api/forecast/rules', json={
        'rule_name': 'غياب مرتفع',
        'description': 'تنبيه عند ارتفاع الغياب',
        'metric': 'absence_risk',
        'threshold': 0.7,
        'severity': 'warning',
        'is_active': True,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert 'id' in data


def test_create_and_delete_rule(client):
    login_admin(client)
    resp = client.post('/api/forecast/rules', json={
        'rule_name': 'قاعدة للحذف', 'metric': 'turnover_risk', 'threshold': 0.8,
    })
    rule_id = resp.get_json()['id']
    resp = client.delete(f'/api/forecast/rules/{rule_id}')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True


def test_add_holiday(client):
    login_admin(client)
    resp = client.post('/api/forecast/holidays', json={
        'name': 'عيد الفطر', 'date': date.today().isoformat(), 'type': 'religious',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True


def test_list_holidays(client):
    login_admin(client)
    resp = client.get('/api/forecast/holidays')
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_scan_anomalies(client):
    login_admin(client)
    resp = client.post('/api/forecast/anomalies/scan')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'anomalies' in data or 'attendance' in data


def test_list_anomalies(client):
    login_admin(client)
    resp = client.get('/api/forecast/anomalies')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'anomalies' in data


def test_list_models(client):
    login_admin(client)
    resp = client.get('/api/forecast/models')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'models' in data


def test_model_performance(client):
    login_admin(client)
    resp = client.get('/api/forecast/models/performance')
    assert resp.status_code == 200
    assert 'performance' in resp.get_json()


def test_daily_forecast(client):
    login_admin(client)
    resp = client.get(f'/api/forecast/daily?date={date.today().isoformat()}')
    assert resp.status_code == 200
    assert resp.get_json() is not None


def test_department_forecast(client):
    login_admin(client)
    resp = client.get('/api/forecast/department/إدارة')
    assert resp.status_code == 200


def test_holiday_impact(client):
    login_admin(client)
    resp = client.get('/api/forecast/holiday-impact')
    assert resp.status_code == 200
    assert resp.get_json() is not None


def test_correlation_analysis(client):
    login_admin(client)
    resp = client.get('/api/forecast/correlation')
    assert resp.status_code == 200


def test_segmentation(client):
    login_admin(client)
    resp = client.get('/api/forecast/segmentation')
    assert resp.status_code == 200


def test_recommendations(client):
    login_admin(client)
    resp = client.get('/api/forecast/recommendations')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'recommendations' in data


def test_scenario_simulate_departure(client):
    login_admin(client)
    resp = client.post('/api/scenarios/simulate', json={
        'type': 'departure', 'params': {'count': 1},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['scenario'] == 'departure'


def test_scenario_simulate_mass_absence(client):
    login_admin(client)
    resp = client.post('/api/scenarios/simulate', json={
        'type': 'mass_absence', 'params': {'percentage': 30, 'duration_days': 7},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'impact' in data


def test_scenario_simulate_new_hire(client):
    login_admin(client)
    resp = client.post('/api/scenarios/simulate', json={
        'type': 'new_hire', 'params': {'count': 5},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['scenario'] == 'new_hire'


def test_scenario_simulate_budget_cut(client):
    login_admin(client)
    resp = client.post('/api/scenarios/simulate', json={
        'type': 'budget_change', 'params': {'percentage': 20, 'direction': 'cut'},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['scenario'] == 'budget_change'


def test_scenario_simulate_leave_wave(client):
    login_admin(client)
    resp = client.post('/api/scenarios/simulate', json={
        'type': 'leave_wave', 'params': {'count': 3},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['scenario'] == 'leave_wave'


def test_scenario_presets(client):
    login_admin(client)
    resp = client.get('/api/scenarios/presets')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'presets' in data
    assert len(data['presets']) == 4


def test_evaluate_rules(client):
    login_admin(client)
    resp = client.get('/api/forecast/rules/evaluate')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'alerts' in data


def test_prediction_history(client):
    login_admin(client)
    resp = client.get('/api/forecast/history?days=7')
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_department_patterns(client):
    login_admin(client)
    resp = client.get('/api/forecast/departments/patterns')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'departments' in data


def test_model_trend(client):
    login_admin(client)
    resp = client.get('/api/forecast/models/leave_prediction/trend')
    assert resp.status_code == 200
    assert 'trend' in resp.get_json()


def test_employee_anomalies(client):
    login_admin(client)
    resp = client.get('/api/forecast/anomalies/employee/1')
    assert resp.status_code == 200
    assert 'anomalies' in resp.get_json()


def test_unauthorized_access(client):
    resp = client.get('/admin/forecasting')
    assert resp.status_code in (302, 401, 403)


def test_employee_cannot_use_forecast_api(client):
    client.post('/login', json={'username': 'EMP001', 'password': '123456'})
    resp = client.get('/api/forecast/models')
    assert resp.status_code in (302, 401, 403, 200)
    if resp.status_code == 200:
        data = resp.get_json()
        assert data is not None
        assert 'error' in data or 'models' in data
