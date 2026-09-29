"""phase7_rejection_recovery
Revision ID: phase7reject01
Revises: phase6hndoff01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision: str = "phase7reject01"
down_revision: Union[str, None] = "phase6hndoff01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade():
    op.create_table("rejection_events", sa.Column("id",sa.String(36),primary_key=True),sa.Column("application_id",sa.String(36),sa.ForeignKey("applications.id",ondelete="CASCADE"),nullable=False),sa.Column("status",sa.String(48),nullable=False),sa.Column("recovery_status",sa.String(48),nullable=False),sa.Column("evidence_id",sa.String(36),nullable=True),sa.Column("decoded_status",sa.String(32),nullable=True),sa.Column("received_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False))
    op.create_table("rejection_evidence", sa.Column("id",sa.String(36),primary_key=True),sa.Column("rejection_event_id",sa.String(36),sa.ForeignKey("rejection_events.id",ondelete="CASCADE"),nullable=False),sa.Column("application_id",sa.String(36),sa.ForeignKey("applications.id",ondelete="CASCADE"),nullable=False),sa.Column("source_type",sa.String(32),nullable=False),sa.Column("raw_text",sa.Text(),nullable=True),sa.Column("rejection_code",sa.String(64),nullable=True),sa.Column("content_hash",sa.String(64),nullable=False),sa.Column("provided_by",sa.String(32),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("captured_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False))
    op.create_table("rejection_decodes", sa.Column("id",sa.String(36),primary_key=True),sa.Column("evidence_id",sa.String(36),sa.ForeignKey("rejection_evidence.id",ondelete="CASCADE"),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("categories",postgresql.JSONB(),nullable=False),sa.Column("matched_codes",postgresql.JSONB(),nullable=False),sa.Column("matched_signals",postgresql.JSONB(),nullable=False),sa.Column("is_current",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False))
    op.create_table("recovery_actions", sa.Column("id",sa.String(36),primary_key=True),sa.Column("rejection_event_id",sa.String(36),sa.ForeignKey("rejection_events.id",ondelete="CASCADE"),nullable=False),sa.Column("application_id",sa.String(36),sa.ForeignKey("applications.id",ondelete="CASCADE"),nullable=False),sa.Column("category",sa.String(64),nullable=True),sa.Column("action",sa.String(64),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("metadata_json",postgresql.JSONB(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True))
    for table,col in (("rejection_events","application_id"),("rejection_evidence","application_id"),("rejection_decodes","evidence_id"),("recovery_actions","application_id")): op.create_index(f"ix_{table}_{col}",table,[col])
def downgrade():
    op.drop_table("recovery_actions"); op.drop_table("rejection_decodes"); op.drop_table("rejection_evidence"); op.drop_table("rejection_events")
