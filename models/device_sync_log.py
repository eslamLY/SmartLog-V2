from datetime import datetime, UTC
from models import db


class DeviceSyncLog(db.Model):
    __tablename__ = 'device_sync_logs'

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    device_id     = db.Column(db.Integer, db.ForeignKey('biometric_devices.id'), nullable=False)
    event_type    = db.Column(db.String(30), nullable=False)
    direction     = db.Column(db.String(10), default='push')
    payload       = db.Column(db.Text, nullable=True)
    status        = db.Column(db.String(20), default='received')
    error_msg     = db.Column(db.Text, nullable=True)
    ip_address    = db.Column(db.String(50), nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    company       = db.relationship('Company', backref='device_sync_logs')
    device        = db.relationship('BiometricDevice', backref='sync_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'device_id': self.device_id,
            'event_type': self.event_type,
            'direction': self.direction,
            'status': self.status,
            'error_msg': self.error_msg,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
