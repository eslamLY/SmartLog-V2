"""add_hrms_tables

Revision ID: 8e05534ba61c
Revises: 1258ca850335
Create Date: 2026-06-18 11:56:15.968023

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e05534ba61c'
down_revision = '1258ca850335'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('employee_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('job_title', sa.String(length=100), nullable=True),
    sa.Column('hire_date', sa.Date(), nullable=True),
    sa.Column('marital_status', sa.String(length=20), nullable=True),
    sa.Column('contract_expiry', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id')
    )
    op.create_table('leave_balances',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('leave_type', sa.String(length=50), nullable=False),
    sa.Column('total_days', sa.Float(), nullable=True),
    sa.Column('used_days', sa.Float(), nullable=True),
    sa.Column('remaining_days', sa.Float(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id', 'leave_type', name='uq_employee_leave_type')
    )
    op.create_table('salary_slip_archives',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('base_salary_snapshot', sa.Text(), nullable=True),
    sa.Column('deductions', sa.Float(), nullable=True),
    sa.Column('overtime_pay', sa.Float(), nullable=True),
    sa.Column('net_salary', sa.Float(), nullable=True),
    sa.Column('archived_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id', 'month', 'year', name='uq_employee_month_year')
    )


def downgrade():
    op.drop_table('salary_slip_archives')
    op.drop_table('leave_balances')
    op.drop_table('employee_profiles')
