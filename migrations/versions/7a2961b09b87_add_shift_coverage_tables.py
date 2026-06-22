"""add_shift_coverage_tables

Revision ID: 7a2961b09b87
Revises: 8e05534ba61c
Create Date: 2026-06-18 13:48:11.100305

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a2961b09b87'
down_revision = '8e05534ba61c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shift_coverage_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('shift_type_id', sa.Integer(), nullable=False),
    sa.Column('department', sa.String(length=50), nullable=True),
    sa.Column('day_of_week', sa.Integer(), nullable=True),
    sa.Column('min_staff', sa.Integer(), nullable=False),
    sa.Column('max_staff', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['shift_type_id'], ['shift_types.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('shift_exceptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('shift_schedule_id', sa.Integer(), nullable=True),
    sa.Column('exception_date', sa.Date(), nullable=False),
    sa.Column('exception_type', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.String(length=300), nullable=True),
    sa.Column('resolved_by', sa.Integer(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.ForeignKeyConstraint(['resolved_by'], ['employees.id'], ),
    sa.ForeignKeyConstraint(['shift_schedule_id'], ['shift_schedules.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('shift_schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('original_employee_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('conflict_status', sa.String(length=20), server_default='ok', nullable=True))
        batch_op.add_column(sa.Column('substituted_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('substituted_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key('fk_ss_original_emp', 'employees', ['original_employee_id'], ['id'])
        batch_op.create_foreign_key('fk_ss_substituted_by', 'employees', ['substituted_by'], ['id'])

    with op.batch_alter_table('shift_swap_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scheduled_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('swap_type', sa.String(length=20), server_default='peer', nullable=True))
        batch_op.add_column(sa.Column('substitute_employee_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_swr_substitute_emp', 'employees', ['substitute_employee_id'], ['id'])


def downgrade():
    with op.batch_alter_table('shift_swap_requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_swr_substitute_emp', type_='foreignkey')
        batch_op.drop_column('substitute_employee_id')
        batch_op.drop_column('swap_type')
        batch_op.drop_column('scheduled_date')

    with op.batch_alter_table('shift_schedules', schema=None) as batch_op:
        batch_op.drop_constraint('fk_ss_original_emp', type_='foreignkey')
        batch_op.drop_constraint('fk_ss_substituted_by', type_='foreignkey')
        batch_op.drop_column('substituted_at')
        batch_op.drop_column('substituted_by')
        batch_op.drop_column('conflict_status')
        batch_op.drop_column('original_employee_id')

    op.drop_table('shift_exceptions')
    op.drop_table('shift_coverage_rules')
