from datetime import datetime, date, UTC
from models import db, get_fernet


class EmployeeGovernment(db.Model):
    __tablename__ = 'employees_government'

    # ─── SYSTEM ────────────────────────────────────────────────────────────────
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(10), default='employee')
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at    = db.Column(db.DateTime, onupdate=lambda: datetime.now(UTC))

    # ─── NAME (Libyan 5-name format) ───────────────────────────────────────────
    first_name   = db.Column(db.String(50), nullable=False)
    second_name  = db.Column(db.String(50), nullable=False)
    third_name   = db.Column(db.String(50), nullable=True)
    fourth_name  = db.Column(db.String(50), nullable=True)
    family_name  = db.Column(db.String(50), nullable=False)

    @property
    def full_name(self):
        parts = [self.first_name, self.second_name]
        if self.third_name:
            parts.append(self.third_name)
        if self.fourth_name:
            parts.append(self.fourth_name)
        parts.append(self.family_name)
        return ' '.join(p for p in parts if p)

    # ─── PERSONAL IDENTITY ──────────────────────────────────────────────────────
    national_id         = db.Column(db.String(20), unique=True, nullable=False, index=True)
    national_id_verified = db.Column(db.Boolean, default=False)
    date_of_birth       = db.Column(db.Date, nullable=False)
    gender              = db.Column(db.String(10), nullable=False)
    marital_status      = db.Column(db.String(20), default='single')
    passport_number     = db.Column(db.String(30), nullable=True)
    passport_expiry     = db.Column(db.Date, nullable=True)
    id_expiry_date      = db.Column(db.Date, nullable=True)
    id_issuing_authority = db.Column(db.String(100), nullable=True)

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    # ─── CONTACT ────────────────────────────────────────────────────────────────
    personal_phone   = db.Column(db.String(20), nullable=True)
    work_phone       = db.Column(db.String(20), nullable=True)
    personal_email   = db.Column(db.String(120), nullable=True)
    work_email       = db.Column(db.String(120), nullable=True)
    permanent_address = db.Column(db.Text, nullable=True)
    current_address   = db.Column(db.Text, nullable=True)
    residence_province = db.Column(db.String(50), nullable=True)

    # Encrypted fields
    email_encrypted   = db.Column(db.Text, nullable=True)
    phone_encrypted   = db.Column(db.Text, nullable=True)
    base_salary_encrypted = db.Column(db.Text, nullable=True)

    @property
    def secure_email(self):
        raw = self.email_encrypted
        if not raw:
            return self.personal_email or ''
        try:
            return get_fernet().decrypt(raw.encode()).decode()
        except Exception:
            return self.personal_email or ''

    @secure_email.setter
    def secure_email(self, value):
        if not value:
            self.email_encrypted = None
            self.personal_email = None
        else:
            self.email_encrypted = get_fernet().encrypt(str(value).encode()).decode()
            self.personal_email = value

    @property
    def secure_phone(self):
        raw = self.phone_encrypted
        if not raw:
            return self.personal_phone or ''
        try:
            return get_fernet().decrypt(raw.encode()).decode()
        except Exception:
            return self.personal_phone or ''

    @secure_phone.setter
    def secure_phone(self, value):
        if not value:
            self.phone_encrypted = None
            self.personal_phone = None
        else:
            self.phone_encrypted = get_fernet().encrypt(str(value).encode()).decode()
            self.personal_phone = value

    # ─── EMERGENCY CONTACT ──────────────────────────────────────────────────────
    emergency_name     = db.Column(db.String(100), nullable=True)
    emergency_phone    = db.Column(db.String(20), nullable=True)
    emergency_relation = db.Column(db.String(30), nullable=True)

    # ─── PROFILE ────────────────────────────────────────────────────────────────
    profile_photo = db.Column(db.String(200), nullable=True)

    # ─── DEPARTMENT / DIVISION ──────────────────────────────────────────────────
    department    = db.Column(db.String(50), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    branch_id     = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    manager_id    = db.Column(db.Integer, db.ForeignKey('employees_government.id'), nullable=True)

    manager     = db.relationship('EmployeeGovernment', foreign_keys=[manager_id], remote_side=[id], backref='subordinates')
    branch      = db.relationship('Branch', backref='gov_employees')
    department_ref = db.relationship('Department', backref='gov_employees')

    # ─── EMPLOYMENT ─────────────────────────────────────────────────────────────
    job_title        = db.Column(db.String(100), nullable=True)
    employment_type  = db.Column(db.String(20), default='full_time')
    contract_type    = db.Column(db.String(30), default='permanent')
    hire_date        = db.Column(db.Date, nullable=True)
    contract_end_date = db.Column(db.Date, nullable=True)
    no_end_date      = db.Column(db.Boolean, default=False)
    job_classification = db.Column(db.String(50), nullable=True)
    career_path      = db.Column(db.String(100), nullable=True)
    category         = db.Column(db.String(30), nullable=True)

    # ─── EMPLOYMENT GRADE ────────────────────────────────────────────────────────
    grade_id    = db.Column(db.Integer, db.ForeignKey('employee_grades.id'), nullable=True)
    grade       = db.relationship('EmployeeGrade', backref='gov_employees')

    # ─── FINANCIAL ──────────────────────────────────────────────────────────────
    housing_allowance    = db.Column(db.Float, default=0.0)
    transport_allowance  = db.Column(db.Float, default=0.0)
    responsibility_allowance = db.Column(db.Float, default=0.0)
    hazard_allowance     = db.Column(db.Float, default=0.0)
    other_allowances     = db.Column(db.Text, nullable=True)

    payment_method       = db.Column(db.String(20), default='bank_transfer')
    bank_name            = db.Column(db.String(100), nullable=True)
    bank_account_name    = db.Column(db.String(100), nullable=True)
    bank_account_number  = db.Column(db.String(30), nullable=True)
    iban                 = db.Column(db.String(34), nullable=True)
    bank_account_type    = db.Column(db.String(20), default='personal')
    bank_branch          = db.Column(db.String(100), nullable=True)
    bank_account_verified = db.Column(db.Boolean, default=False)

    @property
    def base_salary(self):
        raw = self.base_salary_encrypted
        if not raw:
            return 0.0
        try:
            return float(get_fernet().decrypt(raw.encode()).decode())
        except Exception:
            return 0.0

    @base_salary.setter
    def base_salary(self, value):
        if value is None:
            self.base_salary_encrypted = None
        else:
            self.base_salary_encrypted = get_fernet().encrypt(str(float(value)).encode()).decode()

    @property
    def total_salary(self):
        base = self.base_salary
        housing = self.housing_allowance or 0.0
        transport = self.transport_allowance or 0.0
        responsibility = self.responsibility_allowance or 0.0
        hazard = self.hazard_allowance or 0.0
        extras = self.other_allowances_list
        extra_sum = sum(a.get('amount', 0) for a in extras)
        return round(base + housing + transport + responsibility + hazard + extra_sum, 2)

    @property
    def other_allowances_list(self):
        raw = self.other_allowances
        if not raw:
            return []
        try:
            import json
            return json.loads(raw)
        except Exception:
            return []

    @other_allowances_list.setter
    def other_allowances_list(self, value):
        import json
        self.other_allowances = json.dumps(value, ensure_ascii=False)

    # ─── FAMILY ─────────────────────────────────────────────────────────────────
    spouse_name        = db.Column(db.String(100), nullable=True)
    dependent_children = db.Column(db.Integer, default=0)

    # ─── GOVERNMENT DATA ────────────────────────────────────────────────────────
    gov_file_number         = db.Column(db.String(50), unique=True, nullable=True)
    gov_central_emp_id      = db.Column(db.String(50), nullable=True)
    gov_region              = db.Column(db.String(50), nullable=True)
    gov_sector              = db.Column(db.String(100), nullable=True)
    gov_parent_institution  = db.Column(db.String(200), nullable=True)
    gov_supervisory_body    = db.Column(db.String(200), nullable=True)
    administrative_region   = db.Column(db.String(100), nullable=True)
    work_region             = db.Column(db.String(100), nullable=True)

    # ─── SECURITY CLEARANCE ─────────────────────────────────────────────────────
    clearance_level     = db.Column(db.String(30), default='public')
    clearance_date      = db.Column(db.Date, nullable=True)
    clearance_expiry    = db.Column(db.Date, nullable=True)
    clearance_authority = db.Column(db.String(100), nullable=True)

    # ─── SOCIAL SECURITY ────────────────────────────────────────────────────────
    social_security_number = db.Column(db.String(30), nullable=True)
    social_security_start  = db.Column(db.Date, nullable=True)
    social_security_rate   = db.Column(db.Float, default=8.0)
    accumulated_contributions = db.Column(db.Float, default=0.0)

    # ─── HEALTH INSURANCE ───────────────────────────────────────────────────────
    health_insurance_level   = db.Column(db.String(30), default='basic')
    health_insurance_dependents = db.Column(db.Integer, default=0)
    health_insurance_premium = db.Column(db.Float, default=0.0)

    # ─── LIFE INSURANCE ─────────────────────────────────────────────────────────
    life_insurance_coverage    = db.Column(db.Float, default=0.0)
    life_insurance_beneficiary = db.Column(db.String(100), nullable=True)
    life_insurance_premium     = db.Column(db.Float, default=0.0)

    # ─── WORK INJURY INSURANCE ──────────────────────────────────────────────────
    injury_insurance_coverage = db.Column(db.Float, default=0.0)

    # ─── RETIREMENT ─────────────────────────────────────────────────────────────
    retirement_age     = db.Column(db.Integer, default=60)
    pension_rate       = db.Column(db.Float, default=2.5)
    years_of_service   = db.Column(db.Float, default=0.0)
    expected_pension   = db.Column(db.Float, default=0.0)

    @property
    def years_to_retirement(self):
        if not self.retirement_age or self.age is None:
            return None
        return max(0, self.retirement_age - self.age)

    # ─── LEAVE DEFAULTS (Libyan standard) ───────────────────────────────────────
    annual_leave_days    = db.Column(db.Integer, default=30)
    sick_leave_days      = db.Column(db.Integer, default=15)
    maternity_leave_days = db.Column(db.Integer, default=60)
    paternity_leave_days = db.Column(db.Integer, default=5)
    marriage_leave_days  = db.Column(db.Integer, default=7)
    hajj_leave_days      = db.Column(db.Integer, default=15)
    unpaid_leave_days    = db.Column(db.Integer, default=0)

    carried_over_days    = db.Column(db.Float, default=0.0)
    used_leave_days      = db.Column(db.Float, default=0.0)
    remaining_leave_days = db.Column(db.Float, default=0.0)

    def recalculate_leave_balance(self):
        self.remaining_leave_days = (self.annual_leave_days or 0) + (self.carried_over_days or 0) - (self.used_leave_days or 0)
        return self.remaining_leave_days

    # ─── SYSTEM ACCESS ───────────────────────────────────────────────────────────
    permission_level      = db.Column(db.String(30), default='employee')
    force_password_change = db.Column(db.Boolean, default=True)
    two_factor_enabled    = db.Column(db.Boolean, default=False)
    password_changed_at   = db.Column(db.DateTime, nullable=True)
    device_id             = db.Column(db.String(120), nullable=True)

    # ─── SOFT DELETE ─────────────────────────────────────────────────────────────
    deleted_at    = db.Column(db.DateTime, nullable=True)
    deleted_by    = db.Column(db.Integer, db.ForeignKey('employees_government.id'), nullable=True)
    delete_reason = db.Column(db.String(300), nullable=True)

    deleter = db.relationship('EmployeeGovernment', foreign_keys=[deleted_by], remote_side=[id])

    # ─── BIOTIME SYNC ───────────────────────────────────────────────────────────
    biotime_emp_id   = db.Column(db.Integer, nullable=True)
    assigned_devices = db.Column(db.Text, nullable=True)
    last_sync        = db.Column(db.DateTime, nullable=True)
    fp_enrolled      = db.Column(db.Boolean, default=False)
    face_enrolled    = db.Column(db.Boolean, default=False)
    sync_status      = db.Column(db.String(20), default='not_synced')

    @property
    def assigned_device_ids(self):
        raw = self.assigned_devices
        if not raw:
            return []
        try:
            import json
            return json.loads(raw)
        except Exception:
            return []

    @assigned_device_ids.setter
    def assigned_device_ids(self, value):
        import json
        self.assigned_devices = json.dumps(value, ensure_ascii=False)

    # ─── RELATIONSHIPS ──────────────────────────────────────────────────────────
    attendance_logs     = db.relationship('AttendanceLog', backref='gov_employee', lazy=True,
                                          foreign_keys='AttendanceLog.employee_id',
                                          primaryjoin='EmployeeGovernment.id == AttendanceLog.employee_id')
    leave_requests      = db.relationship('EmployeeLeaveRequest', backref='gov_employee', lazy=True,
                                          foreign_keys='EmployeeLeaveRequest.employee_id',
                                          primaryjoin='EmployeeGovernment.id == EmployeeLeaveRequest.employee_id')
    children            = db.relationship('EmployeeChild', backref='gov_employee', lazy=True,
                                          cascade='all, delete-orphan',
                                          primaryjoin='EmployeeGovernment.id == EmployeeChild.employee_id',
                                          foreign_keys='EmployeeChild.employee_id')
    qualifications      = db.relationship('EmployeeQualification', backref='gov_employee', lazy=True,
                                          cascade='all, delete-orphan',
                                          primaryjoin='EmployeeGovernment.id == EmployeeQualification.employee_id',
                                          foreign_keys='EmployeeQualification.employee_id')
    certifications      = db.relationship('EmployeeCertification', backref='gov_employee', lazy=True,
                                          cascade='all, delete-orphan',
                                          primaryjoin='EmployeeGovernment.id == EmployeeCertification.employee_id',
                                          foreign_keys='EmployeeCertification.employee_id')
    promotions          = db.relationship('EmployeePromotion', backref='gov_employee', lazy=True,
                                          foreign_keys='EmployeePromotion.employee_id',
                                          primaryjoin='EmployeeGovernment.id == EmployeePromotion.employee_id')
    promotion_eligibility = db.relationship('PromotionEligibility', backref='gov_employee', lazy=True,
                                            foreign_keys='PromotionEligibility.employee_id',
                                            primaryjoin='EmployeeGovernment.id == PromotionEligibility.employee_id')
    leave_balances      = db.relationship('EmployeeLeaveBalance', backref='gov_employee', lazy=True,
                                          foreign_keys='EmployeeLeaveBalance.employee_id',
                                          primaryjoin='EmployeeGovernment.id == EmployeeLeaveBalance.employee_id')
    training_records    = db.relationship('EmployeeTraining', backref='gov_employee', lazy=True,
                                          foreign_keys='EmployeeTraining.employee_id',
                                          primaryjoin='EmployeeGovernment.id == EmployeeTraining.employee_id')
    performance_evals   = db.relationship('EmployeePerformance', backref='gov_employee', lazy=True,
                                          foreign_keys='EmployeePerformance.employee_id',
                                          primaryjoin='EmployeeGovernment.id == EmployeePerformance.employee_id')
    disciplinary_actions = db.relationship('EmployeeDisciplinaryAction', backref='gov_employee', lazy=True,
                                           foreign_keys='EmployeeDisciplinaryAction.employee_id',
                                           primaryjoin='EmployeeGovernment.id == EmployeeDisciplinaryAction.employee_id')
    delegations         = db.relationship('EmployeeDelegation', backref='gov_employee', lazy=True,
                                          foreign_keys='EmployeeDelegation.employee_id',
                                          primaryjoin='EmployeeGovernment.id == EmployeeDelegation.employee_id')

    # ─── CLAIMS EXPIRY ─────────────────────────────────────────────────────────

    @property
    def claims_expiry_status(self):
        """Returns a dict with the nearest expiring administrative claim."""
        today = date.today()
        claims = []
        for label, field in [
            ('تصريح أمني', self.clearance_expiry),
            ('جواز سفر', self.passport_expiry),
            ('بطاقة هوية', self.id_expiry_date),
            ('عقد عمل', self.contract_end_date if not self.no_end_date else None),
        ]:
            if field:
                delta = (field - today).days
                claims.append({'label': label, 'date': field, 'delta': delta, 'status':
                    'expired' if delta < 0 else 'expiring_soon' if delta <= 7 else 'active'})
        claims.sort(key=lambda c: c['delta'])
        nearest = claims[0] if claims else None
        return {
            'claims': claims,
            'nearest_label': nearest['label'] if nearest else None,
            'nearest_delta': nearest['delta'] if nearest else None,
            'nearest_status': nearest['status'] if nearest else None,
        }

    # ─── SERIALIZATION ──────────────────────────────────────────────────────────

    def to_dict(self, include_sensitive=False):
        d = {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'second_name': self.second_name,
            'third_name': self.third_name,
            'fourth_name': self.fourth_name,
            'family_name': self.family_name,
            'full_name': self.full_name,
            'department': self.department,
            'department_id': self.department_id,
            'role': self.role,
            'is_active': self.is_active,
            'national_id': self.national_id,
            'national_id_verified': self.national_id_verified,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'age': self.age,
            'gender': self.gender,
            'marital_status': self.marital_status,
            'passport_number': self.passport_number,
            'passport_expiry': self.passport_expiry.isoformat() if self.passport_expiry else None,
            'id_expiry_date': self.id_expiry_date.isoformat() if self.id_expiry_date else None,
            'id_issuing_authority': self.id_issuing_authority,
            'personal_phone': self.secure_phone,
            'work_phone': self.work_phone,
            'personal_email': self.secure_email,
            'work_email': self.work_email,
            'permanent_address': self.permanent_address,
            'current_address': self.current_address,
            'residence_province': self.residence_province,
            'emergency_name': self.emergency_name,
            'emergency_phone': self.emergency_phone,
            'emergency_relation': self.emergency_relation,
            'profile_photo': self.profile_photo,
            'job_title': self.job_title,
            'employment_type': self.employment_type,
            'contract_type': self.contract_type,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'contract_end_date': self.contract_end_date.isoformat() if self.contract_end_date else None,
            'no_end_date': self.no_end_date,
            'job_classification': self.job_classification,
            'career_path': self.career_path,
            'category': self.category,
            'grade_id': self.grade_id,
            'manager_id': self.manager_id,
            'branch_id': self.branch_id,
            'base_salary': self.base_salary,
            'housing_allowance': self.housing_allowance or 0.0,
            'transport_allowance': self.transport_allowance or 0.0,
            'responsibility_allowance': self.responsibility_allowance or 0.0,
            'hazard_allowance': self.hazard_allowance or 0.0,
            'other_allowances': self.other_allowances_list,
            'total_salary': self.total_salary,
            'payment_method': self.payment_method,
            'bank_name': self.bank_name,
            'bank_account_name': self.bank_account_name,
            'bank_account_number': self.bank_account_number if include_sensitive else None,
            'iban': self.iban if include_sensitive else None,
            'bank_account_type': self.bank_account_type,
            'bank_branch': self.bank_branch,
            'bank_account_verified': self.bank_account_verified,
            'spouse_name': self.spouse_name,
            'dependent_children': self.dependent_children,
            'gov_file_number': self.gov_file_number,
            'gov_central_emp_id': self.gov_central_emp_id,
            'gov_region': self.gov_region,
            'gov_sector': self.gov_sector,
            'gov_parent_institution': self.gov_parent_institution,
            'gov_supervisory_body': self.gov_supervisory_body,
            'administrative_region': self.administrative_region,
            'work_region': self.work_region,
            'clearance_level': self.clearance_level,
            'clearance_date': self.clearance_date.isoformat() if self.clearance_date else None,
            'clearance_expiry': self.clearance_expiry.isoformat() if self.clearance_expiry else None,
            'clearance_authority': self.clearance_authority,
            'social_security_number': self.social_security_number,
            'social_security_start': self.social_security_start.isoformat() if self.social_security_start else None,
            'social_security_rate': self.social_security_rate,
            'accumulated_contributions': self.accumulated_contributions,
            'health_insurance_level': self.health_insurance_level,
            'health_insurance_dependents': self.health_insurance_dependents,
            'health_insurance_premium': self.health_insurance_premium,
            'life_insurance_coverage': self.life_insurance_coverage,
            'life_insurance_beneficiary': self.life_insurance_beneficiary,
            'life_insurance_premium': self.life_insurance_premium,
            'injury_insurance_coverage': self.injury_insurance_coverage,
            'retirement_age': self.retirement_age,
            'pension_rate': self.pension_rate,
            'years_of_service': self.years_of_service,
            'years_to_retirement': self.years_to_retirement,
            'expected_pension': self.expected_pension,
            'annual_leave_days': self.annual_leave_days,
            'sick_leave_days': self.sick_leave_days,
            'maternity_leave_days': self.maternity_leave_days,
            'paternity_leave_days': self.paternity_leave_days,
            'marriage_leave_days': self.marriage_leave_days,
            'hajj_leave_days': self.hajj_leave_days,
            'carried_over_days': self.carried_over_days,
            'used_leave_days': self.used_leave_days,
            'remaining_leave_days': self.remaining_leave_days,
            'permission_level': self.permission_level,
            'force_password_change': self.force_password_change,
            'two_factor_enabled': self.two_factor_enabled,
            'device_id': self.device_id,
            'biotime_emp_id': self.biotime_emp_id,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'fp_enrolled': self.fp_enrolled,
            'face_enrolled': self.face_enrolled,
            'sync_status': self.sync_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'claims_expiry_status': self.claims_expiry_status,
        }
        return d
