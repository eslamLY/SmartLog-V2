"""
models/predictions.py — Database models for AI prediction system.
Tables: ModelRegistry, ModelPerformanceLog, PredictionResult,
CustomRule, HolidayCalendar, AnomalyLog, RiskAssessment.
"""

from datetime import datetime
from models import db


class ModelRegistry(db.Model):
    __tablename__ = 'model_registry'

    id = db.Column(db.Integer, primary_key=True)
    model_key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    model_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(500))
    training_date = db.Column(db.DateTime, default=datetime.utcnow)
    metrics_json = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ModelRegistry {self.model_key}>'


class ModelPerformanceLog(db.Model):
    __tablename__ = 'model_performance_log'

    id = db.Column(db.Integer, primary_key=True)
    model_key = db.Column(db.String(100), nullable=False, index=True)
    prediction_date = db.Column(db.Date, nullable=False)
    total_predictions = db.Column(db.Integer, default=0)
    correct_predictions = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0.0)
    precision = db.Column(db.Float, default=0.0)
    recall = db.Column(db.Float, default=0.0)
    f1_score = db.Column(db.Float, default=0.0)
    training_duration_seconds = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ModelPerformanceLog {self.model_key} {self.prediction_date}>'


class PredictionResult(db.Model):
    __tablename__ = 'prediction_result'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    prediction_type = db.Column(db.String(50), nullable=False, index=True)
    prediction_date = db.Column(db.Date, nullable=False, index=True)
    probability = db.Column(db.Float, default=0.0)
    risk_level = db.Column(db.String(20), default='low')
    was_correct = db.Column(db.Boolean, default=None)
    actual_outcome = db.Column(db.String(50))
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_prediction_lookup', 'employee_id', 'prediction_type', 'prediction_date'),
    )

    def __repr__(self):
        return f'<PredictionResult {self.employee_id} {self.prediction_type} {self.prediction_date}>'


class CustomRule(db.Model):
    __tablename__ = 'custom_rule'

    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(200), nullable=False)
    rule_description = db.Column(db.Text)
    metric = db.Column(db.String(100), nullable=False)
    condition = db.Column(db.String(50), default='greater_than')
    threshold = db.Column(db.Float, default=0.5)
    rule_params = db.Column(db.Text)
    alert_message = db.Column(db.Text)
    severity = db.Column(db.String(20), default='warning')
    notification_method = db.Column(db.String(50), default='dashboard')
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CustomRule {self.rule_name}>'


class HolidayCalendar(db.Model):
    __tablename__ = 'holiday_calendar'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    type = db.Column(db.String(50), default='national')
    is_recurring = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('name', 'date', name='uq_holiday_name_date'),
    )

    def __repr__(self):
        return f'<HolidayCalendar {self.name} {self.date}>'


class AnomalyLog(db.Model):
    __tablename__ = 'anomaly_log'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, nullable=True, index=True)
    anomaly_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(20), default='medium')
    score = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    detected_date = db.Column(db.Date, nullable=False, index=True)
    metadata_json = db.Column(db.Text)
    resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AnomalyLog {self.anomaly_type} {self.detected_date}>'


class RiskAssessment(db.Model):
    __tablename__ = 'risk_assessment'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    assessment_type = db.Column(db.String(50), nullable=False)
    risk_score = db.Column(db.Float, default=0.0)
    risk_level = db.Column(db.String(20), default='low')
    factors_json = db.Column(db.Text)
    assessment_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_risk_lookup', 'employee_id', 'assessment_type', 'assessment_date'),
    )

    def __repr__(self):
        return f'<RiskAssessment {self.employee_id} {self.assessment_type}>'
