from datetime import datetime, date, UTC
from models import db

role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('rbac_permissions.id', ondelete='CASCADE'), primary_key=True),
)

role_departments = db.Table(
    'role_departments',
    db.Column('role_id', db.Integer, db.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('department_id', db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), primary_key=True),
)

class RbacRole(db.Model):
    __tablename__ = 'rbac_roles'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), unique=True, nullable=False)
    name_ar         = db.Column(db.String(100), nullable=True)
    description     = db.Column(db.Text, nullable=True)
    parent_id       = db.Column(db.Integer, db.ForeignKey('rbac_roles.id'), nullable=True)
    scope           = db.Column(db.String(20), default='department')
    is_system       = db.Column(db.Boolean, default=False)
    is_active       = db.Column(db.Boolean, default=True)
    risk_level      = db.Column(db.String(20), default='low')
    max_assignees   = db.Column(db.Integer, nullable=True)
    created_by      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    parent          = db.relationship('RbacRole', remote_side=[id], backref='children')
    permissions     = db.relationship('RbacPermission', secondary=role_permissions, lazy='subquery',
                        backref=db.backref('roles', lazy=True))
    departments     = db.relationship('Department', secondary=role_departments, lazy='subquery',
                        backref=db.backref('rbac_roles', lazy=True))

    def get_all_permissions(self):
        perms = set(p.code for p in self.permissions)
        if self.parent:
            perms |= self.parent.get_all_permissions()
        return perms

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'description': self.description,
            'parent_id': self.parent_id,
            'parent_name': self.parent.name if self.parent else None,
            'scope': self.scope,
            'is_system': self.is_system,
            'is_active': self.is_active,
            'risk_level': self.risk_level,
            'max_assignees': self.max_assignees,
            'permissions': [p.to_dict() for p in self.permissions],
            'department_ids': [d.id for d in self.departments],
            'child_count': len(self.children) if self.children else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class RbacPermission(db.Model):
    __tablename__ = 'rbac_permissions'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    name_ar         = db.Column(db.String(100), nullable=True)
    code            = db.Column(db.String(100), unique=True, nullable=False)
    description     = db.Column(db.Text, nullable=True)
    module          = db.Column(db.String(50), nullable=True)
    is_high_risk    = db.Column(db.Boolean, default=False)
    requires_2fa    = db.Column(db.Boolean, default=False)
    requires_approval = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'code': self.code,
            'description': self.description,
            'module': self.module,
            'is_high_risk': self.is_high_risk,
            'requires_2fa': self.requires_2fa,
            'requires_approval': self.requires_approval,
        }

class RbacEmployeeRole(db.Model):
    __tablename__ = 'rbac_employee_roles'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    role_id           = db.Column(db.Integer, db.ForeignKey('rbac_roles.id', ondelete='CASCADE'), nullable=False)
    is_primary        = db.Column(db.Boolean, default=False)
    assignment_type   = db.Column(db.String(20), default='permanent')
    effective_date    = db.Column(db.Date, default=lambda: date.today())
    expiry_date       = db.Column(db.Date, nullable=True)
    season_months     = db.Column(db.String(50), nullable=True)
    shift_type_ids    = db.Column(db.String(100), nullable=True)
    notes             = db.Column(db.Text, nullable=True)
    assigned_by       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    assigned_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    is_active         = db.Column(db.Boolean, default=True)
    revoked_at        = db.Column(db.DateTime, nullable=True)
    revoked_by        = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    role    = db.relationship('RbacRole', backref='assignments')
    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='rbac_role_assignments')

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'role_id': self.role_id,
            'role_name': self.role.name if self.role else None,
            'is_primary': self.is_primary,
            'assignment_type': self.assignment_type,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'season_months': self.season_months,
            'shift_type_ids': self.shift_type_ids,
            'notes': self.notes,
            'assigned_by': self.assigned_by,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'is_active': self.is_active,
        }

class RbacAuditLog(db.Model):
    __tablename__ = 'rbac_audit_logs'
    id            = db.Column(db.Integer, primary_key=True)
    action        = db.Column(db.String(50), nullable=False)
    entity_type   = db.Column(db.String(50), nullable=False)
    entity_id     = db.Column(db.Integer, nullable=True)
    changes       = db.Column(db.Text, nullable=True)
    ip_address    = db.Column(db.String(45), nullable=True)
    user_agent    = db.Column(db.String(200), nullable=True)
    performed_by  = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    performer     = db.relationship('Employee', foreign_keys=[performed_by])

    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'changes': self.changes,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'performed_by': self.performed_by,
            'performer_name': self.performer.full_name if self.performer else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class RbacPermissionRequest(db.Model):
    __tablename__ = 'rbac_permission_requests'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    requested_perms   = db.Column(db.Text, nullable=False)
    justification     = db.Column(db.Text, nullable=True)
    duration_days     = db.Column(db.Integer, nullable=True)
    risk_level        = db.Column(db.String(20), default='low')
    status            = db.Column(db.String(20), default='pending')
    reviewed_by       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    review_comment    = db.Column(db.Text, nullable=True)
    reviewed_at       = db.Column(db.DateTime, nullable=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee   = db.relationship('Employee', foreign_keys=[employee_id], backref='rbac_requests')
    reviewer   = db.relationship('Employee', foreign_keys=[reviewed_by])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'requested_perms': self.requested_perms,
            'justification': self.justification,
            'duration_days': self.duration_days,
            'risk_level': self.risk_level,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'review_comment': self.review_comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class RbacRoleTemplate(db.Model):
    __tablename__ = 'rbac_role_templates'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    description   = db.Column(db.Text, nullable=True)
    permissions   = db.Column(db.Text, nullable=True)
    scope         = db.Column(db.String(20), default='department')
    risk_level    = db.Column(db.String(20), default='low')
    is_builtin    = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'permissions': self.permissions,
            'scope': self.scope,
            'risk_level': self.risk_level,
            'is_builtin': self.is_builtin,
        }

class RbacDelegation(db.Model):
    __tablename__ = 'rbac_delegations'
    id              = db.Column(db.Integer, primary_key=True)
    delegator_id    = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    delegate_id     = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    permission_ids  = db.Column(db.Text, nullable=False)
    start_date      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    end_date        = db.Column(db.DateTime, nullable=False)
    reason          = db.Column(db.Text, nullable=True)
    is_active       = db.Column(db.Boolean, default=True)
    revoked_at      = db.Column(db.DateTime, nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    delegator = db.relationship('Employee', foreign_keys=[delegator_id], backref='rbac_delegations_given')
    delegate  = db.relationship('Employee', foreign_keys=[delegate_id], backref='rbac_delegations_received')

    def to_dict(self):
        return {
            'id': self.id,
            'delegator_id': self.delegator_id,
            'delegator_name': self.delegator.full_name if self.delegator else None,
            'delegate_id': self.delegate_id,
            'delegate_name': self.delegate.full_name if self.delegate else None,
            'permission_ids': self.permission_ids,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'reason': self.reason,
            'is_active': self.is_active,
        }
