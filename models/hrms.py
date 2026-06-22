from datetime import datetime, UTC
from models import db, get_fernet


class EmployeeProfile(db.Model):
    __tablename__ = 'employee_profiles'
    id             = db.Column(db.Integer, primary_key=True)
    employee_id    = db.Column(db.Integer, db.ForeignKey('employees.id'), unique=True, nullable=False)
    job_title      = db.Column(db.String(100), nullable=True)
    hire_date      = db.Column(db.Date, nullable=True)
    marital_status = db.Column(db.String(20), nullable=True)
    contract_expiry = db.Column(db.Date, nullable=True)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at     = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    employee       = db.relationship('Employee', backref=db.backref('profile', uselist=False))


class LeaveBalance(db.Model):
    __tablename__ = 'leave_balances'
    id             = db.Column(db.Integer, primary_key=True)
    employee_id    = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type     = db.Column(db.String(50), nullable=False)
    total_days     = db.Column(db.Float, default=0.0)
    used_days      = db.Column(db.Float, default=0.0)
    remaining_days = db.Column(db.Float, default=0.0)
    updated_at     = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    employee       = db.relationship('Employee', backref='leave_balances')

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'leave_type', name='uq_employee_leave_type'),
    )


class SalarySlipArchive(db.Model):
    __tablename__ = 'salary_slip_archives'
    id                   = db.Column(db.Integer, primary_key=True)
    employee_id          = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    month                = db.Column(db.Integer, nullable=False)
    year                 = db.Column(db.Integer, nullable=False)
    base_salary_snapshot = db.Column(db.Text, nullable=True)
    deductions           = db.Column(db.Float, default=0.0)
    overtime_pay         = db.Column(db.Float, default=0.0)
    net_salary           = db.Column(db.Float, default=0.0)
    archived_at          = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee             = db.relationship('Employee', backref='salary_archives')

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'month', 'year', name='uq_employee_month_year'),
    )

    @property
    def base_salary(self):
        raw = self.base_salary_snapshot
        if not raw:
            return 0.0
        try:
            return float(get_fernet().decrypt(raw.encode()).decode())
        except Exception:
            return 0.0

    @base_salary.setter
    def base_salary(self, value):
        if value is None:
            self.base_salary_snapshot = None
        else:
            val = float(value)
            self.base_salary_snapshot = get_fernet().encrypt(str(val).encode()).decode()
