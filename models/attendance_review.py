from datetime import datetime, UTC
from models import db


class AttendanceReviewQueue(db.Model):
    __tablename__ = 'attendance_review_queue'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    record_id = db.Column(db.Integer, nullable=True)
    flagged_reason = db.Column(
        db.String(50), nullable=False,
        default='time_mismatch'
    )
    client_time = db.Column(db.DateTime, nullable=True)
    server_time = db.Column(db.DateTime, nullable=True)
    time_variance_minutes = db.Column(db.Float, default=0.0)
    department = db.Column(db.String(50), nullable=True)
    status = db.Column(
        db.String(30), nullable=False,
        default='pending_review'
    )
    flagged_by = db.Column(db.String(50), default='system')
    flagged_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(UTC)
    )
    reviewed_by = db.Column(
        db.Integer, db.ForeignKey('employees.id'), nullable=True
    )
    reviewed_at = db.Column(db.DateTime, nullable=True)
    admin_action = db.Column(
        db.String(30), nullable=True
    )
    adjusted_time = db.Column(db.DateTime, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    reference_type = db.Column(db.String(30), nullable=True)
    is_superseded = db.Column(db.Boolean, default=False)
    superseded_by = db.Column(db.Integer, nullable=True)
    notification_sent = db.Column(db.Boolean, default=False)

    employee = db.relationship(
        'Employee', foreign_keys=[employee_id],
        backref='review_queue_entries'
    )
    reviewer = db.relationship(
        'Employee', foreign_keys=[reviewed_by],
        backref='reviewed_entries'
    )

    FLAGGED_REASONS = [
        'time_mismatch',
        'future_time',
        'extreme_time_variance',
        'off_shift',
        'possible_duplicate',
        'device_mismatch',
        'location_outside_range',
        'biometric_mismatch',
    ]

    ADMIN_ACTIONS = [
        'approved',
        'rejected',
        'adjusted',
    ]

    REVIEW_STATUSES = [
        'pending_review',
        'reviewed',
        'escalated',
    ]

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'record_id': self.record_id,
            'flagged_reason': self.flagged_reason,
            'flagged_reason_ar': self.get_reason_arabic(),
            'client_time': self.client_time.isoformat() if self.client_time else None,
            'server_time': self.server_time.isoformat() if self.server_time else None,
            'time_variance_minutes': self.time_variance_minutes,
            'department': self.department,
            'status': self.status,
            'status_ar': 'قيد المراجعة' if self.status == 'pending_review' else 'تمت المراجعة' if self.status == 'reviewed' else 'مرفوع للإدارة',
            'flagged_by': self.flagged_by,
            'flagged_at': self.flagged_at.isoformat() if self.flagged_at else None,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'admin_action': self.admin_action,
            'admin_action_ar': self.get_action_arabic(),
            'adjusted_time': self.adjusted_time.isoformat() if self.adjusted_time else None,
            'admin_notes': self.admin_notes,
            'is_superseded': self.is_superseded,
        }

    def get_reason_arabic(self):
        labels = {
            'time_mismatch': 'تباين في الوقت',
            'future_time': 'توقيت مستقبلي',
            'extreme_time_variance': 'تباين زمني كبير',
            'off_shift': 'خارج وقت المناوبة',
            'possible_duplicate': 'مكرر محتمل',
            'device_mismatch': 'تباين في الجهاز',
            'location_outside_range': 'موقع خارج النطاق',
            'biometric_mismatch': 'تباين في البصمة',
        }
        return labels.get(self.flagged_reason, self.flagged_reason)

    def get_action_arabic(self):
        labels = {
            'approved': 'تمت الموافقة',
            'rejected': 'مرفوض',
            'adjusted': 'تم التعديل',
        }
        return labels.get(self.admin_action, self.admin_action)
