"""
Yojana Saathi - Application Document Requirement Model
=====================================================
Maps an Application track to its scheme-specific document requirements.
Allows independent requirement state and explicit document reuse across applications.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class ApplicationDocumentRequirement(Base):
    """Application-specific document requirement link."""
    __tablename__ = "application_document_requirements"
    __table_args__ = (
        UniqueConstraint("application_id", "requirement_id", name="uq_app_doc_req"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="REQUIRED", nullable=False
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    source_status: Mapped[str] = mapped_column(
        String(32), default="VERIFIED", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="requirements")
    document: Mapped[Optional["Document"]] = relationship("Document")
