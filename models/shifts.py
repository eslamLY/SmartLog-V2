from datetime import datetime, date, UTC
from models import db


class ShiftType(db.Model):
    __tablename__ = 'shift_types'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), nullable=False)
    start_hour  = db.Column(db.Integer, nullable=False, default=8)
    start_min   = db.Column(db.Integer, default=0)
    end_hour    = db.Column(db.Integer, nullable=False, default=16)
    end_min     = db.Column(db.Integer, default=0)
    color       = db.Column(db.String(10), default='#3b82f6')
    description = db.Column(db.String(200), nullable=True)
    min_staff   = db.Column(db.Integer, default=1)
    max_staff   = db.Column(db.Integer, default=10)
    is_overnight= db.Column(db.Boolean, default=False)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    schedules   = db.relationship('ShiftSchedule', backref='shift_type', lazy=True)

    @property
    def duration_hours(self):
        s = self.start_hour * 60 + self.start_min
        e = self.end_hour   * 60 + self.end_min
        if e <= s: e += 1440
        return round((e - s) / 60, 1)

    @property
    def time_range(self):
        return f"{self.start_hour:02d}:{self.start_min:02d} – {self.end_hour:02d}:{self.end_min:02d}"


class ShiftSchedule(db.Model):
    __tablename__ = 'shift_schedules'
    id                  = db.Column(db.Integer, primary_key=True)
    employee_id         = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    shift_type_id       = db.Column(db.Integer, db.ForeignKey('shift_types.id'), nullable=False)
    scheduled_date      = db.Column(db.Date, nullable=False)
    status              = db.Column(db.String(20), default='confirmed')
    notes               = db.Column(db.String(200), nullable=True)
    overtime_hours      = db.Column(db.Float, default=0.0)
    created_by          = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at          = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    original_employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    conflict_status     = db.Column(db.String(20), default='ok')
    substituted_by      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    substituted_at      = db.Column(db.DateTime, nullable=True)

    emp                 = db.relationship('Employee', foreign_keys=[employee_id], backref='shift_schedules')
    creator             = db.relationship('Employee', foreign_keys=[created_by])
    original_employee   = db.relationship('Employee', foreign_keys=[original_employee_id])
    substitute_approver = db.relationship('Employee', foreign_keys=[substituted_by])


class ShiftSwapRequest(db.Model):
    __tablename__    = 'shift_swap_requests'
    id               = db.Column(db.Integer, primary_key=True)
    requester_id     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    target_id        = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    req_sched_id     = db.Column(db.Integer, db.ForeignKey('shift_schedules.id'), nullable=True)
    tgt_sched_id     = db.Column(db.Integer, db.ForeignKey('shift_schedules.id'), nullable=True)
    scheduled_date   = db.Column(db.Date, nullable=True)
    swap_type        = db.Column(db.String(20), default='peer')
    substitute_employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    reason           = db.Column(db.Text, nullable=True)
    status           = db.Column(db.String(30), default='pending')
    target_response  = db.Column(db.String(20), nullable=True)
    admin_notes      = db.Column(db.String(300), nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    requester     = db.relationship('Employee', foreign_keys=[requester_id], backref='swap_requests_sent')
    target        = db.relationship('Employee', foreign_keys=[target_id], backref='swap_requests_recv')
    req_sched     = db.relationship('ShiftSchedule', foreign_keys=[req_sched_id])
    tgt_sched     = db.relationship('ShiftSchedule', foreign_keys=[tgt_sched_id])
    substitute    = db.relationship('Employee', foreign_keys=[substitute_employee_id])


class ShiftCoverageRule(db.Model):
    __tablename__ = 'shift_coverage_rules'
    id            = db.Column(db.Integer, primary_key=True)
    shift_type_id = db.Column(db.Integer, db.ForeignKey('shift_types.id'), nullable=False)
    department    = db.Column(db.String(50), nullable=True)
    day_of_week   = db.Column(db.Integer, nullable=True)
    min_staff     = db.Column(db.Integer, nullable=False, default=1)
    max_staff     = db.Column(db.Integer, nullable=True)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    shift_type = db.relationship('ShiftType', backref='coverage_rules')


class ShiftException(db.Model):
    __tablename__ = 'shift_exceptions'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    shift_schedule_id = db.Column(db.Integer, db.ForeignKey('shift_schedules.id'), nullable=True)
    exception_date    = db.Column(db.Date, nullable=False)
    exception_type    = db.Column(db.String(20), nullable=False)
    reason            = db.Column(db.String(300), nullable=True)
    resolved_by       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    resolved_at       = db.Column(db.DateTime, nullable=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee       = db.relationship('Employee', foreign_keys=[employee_id], backref='shift_exceptions')
    resolver       = db.relationship('Employee', foreign_keys=[resolved_by])
    shift_schedule = db.relationship('ShiftSchedule', backref='exceptions')
