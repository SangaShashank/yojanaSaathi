"""
Yojana Saathi - Confirmed Profile Model
======================================
Stores authoritative confirmed citizen profile facts in PostgreSQL.
Includes optimistic locking version and SHA-256 profile fingerprint to track staleness.
"""

import uuid
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class Profile(Base):
    """Authoritative confirmed profile for an active case."""
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    profile_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    profile_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    confirmed: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="profile")
