from datetime import datetime, date, UTC
from models import db


class PayrollRecord(db.Model):
    __tablename__ = 'payroll_records'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    base_salary = db.Column(db.Float, default=0)
    housing_allowance = db.Column(db.Float, default=0)
    transport_allowance = db.Column(db.Float, default=0)
    other_allowances = db.Column(db.Float, default=0)
    total_allowances = db.Column(db.Float, default=0)
    overtime_hours = db.Column(db.Float, default=0)
    overtime_pay = db.Column(db.Float, default=0)
    gross_salary = db.Column(db.Float, default=0)
    late_minutes = db.Column(db.Integer, default=0)
    late_deduction = db.Column(db.Float, default=0)
    absent_days = db.Column(db.Integer, default=0)
    absent_deduction = db.Column(db.Float, default=0)
    other_deductions = db.Column(db.Float, default=0)
    total_deductions = db.Column(db.Float, default=0)
    income_tax = db.Column(db.Float, default=0)
    social_security = db.Column(db.Float, default=0)
    total_tax = db.Column(db.Float, default=0)
    net_salary = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(20), default='bank_transfer')
    status = db.Column(db.String(20), default='calculated')
    notes = db.Column(db.Text, nullable=True)
    calculated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='payroll_records')
    approver = db.relationship('Employee', foreign_keys=[approved_by])

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'month', 'year', name='uq_employee_payroll_month'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'month': self.month,
            'year': self.year,
            'base_salary': self.base_salary,
            'total_allowances': self.total_allowances,
            'overtime_pay': self.overtime_pay,
            'gross_salary': self.gross_salary,
            'total_deductions': self.total_deductions,
            'total_tax': self.total_tax,
            'net_salary': self.net_salary,
            'status': self.status,
            'payment_method': self.payment_method,
            'notes': self.notes,
        }


class SalaryComponent(db.Model):
    __tablename__ = 'salary_components'
    id = db.Column(db.Integer, primary_key=True)
    payroll_record_id = db.Column(db.Integer, db.ForeignKey('payroll_records.id'), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    component_type = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, default=0)
    is_earning = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    payroll_record = db.relationship('PayrollRecord', backref='components')
    employee = db.relationship('Employee', foreign_keys=[employee_id])


class DeductionRecord(db.Model):
    __tablename__ = 'deduction_records'
    id = db.Column(db.Integer, primary_key=True)
    payroll_record_id = db.Column(db.Integer, db.ForeignKey('payroll_records.id'), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    deduction_type = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, default=0)
    reason = db.Column(db.Text, nullable=True)
    days_count = db.Column(db.Integer, default=0)
    minutes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    payroll_record = db.relationship('PayrollRecord', backref='deductions')
    employee = db.relationship('Employee', foreign_keys=[employee_id])


class SalaryAdvance(db.Model):
    __tablename__ = 'salary_advances'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    installments_count = db.Column(db.Integer, default=1)
    installment_amount = db.Column(db.Float, default=0)
    installments_paid = db.Column(db.JSON, default=list)
    reason = db.Column(db.String(200), nullable=True)
    auto_deduct = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    settled_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='salary_advances')

    def to_dict(self):
        repaid = sum(self.installments_paid or [])
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'amount': self.amount,
            'repaid': repaid,
            'remaining': round(self.amount - repaid, 2),
            'installments_count': self.installments_count,
            'installment_amount': self.installment_amount,
            'installments_paid': self.installments_paid or [],
            'repaid_pct': round(repaid / self.amount * 100, 1) if self.amount else 0,
            'reason': self.reason or '',
            'auto_deduct': self.auto_deduct,
            'status': self.status,
            'notes': self.notes or '',
            'created_at': self.created_at.isoformat() if self.created_at else '',
            'settled_at': self.settled_at.isoformat() if self.settled_at else '',
        }


class ApprovalWorkflow(db.Model):
    __tablename__ = 'approval_workflows'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    current_gross = db.Column(db.Float, default=0)
    proposed_gross = db.Column(db.Float, default=0)
    proposed_net = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')
    current_step = db.Column(db.Integer, default=1)
    total_steps = db.Column(db.Integer, default=2)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='approval_workflows')
    reviewer = db.relationship('Employee', foreign_keys=[reviewed_by])


class ApprovalStep(db.Model):
    __tablename__ = 'approval_steps'
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('approval_workflows.id'), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    approver_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending')
    comment = db.Column(db.Text, nullable=True)
    acted_at = db.Column(db.DateTime, nullable=True)
    acted_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    workflow = db.relationship('ApprovalWorkflow', backref='steps')
    approver = db.relationship('Employee', foreign_keys=[approver_id])
    actor = db.relationship('Employee', foreign_keys=[acted_by])


class PayrollAuditLog(db.Model):
    __tablename__ = 'payroll_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    changed_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    details = db.Column(db.Text, nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    @staticmethod
    def log(action, employee_id=None, changed_by=None, details='',
            old_value='', new_value='', ip_address=None):
        log_entry = PayrollAuditLog(
            action=action,
            employee_id=employee_id,
            changed_by=changed_by,
            details=details,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry

    ACTION_NAMES = {
        'initiate_approval': 'بدء طلب موافقة',
        'approval_approve': 'موافقة على الراتب',
        'approval_reject': 'رفض طلب الراتب',
        'approval_request_changes': 'طلب تعديل الراتب',
        'cancel_approval': 'إلغاء طلب موافقة',
        'create_advance': 'إنشاء سلفة',
        'repay_advance': 'سداد سلفة',
        'salary_adjustment': 'تعديل راتب',
        'bulk_salary_change': 'تعديل رواتب جماعي',
        'save_payroll': 'حفظ كشف راتب',
        'export_payroll': 'تصدير كشف راتب',
        'generate_bank_payments': 'إنشاء مدفوعات بنكية',
        'update_bank_status': 'تحديث حالة دفع بنكي',
        'print_payslip': 'طباعة كشف راتب',
    }

    def get_action_arabic(self):
        return self.ACTION_NAMES.get(self.action, self.action)


class BankPaymentDetail(db.Model):
    __tablename__ = 'bank_payment_details'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    net_amount = db.Column(db.Float, default=0)
    iban = db.Column(db.String(30), nullable=True)
    bank_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending')
    payment_date = db.Column(db.Date, nullable=True)
    transaction_id = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='bank_payments')

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'month', 'year', name='uq_bank_payment_month'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'month': self.month,
            'year': self.year,
            'net_amount': self.net_amount,
            'iban': self.iban or '',
            'bank_name': self.bank_name or '',
            'status': self.status,
            'payment_date': self.payment_date.isoformat() if self.payment_date else '',
            'transaction_id': self.transaction_id or '',
            'notes': self.notes or '',
        }
