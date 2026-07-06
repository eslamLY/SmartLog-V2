from datetime import datetime, UTC
from models import db

DEVICE_MODELS = [
    {'value': 'zkteco_k40', 'label': 'ZKTeco K40'},
    {'value': 'zkteco_f22', 'label': 'ZKTeco F22'},
    {'value': 'zkteco_mb360', 'label': 'ZKTeco MB360'},
    {'value': 'speedface_v5', 'label': 'SpeedFace V5'},
    {'value': 'proface_x', 'label': 'ProFace X'},
    {'value': 'inbio_260', 'label': 'inBio 260'},
    {'value': 'zkteco_k30', 'label': 'ZKTeco K30'},
    {'value': 'zkteco_sf100', 'label': 'ZKTeco SF100'},
    {'value': 'custom', 'label': 'أخرى (Custom)'},
]


class BiometricDevice(db.Model):
    __tablename__ = 'biometric_devices'

    id              = db.Column(db.Integer, primary_key=True)
    company_id      = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    serial_no       = db.Column(db.String(60), unique=True, nullable=False)
    name            = db.Column(db.String(100), nullable=False)
    device_model    = db.Column(db.String(30), nullable=True)
    firmware_ver    = db.Column(db.String(20), nullable=True)
    location        = db.Column(db.String(100), nullable=True)
    branch_id       = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    ip_address      = db.Column(db.String(50), nullable=True)
    mac_address     = db.Column(db.String(30), nullable=True)
    port            = db.Column(db.Integer, default=4370)
    comm_password   = db.Column(db.String(20), nullable=True)

    license_key     = db.Column(db.String(64), unique=True, nullable=True)
    api_key         = db.Column(db.String(64), nullable=True)
    secret_key      = db.Column(db.String(128), nullable=True)

    protocol        = db.Column(db.String(10), default='adms')
    is_active       = db.Column(db.Boolean, default=True)
    is_online       = db.Column(db.Boolean, default=False)
    last_online_at  = db.Column(db.DateTime, nullable=True)
    last_sync       = db.Column(db.DateTime, nullable=True)

    fp_capacity     = db.Column(db.Integer, default=0)
    fp_enrolled     = db.Column(db.Integer, default=0)
    face_capacity   = db.Column(db.Integer, default=0)
    face_enrolled   = db.Column(db.Integer, default=0)
    card_capacity   = db.Column(db.Integer, default=0)
    card_enrolled   = db.Column(db.Integer, default=0)
    txlog_capacity  = db.Column(db.Integer, default=0)
    txlog_used      = db.Column(db.Integer, default=0)
    records_pulled  = db.Column(db.Integer, default=0)

    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    deleted_at      = db.Column(db.DateTime, nullable=True)

    company         = db.relationship('Company', backref='biometric_devices')
    branch          = db.relationship('Branch', backref='biometric_devices')

    @property
    def device_model_label(self):
        for m in DEVICE_MODELS:
            if m['value'] == self.device_model:
                return m['label']
        return self.device_model or '—'

    @property
    def storage_used_percent(self):
        cap = self.txlog_capacity or 1
        used = self.txlog_used or 0
        return min(round(used / cap * 100, 1), 100.0)

    @property
    def online_status(self):
        if self.is_online:
            return 'online'
        if self.last_online_at:
            diff = (datetime.now(UTC) - self.last_online_at).total_seconds()
            if diff < 300:
                return 'warning'
        return 'offline'

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'serial_no': self.serial_no,
            'name': self.name,
            'device_model': self.device_model,
            'device_model_label': self.device_model_label,
            'firmware_ver': self.firmware_ver,
            'location': self.location,
            'branch_id': self.branch_id,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'port': self.port or 4370,
            'comm_password': bool(self.comm_password),
            'license_key': self.license_key,
            'api_key': self.api_key,
            'protocol': self.protocol,
            'is_active': self.is_active,
            'is_online': self.is_online,
            'last_online_at': self.last_online_at.isoformat() if self.last_online_at else None,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'online_status': self.online_status,
            'storage_used_percent': self.storage_used_percent,
            'fp_capacity': self.fp_capacity or 0,
            'fp_enrolled': self.fp_enrolled or 0,
            'face_capacity': self.face_capacity or 0,
            'face_enrolled': self.face_enrolled or 0,
            'card_capacity': self.card_capacity or 0,
            'card_enrolled': self.card_enrolled or 0,
            'txlog_capacity': self.txlog_capacity or 0,
            'txlog_used': self.txlog_used or 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
