"""Add multi-tenancy: company tables + company_id columns

Revision ID: a1b2c3d4e5f6
Revises: d4f2c8b1a93e
Create Date: 2026-06-29 02:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, UTC

revision = 'a1b2c3d4e5f6'
down_revision = 'd4f2c8b1a93e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name_ar', sa.String(length=200), nullable=False),
        sa.Column('name_en', sa.String(length=200), nullable=True),
        sa.Column('domain', sa.String(length=100), nullable=True, unique=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(length=300), nullable=True),
        sa.Column('primary_color', sa.String(length=7), nullable=True),
        sa.Column('bg_color', sa.String(length=7), nullable=True),
        sa.Column('plan', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True),
        sa.Column('max_employees', sa.Integer(), nullable=True),
        sa.Column('max_devices', sa.Integer(), nullable=True),
        sa.Column('features_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('company_admins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('username', sa.String(length=60), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('biometric_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('serial_no', sa.String(length=60), nullable=False, unique=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('device_model', sa.String(length=30), nullable=True),
        sa.Column('firmware_ver', sa.String(length=20), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('branch_id', sa.Integer(), sa.ForeignKey('branches.id'), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('mac_address', sa.String(length=30), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('comm_password', sa.String(length=20), nullable=True),
        sa.Column('license_key', sa.String(length=64), nullable=True, unique=True),
        sa.Column('api_key', sa.String(length=64), nullable=True),
        sa.Column('protocol', sa.String(length=10), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_online', sa.Boolean(), nullable=True),
        sa.Column('last_online_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync', sa.DateTime(), nullable=True),
        sa.Column('fp_capacity', sa.Integer(), nullable=True),
        sa.Column('fp_enrolled', sa.Integer(), nullable=True),
        sa.Column('face_capacity', sa.Integer(), nullable=True),
        sa.Column('face_enrolled', sa.Integer(), nullable=True),
        sa.Column('card_capacity', sa.Integer(), nullable=True),
        sa.Column('card_enrolled', sa.Integer(), nullable=True),
        sa.Column('txlog_capacity', sa.Integer(), nullable=True),
        sa.Column('txlog_used', sa.Integer(), nullable=True),
        sa.Column('records_pulled', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('device_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('biometric_devices.id'), nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=True),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('employees', sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True))
    op.add_column('attendance_logs', sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True))
    op.add_column('attendance_logs', sa.Column('device_id', sa.Integer(), sa.ForeignKey('biometric_devices.id'), nullable=True))
    op.add_column('attendance_logs', sa.Column('device_serial', sa.String(length=60), nullable=True))
    op.add_column('biotime_devices', sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True))

    op.create_index('idx_attendance_company_date', 'attendance_logs', ['company_id', 'log_date'])
    op.create_index('idx_employee_company', 'employees', ['company_id'])
    op.create_index('idx_biometric_device_company', 'biometric_devices', ['company_id'])
    op.create_index('idx_device_sync_log_company', 'device_sync_logs', ['company_id', 'device_id'])


def downgrade():
    op.drop_index('idx_device_sync_log_company', table_name='device_sync_logs')
    op.drop_index('idx_biometric_device_company', table_name='biometric_devices')
    op.drop_index('idx_employee_company', table_name='employees')
    op.drop_index('idx_attendance_company_date', table_name='attendance_logs')

    op.drop_column('biotime_devices', 'company_id')
    op.drop_column('attendance_logs', 'device_serial')
    op.drop_column('attendance_logs', 'device_id')
    op.drop_column('attendance_logs', 'company_id')
    op.drop_column('employees', 'company_id')

    op.drop_table('device_sync_logs')
    op.drop_table('biometric_devices')
    op.drop_table('company_admins')
    op.drop_table('companies')
