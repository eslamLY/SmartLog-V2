"""Add payroll tables

Revision ID: d4f2c8b1a93e
Revises: eb8eca36e3c9
Create Date: 2026-06-19 02:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, UTC

revision = 'd4f2c8b1a93e'
down_revision = 'eb8eca36e3c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('payroll_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('base_salary', sa.Float(), nullable=True),
        sa.Column('housing_allowance', sa.Float(), nullable=True),
        sa.Column('transport_allowance', sa.Float(), nullable=True),
        sa.Column('other_allowances', sa.Float(), nullable=True),
        sa.Column('total_allowances', sa.Float(), nullable=True),
        sa.Column('overtime_hours', sa.Float(), nullable=True),
        sa.Column('overtime_pay', sa.Float(), nullable=True),
        sa.Column('gross_salary', sa.Float(), nullable=True),
        sa.Column('late_minutes', sa.Integer(), nullable=True),
        sa.Column('late_deduction', sa.Float(), nullable=True),
        sa.Column('absent_days', sa.Integer(), nullable=True),
        sa.Column('absent_deduction', sa.Float(), nullable=True),
        sa.Column('other_deductions', sa.Float(), nullable=True),
        sa.Column('total_deductions', sa.Float(), nullable=True),
        sa.Column('income_tax', sa.Float(), nullable=True),
        sa.Column('social_security', sa.Float(), nullable=True),
        sa.Column('total_tax', sa.Float(), nullable=True),
        sa.Column('net_salary', sa.Float(), nullable=True),
        sa.Column('payment_method', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', 'month', 'year', name='uq_employee_payroll_month'),
    )
    op.create_table('salary_components',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payroll_record_id', sa.Integer(), sa.ForeignKey('payroll_records.id'), nullable=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('component_type', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('is_earning', sa.Boolean(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('deduction_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payroll_record_id', sa.Integer(), sa.ForeignKey('payroll_records.id'), nullable=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('deduction_type', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('days_count', sa.Integer(), nullable=True),
        sa.Column('minutes_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('salary_advances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('installments_count', sa.Integer(), nullable=True),
        sa.Column('installment_amount', sa.Float(), nullable=True),
        sa.Column('installments_paid', sa.JSON(), nullable=True),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('auto_deduct', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('settled_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('approval_workflows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('current_gross', sa.Float(), nullable=True),
        sa.Column('proposed_gross', sa.Float(), nullable=True),
        sa.Column('proposed_net', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('current_step', sa.Integer(), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('approval_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), sa.ForeignKey('approval_workflows.id'), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('approver_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('approver_name', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('acted_at', sa.DateTime(), nullable=True),
        sa.Column('acted_by', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('payroll_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('bank_payment_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('net_amount', sa.Float(), nullable=True),
        sa.Column('iban', sa.String(length=30), nullable=True),
        sa.Column('bank_name', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('transaction_id', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', 'month', 'year', name='uq_bank_payment_month'),
    )


def downgrade():
    op.drop_table('bank_payment_details')
    op.drop_table('payroll_audit_logs')
    op.drop_table('approval_steps')
    op.drop_table('approval_workflows')
    op.drop_table('salary_advances')
    op.drop_table('deduction_records')
    op.drop_table('salary_components')
    op.drop_table('payroll_records')
