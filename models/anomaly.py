from datetime import datetime, UTC
from models import db


ANOMALY_TYPES = {
    'early_clock_in': {'label': 'حضور مبكر جداً', 'severity': 'warning'},
    'late_clock_in': {'label': 'حضور متأخر جداً', 'severity': 'warning'},
    'early_clock_out': {'label': 'انصراف مبكر جداً', 'severity': 'warning'},
    'late_clock_out': {'label': 'انصراف متأخر جداً', 'severity': 'info'},
    'unexpected_device': {'label': 'جهاز غير معتاد', 'severity': 'critical'},
    'long_break': {'label': 'استراحة طويلة', 'severity': 'warning'},
    'ghost_attendance': {'label': 'حضور وهمي', 'severity': 'critical'},
    'duplicate_punch': {'label': 'بصمة مكررة', 'severity': 'warning'},
    'off_hours_access': {'label': 'دخول خارج ساعات العمل', 'severity': 'info'},
}


class AttendanceAnomaly(db.Model):
    __tablename__ = 'attendance_anomalies'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    log_date      = db.Column(db.Date, nullable=False)
    anomaly_type  = db.Column(db.String(30), nullable=False)
    severity      = db.Column(db.String(10), default='warning')
    description   = db.Column(db.String(300))
    details       = db.Column(db.Text)
    expected_value = db.Column(db.String(50))
    actual_value   = db.Column(db.String(50))
    status        = db.Column(db.String(20), default='open')
    reviewed_by   = db.Column(db.Integer, db.ForeignKey('employees.id'))
    reviewed_at   = db.Column(db.DateTime)
    review_notes  = db.Column(db.String(300))
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee      = db.relationship('Employee', foreign_keys=[employee_id], backref='anomalies')
    reviewer      = db.relationship('Employee', foreign_keys=[reviewed_by])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else '',
            'log_date': self.log_date.isoformat() if self.log_date else None,
            'anomaly_type': self.anomaly_type,
            'anomaly_label': ANOMALY_TYPES.get(self.anomaly_type, {}).get('label', self.anomaly_type),
            'severity': self.severity,
            'description': self.description,
            'details': self.details,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EmployeePattern(db.Model):
    __tablename__ = 'employee_patterns'
    id                    = db.Column(db.Integer, primary_key=True)
    employee_id           = db.Column(db.Integer, db.ForeignKey('employees.id'), unique=True, nullable=False)
    avg_clock_in_minutes  = db.Column(db.Float)
    std_clock_in_minutes  = db.Column(db.Float)
    avg_clock_out_minutes = db.Column(db.Float)
    std_clock_out_minutes = db.Column(db.Float)
    avg_break_minutes     = db.Column(db.Float)
    std_break_minutes     = db.Column(db.Float)
    usual_device_ids      = db.Column(db.Text)
    avg_hours_worked      = db.Column(db.Float)
    std_hours_worked      = db.Column(db.Float)
    total_samples         = db.Column(db.Integer, default=0)
    last_updated          = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee              = db.relationship('Employee', backref=db.backref('attendance_pattern', uselist=False))

    def to_dict(self):
        return {
            'employee_id': self.employee_id,
            'avg_clock_in_minutes': self.avg_clock_in_minutes,
            'std_clock_in_minutes': self.std_clock_in_minutes,
            'avg_clock_out_minutes': self.avg_clock_out_minutes,
            'std_clock_out_minutes': self.std_clock_out_minutes,
            'avg_break_minutes': self.avg_break_minutes,
            'std_break_minutes': self.std_break_minutes,
            'avg_hours_worked': self.avg_hours_worked,
            'std_hours_worked': self.std_hours_worked,
            'total_samples': self.total_samples,
        }
