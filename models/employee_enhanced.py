from datetime import datetime, date, UTC
from models import db

# ─── EXTENDED EMPLOYEE INFO (one-to-one with Employee) ──────────────────────

class EmployeeExtended(db.Model):
    __tablename__ = 'employee_extended'
    id               = db.Column(db.Integer, primary_key=True)
    employee_id      = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), unique=True, nullable=False)

    # Personal ID Documentation
    national_id           = db.Column(db.String(20), unique=True, nullable=True)
    passport_number       = db.Column(db.String(30), nullable=True)
    id_expiry_date        = db.Column(db.Date, nullable=True)
    id_issuing_authority  = db.Column(db.String(100), nullable=True)
    id_verified           = db.Column(db.Boolean, default=False)

    # Contact Enhancement
    personal_phone   = db.Column(db.String(20), nullable=True)
    work_phone       = db.Column(db.String(20), nullable=True)
    personal_email   = db.Column(db.String(120), nullable=True)
    work_email       = db.Column(db.String(120), nullable=True)
    permanent_address = db.Column(db.Text, nullable=True)
    current_address   = db.Column(db.Text, nullable=True)

    # Emergency Contact
    emergency_name   = db.Column(db.String(100), nullable=True)
    emergency_phone  = db.Column(db.String(20), nullable=True)
    emergency_relation = db.Column(db.String(30), nullable=True)

    # Bank Details (Government Payment)
    bank_name          = db.Column(db.String(100), nullable=True)
    bank_account_name  = db.Column(db.String(100), nullable=True)
    iban               = db.Column(db.String(34), nullable=True)
    bank_account_type  = db.Column(db.String(20), default='personal')
    bank_branch        = db.Column(db.String(100), nullable=True)
    bank_account_verified = db.Column(db.Boolean, default=False)

    # Family Information
    marital_status      = db.Column(db.String(20), default='single')
    spouse_name         = db.Column(db.String(100), nullable=True)
    dependent_children  = db.Column(db.Integer, default=0)

    # Employment Grade
    grade_id            = db.Column(db.Integer, db.ForeignKey('employee_grades.id'), nullable=True)
    job_classification  = db.Column(db.String(50), nullable=True)
    career_path         = db.Column(db.String(100), nullable=True)
    contract_type       = db.Column(db.String(30), default='permanent')

    # Government Data
    gov_file_number     = db.Column(db.String(50), unique=True, nullable=True)
    gov_central_emp_id  = db.Column(db.String(50), nullable=True)
    gov_region          = db.Column(db.String(50), nullable=True)
    gov_sector          = db.Column(db.String(100), nullable=True)
    gov_parent_institution = db.Column(db.String(200), nullable=True)
    gov_supervisory_body   = db.Column(db.String(200), nullable=True)

    # Security Clearance
    clearance_level     = db.Column(db.String(30), default='public')
    clearance_date      = db.Column(db.Date, nullable=True)
    clearance_expiry    = db.Column(db.Date, nullable=True)
    clearance_authority = db.Column(db.String(100), nullable=True)

    # Social Security
    social_security_number = db.Column(db.String(30), nullable=True)
    social_security_start  = db.Column(db.Date, nullable=True)
    social_security_rate   = db.Column(db.Float, default=8.0)
    accumulated_contributions = db.Column(db.Float, default=0.0)

    # Health Insurance
    health_insurance_level   = db.Column(db.String(30), default='basic')
    health_insurance_dependents = db.Column(db.Integer, default=0)
    health_insurance_premium = db.Column(db.Float, default=0.0)

    # Life Insurance
    life_insurance_coverage    = db.Column(db.Float, default=0.0)
    life_insurance_beneficiary = db.Column(db.String(100), nullable=True)
    life_insurance_premium     = db.Column(db.Float, default=0.0)

    # Work Injury Insurance
    injury_insurance_coverage = db.Column(db.Float, default=0.0)

    # Retirement
    retirement_age      = db.Column(db.Integer, default=60)
    pension_rate        = db.Column(db.Float, default=2.5)
    years_of_service    = db.Column(db.Float, default=0.0)
    expected_pension    = db.Column(db.Float, default=0.0)

    # Annual leave defaults (Libyan government standard)
    annual_leave_days    = db.Column(db.Integer, default=30)
    sick_leave_days      = db.Column(db.Integer, default=15)
    maternity_leave_days = db.Column(db.Integer, default=60)
    paternity_leave_days = db.Column(db.Integer, default=5)
    marriage_leave_days  = db.Column(db.Integer, default=7)
    hajj_leave_days      = db.Column(db.Integer, default=15)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref=db.backref('extended', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'national_id': self.national_id,
            'passport_number': self.passport_number,
            'id_expiry_date': self.id_expiry_date.isoformat() if self.id_expiry_date else None,
            'id_issuing_authority': self.id_issuing_authority,
            'id_verified': self.id_verified,
            'personal_phone': self.personal_phone,
            'work_phone': self.work_phone,
            'personal_email': self.personal_email,
            'work_email': self.work_email,
            'permanent_address': self.permanent_address,
            'current_address': self.current_address,
            'emergency_name': self.emergency_name,
            'emergency_phone': self.emergency_phone,
            'emergency_relation': self.emergency_relation,
            'bank_name': self.bank_name,
            'bank_account_name': self.bank_account_name,
            'iban': self.iban,
            'bank_account_type': self.bank_account_type,
            'bank_branch': self.bank_branch,
            'bank_account_verified': self.bank_account_verified,
            'marital_status': self.marital_status,
            'spouse_name': self.spouse_name,
            'dependent_children': self.dependent_children,
            'grade_id': self.grade_id,
            'job_classification': self.job_classification,
            'career_path': self.career_path,
            'contract_type': self.contract_type,
            'gov_file_number': self.gov_file_number,
            'gov_central_emp_id': self.gov_central_emp_id,
            'gov_region': self.gov_region,
            'gov_sector': self.gov_sector,
            'gov_parent_institution': self.gov_parent_institution,
            'gov_supervisory_body': self.gov_supervisory_body,
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
            'expected_pension': self.expected_pension,
            'annual_leave_days': self.annual_leave_days,
            'sick_leave_days': self.sick_leave_days,
            'maternity_leave_days': self.maternity_leave_days,
            'paternity_leave_days': self.paternity_leave_days,
            'marriage_leave_days': self.marriage_leave_days,
            'hajj_leave_days': self.hajj_leave_days,
        }


# ─── EMPLOYEE CHILDREN (for family allowance) ──────────────────────────────

class EmployeeChild(db.Model):
    __tablename__ = 'employee_children'
    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    full_name   = db.Column(db.String(100), nullable=False)
    birth_date  = db.Column(db.Date, nullable=False)
    relation    = db.Column(db.String(30), default='child')
    is_student  = db.Column(db.Boolean, default=False)
    is_disabled = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='children')

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'full_name': self.full_name,
            'birth_date': self.birth_date.isoformat() if self.birth_date else None,
            'relation': self.relation,
            'is_student': self.is_student,
            'is_disabled': self.is_disabled,
        }


# ─── EMPLOYEE GRADE / RANK (الدرجة الوظيفية) ───────────────────────────────

class EmployeeGrade(db.Model):
    __tablename__ = 'employee_grades'
    id                 = db.Column(db.Integer, primary_key=True)
    code               = db.Column(db.String(20), unique=True, nullable=False)
    name_ar            = db.Column(db.String(100), nullable=False)
    category           = db.Column(db.String(30), nullable=False)
    level              = db.Column(db.Integer, nullable=False)
    base_salary        = db.Column(db.Float, default=0.0)
    responsibility_allowance = db.Column(db.Float, default=0.0)
    hazard_allowance   = db.Column(db.Float, default=0.0)
    transport_allowance = db.Column(db.Float, default=0.0)
    housing_allowance  = db.Column(db.Float, default=0.0)
    medical_insurance_level = db.Column(db.String(30), default='basic')
    annual_leave_days  = db.Column(db.Integer, default=30)
    sick_leave_days    = db.Column(db.Integer, default=15)
    retirement_age     = db.Column(db.Integer, default=60)
    pension_rate       = db.Column(db.Float, default=2.5)
    min_years_for_promotion = db.Column(db.Integer, default=5)
    required_qualification = db.Column(db.String(50), nullable=True)
    next_grade_id      = db.Column(db.Integer, db.ForeignKey('employee_grades.id'), nullable=True)
    is_active          = db.Column(db.Boolean, default=True)
    created_at         = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    next_grade = db.relationship('EmployeeGrade', remote_side=[id])

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name_ar': self.name_ar,
            'category': self.category,
            'level': self.level,
            'base_salary': self.base_salary,
            'responsibility_allowance': self.responsibility_allowance,
            'hazard_allowance': self.hazard_allowance,
            'transport_allowance': self.transport_allowance,
            'housing_allowance': self.housing_allowance,
            'medical_insurance_level': self.medical_insurance_level,
            'annual_leave_days': self.annual_leave_days,
            'sick_leave_days': self.sick_leave_days,
            'retirement_age': self.retirement_age,
            'pension_rate': self.pension_rate,
            'min_years_for_promotion': self.min_years_for_promotion,
            'required_qualification': self.required_qualification,
            'next_grade_id': self.next_grade_id,
            'is_active': self.is_active,
        }


# ─── QUALIFICATIONS (المؤهلات التعليمية) ────────────────────────────────────

class EmployeeQualification(db.Model):
    __tablename__ = 'employee_qualifications'
    id               = db.Column(db.Integer, primary_key=True)
    employee_id      = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    level            = db.Column(db.String(30), nullable=False)
    specialization   = db.Column(db.String(100), nullable=False)
    institution      = db.Column(db.String(200), nullable=False)
    graduation_year  = db.Column(db.Integer, nullable=False)
    grade            = db.Column(db.String(30), nullable=True)
    is_foreign       = db.Column(db.Boolean, default=False)
    equivalency_file = db.Column(db.String(200), nullable=True)
    certificate_file = db.Column(db.String(200), nullable=True)
    is_verified      = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='qualifications')

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'level': self.level,
            'specialization': self.specialization,
            'institution': self.institution,
            'graduation_year': self.graduation_year,
            'grade': self.grade,
            'is_foreign': self.is_foreign,
            'equivalency_file': self.equivalency_file,
            'certificate_file': self.certificate_file,
            'is_verified': self.is_verified,
        }


# ─── CERTIFICATIONS (الشهادات المهنية) ──────────────────────────────────────

class EmployeeCertification(db.Model):
    __tablename__ = 'employee_certifications'
    id               = db.Column(db.Integer, primary_key=True)
    employee_id      = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    cert_type        = db.Column(db.String(100), nullable=False)
    cert_number      = db.Column(db.String(50), nullable=True)
    issuing_body     = db.Column(db.String(200), nullable=False)
    issue_date       = db.Column(db.Date, nullable=False)
    expiry_date      = db.Column(db.Date, nullable=True)
    is_valid         = db.Column(db.Boolean, default=True)
    cert_file        = db.Column(db.String(200), nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='certifications')

    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - date.today()
        return delta.days

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'cert_type': self.cert_type,
            'cert_number': self.cert_number,
            'issuing_body': self.issuing_body,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'is_valid': self.is_valid,
            'cert_file': self.cert_file,
            'days_until_expiry': self.days_until_expiry(),
        }


# ─── PROMOTIONS (الترقيات) ──────────────────────────────────────────────────

class EmployeePromotion(db.Model):
    __tablename__ = 'employee_promotions'
    id               = db.Column(db.Integer, primary_key=True)
    employee_id      = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    from_grade_id    = db.Column(db.Integer, db.ForeignKey('employee_grades.id'), nullable=True)
    to_grade_id      = db.Column(db.Integer, db.ForeignKey('employee_grades.id'), nullable=False)
    from_grade_name  = db.Column(db.String(100), nullable=True)
    to_grade_name    = db.Column(db.String(100), nullable=False)
    from_salary      = db.Column(db.Float, default=0.0)
    to_salary        = db.Column(db.Float, default=0.0)
    decision_number  = db.Column(db.String(50), nullable=True)
    decision_date    = db.Column(db.Date, nullable=True)
    effective_date   = db.Column(db.Date, nullable=False)
    approved_by      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    justification    = db.Column(db.Text, nullable=True)
    status           = db.Column(db.String(20), default='completed')
    notes            = db.Column(db.Text, nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee  = db.relationship('Employee', foreign_keys=[employee_id], backref='promotions')
    approver  = db.relationship('Employee', foreign_keys=[approved_by])
    from_grade = db.relationship('EmployeeGrade', foreign_keys=[from_grade_id])
    to_grade   = db.relationship('EmployeeGrade', foreign_keys=[to_grade_id])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'from_grade_id': self.from_grade_id,
            'to_grade_id': self.to_grade_id,
            'from_grade_name': self.from_grade_name,
            'to_grade_name': self.to_grade_name,
            'from_salary': self.from_salary,
            'to_salary': self.to_salary,
            'decision_number': self.decision_number,
            'decision_date': self.decision_date.isoformat() if self.decision_date else None,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'approved_by': self.approved_by,
            'approver_name': self.approver.full_name if self.approver else None,
            'justification': self.justification,
            'status': self.status,
            'notes': self.notes,
        }


# ─── PROMOTION ELIGIBILITY (متطلبات الترقية) ────────────────────────────────

class PromotionEligibility(db.Model):
    __tablename__ = 'promotion_eligibility'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    current_grade_id  = db.Column(db.Integer, db.ForeignKey('employee_grades.id'), nullable=True)
    target_grade_id   = db.Column(db.Integer, db.ForeignKey('employee_grades.id'), nullable=True)
    min_service_met   = db.Column(db.Boolean, default=False)
    performance_met   = db.Column(db.Boolean, default=False)
    qualifications_met = db.Column(db.Boolean, default=False)
    conduct_met       = db.Column(db.Boolean, default=False)
    total_requirements = db.Column(db.Integer, default=0)
    completed_requirements = db.Column(db.Integer, default=0)
    expected_date     = db.Column(db.Date, nullable=True)
    last_evaluated_at = db.Column(db.DateTime, nullable=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='promotion_eligibility')
    current_grade = db.relationship('EmployeeGrade', foreign_keys=[current_grade_id])
    target_grade  = db.relationship('EmployeeGrade', foreign_keys=[target_grade_id])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'current_grade_id': self.current_grade_id,
            'current_grade_name': self.current_grade.name_ar if self.current_grade else None,
            'target_grade_id': self.target_grade_id,
            'target_grade_name': self.target_grade.name_ar if self.target_grade else None,
            'min_service_met': self.min_service_met,
            'performance_met': self.performance_met,
            'qualifications_met': self.qualifications_met,
            'conduct_met': self.conduct_met,
            'total_requirements': self.total_requirements,
            'completed_requirements': self.completed_requirements,
            'expected_date': self.expected_date.isoformat() if self.expected_date else None,
        }


# ─── LEAVE MANAGEMENT ──────────────────────────────────────────────────────

class LeaveType(db.Model):
    __tablename__ = 'leave_types'
    id            = db.Column(db.Integer, primary_key=True)
    code          = db.Column(db.String(30), unique=True, nullable=False)
    name_ar       = db.Column(db.String(100), nullable=False)
    default_days  = db.Column(db.Integer, default=0)
    is_paid       = db.Column(db.Boolean, default=True)
    is_recurring  = db.Column(db.Boolean, default=True)
    max_consecutive = db.Column(db.Integer, nullable=True)
    requires_approval = db.Column(db.Boolean, default=True)
    notes         = db.Column(db.Text, nullable=True)
    is_active     = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name_ar': self.name_ar,
            'default_days': self.default_days,
            'is_paid': self.is_paid,
            'is_recurring': self.is_recurring,
            'max_consecutive': self.max_consecutive,
            'requires_approval': self.requires_approval,
            'notes': self.notes,
        }


class EmployeeLeaveBalance(db.Model):
    __tablename__ = 'employee_leave_balances'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    leave_type_id     = db.Column(db.Integer, db.ForeignKey('leave_types.id', ondelete='CASCADE'), nullable=False)
    year              = db.Column(db.Integer, nullable=False)
    total_days        = db.Column(db.Float, default=0.0)
    used_days         = db.Column(db.Float, default=0.0)
    remaining_days    = db.Column(db.Float, default=0.0)
    carried_over      = db.Column(db.Float, default=0.0)
    carry_expiry_date = db.Column(db.Date, nullable=True)
    updated_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    employee  = db.relationship('Employee', backref='leave_balances_new')
    leave_type = db.relationship('LeaveType')

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'leave_type_id', 'year', name='uq_emp_leave_year'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'leave_type_id': self.leave_type_id,
            'leave_type_name': self.leave_type.name_ar if self.leave_type else None,
            'year': self.year,
            'total_days': self.total_days,
            'used_days': self.used_days,
            'remaining_days': self.remaining_days,
            'carried_over': self.carried_over,
            'carry_expiry_date': self.carry_expiry_date.isoformat() if self.carry_expiry_date else None,
        }


class EmployeeLeaveRequest(db.Model):
    __tablename__ = 'employee_leave_requests'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    leave_type_id     = db.Column(db.Integer, db.ForeignKey('leave_types.id', ondelete='CASCADE'), nullable=False)
    start_date        = db.Column(db.Date, nullable=False)
    end_date          = db.Column(db.Date, nullable=False)
    total_days        = db.Column(db.Float, nullable=False)
    reason            = db.Column(db.Text, nullable=True)
    status            = db.Column(db.String(20), default='pending')
    reviewed_by       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    review_comment    = db.Column(db.Text, nullable=True)
    reviewed_at       = db.Column(db.DateTime, nullable=True)
    attachment        = db.Column(db.String(200), nullable=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee   = db.relationship('Employee', foreign_keys=[employee_id], backref='leave_requests_new')
    reviewer   = db.relationship('Employee', foreign_keys=[reviewed_by])
    leave_type = db.relationship('LeaveType')

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'leave_type_id': self.leave_type_id,
            'leave_type_name': self.leave_type.name_ar if self.leave_type else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'total_days': self.total_days,
            'reason': self.reason,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'review_comment': self.review_comment,
            'attachment': self.attachment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ─── OFFICIAL DELEGATIONS (المهام واللجان الرسمية) ─────────────────────────

class EmployeeDelegation(db.Model):
    __tablename__ = 'employee_delegations'
    id              = db.Column(db.Integer, primary_key=True)
    employee_id     = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    delegation_type = db.Column(db.String(100), nullable=False)
    delegation_body = db.Column(db.String(200), nullable=False)
    role            = db.Column(db.String(100), nullable=True)
    start_date      = db.Column(db.Date, nullable=False)
    end_date        = db.Column(db.Date, nullable=True)
    decision_number = db.Column(db.String(50), nullable=True)
    notes           = db.Column(db.Text, nullable=True)
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='delegations')

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'delegation_type': self.delegation_type,
            'delegation_body': self.delegation_body,
            'role': self.role,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'decision_number': self.decision_number,
            'notes': self.notes,
            'is_active': self.is_active,
        }


# ─── TRAINING & DEVELOPMENT ─────────────────────────────────────────────────

class EmployeeTraining(db.Model):
    __tablename__ = 'employee_training'
    id              = db.Column(db.Integer, primary_key=True)
    employee_id     = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    course_name     = db.Column(db.String(200), nullable=False)
    provider        = db.Column(db.String(200), nullable=False)
    start_date      = db.Column(db.Date, nullable=True)
    end_date        = db.Column(db.Date, nullable=True)
    duration_hours  = db.Column(db.Float, nullable=True)
    cert_earned     = db.Column(db.Boolean, default=False)
    cert_file       = db.Column(db.String(200), nullable=True)
    is_government_required = db.Column(db.Boolean, default=False)
    status          = db.Column(db.String(20), default='completed')
    notes           = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='training_records')

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'course_name': self.course_name,
            'provider': self.provider,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'duration_hours': self.duration_hours,
            'cert_earned': self.cert_earned,
            'cert_file': self.cert_file,
            'is_government_required': self.is_government_required,
            'status': self.status,
            'notes': self.notes,
        }


# ─── PERFORMANCE EVALUATIONS (تقييم الأداء) ─────────────────────────────────

class EmployeePerformance(db.Model):
    __tablename__ = 'employee_performance'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    evaluation_year   = db.Column(db.Integer, nullable=False)
    evaluation_period = db.Column(db.String(20), default='annual')
    overall_rating    = db.Column(db.String(30), nullable=True)
    score             = db.Column(db.Float, nullable=True)
    evaluated_by      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    comments          = db.Column(db.Text, nullable=True)
    goals_next_period = db.Column(db.Text, nullable=True)
    status            = db.Column(db.String(20), default='draft')
    completed_at      = db.Column(db.DateTime, nullable=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee   = db.relationship('Employee', foreign_keys=[employee_id], backref='performance_evaluations')
    evaluator  = db.relationship('Employee', foreign_keys=[evaluated_by])

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'evaluation_year', 'evaluation_period', name='uq_emp_eval_period'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'evaluation_year': self.evaluation_year,
            'evaluation_period': self.evaluation_period,
            'overall_rating': self.overall_rating,
            'score': self.score,
            'evaluated_by': self.evaluated_by,
            'evaluator_name': self.evaluator.full_name if self.evaluator else None,
            'comments': self.comments,
            'goals_next_period': self.goals_next_period,
            'status': self.status,
        }


# ─── DISCIPLINARY ACTIONS (الإجراءات التأديبية) ────────────────────────────

class EmployeeDisciplinaryAction(db.Model):
    __tablename__ = 'employee_disciplinary_actions'
    id               = db.Column(db.Integer, primary_key=True)
    employee_id      = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    action_type      = db.Column(db.String(50), nullable=False)
    description      = db.Column(db.Text, nullable=False)
    decision_number  = db.Column(db.String(50), nullable=True)
    decision_date    = db.Column(db.Date, nullable=True)
    issued_by        = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    duration_days    = db.Column(db.Integer, nullable=True)
    status           = db.Column(db.String(20), default='active')
    appeal_notes     = db.Column(db.Text, nullable=True)
    closed_at        = db.Column(db.DateTime, nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='disciplinary_actions')
    issuer   = db.relationship('Employee', foreign_keys=[issued_by])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'action_type': self.action_type,
            'description': self.description,
            'decision_number': self.decision_number,
            'decision_date': self.decision_date.isoformat() if self.decision_date else None,
            'issued_by': self.issued_by,
            'issuer_name': self.issuer.full_name if self.issuer else None,
            'duration_days': self.duration_days,
            'status': self.status,
            'appeal_notes': self.appeal_notes,
        }
