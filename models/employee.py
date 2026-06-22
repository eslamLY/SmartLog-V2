from datetime import datetime, date, UTC
from models import db, get_fernet


class Employee(db.Model):
    __tablename__ = 'employees'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(20), unique=True, nullable=False)
    full_name     = db.Column(db.String(100), nullable=False)
    department    = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    base_salary_encrypted = db.Column(db.Text, nullable=True)
    overtime_multiplier = db.Column(db.Float, default=1.5)
    device_id     = db.Column(db.String(120), nullable=True)
    role          = db.Column(db.String(10), default='employee')
    is_active     = db.Column(db.Boolean, default=True)
    email         = db.Column(db.String(120), nullable=True)
    email_encrypted = db.Column(db.Text, nullable=True)
    phone         = db.Column(db.String(20), nullable=True)
    phone_encrypted = db.Column(db.Text, nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    department_ref = db.relationship('Department', foreign_keys=[department_id], backref='employees')

    attendance_logs = db.relationship('AttendanceLog', backref='employee',
                                      lazy=True, foreign_keys='AttendanceLog.employee_id')
    leave_requests  = db.relationship('LeaveRequest', backref='employee',
                                      lazy=True, foreign_keys='LeaveRequest.employee_id')

    # Personal info
    phone_country_code = db.Column(db.String(5), default='+218')
    national_id        = db.Column(db.String(20), nullable=True, unique=True)
    date_of_birth      = db.Column(db.Date, nullable=True)
    gender             = db.Column(db.String(10), nullable=True)
    marital_status     = db.Column(db.String(20), nullable=True)
    address            = db.Column(db.Text, nullable=True)
    profile_photo      = db.Column(db.String(200), nullable=True)

    # Employment info
    job_title        = db.Column(db.String(100), nullable=True)
    employment_type  = db.Column(db.String(20), default='full_time')
    hire_date        = db.Column(db.Date, nullable=True)
    contract_end_date = db.Column(db.Date, nullable=True)
    no_end_date      = db.Column(db.Boolean, default=False)
    manager_id       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    shift_type_id    = db.Column(db.Integer, db.ForeignKey('shift_types.id'), nullable=True)
    branch_id        = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)

    manager     = db.relationship('Employee', foreign_keys=[manager_id], remote_side=[id], backref='subordinates')
    shift_type  = db.relationship('ShiftType', backref='employees')
    branch      = db.relationship('Branch', backref='employees')

    # BIOTIME sync
    biotime_emp_id   = db.Column(db.Integer, nullable=True)
    assigned_devices = db.Column(db.Text, nullable=True)
    last_sync        = db.Column(db.DateTime, nullable=True)
    fp_enrolled      = db.Column(db.Boolean, default=False)
    face_enrolled    = db.Column(db.Boolean, default=False)
    sync_status      = db.Column(db.String(20), default='not_synced')

    # Financial
    housing_allowance      = db.Column(db.Float, default=0.0)
    transport_allowance    = db.Column(db.Float, default=0.0)
    other_allowances       = db.Column(db.Text, nullable=True)
    payment_method         = db.Column(db.String(20), default='bank_transfer')
    bank_account_number    = db.Column(db.String(30), nullable=True)
    bank_name              = db.Column(db.String(60), nullable=True)

    # System access
    permission_level        = db.Column(db.String(30), default='employee')
    force_password_change   = db.Column(db.Boolean, default=True)
    two_factor_enabled      = db.Column(db.Boolean, default=False)
    password_changed_at     = db.Column(db.DateTime, nullable=True)

    # Emergency contact
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_relationship = db.Column(db.String(30), nullable=True)
    emergency_phone        = db.Column(db.String(20), nullable=True)
    emergency_phone2       = db.Column(db.String(20), nullable=True)

    # Soft delete
    deleted_at     = db.Column(db.DateTime, nullable=True)
    deleted_by     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    delete_reason  = db.Column(db.String(300), nullable=True)

    deleter = db.relationship('Employee', foreign_keys=[deleted_by])

    @property
    def secure_email(self):
        raw = self.email_encrypted
        if not raw: return self.email or ''
        try: return get_fernet().decrypt(raw.encode()).decode()
        except Exception: return self.email or ''

    @secure_email.setter
    def secure_email(self, value):
        if value is None or value == '':
            self.email_encrypted = None; self.email = value
        else:
            self.email_encrypted = get_fernet().encrypt(str(value).encode()).decode()
            self.email = value

    @property
    def secure_phone(self):
        raw = self.phone_encrypted
        if not raw: return self.phone or ''
        try: return get_fernet().decrypt(raw.encode()).decode()
        except Exception: return self.phone or ''

    @secure_phone.setter
    def secure_phone(self, value):
        if value is None or value == '':
            self.phone_encrypted = None; self.phone = value
        else:
            self.phone_encrypted = get_fernet().encrypt(str(value).encode()).decode()
            self.phone = value

    @property
    def base_salary(self):
        raw = self.base_salary_encrypted
        if not raw: return 0.0
        try: return float(get_fernet().decrypt(raw.encode()).decode())
        except Exception: return 0.0

    @base_salary.setter
    def base_salary(self, value):
        if value is None:
            self.base_salary_encrypted = None
        else:
            val = float(value)
            self.base_salary_encrypted = get_fernet().encrypt(str(val).encode()).decode()

    @property
    def total_salary(self):
        base = self.base_salary
        housing = self.housing_allowance or 0.0
        transport = self.transport_allowance or 0.0
        others = self.other_allowances_list
        extra = sum(a['amount'] for a in others)
        return round(base + housing + transport + extra, 2)

    @property
    def other_allowances_list(self):
        raw = self.other_allowances
        if not raw: return []
        try:
            import json
            return json.loads(raw)
        except Exception:
            return []

    @other_allowances_list.setter
    def other_allowances_list(self, value):
        import json
        self.other_allowances = json.dumps(value, ensure_ascii=False)

    @property
    def assigned_device_ids(self):
        raw = self.assigned_devices
        if not raw: return []
        try:
            import json
            return json.loads(raw)
        except Exception:
            return []

    @assigned_device_ids.setter
    def assigned_device_ids(self, value):
        import json
        self.assigned_devices = json.dumps(value, ensure_ascii=False)

    @property
    def age(self):
        if not self.date_of_birth: return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def to_dict(self, include_sensitive=False):
        d = {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name,
            'department': self.department,
            'department_id': self.department_id,
            'role': self.role,
            'is_active': self.is_active,
            'base_salary': self.base_salary,
            'phone': self.secure_phone,
            'phone_country_code': self.phone_country_code or '+218',
            'national_id': self.national_id,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'age': self.age,
            'gender': self.gender,
            'marital_status': self.marital_status,
            'address': self.address,
            'profile_photo': self.profile_photo,
            'job_title': self.job_title,
            'employment_type': self.employment_type,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'contract_end_date': self.contract_end_date.isoformat() if self.contract_end_date else None,
            'no_end_date': self.no_end_date,
            'manager_id': self.manager_id,
            'shift_type_id': self.shift_type_id,
            'branch_id': self.branch_id,
            'biotime_emp_id': self.biotime_emp_id,
            'assigned_devices': self.assigned_device_ids,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'fp_enrolled': self.fp_enrolled,
            'face_enrolled': self.face_enrolled,
            'sync_status': self.sync_status,
            'housing_allowance': self.housing_allowance or 0.0,
            'transport_allowance': self.transport_allowance or 0.0,
            'other_allowances': self.other_allowances_list,
            'total_salary': self.total_salary,
            'payment_method': self.payment_method,
            'bank_account_number': self.bank_account_number if include_sensitive else None,
            'bank_name': self.bank_name,
            'permission_level': self.permission_level,
            'force_password_change': self.force_password_change,
            'two_factor_enabled': self.two_factor_enabled,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_relationship': self.emergency_relationship,
            'emergency_phone': self.emergency_phone,
            'emergency_phone2': self.emergency_phone2,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        return d



class Branch(db.Model):
    __tablename__ = 'branches'
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(100), nullable=False)
    address   = db.Column(db.String(200), nullable=True)
    phone     = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
