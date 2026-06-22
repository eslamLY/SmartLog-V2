from datetime import datetime, date, UTC
from models import db, get_fernet

class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id           = db.Column(db.Integer, primary_key=True)
    employee_id  = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    request_type = db.Column(db.String(30), nullable=False)
    start_date   = db.Column(db.Date, nullable=False)
    end_date     = db.Column(db.Date, nullable=True)
    reason       = db.Column(db.Text, nullable=True)
    status       = db.Column(db.String(20), default='pending')
    approved_by  = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    approved_at  = db.Column(db.DateTime, nullable=True)

class OutingRequest(db.Model):
    __tablename__ = 'outing_requests'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    outing_date   = db.Column(db.Date, default=date.today)
    reason        = db.Column(db.String(200), nullable=True)
    status        = db.Column(db.String(20), default='pending')
    approved_by   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    approved_at   = db.Column(db.DateTime, nullable=True)
    employee      = db.relationship('Employee', backref='outing_requests', foreign_keys=[employee_id])
    reviewer      = db.relationship('Employee', backref='reviewed_outings', foreign_keys=[approved_by])

class GPSLog(db.Model):
    __tablename__ = 'gps_logs'
    id              = db.Column(db.Integer, primary_key=True)
    employee_id     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    latitude        = db.Column(db.Float, nullable=True)
    latitude_enc    = db.Column(db.Text, nullable=True)
    longitude       = db.Column(db.Float, nullable=True)
    longitude_enc   = db.Column(db.Text, nullable=True)
    accuracy        = db.Column(db.Float, default=0)
    battery         = db.Column(db.Float, nullable=True)
    source          = db.Column(db.String(20), default='app')
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee        = db.relationship('Employee', backref='gps_logs', lazy=True)

    def set_coords(self, lat, lng):
        self.latitude = lat
        self.longitude = lng
        try:
            self.latitude_enc = get_fernet().encrypt(str(lat).encode()).decode()
            self.longitude_enc = get_fernet().encrypt(str(lng).encode()).decode()
        except Exception:
            pass

    @property
    def decrypted_lat(self):
        if self.latitude_enc:
            try: return float(get_fernet().decrypt(self.latitude_enc.encode()).decode())
            except Exception: return self.latitude
        return self.latitude

    @property
    def decrypted_lng(self):
        if self.longitude_enc:
            try: return float(get_fernet().decrypt(self.longitude_enc.encode()).decode())
            except Exception: return self.longitude
        return self.longitude

class BrandingConfig(db.Model):
    __tablename__ = 'branding_config'
    id            = db.Column(db.Integer, primary_key=True)
    tenant_name   = db.Column(db.String(100), default='منظومة بنك دم طبرق')
    logo_url      = db.Column(db.String(300), nullable=True)
    primary_color = db.Column(db.String(10), default='#dc2626')
    accent_color  = db.Column(db.String(10), default='#818cf8')
    bg_color      = db.Column(db.String(10), default='#080c18')
    card_color    = db.Column(db.String(10), default='#0f172a')
    custom_css    = db.Column(db.Text, nullable=True)
    company_lat   = db.Column(db.Float, default=32.0755)
    company_lng   = db.Column(db.Float, default=23.9752)
    allowed_radius_meters = db.Column(db.Integer, default=200)
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class EmployeeDocument(db.Model):
    __tablename__ = 'employee_documents'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    doc_type      = db.Column(db.String(50), nullable=False)
    doc_name      = db.Column(db.String(100), nullable=False)
    file_path     = db.Column(db.String(300), nullable=False)
    file_size     = db.Column(db.Integer, default=0)
    mime_type     = db.Column(db.String(50), nullable=True)
    expiry_date   = db.Column(db.Date, nullable=True)
    is_verified   = db.Column(db.Boolean, default=False)
    notes         = db.Column(db.Text, nullable=True)
    uploaded_by   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def status(self):
        if not self.expiry_date:
            return 'غير محدد'
        d = self.days_until_expiry
        if d < 0:
            return 'منتهية'
        if d <= 30:
            return 'تنتهي قريباً'
        return 'سارية'

    @property
    def status_badge(self):
        return {
            'منتهية': 'badge-absent',
            'تنتهي قريباً': 'badge-late',
            'سارية': 'badge-present',
            'غير محدد': 'badge-info'
        }.get(self.status, 'badge-info')
