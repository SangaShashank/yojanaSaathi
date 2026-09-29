"""Persisted, non-official Phase 6 pre-submission package metadata."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class HandoffPackage(Base):
    """An immutable snapshot of one application's preparation package."""

    __tablename__ = "handoff_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    scheme_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evaluation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("scheme_evaluations.id", ondelete="SET NULL"), nullable=True)
    readiness_status: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_sheet_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dossier_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="GENERATED", index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
