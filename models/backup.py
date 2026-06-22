from datetime import datetime, UTC
from models import db


class BackupMetadata(db.Model):
    __tablename__ = 'backup_metadata'
    id            = db.Column(db.Integer, primary_key=True)
    filename      = db.Column(db.String(255), nullable=False)
    backup_type   = db.Column(db.String(20), default='full')
    size_bytes    = db.Column(db.BigInteger, default=0)
    checksum      = db.Column(db.String(128), nullable=True)
    encrypted     = db.Column(db.Boolean, default=True)
    location      = db.Column(db.String(50), default='local')
    filepath      = db.Column(db.String(500), nullable=True)
    status        = db.Column(db.String(20), default='completed')
    verified_at   = db.Column(db.DateTime, nullable=True)
    verified_by   = db.Column(db.Integer, nullable=True)
    locked        = db.Column(db.Boolean, default=False)
    locked_until  = db.Column(db.DateTime, nullable=True)
    description   = db.Column(db.Text, nullable=True)
    manifest_json = db.Column(db.Text, nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    deleted_at    = db.Column(db.DateTime, nullable=True)

    @property
    def size_display(self):
        if self.size_bytes < 1024:
            return f'{self.size_bytes} B'
        elif self.size_bytes < 1024 * 1024:
            return f'{self.size_bytes / 1024:.1f} KB'
        elif self.size_bytes < 1024 * 1024 * 1024:
            return f'{self.size_bytes / (1024 * 1024):.1f} MB'
        return f'{self.size_bytes / (1024 * 1024 * 1024):.2f} GB'

    @property
    def is_locked(self):
        if not self.locked:
            return False
        if self.locked_until and self.locked_until > datetime.now(UTC):
            return True
        return False


class BackupSchedule(db.Model):
    __tablename__ = 'backup_schedules'
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(100), nullable=False)
    backup_type      = db.Column(db.String(20), default='full')
    frequency        = db.Column(db.String(20), default='daily')
    frequency_value  = db.Column(db.Integer, default=1)
    time_str         = db.Column(db.String(10), default='02:00')
    destination      = db.Column(db.String(50), default='local')
    encrypt          = db.Column(db.Boolean, default=True)
    is_active        = db.Column(db.Boolean, default=True)
    last_run         = db.Column(db.DateTime, nullable=True)
    last_status      = db.Column(db.String(20), nullable=True)
    last_duration    = db.Column(db.Float, nullable=True)
    last_size        = db.Column(db.BigInteger, default=0)
    next_run         = db.Column(db.DateTime, nullable=True)
    total_runs       = db.Column(db.Integer, default=0)
    successful_runs  = db.Column(db.Integer, default=0)
    failed_runs      = db.Column(db.Integer, default=0)
    notify_on_success = db.Column(db.Boolean, default=True)
    notify_on_failure = db.Column(db.Boolean, default=True)
    retention_count  = db.Column(db.Integer, default=20)
    employee_filter  = db.Column(db.Text, nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class BackupAuditLog(db.Model):
    __tablename__ = 'backup_audit_logs'
    id          = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('backup_schedules.id'), nullable=True)
    action      = db.Column(db.String(50), nullable=False)
    details     = db.Column(db.Text, nullable=True)
    user_id     = db.Column(db.Integer, nullable=True)
    user_name   = db.Column(db.String(100), nullable=True)
    ip_address  = db.Column(db.String(50), nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    schedule = db.relationship('BackupSchedule', backref='audit_logs', lazy=True,
                               foreign_keys=[schedule_id])


class BackupConfig(db.Model):
    __tablename__ = 'backup_config'
    id                       = db.Column(db.Integer, primary_key=True)
    encryption_enabled       = db.Column(db.Boolean, default=True)
    encryption_algorithm     = db.Column(db.String(20), default='AES-256')
    master_key_hash          = db.Column(db.String(128), nullable=True)
    salt_hex                 = db.Column(db.String(128), nullable=True)
    compression_enabled      = db.Column(db.Boolean, default=True)
    compression_level        = db.Column(db.Integer, default=9)
    auto_verify              = db.Column(db.Boolean, default=True)
    verify_interval_days     = db.Column(db.Integer, default=7)
    retention_days           = db.Column(db.Integer, default=180)
    max_local_backups        = db.Column(db.Integer, default=10)
    max_server_backups       = db.Column(db.Integer, default=50)
    secure_delete_passes     = db.Column(db.Integer, default=3)
    notification_email       = db.Column(db.String(200), nullable=True)
    backup_directory         = db.Column(db.String(500), nullable=True)
    server_backup_directory  = db.Column(db.String(500), nullable=True)
    auto_cleanup_enabled     = db.Column(db.Boolean, default=True)
    created_at               = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at               = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class BackupRestoreLog(db.Model):
    __tablename__ = 'backup_restore_logs'
    id               = db.Column(db.Integer, primary_key=True)
    backup_id        = db.Column(db.Integer, db.ForeignKey('backup_metadata.id'), nullable=True)
    backup_filename  = db.Column(db.String(255), nullable=True)
    restore_type     = db.Column(db.String(20), default='full')
    status           = db.Column(db.String(20), default='pending')
    records_restored = db.Column(db.Integer, default=0)
    tables_restored  = db.Column(db.Integer, default=0)
    files_restored   = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Float, nullable=True)
    error_message    = db.Column(db.Text, nullable=True)
    created_backup   = db.Column(db.Boolean, default=True)
    performed_by     = db.Column(db.Integer, nullable=True)
    performed_by_name = db.Column(db.String(100), nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    backup = db.relationship('BackupMetadata', backref='restore_logs', lazy=True,
                             foreign_keys=[backup_id])
