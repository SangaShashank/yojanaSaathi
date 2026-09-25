"""phase5_documents_and_readiness

Revision ID: c48056fbfdca
Revises: 2c3e01842923
Create Date: 2026-09-26 03:10:09.463849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c48056fbfdca'
down_revision: Union[str, None] = '2c3e01842923'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions to documents table
    op.add_column('documents', sa.Column('requirement_id', sa.String(length=64), nullable=True))
    op.add_column('documents', sa.Column('original_filename', sa.String(length=255), nullable=True))
    op.add_column('documents', sa.Column('mime_type', sa.String(length=64), nullable=True))
    op.add_column('documents', sa.Column('size_bytes', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('sha256_hash', sa.String(length=64), nullable=True))
    op.add_column('documents', sa.Column('extraction_status', sa.String(length=32), nullable=True, server_default='PENDING'))
    op.add_column('documents', sa.Column('verification_status', sa.String(length=32), nullable=True, server_default='PENDING'))
    op.add_column('documents', sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_documents_sha256_hash'), 'documents', ['sha256_hash'], unique=False)
    op.create_index(op.f('ix_documents_requirement_id'), 'documents', ['requirement_id'], unique=False)

    # Extensions to document_discrepancies table
    op.add_column('document_discrepancies', sa.Column('application_id', sa.String(length=36), nullable=True))
    op.add_column('document_discrepancies', sa.Column('discrepancy_type', sa.String(length=64), nullable=True, server_default='VALUE_MISMATCH'))
    op.create_foreign_key(
        'fk_document_discrepancies_application_id',
        'document_discrepancies',
        'applications',
        ['application_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index(op.f('ix_document_discrepancies_application_id'), 'document_discrepancies', ['application_id'], unique=False)

    # New table: application_document_requirements
    op.create_table(
        'application_document_requirements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('application_id', sa.String(length=36), nullable=False),
        sa.Column('requirement_id', sa.String(length=64), nullable=False),
        sa.Column('document_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='REQUIRED', nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=True),
        sa.Column('source_status', sa.String(length=32), server_default='VERIFIED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', 'requirement_id', name='uq_app_doc_req'),
    )
    op.create_index(op.f('ix_app_doc_req_application_id'), 'application_document_requirements', ['application_id'], unique=False)
    op.create_index(op.f('ix_app_doc_req_requirement_id'), 'application_document_requirements', ['requirement_id'], unique=False)
    op.create_index(op.f('ix_app_doc_req_document_type'), 'application_document_requirements', ['document_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_app_doc_req_document_type'), table_name='application_document_requirements')
    op.drop_index(op.f('ix_app_doc_req_requirement_id'), table_name='application_document_requirements')
    op.drop_index(op.f('ix_app_doc_req_application_id'), table_name='application_document_requirements')
    op.drop_table('application_document_requirements')

    op.drop_constraint('fk_document_discrepancies_application_id', 'document_discrepancies', type_='foreignkey')
    op.drop_index(op.f('ix_document_discrepancies_application_id'), table_name='document_discrepancies')
    op.drop_column('document_discrepancies', 'discrepancy_type')
    op.drop_column('document_discrepancies', 'application_id')

    op.drop_index(op.f('ix_documents_requirement_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_sha256_hash'), table_name='documents')
    op.drop_column('documents', 'processed_at')
    op.drop_column('documents', 'verification_status')
    op.drop_column('documents', 'extraction_status')
    op.drop_column('documents', 'sha256_hash')
    op.drop_column('documents', 'size_bytes')
    op.drop_column('documents', 'mime_type')
    op.drop_column('documents', 'original_filename')
    op.drop_column('documents', 'requirement_id')
