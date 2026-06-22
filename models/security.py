from datetime import datetime, UTC
from models import db


class LoginAttempt(db.Model):
    __tablename__   = 'login_attempts'
    id              = db.Column(db.Integer, primary_key=True)
    ip_address      = db.Column(db.String(50), nullable=False, unique=True)
    attempts        = db.Column(db.Integer, default=0)
    last_attempt    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    blocked_until   = db.Column(db.DateTime, nullable=True)


class BlockedIP(db.Model):
    __tablename__ = 'blocked_ips'
    id              = db.Column(db.Integer, primary_key=True)
    ip_address      = db.Column(db.String(50), nullable=False, unique=True)
    violation_count = db.Column(db.Integer, default=0)
    banned_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    ban_expiry      = db.Column(db.DateTime, nullable=True)
    is_permanent    = db.Column(db.Boolean, default=False)
    is_active       = db.Column(db.Boolean, default=True)
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'violation_count': self.violation_count,
            'banned_at': self.banned_at.isoformat() if self.banned_at else None,
            'ban_expiry': self.ban_expiry.isoformat() if self.ban_expiry else None,
            'is_permanent': self.is_permanent,
            'is_active': self.is_active,
        }


class BiometricCredential(db.Model):
    __tablename__ = 'biometric_credentials'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    credential_id = db.Column(db.String(128), unique=True, nullable=False)
    public_key    = db.Column(db.Text, nullable=True)
    device_info   = db.Column(db.String(100), nullable=True)
    biometric_type= db.Column(db.String(20), default='fingerprint')
    is_active     = db.Column(db.Boolean, default=True)
    last_used     = db.Column(db.DateTime, nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class TrustedDevice(db.Model):
    __tablename__ = 'trusted_devices'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    device_name   = db.Column(db.String(100), nullable=False)
    device_fingerprint = db.Column(db.String(128), nullable=False)
    device_os     = db.Column(db.String(30), nullable=True)
    ip_address    = db.Column(db.String(50), nullable=True)
    is_trusted    = db.Column(db.Boolean, default=True)
    last_used     = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee      = db.relationship('Employee', backref='trusted_devices', lazy=True)
