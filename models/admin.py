from datetime import datetime, UTC
from models import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    user_name   = db.Column(db.String(100), nullable=True)
    action      = db.Column(db.String(30), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id   = db.Column(db.Integer, nullable=True)
    changes     = db.Column(db.Text, nullable=True)
    ip_address  = db.Column(db.String(45), nullable=True)
    timestamp   = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class Role(db.Model):
    __tablename__ = 'roles'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), unique=True, nullable=False)
    permissions = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class Permission(db.Model):
    __tablename__ = 'permissions'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    code        = db.Column(db.String(50), unique=True, nullable=False)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class EmployeePermission(db.Model):
    __tablename__ = 'employee_permissions'
    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)
