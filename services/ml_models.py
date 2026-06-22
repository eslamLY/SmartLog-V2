"""
services/ml_models.py — All ML model definitions for AI forecasting system.
Covers: Random Forest, Decision Trees, Prophet-style time series,
Isolation Forest anomaly detection, K-Means clustering, correlation analysis.
"""

import numpy as np
import pickle
import os
import json
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Optional, List, Dict, Tuple, Any

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.employee_enhanced import (
    EmployeeLeaveRequest, LeaveType, EmployeePerformance,
    EmployeePromotion, EmployeeDisciplinaryAction,
    EmployeeGrade, EmployeeExtended,
)
from models.shifts import ShiftSchedule
from models.predictions import (
    ModelRegistry, ModelPerformanceLog, PredictionResult,
    CustomRule, HolidayCalendar, AnomalyLog,
)
from services.data_preprocessing import DataPreprocessor


MODEL_STORAGE_DIR = os.path.join(os.path.dirname(__file__), '..', 'ml_models')
os.makedirs(MODEL_STORAGE_DIR, exist_ok=True)


class MLModelRegistry:
    _instances: Dict[str, Any] = {}

    @classmethod
    def get_model(cls, model_key: str):
        if model_key in cls._instances:
            return cls._instances[model_key]
        entry = ModelRegistry.query.filter_by(model_key=model_key).first()
        if not entry:
            return None
        path = entry.file_path
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                model = pickle.load(f)
                cls._instances[model_key] = model
                return model
        return None

    @classmethod
    def save_model(cls, model_key: str, model_obj: Any, model_type: str, metrics: dict):
        path = os.path.join(MODEL_STORAGE_DIR, f'{model_key}.pkl')
        with open(path, 'wb') as f:
            pickle.dump(model_obj, f)
        entry = ModelRegistry.query.filter_by(model_key=model_key).first()
        if not entry:
            entry = ModelRegistry(model_key=model_key, model_type=model_type)
            db.session.add(entry)
        entry.file_path = path
        entry.training_date = datetime.utcnow()
        entry.metrics_json = json.dumps(metrics)
        entry.is_active = True
        db.session.commit()
        cls._instances[model_key] = model_obj
        return entry


class LeavePredictionModel:
    def __init__(self):
        self.model = None
        self.feature_importances_ = None
        self.classes_ = None

    def _extract_features(self, emp: Employee, target_date: date) -> np.ndarray:
        dp = DataPreprocessor()
        features = []
        base = dp.get_employee_base_features(emp, target_date)
        features.extend(base)
        hist = dp.get_leave_history_features(emp, target_date)
        features.extend(hist)
        cal = dp.get_calendar_features(target_date)
        features.extend(cal)
        dept = dp.get_department_features(emp.department, target_date)
        features.extend(dept)
        return np.array(features, dtype=np.float32)

    def build_dataset(self, employees: List[Employee], date_from: date, date_to: date) -> Tuple[np.ndarray, np.ndarray]:
        X, y = [], []
        for emp in employees:
            leaves = EmployeeLeaveRequest.query.filter(
                EmployeeLeaveRequest.employee_id == emp.id,
                EmployeeLeaveRequest.status == 'approved',
                EmployeeLeaveRequest.start_date >= date_from,
                EmployeeLeaveRequest.start_date <= date_to,
            ).all()
            leave_dates = set()
            for lv in leaves:
                d = lv.start_date
                while d <= lv.end_date:
                    leave_dates.add(d)
                    d += timedelta(days=1)
            sampled = DataPreprocessor.sample_dates(date_from, date_to, max_samples=60)
            for d in sampled:
                feats = self._extract_features(emp, d)
                X.append(feats)
                y.append(1 if d in leave_dates else 0)
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score
        self.model = RandomForestClassifier(
            n_estimators=120, max_depth=8, min_samples_leaf=3,
            class_weight='balanced', random_state=42, n_jobs=-1
        )
        self.model.fit(X, y)
        self.feature_importances_ = self.model.feature_importances_.tolist()
        self.classes_ = self.model.classes_.tolist()
        cv_scores = cross_val_score(self.model, X, y, cv=min(3, len(np.unique(y)) - 1)) if len(set(y)) > 1 else [0.0]
        metrics = {
            'accuracy': float(self.model.score(X, y)),
            'cv_mean': float(np.mean(cv_scores)),
            'cv_std': float(np.std(cv_scores)),
            'n_samples': len(X),
            'n_features': X.shape[1],
            'feature_importances': self.feature_importances_,
        }
        return metrics

    def predict_proba(self, emp: Employee, dates: List[date]) -> List[float]:
        if not self.model:
            raise ValueError('Model not trained')
        probs = []
        for d in dates:
            feats = self._extract_features(emp, d).reshape(1, -1)
            prob = self.model.predict_proba(feats)[0]
            pos_idx = list(self.model.classes_).index(1) if 1 in self.model.classes_ else 1
            probs.append(float(prob[pos_idx]))
        return probs


class AbsencePredictionModel:
    def __init__(self):
        self.model = None
        self.feature_importances_ = None

    def _extract_features(self, emp: Employee, target_date: date) -> np.ndarray:
        dp = DataPreprocessor()
        features = dp.get_employee_base_features(emp, target_date)
        features.extend(dp.get_absence_history_features(emp, target_date))
        features.extend(dp.get_calendar_features(target_date))
        features.extend(dp.get_attendance_pattern_features(emp, target_date))
        return np.array(features, dtype=np.float32)

    def build_dataset(self, employees: List[Employee], date_from: date, date_to: date) -> Tuple[np.ndarray, np.ndarray]:
        X, y = [], []
        for emp in employees:
            logs = AttendanceLog.query.filter(
                AttendanceLog.employee_id == emp.id,
                AttendanceLog.log_date >= date_from,
                AttendanceLog.log_date <= date_to,
            ).all()
            for log in logs:
                feats = self._extract_features(emp, log.log_date)
                X.append(feats)
                y.append(1 if log.status == 'absent' else 0)
            if not logs:
                sampled = DataPreprocessor.sample_dates(date_from, date_to, max_samples=20)
                for d in sampled:
                    feats = self._extract_features(emp, d)
                    X.append(feats)
                    y.append(0)
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import cross_val_score
        self.model = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.08,
            subsample=0.8, random_state=42
        )
        self.model.fit(X, y)
        self.feature_importances_ = self.model.feature_importances_.tolist()
        cv_scores = cross_val_score(self.model, X, y, cv=min(3, len(np.unique(y)) - 1)) if len(set(y)) > 1 else [0.0]
        return {
            'accuracy': float(self.model.score(X, y)),
            'cv_mean': float(np.mean(cv_scores)),
            'cv_std': float(np.std(cv_scores)),
            'n_samples': len(X),
            'n_features': X.shape[1],
            'feature_importances': self.feature_importances_,
        }

    def predict_proba(self, emp: Employee, target_date: date) -> float:
        if not self.model:
            return 0.0
        feats = self._extract_features(emp, target_date).reshape(1, -1)
        prob = self.model.predict_proba(feats)[0]
        pos_idx = list(self.model.classes_).index(1) if 1 in self.model.classes_ else 1
        return float(prob[pos_idx])


class TurnoverPredictionModel:
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.feature_importances_ = None

    def _extract_features(self, emp: Employee) -> np.ndarray:
        dp = DataPreprocessor()
        features = dp.get_employee_base_features(emp, date.today())
        features.extend(dp.get_turnover_features(emp))
        features.extend(dp.get_performance_features(emp))
        features.extend(dp.get_financial_features(emp))
        return np.array(features, dtype=np.float32)

    def build_dataset(self, employees: List[Employee]) -> Tuple[np.ndarray, np.ndarray]:
        X, y = [], []
        for emp in employees:
            feats = self._extract_features(emp)
            is_inactive = not emp.is_active
            risk = 1 if is_inactive else 0
            recent_inactive = Employee.query.filter(
                Employee.department == emp.department,
                Employee.is_active == False,
                Employee.deleted_at >= (date.today() - timedelta(days=365)),
            ).count()
            if recent_inactive > 2:
                risk = max(risk, 1)
            X.append(feats)
            y.append(risk)
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        from sklearn.ensemble import RandomForestClassifier
        self.model = RandomForestClassifier(
            n_estimators=150, max_depth=6, min_samples_leaf=2,
            class_weight='balanced_subsample', random_state=42, n_jobs=-1
        )
        self.model.fit(X, y)
        self.feature_importances_ = self.model.feature_importances_.tolist()
        return {
            'accuracy': float(self.model.score(X, y)),
            'n_samples': len(X),
            'n_features': X.shape[1],
            'feature_importances': self.feature_importances_,
        }

    def predict_proba(self, emp: Employee) -> float:
        if not self.model:
            return 0.0
        feats = self._extract_features(emp).reshape(1, -1)
        prob = self.model.predict_proba(feats)[0]
        pos_idx = list(self.model.classes_).index(1) if 1 in self.model.classes_ else 1
        return float(prob[pos_idx])


class TimeSeriesForecastModel:
    def __init__(self):
        self.model = None
        self.params = {}

    def fit_prophet(self, df: List[Dict]) -> dict:
        try:
            from prophet import Prophet
            import pandas as pd
            pdf = pd.DataFrame(df)
            pdf.columns = ['ds', 'y']
            pdf['ds'] = pd.to_datetime(pdf['ds'])
            self.model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                seasonality_mode='multiplicative',
                changepoint_prior_scale=0.05,
            )
            self.model.add_country_holidays('LY')
            self.model.fit(pdf)
            future = self.model.make_future_dataframe(periods=60)
            forecast = self.model.predict(future)
            result = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(60).to_dict('records')
            return {
                'forecast': [{ 'ds': str(r['ds'].date()), 'yhat': float(r['yhat']),
                               'yhat_lower': float(r['yhat_lower']), 'yhat_upper': float(r['yhat_upper']) } for r in result],
                'trend': self.model.params.get('trend', None),
            }
        except ImportError:
            return self._simple_moving_average(df)

    def _simple_moving_average(self, df: List[Dict]) -> dict:
        values = [d.get('y', 0) for d in df]
        if len(values) < 2:
            return {'forecast': [], 'trend': None}
        window = max(3, len(values) // 4)
        smoothed = []
        for i in range(len(values)):
            start = max(0, i - window)
            end = min(len(values), i + window + 1)
            smoothed.append(sum(values[start:end]) / (end - start))
        last_value = smoothed[-1] if smoothed else 0
        trend = (smoothed[-1] - smoothed[-min(7, len(smoothed))]) / min(7, len(smoothed)) if len(smoothed) > 7 else 0
        forecast = []
        for i in range(1, 61):
            pred = last_value + trend * i
            forecast.append({
                'ds': (date.today() + timedelta(days=i)).isoformat(),
                'yhat': max(0, round(pred, 2)),
                'yhat_lower': max(0, round(pred * 0.8, 2)),
                'yhat_upper': round(pred * 1.2, 2),
            })
        return {'forecast': forecast, 'trend': float(trend)}


class AnomalyDetectionModel:
    def __init__(self):
        self.model = None
        self.threshold = None

    def train_isolation_forest(self, X: np.ndarray, contamination: float = 0.05) -> dict:
        from sklearn.ensemble import IsolationForest
        self.model = IsolationForest(
            n_estimators=100, contamination=contamination,
            random_state=42, n_jobs=-1
        )
        self.model.fit(X)
        scores = self.model.decision_function(X)
        self.threshold = float(np.percentile(scores, contamination * 100))
        return {
            'n_samples': len(X),
            'contamination': contamination,
            'threshold': self.threshold,
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.model:
            raise ValueError('Model not trained')
        return self.model.predict(X)

    def anomaly_score(self, X: np.ndarray) -> np.ndarray:
        if not self.model:
            return np.zeros(len(X))
        return self.model.decision_function(X)

    def build_employee_behavior_features(self, emp: Employee) -> np.ndarray:
        dp = DataPreprocessor()
        features = dp.get_employee_base_features(emp, date.today())
        recent_logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == emp.id,
            AttendanceLog.log_date >= (date.today() - timedelta(days=90)),
        ).order_by(AttendanceLog.log_date.desc()).limit(60).all()
        late_count = sum(1 for l in recent_logs if (l.late_minutes or 0) > 15)
        absent_count = sum(1 for l in recent_logs if l.status == 'absent')
        early_departure = sum(1 for l in recent_logs if l.clock_out and l.clock_in and
                              (l.clock_out - l.clock_in).total_seconds() / 3600 < 6)
        features.extend([late_count / max(len(recent_logs), 1),
                         absent_count / max(len(recent_logs), 1),
                         early_departure / max(len(recent_logs), 1),
                         float(len(recent_logs))])
        return np.array(features, dtype=np.float32)

    def build_all_employee_features(self) -> Tuple[np.ndarray, List[int]]:
        employees = Employee.query.filter_by(is_active=True).all()
        X, ids = [], []
        for emp in employees:
            try:
                feats = self.build_employee_behavior_features(emp)
                X.append(feats)
                ids.append(emp.id)
            except Exception:
                pass
        return np.array(X, dtype=np.float32), ids


class EmployeeSegmentationModel:
    def __init__(self):
        self.model = None
        self.labels_ = None
        self.cluster_centers_ = None

    def train_kmeans(self, X: np.ndarray, n_clusters: int = 4) -> dict:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.labels_ = self.model.fit_predict(X_scaled)
        self.cluster_centers_ = self.model.cluster_centers_
        from sklearn.metrics import silhouette_score
        sil = silhouette_score(X_scaled, self.labels_) if len(set(self.labels_)) > 1 else 0
        return {
            'n_clusters': n_clusters,
            'silhouette_score': float(sil),
            'inertia': float(self.model.inertia_),
            'n_samples': len(X),
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.model:
            raise ValueError('Model not trained')
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def build_segmentation_features(self, emp: Employee) -> np.ndarray:
        dp = DataPreprocessor()
        features = dp.get_employee_base_features(emp, date.today())
        features.extend(dp.get_performance_features(emp))
        features.extend(dp.get_financial_features(emp))
        tenure = (date.today() - emp.hire_date).days / 365 if emp.hire_date else 0
        features.append(tenure)
        return np.array(features, dtype=np.float32)

    def build_all_features(self) -> Tuple[np.ndarray, List[int]]:
        employees = Employee.query.filter_by(is_active=True).all()
        X, ids = [], []
        for emp in employees:
            try:
                X.append(self.build_segmentation_features(emp))
                ids.append(emp.id)
            except Exception:
                pass
        return np.array(X, dtype=np.float32), ids

    def get_cluster_labels(self) -> Dict[int, int]:
        if self.labels_ is None:
            return {}
        return {i: int(l) for i, l in enumerate(self.labels_)}


class CorrelationAnalyzer:
    @staticmethod
    def analyze_leave_factors() -> List[Dict]:
        employees = Employee.query.filter_by(is_active=True).all()
        data = []
        for emp in employees:
            leaves = EmployeeLeaveRequest.query.filter(
                EmployeeLeaveRequest.employee_id == emp.id,
                EmployeeLeaveRequest.status == 'approved',
            ).count()
            if not emp.hire_date:
                continue
            tenure = (date.today() - emp.hire_date).days / 365
            promo = EmployeePromotion.query.filter_by(employee_id=emp.id, status='completed').count()
            discipline = EmployeeDisciplinaryAction.query.filter_by(employee_id=emp.id, status='active').count()
            perf = EmployeePerformance.query.filter_by(employee_id=emp.id, status='completed').order_by(
                EmployeePerformance.created_at.desc()).first()
            perf_score = perf.score if perf and perf.score else 50
            data.append({
                'leaves': leaves, 'tenure': tenure, 'promotions': promo,
                'discipline': discipline, 'perf_score': perf_score,
                'department': emp.department,
            })
        from scipy.stats import pearsonr
        factors = []
        for field in ['tenure', 'promotions', 'discipline', 'perf_score']:
            vals = [(d['leaves'], d[field]) for d in data if d[field] is not None]
            if len(vals) > 3:
                x = [v[0] for v in vals]
                y = [v[1] for v in vals]
                corr, pval = pearsonr(x, y)
                strength = 'strong' if abs(corr) > 0.5 else 'moderate' if abs(corr) > 0.3 else 'weak'
                factors.append({
                    'factor': field,
                    'correlation': round(float(corr), 3),
                    'p_value': round(float(pval), 4),
                    'strength': strength,
                    'direction': 'positive' if corr > 0 else 'negative',
                    'interpretation': f'{field} له {"تأثير إيجابي" if corr > 0 else "تأثير سلبي"} {"قوي" if strength == "strong" else "متوسط" if strength == "moderate" else "ضعيف"} على الإجازات',
                })
        return factors

    @staticmethod
    def analyze_turnover_factors() -> List[Dict]:
        active = Employee.query.filter_by(is_active=True).all()
        inactive = Employee.query.filter_by(is_active=False).limit(20).all()
        data = []
        for emp in active + inactive:
            if not emp.hire_date:
                continue
            tenure = (date.today() - emp.hire_date).days / 365
            promo = EmployeePromotion.query.filter_by(employee_id=emp.id, status='completed').count()
            years_since_promo = 99
            last_p = EmployeePromotion.query.filter_by(employee_id=emp.id, status='completed').order_by(
                EmployeePromotion.effective_date.desc()).first()
            if last_p and last_p.effective_date:
                years_since_promo = (date.today() - last_p.effective_date).days / 365
            discipline = EmployeeDisciplinaryAction.query.filter_by(employee_id=emp.id, status='active').count()
            late_count = AttendanceLog.query.filter(
                AttendanceLog.employee_id == emp.id,
                AttendanceLog.log_date >= (date.today() - timedelta(days=90)),
                AttendanceLog.late_minutes > 15,
            ).count()
            data.append({
                'left': 1 if not emp.is_active else 0,
                'tenure': tenure, 'promotions': promo,
                'years_since_promo': years_since_promo,
                'discipline': discipline, 'late_count': late_count,
            })
        from scipy.stats import pearsonr
        factors = []
        for field in ['tenure', 'promotions', 'years_since_promo', 'discipline', 'late_count']:
            vals = [(d['left'], d[field]) for d in data if d[field] is not None]
            if len(vals) > 3:
                x = [v[0] for v in vals]
                y = [v[1] for v in vals]
                corr, pval = pearsonr(x, y)
                factors.append({
                    'factor': field.replace('_', ' '),
                    'correlation': round(float(corr), 3),
                    'p_value': round(float(pval), 4),
                    'strength': 'strong' if abs(corr) > 0.4 else 'moderate' if abs(corr) > 0.2 else 'weak',
                })
        return factors


class DepartmentSpecificModel:
    def __init__(self, department: str):
        self.department = department
        self.leave_model = LeavePredictionModel()
        self.absence_model = AbsencePredictionModel()
        self.turnover_model = TurnoverPredictionModel()
        self.patterns = {}

    def analyze_patterns(self) -> dict:
        employees = Employee.query.filter_by(department=self.department, is_active=True).all()
        total = len(employees)
        if total == 0:
            return {'department': self.department, 'error': 'لا يوجد موظفين'}
        total_leaves = 0
        weekday_dist = defaultdict(int)
        monthly_dist = defaultdict(int)
        for emp in employees:
            leaves = EmployeeLeaveRequest.query.filter(
                EmployeeLeaveRequest.employee_id == emp.id,
                EmployeeLeaveRequest.status == 'approved',
                EmployeeLeaveRequest.start_date >= (date.today() - timedelta(days=365)),
            ).all()
            for lv in leaves:
                total_leaves += lv.total_days or 1
                weekday_dist[lv.start_date.strftime('%A')] += 1
                monthly_dist[lv.start_date.strftime('%B')] += 1
        peak_weekday = max(weekday_dist, key=weekday_dist.get) if weekday_dist else None
        peak_month = max(monthly_dist, key=monthly_dist.get) if monthly_dist else None
        leave_ratio = total_leaves / max(total, 1)
        return {
            'department': self.department,
            'total_employees': total,
            'total_leaves_annual': total_leaves,
            'leave_per_employee': round(leave_ratio, 1),
            'peak_leave_weekday': peak_weekday,
            'peak_leave_month': peak_month,
            'weekday_distribution': dict(weekday_dist),
            'monthly_distribution': dict(monthly_dist),
            'recommended_model': self._recommend_model(leave_ratio, total),
        }

    def _recommend_model(self, leave_ratio: float, total: int) -> str:
        if total < 3:
            return 'rule_based'
        if leave_ratio > 2:
            return 'random_forest'
        if total > 10:
            return 'gradient_boosting'
        return 'random_forest'


class HolidayImpactModel:
    HOLIDAYS_LY = [
        {'date': '01-01', 'name': 'رأس السنة', 'type': 'national'},
        {'date': '02-17', 'name': 'ثورة 17 فبراير', 'type': 'national'},
        {'date': '05-01', 'name': 'عيد العمال', 'type': 'national'},
        {'date': '09-01', 'name': 'يوم الجماهيرية', 'type': 'national'},
        {'date': '10-07', 'name': 'عيد الجلاء', 'type': 'national'},
        {'date': '12-24', 'name': 'عيد الاستقلال', 'type': 'national'},
    ]

    MOVABLE_HOLIDAYS = [
        {'name': 'عيد الفطر', 'type': 'religious', 'days': 3},
        {'name': 'عيد الأضحى', 'type': 'religious', 'days': 4},
        {'name': 'رأس السنة الهجرية', 'type': 'religious', 'days': 1},
        {'name': 'المولد النبوي', 'type': 'religious', 'days': 1},
        {'name': 'رمضان', 'type': 'religious', 'days': 30},
    ]

    @staticmethod
    def get_holidays_for_year(year: int) -> List[Dict]:
        holidays = []
        for h in HolidayImpactModel.HOLIDAYS_LY:
            d = date(year, int(h['date'].split('-')[0]), int(h['date'].split('-')[1]))
            holidays.append({'date': d.isoformat(), 'name': h['name'], 'type': h['type']})
        db_holidays = HolidayCalendar.query.filter(
            HolidayCalendar.date >= date(year, 1, 1),
            HolidayCalendar.date <= date(year, 12, 31),
        ).all()
        for h in db_holidays:
            holidays.append({'date': h.date.isoformat(), 'name': h.name, 'type': h.type})
        return holidays

    @staticmethod
    def predict_holiday_impact(year: int) -> Dict:
        holidays = HolidayImpactModel.get_holidays_for_year(year)
        total_employees = Employee.query.filter_by(is_active=True).count()
        impacts = []
        for h in holidays:
            h_date = date.fromisoformat(h['date'])
            predicted_leaves = 0
            if h['type'] == 'national':
                predicted_leaves = int(total_employees * 0.85)
            elif h['type'] == 'religious':
                predicted_leaves = int(total_employees * 0.70)
            else:
                predicted_leaves = int(total_employees * 0.30)
            impacts.append({
                'date': h['date'],
                'name': h['name'],
                'type': h['type'],
                'predicted_absent': predicted_leaves,
                'available': total_employees - predicted_leaves,
                'severity': 'critical' if predicted_leaves > total_employees * 0.8 else 'warning' if predicted_leaves > total_employees * 0.5 else 'normal',
            })
        return {'year': year, 'holidays': impacts, 'total_employees': total_employees}


def get_model(model_key: str):
    registry = {
        'leave_prediction': LeavePredictionModel,
        'absence_prediction': AbsencePredictionModel,
        'turnover_prediction': TurnoverPredictionModel,
        'time_series_forecast': TimeSeriesForecastModel,
        'anomaly_detection': AnomalyDetectionModel,
        'employee_segmentation': EmployeeSegmentationModel,
    }
    cls = registry.get(model_key)
    if not cls:
        return None
    return cls()
