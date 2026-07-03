from datetime import datetime, UTC
from models import db

PLANS = {
    'starter': {'max_employees': 50, 'max_devices': 2, 'has_reports': False, 'has_api': False, 'support': 'email'},
    'pro': {'max_employees': 500, 'max_devices': 10, 'has_reports': True, 'has_api': True, 'support': 'priority'},
    'enterprise': {'max_employees': 99999, 'max_devices': 100, 'has_reports': True, 'has_api': True, 'support': 'dedicated'},
}


class Company(db.Model):
    __tablename__ = 'companies'

    id              = db.Column(db.Integer, primary_key=True)
    name_ar         = db.Column(db.String(200), nullable=False)
    name_en         = db.Column(db.String(200), nullable=True)
    domain          = db.Column(db.String(100), unique=True, nullable=True)
    email           = db.Column(db.String(120), nullable=True)
    phone           = db.Column(db.String(20), nullable=True)
    address         = db.Column(db.Text, nullable=True)
    logo_url        = db.Column(db.String(300), nullable=True)
    primary_color   = db.Column(db.String(7), default='#dc2626')
    bg_color        = db.Column(db.String(7), default='#0f172a')

    plan            = db.Column(db.String(20), default='starter')
    is_active       = db.Column(db.Boolean, default=True)
    is_verified     = db.Column(db.Boolean, default=False)
    max_employees   = db.Column(db.Integer, default=50)
    max_devices     = db.Column(db.Integer, default=2)
    features_json   = db.Column(db.Text, nullable=True)

    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    deleted_at      = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        _plan = self.plan or 'starter'
        p = PLANS.get(_plan, PLANS['starter'])
        if 'max_employees' not in kwargs or not kwargs.get('max_employees'):
            self.max_employees = p['max_employees']
        if 'max_devices' not in kwargs or not kwargs.get('max_devices'):
            self.max_devices = p['max_devices']

    @property
    def features(self):
        raw = self.features_json
        if not raw:
            return {}
        try:
            import json
            return json.loads(raw)
        except Exception:
            return {}

    @features.setter
    def features(self, value):
        import json
        self.features_json = json.dumps(value, ensure_ascii=False)

    @property
    def plan_details(self):
        return PLANS.get(self.plan, PLANS['starter'])

    @property
    def employee_count(self):
        from models import Employee
        return Employee.query.filter_by(company_id=self.id, deleted_at=None, is_active=True).count()

    @property
    def device_count(self):
        from models import BiometricDevice
        return BiometricDevice.query.filter_by(company_id=self.id, deleted_at=None).count()

    def can_add_employee(self):
        return self.employee_count < self.max_employees

    def can_add_device(self):
        return self.device_count < self.max_devices

    def has_feature(self, feature_name):
        return self.features.get(feature_name, False)

    def to_dict(self):
        return {
            'id': self.id,
            'name_ar': self.name_ar,
            'name_en': self.name_en,
            'domain': self.domain,
            'email': self.email,
            'phone': self.phone,
            'plan': self.plan,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'max_employees': self.max_employees,
            'max_devices': self.max_devices,
            'employee_count': self.employee_count,
            'device_count': self.device_count,
            'features': self.features,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CompanyAdmin(db.Model):
    __tablename__ = 'company_admins'

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    username      = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(100), nullable=True)
    email         = db.Column(db.String(120), nullable=True)
    phone         = db.Column(db.String(20), nullable=True)
    role          = db.Column(db.String(20), default='admin')
    is_active     = db.Column(db.Boolean, default=True)
    last_login    = db.Column(db.DateTime, nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    company       = db.relationship('Company', backref='admins')

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'username': self.username,
            'full_name': self.full_name,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
