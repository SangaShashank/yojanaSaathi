"""
Yojana Saathi - User Model
==========================
Persistent citizen / operator reference model.
Stores zero sensitive identifiers (no Aadhaar, no bank numbers).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class User(Base):
    """Citizen user or operator profile."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    external_reference: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="user", cascade="all, delete-orphan"
    )
