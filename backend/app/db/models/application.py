"""
Yojana Saathi - Scheme Application Model
========================================
Persists scheme-specific application records within a citizen case.
Supports multi-scheme tracking (Phase 4 readiness).
"""

import uuid
from datetime import datetime
from typing import List
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class Application(Base):
    """Scheme-specific application tied to a parent case."""
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("case_id", "scheme_id", name="uq_case_scheme_application"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheme_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="ELIGIBLE_PENDING", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="applications")
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="application", cascade="all, delete-orphan"
    )
    events: Mapped[List["ApplicationEvent"]] = relationship(
        "ApplicationEvent", back_populates="application", cascade="all, delete-orphan"
    )
    requirements: Mapped[List["ApplicationDocumentRequirement"]] = relationship(
        "ApplicationDocumentRequirement", back_populates="application", cascade="all, delete-orphan"
    )

