"""phase6_handoff_packages

Revision ID: phase6hndoff01
Revises: c48056fbfdca
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "phase6hndoff01"
down_revision: Union[str, None] = "c48056fbfdca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "handoff_packages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("scheme_id", sa.String(length=64), nullable=False),
        sa.Column("profile_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evaluation_id", sa.String(length=36), nullable=True),
        sa.Column("readiness_status", sa.String(length=64), nullable=False),
        sa.Column("reference_sheet_key", sa.String(length=255), nullable=True),
        sa.Column("dossier_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="GENERATED"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["scheme_evaluations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_handoff_packages_case_id"), "handoff_packages", ["case_id"])
    op.create_index(op.f("ix_handoff_packages_application_id"), "handoff_packages", ["application_id"])
    op.create_index(op.f("ix_handoff_packages_scheme_id"), "handoff_packages", ["scheme_id"])
    op.create_index(op.f("ix_handoff_packages_profile_fingerprint"), "handoff_packages", ["profile_fingerprint"])
    op.create_index(op.f("ix_handoff_packages_status"), "handoff_packages", ["status"])


def downgrade() -> None:
    op.drop_table("handoff_packages")
