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

ACCESS_MODES = [
    {'value': 'fingerprint', 'label': 'بصمة فقط'},
    {'value': 'face', 'label': 'وجه فقط'},
    {'value': 'card', 'label': 'بطاقة فقط'},
    {'value': 'fp_pin', 'label': 'بصمة + PIN'},
    {'value': 'face_fp', 'label': 'وجه + بصمة'},
    {'value': 'any', 'label': 'أي طريقة'},
]

PROTOCOLS = [
    {'value': 'tcp_ip', 'label': 'TCP/IP'},
    {'value': 'udp', 'label': 'UDP'},
    {'value': 'http', 'label': 'HTTP'},
    {'value': 'https', 'label': 'HTTPS'},
]

SYNC_INTERVALS = [
    {'value': 5, 'label': 'كل 5 دقائق'},
    {'value': 15, 'label': 'كل 15 دقيقة'},
    {'value': 30, 'label': 'كل 30 دقيقة'},
    {'value': 60, 'label': 'كل ساعة'},
    {'value': 0, 'label': 'يدوي فقط'},
]


class BioTimeDevice(db.Model):
    __tablename__ = 'biotime_devices'

    id                = db.Column(db.Integer, primary_key=True)
    serial_no         = db.Column(db.String(60), unique=True, nullable=False)
    name              = db.Column(db.String(100), nullable=False)
    device_type       = db.Column(db.String(30), default='biometric')
    location          = db.Column(db.String(100), nullable=True)
    ip_address        = db.Column(db.String(50), nullable=True)
    mac_address       = db.Column(db.String(30), nullable=True)
    firmware_ver      = db.Column(db.String(20), nullable=True)
    api_key           = db.Column(db.String(64), nullable=True)
    is_active         = db.Column(db.Boolean, default=True)
    last_sync         = db.Column(db.DateTime, nullable=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    # Connection & Auth
    port              = db.Column(db.Integer, default=4370)
    comm_password     = db.Column(db.String(20), nullable=True)
    protocol          = db.Column(db.String(10), default='tcp_ip')

    # Device Identity & Hardware
    device_model      = db.Column(db.String(30), nullable=True)
    manufacture_date  = db.Column(db.Date, nullable=True)
    warranty_expiry   = db.Column(db.Date, nullable=True)

    fp_capacity       = db.Column(db.Integer, default=0)
    fp_enrolled       = db.Column(db.Integer, default=0)
    face_capacity     = db.Column(db.Integer, default=0)
    face_enrolled     = db.Column(db.Integer, default=0)
    card_capacity     = db.Column(db.Integer, default=0)
    card_enrolled     = db.Column(db.Integer, default=0)
    txlog_capacity    = db.Column(db.Integer, default=0)
    txlog_used        = db.Column(db.Integer, default=0)

    # Assignment & Access
    assigned_departments = db.Column(db.Text, nullable=True)
    assigned_employees   = db.Column(db.Text, nullable=True)
    access_mode          = db.Column(db.String(20), default='fingerprint')
    door_relay_enabled   = db.Column(db.Boolean, default=False)
    anti_passback_enabled = db.Column(db.Boolean, default=False)

    # Sync Settings
    auto_sync_enabled  = db.Column(db.Boolean, default=True)
    sync_interval      = db.Column(db.Integer, default=5)
    sync_window_start  = db.Column(db.String(5), nullable=True)
    sync_window_end    = db.Column(db.String(5), nullable=True)
    records_pulled     = db.Column(db.Integer, default=0)
    sync_error_log     = db.Column(db.Text, nullable=True)

    # Health
    is_online          = db.Column(db.Boolean, default=False)
    last_online_at     = db.Column(db.DateTime, nullable=True)
    uptime_percent_24h = db.Column(db.Float, default=100.0)

    updated_at         = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    @property
    def device_model_label(self):
        for m in DEVICE_MODELS:
            if m['value'] == self.device_model:
                return m['label']
        return self.device_model or '—'

    @property
    def assigned_department_list(self):
        if not self.assigned_departments:
            return []
        try:
            import json
            return json.loads(self.assigned_departments)
        except Exception:
            return []

    @assigned_department_list.setter
    def assigned_department_list(self, value):
        import json
        self.assigned_departments = json.dumps(value, ensure_ascii=False)

    @property
    def assigned_employee_list(self):
        if not self.assigned_employees:
            return []
        try:
            import json
            return json.loads(self.assigned_employees)
        except Exception:
            return []

    @assigned_employee_list.setter
    def assigned_employee_list(self, value):
        import json
        self.assigned_employees = json.dumps(value, ensure_ascii=False)

    @property
    def sync_error_list(self):
        if not self.sync_error_log:
            return []
        try:
            import json
            return json.loads(self.sync_error_log)
        except Exception:
            return []

    @sync_error_list.setter
    def sync_error_list(self, value):
        import json
        self.sync_error_log = json.dumps(value, ensure_ascii=False)

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

    @property
    def today_transactions(self):
        from models import AttendanceLog
        today = datetime.now(UTC).date()
        return AttendanceLog.query.filter(
            AttendanceLog.device_serial == self.serial_no,
            AttendanceLog.log_date == today
        ).count()

    @property
    def currently_clocked_in(self):
        from models import AttendanceLog
        today = datetime.now(UTC).date()
        return AttendanceLog.query.filter(
            AttendanceLog.device_serial == self.serial_no,
            AttendanceLog.log_date == today,
            AttendanceLog.clock_in.isnot(None),
            AttendanceLog.clock_out.is_(None)
        ).count()

    def to_dict(self):
        return {
            'id': self.id,
            'serial_no': self.serial_no,
            'name': self.name,
            'device_type': self.device_type,
            'location': self.location,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'port': self.port or 4370,
            'comm_password': bool(self.comm_password),
            'protocol': self.protocol or 'tcp_ip',
            'device_model': self.device_model,
            'device_model_label': self.device_model_label,
            'firmware_ver': self.firmware_ver,
            'manufacture_date': self.manufacture_date.isoformat() if self.manufacture_date else None,
            'warranty_expiry': self.warranty_expiry.isoformat() if self.warranty_expiry else None,
            'api_key': self.api_key,
            'is_active': self.is_active,
            'fp_capacity': self.fp_capacity or 0,
            'fp_enrolled': self.fp_enrolled or 0,
            'face_capacity': self.face_capacity or 0,
            'face_enrolled': self.face_enrolled or 0,
            'card_capacity': self.card_capacity or 0,
            'card_enrolled': self.card_enrolled or 0,
            'txlog_capacity': self.txlog_capacity or 0,
            'txlog_used': self.txlog_used or 0,
            'storage_used_percent': self.storage_used_percent,
            'assigned_departments': self.assigned_department_list,
            'assigned_employees': self.assigned_employee_list,
            'access_mode': self.access_mode or 'fingerprint',
            'door_relay_enabled': self.door_relay_enabled,
            'anti_passback_enabled': self.anti_passback_enabled,
            'auto_sync_enabled': self.auto_sync_enabled,
            'sync_interval': self.sync_interval or 0,
            'sync_window_start': self.sync_window_start,
            'sync_window_end': self.sync_window_end,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'records_pulled': self.records_pulled or 0,
            'online_status': self.online_status,
            'is_online': self.is_online,
            'last_online_at': self.last_online_at.isoformat() if self.last_online_at else None,
            'uptime_percent_24h': self.uptime_percent_24h or 100.0,
            'today_transactions': self.today_transactions,
            'currently_clocked_in': self.currently_clocked_in,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DeviceEventLog(db.Model):
    __tablename__ = 'device_event_logs'
    id          = db.Column(db.Integer, primary_key=True)
    device_id   = db.Column(db.Integer, db.ForeignKey('biotime_devices.id'), nullable=False)
    event_type  = db.Column(db.String(30), nullable=False)
    message     = db.Column(db.String(300), nullable=True)
    error_code  = db.Column(db.String(20), nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    device      = db.relationship('BioTimeDevice', backref='event_logs')


class DeviceHealthSnapshot(db.Model):
    __tablename__ = 'device_health_snapshots'
    id          = db.Column(db.Integer, primary_key=True)
    device_id   = db.Column(db.Integer, db.ForeignKey('biotime_devices.id'), nullable=False)
    is_online   = db.Column(db.Boolean, default=False)
    ping_ms     = db.Column(db.Float, nullable=True)
    fp_enrolled = db.Column(db.Integer, default=0)
    face_enrolled = db.Column(db.Integer, default=0)
    txlog_used  = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    device      = db.relationship('BioTimeDevice', backref='health_snapshots')
