"""
Yojana Saathi - Document Discrepancy Model
==========================================
Persists data mismatches between extracted document fields and citizen profile facts.
"""

import uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class DocumentDiscrepancy(Base):
    """Factual mismatch detected between a document and citizen profile."""
    __tablename__ = "document_discrepancies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    field_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    profile_value: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True
    )
    document_value: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True
    )
    discrepancy_type: Mapped[Optional[str]] = mapped_column(
        String(64), default="VALUE_MISMATCH", nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="OPEN", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="discrepancies")

