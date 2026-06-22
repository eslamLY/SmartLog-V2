#!/usr/bin/env python
"""
scripts/train_models.py — ML model training script.
Trains all forecasting models on historical data, saves to registry.
Run daily via cron/scheduler: python scripts/train_models.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, date, timedelta
import numpy as np

from app import app
from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.employee_enhanced import EmployeeLeaveRequest
from services.ml_models import (
    MLModelRegistry, LeavePredictionModel, AbsencePredictionModel,
    TurnoverPredictionModel, AnomalyDetectionModel,
    EmployeeSegmentationModel, TimeSeriesForecastModel,
)
from services.data_preprocessing import DataPreprocessor
from models.ml_performance import MLPerformanceTracker


def log(msg):
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}')


def train_leave_model():
    log('Training leave prediction model...')
    model = LeavePredictionModel()
    employees = Employee.query.filter_by(is_active=True).all()
    if len(employees) < 3:
        log('  SKIP: insufficient employees')
        return None
    date_to = date.today()
    date_from = date_to - timedelta(days=365)
    X, y = model.build_dataset(employees, date_from, date_to)
    if len(X) < 50 or len(set(y)) < 2:
        log('  SKIP: insufficient training data')
        return None
    metrics = model.train(X, y)
    MLModelRegistry.save_model('leave_prediction', model, 'RandomForest', metrics)
    log(f'  Done: accuracy={metrics["accuracy"]:.2f}, samples={metrics["n_samples"]}')
    return metrics


def train_absence_model():
    log('Training absence prediction model...')
    model = AbsencePredictionModel()
    employees = Employee.query.filter_by(is_active=True).all()
    if len(employees) < 3:
        log('  SKIP: insufficient employees')
        return None
    date_to = date.today()
    date_from = date_to - timedelta(days=180)
    X, y = model.build_dataset(employees, date_from, date_to)
    if len(X) < 50 or len(set(y)) < 2:
        log('  SKIP: insufficient training data')
        return None
    metrics = model.train(X, y)
    MLModelRegistry.save_model('absence_prediction', model, 'GradientBoosting', metrics)
    log(f'  Done: accuracy={metrics["accuracy"]:.2f}, samples={metrics["n_samples"]}')
    return metrics


def train_turnover_model():
    log('Training turnover prediction model...')
    model = TurnoverPredictionModel()
    employees = Employee.query.all()
    if len(employees) < 5:
        log('  SKIP: insufficient employees')
        return None
    X, y = model.build_dataset(employees)
    if len(X) < 10 or len(set(y)) < 2:
        log('  SKIP: insufficient training data')
        return None
    metrics = model.train(X, y)
    MLModelRegistry.save_model('turnover_prediction', model, 'RandomForest', metrics)
    log(f'  Done: accuracy={metrics["accuracy"]:.2f}, samples={metrics["n_samples"]}')
    return metrics


def train_anomaly_model():
    log('Training anomaly detection model...')
    model = AnomalyDetectionModel()
    employees = Employee.query.filter_by(is_active=True).all()
    if len(employees) < 5:
        log('  SKIP: insufficient employees')
        return None
    X, ids = model.build_all_employee_features()
    if len(X) < 5:
        log('  SKIP: insufficient feature data')
        return None
    metrics = model.train_isolation_forest(X, contamination=0.1)
    MLModelRegistry.save_model('anomaly_detection', model, 'IsolationForest', metrics)
    log(f'  Done: contamination={metrics["contamination"]}, samples={metrics["n_samples"]}')
    return metrics


def train_segmentation_model():
    log('Training employee segmentation model...')
    model = EmployeeSegmentationModel()
    employees = Employee.query.filter_by(is_active=True).all()
    if len(employees) < 5:
        log('  SKIP: insufficient employees')
        return None
    X, ids = model.build_all_features()
    if len(X) < 5:
        log('  SKIP: insufficient feature data')
        return None
    n_clusters = min(4, len(X) // 2)
    metrics = model.train_kmeans(X, n_clusters=max(2, n_clusters))
    MLModelRegistry.save_model('employee_segmentation', model, 'KMeans', metrics)
    log(f'  Done: clusters={metrics["n_clusters"]}, silhouette={metrics["silhouette_score"]:.2f}')
    return metrics


def compute_performance():
    log('Computing daily performance...')
    models = ['leave_prediction', 'absence_prediction', 'turnover_prediction']
    for key in models:
        try:
            result = MLPerformanceTracker.compute_daily_accuracy(key, date.today())
            log(f'  {key}: accuracy={result["accuracy"]:.2f}')
        except Exception as e:
            log(f'  {key}: error={e}')


def cleanup():
    log('Cleaning up old data...')
    count = MLPerformanceTracker.cleanup_old_logs(retain_days=365)
    log(f'  Removed {count} old performance logs')


def main():
    log('=' * 50)
    log('STARTING MODEL TRAINING PIPELINE')
    log('=' * 50)
    
    with app.app_context():
        train_leave_model()
        train_absence_model()
        train_turnover_model()
        train_anomaly_model()
        train_segmentation_model()
        compute_performance()
        cleanup()
    
    log('=' * 50)
    log('TRAINING PIPELINE COMPLETE')
    log('=' * 50)


if __name__ == '__main__':
    main()
