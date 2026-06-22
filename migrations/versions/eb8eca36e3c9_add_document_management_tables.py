"""add_document_management_tables

Revision ID: eb8eca36e3c9
Revises: 7a2961b09b87
Create Date: 2026-06-18 14:06:34.209035

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb8eca36e3c9'
down_revision = '7a2961b09b87'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('document_references',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference_code', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_references', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_references_reference_code'), ['reference_code'], unique=True)

    op.create_table('archived_documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference_code', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('file_path', sa.String(length=300), nullable=True),
    sa.Column('department', sa.String(length=50), nullable=True),
    sa.Column('employee_id', sa.Integer(), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=True),
    sa.Column('has_expiry_date', sa.Boolean(), nullable=True),
    sa.Column('expiry_date', sa.Date(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=True),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reference_code'], ['document_references.reference_code'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['employees.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('reference_code', 'version', name='uq_archived_doc_ref_version')
    )


def downgrade():
    op.drop_table('archived_documents')
    with op.batch_alter_table('document_references', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_references_reference_code'))

    op.drop_table('document_references')
