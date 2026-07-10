"""add otp_secret to employee

Revision ID: f7e3d2c1b0a9
Revises: eb8eca36e3c9
Create Date: 2026-07-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f7e3d2c1b0a9'
down_revision = 'eb8eca36e3c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('employees', sa.Column('otp_secret', sa.String(length=32), nullable=True))


def downgrade():
    op.drop_column('employees', 'otp_secret')
