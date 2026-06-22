from datetime import datetime, date, UTC
import json

from models import db


dept_required_certs = db.Table(
    'dept_required_certs',
    db.Column('department_id', db.Integer, db.ForeignKey('departments.id'), primary_key=True),
    db.Column('certification', db.String(100), primary_key=True),
)

dept_allowed_devices = db.Table(
    'dept_allowed_devices',
    db.Column('department_id', db.Integer, db.ForeignKey('departments.id'), primary_key=True),
    db.Column('device_id', db.Integer, db.ForeignKey('biotime_devices.id'), primary_key=True),
)

dept_alert_recipients = db.Table(
    'dept_alert_recipients',
    db.Column('department_id', db.Integer, db.ForeignKey('departments.id'), primary_key=True),
    db.Column('employee_id', db.Integer, db.ForeignKey('employees.id'), primary_key=True),
)


class Department(db.Model):
    __tablename__ = 'departments'

    id                                 = db.Column(db.Integer, primary_key=True)
    code                               = db.Column(db.String(20), unique=True, nullable=False)
    name_ar                            = db.Column(db.String(50), nullable=False)
    name_en                            = db.Column(db.String(50), nullable=True)

    # Identity & Branding
    icon                               = db.Column(db.String(50), default='building')
    color                              = db.Column(db.String(7), default='#e53935')
    description_ar                     = db.Column(db.String(200), nullable=True)
    description_en                     = db.Column(db.String(200), nullable=True)
    dept_type                          = db.Column(db.String(20), default='operational')
    is_active                          = db.Column(db.Boolean, default=True)
    inactive_reason                    = db.Column(db.String(200), nullable=True)

    # Organizational Structure
    parent_id                          = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    dept_level                         = db.Column(db.Integer, default=1)
    manager_id                         = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    deputy_id                          = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    cost_center_code                   = db.Column(db.String(20), nullable=True)

    # Staffing & Capacity
    min_staff_required                 = db.Column(db.Integer, default=2)
    max_staff_capacity                 = db.Column(db.Integer, default=50)
    allowed_employment_types           = db.Column(db.String(200), default='full_time,part_time')

    # Attendance & Shift Rules
    default_shift_id                   = db.Column(db.Integer, db.ForeignKey('shift_types.id'), nullable=True)
    grace_period_override              = db.Column(db.Integer, nullable=True)
    remote_work_allowed                = db.Column(db.Boolean, default=False)
    break_duration_policy              = db.Column(db.Integer, default=60)
    overtime_max_weekly                = db.Column(db.Integer, default=12)
    overtime_requires_approval         = db.Column(db.Boolean, default=True)
    overtime_auto_approve_under        = db.Column(db.Integer, default=2)

    # Notifications & Alerts
    whatsapp_group_id                  = db.Column(db.String(50), nullable=True)
    alert_settings                     = db.Column(db.Text, nullable=True)
    alert_threshold_minutes            = db.Column(db.Integer, default=15)
    alert_understaffing_threshold      = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at                         = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at                         = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    parent                             = db.relationship('Department', remote_side='Department.id', backref='children', foreign_keys=[parent_id])
    manager                            = db.relationship('Employee', foreign_keys=[manager_id], backref='managed_departments')
    deputy                             = db.relationship('Employee', foreign_keys=[deputy_id], backref='deputy_departments')
    default_shift                      = db.relationship('ShiftType', foreign_keys=[default_shift_id])
    allowed_devices                    = db.relationship('BioTimeDevice', secondary=dept_allowed_devices, backref=db.backref('departments', lazy='dynamic'))
    alert_recipients                   = db.relationship('Employee', secondary=dept_alert_recipients, backref=db.backref('alert_departments', lazy='dynamic'))
    required_certifications            = db.relationship('DepartmentCertification', backref='department', cascade='all, delete-orphan')

    @property
    def hierarchy_path(self):
        parts = []
        d = self
        while d:
            parts.append(d.name_ar)
            d = Department.query.get(d.parent_id) if d.parent_id else None
        return ' > '.join(reversed(parts))

    @property
    def employee_count(self):
        from models.employee import Employee
        return Employee.query.filter_by(department_id=self.id, deleted_at=None).count()

    @property
    def current_headcount_label(self):
        return f'{self.employee_count} / {self.max_staff_capacity}'

    @property
    def headcount_percent(self):
        if self.max_staff_capacity and self.max_staff_capacity > 0:
            return min(100, int((self.employee_count / self.max_staff_capacity) * 100))
        return 0

    @property
    def employment_types_list(self):
        if not self.allowed_employment_types:
            return []
        return [t.strip() for t in self.allowed_employment_types.split(',')]

    @property
    def alert_settings_dict(self):
        if not self.alert_settings:
            return {}
        try:
            return json.loads(self.alert_settings)
        except (json.JSONDecodeError, TypeError):
            return {}

    @alert_settings_dict.setter
    def alert_settings_dict(self, value):
        self.alert_settings = json.dumps(value, ensure_ascii=False)

    @staticmethod
    def generate_code():
        last = Department.query.order_by(Department.id.desc()).first()
        if not last:
            return 'DEPT-001'
        try:
            num = int(last.code.split('-')[-1]) if last.code else 0
        except (ValueError, IndexError):
            num = 0
        return f'DEPT-{num + 1:03d}'

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name_ar': self.name_ar,
            'name_en': self.name_en,
            'icon': self.icon,
            'color': self.color,
            'description_ar': self.description_ar,
            'description_en': self.description_en,
            'dept_type': self.dept_type,
            'is_active': self.is_active,
            'inactive_reason': self.inactive_reason,
            'parent_id': self.parent_id,
            'parent_name': self.parent.name_ar if self.parent else None,
            'dept_level': self.dept_level,
            'manager_id': self.manager_id,
            'manager_name': self.manager.full_name if self.manager else None,
            'deputy_id': self.deputy_id,
            'deputy_name': self.deputy.full_name if self.deputy else None,
            'cost_center_code': self.cost_center_code,
            'min_staff_required': self.min_staff_required,
            'max_staff_capacity': self.max_staff_capacity,
            'employee_count': self.employee_count,
            'current_headcount_label': self.current_headcount_label,
            'headcount_percent': self.headcount_percent,
            'allowed_employment_types': self.employment_types_list,
            'default_shift_id': self.default_shift_id,
            'default_shift_name': self.default_shift.name_ar if self.default_shift else None,
            'grace_period_override': self.grace_period_override,
            'remote_work_allowed': self.remote_work_allowed,
            'break_duration_policy': self.break_duration_policy,
            'overtime_max_weekly': self.overtime_max_weekly,
            'overtime_requires_approval': self.overtime_requires_approval,
            'overtime_auto_approve_under': self.overtime_auto_approve_under,
            'whatsapp_group_id': self.whatsapp_group_id,
            'alert_settings': self.alert_settings_dict,
            'alert_threshold_minutes': self.alert_threshold_minutes,
            'alert_understaffing_threshold': self.alert_understaffing_threshold,
            'hierarchy_path': self.hierarchy_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'children': [{'id': c.id, 'name_ar': c.name_ar} for c in self.children] if self.children else [],
        }


class DepartmentCertification(db.Model):
    __tablename__ = 'department_certifications'
    id              = db.Column(db.Integer, primary_key=True)
    department_id   = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    certification   = db.Column(db.String(100), nullable=False)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class DepartmentAnnouncement(db.Model):
    __tablename__ = 'department_announcements'
    id              = db.Column(db.Integer, primary_key=True)
    department_id   = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    message         = db.Column(db.Text, nullable=False)
    priority        = db.Column(db.String(10), default='normal')
    delivery_method = db.Column(db.String(50), default='in_app')
    scheduled_at    = db.Column(db.DateTime, nullable=True)
    sent_at         = db.Column(db.DateTime, nullable=True)
    sent_by         = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    target_type     = db.Column(db.String(20), default='all')
    target_ids      = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    department      = db.relationship('Department', backref='announcements')
    sender          = db.relationship('Employee', foreign_keys=[sent_by])

    def to_dict(self):
        return {
            'id': self.id,
            'department_id': self.department_id,
            'message': self.message,
            'priority': self.priority,
            'delivery_method': self.delivery_method,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'sent_by': self.sent_by,
            'sender_name': self.sender.full_name if self.sender else None,
            'target_type': self.target_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DepartmentTransfer(db.Model):
    __tablename__ = 'department_transfers'
    id                  = db.Column(db.Integer, primary_key=True)
    employee_id         = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    from_department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    to_department_id    = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    transfer_date       = db.Column(db.Date, nullable=False)
    reason_type         = db.Column(db.String(30), nullable=True)
    reason_notes        = db.Column(db.Text, nullable=True)
    status              = db.Column(db.String(20), default='pending')
    approved_by_manager = db.Column(db.Boolean, default=False)
    approved_by_hr      = db.Column(db.Boolean, default=False)
    manager_approved_at = db.Column(db.DateTime, nullable=True)
    hr_approved_at      = db.Column(db.DateTime, nullable=True)
    executed_at         = db.Column(db.DateTime, nullable=True)
    created_at          = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee            = db.relationship('Employee', foreign_keys=[employee_id], backref='transfers')
    from_department     = db.relationship('Department', foreign_keys=[from_department_id])
    to_department       = db.relationship('Department', foreign_keys=[to_department_id])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else '',
            'from_department_id': self.from_department_id,
            'from_department_name': self.from_department.name_ar if self.from_department else '',
            'to_department_id': self.to_department_id,
            'to_department_name': self.to_department.name_ar if self.to_department else '',
            'transfer_date': self.transfer_date.isoformat() if self.transfer_date else None,
            'reason_type': self.reason_type,
            'reason_notes': self.reason_notes,
            'status': self.status,
            'approved_by_manager': self.approved_by_manager,
            'approved_by_hr': self.approved_by_hr,
            'manager_approved_at': self.manager_approved_at.isoformat() if self.manager_approved_at else None,
            'hr_approved_at': self.hr_approved_at.isoformat() if self.hr_approved_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
