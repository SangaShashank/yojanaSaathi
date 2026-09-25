"""
Yojana Saathi - Document Model
==============================
Persistent model for scheme-related documents (Phase 5 preparation).
Stores references rather than raw binaries.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class Document(Base):
    """Document metadata and reference attached to a scheme application."""
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING_UPLOAD", nullable=False
    )
    file_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    extracted_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    requirement_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    original_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    size_bytes: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )
    sha256_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    extraction_status: Mapped[Optional[str]] = mapped_column(
        String(32), default="PENDING", nullable=True
    )
    verification_status: Mapped[Optional[str]] = mapped_column(
        String(32), default="PENDING", nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="documents")
    discrepancies: Mapped[List["DocumentDiscrepancy"]] = relationship(
        "DocumentDiscrepancy", back_populates="document", cascade="all, delete-orphan"
    )

