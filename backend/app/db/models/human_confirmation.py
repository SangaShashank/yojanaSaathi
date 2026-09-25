"""
Yojana Saathi - Human Confirmation Model
========================================
Persists proposed profile patches awaiting citizen or CSC confirmation.
Safeguards that unconfirmed Gemini proposals never leak into the authoritative profile.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class HumanConfirmation(Base):
    """Human/CSC confirmation requests and their resolution state."""
    __tablename__ = "human_confirmations"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confirmation_type: Mapped[str] = mapped_column(
        String(32), default="PROFILE_PATCH", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False, index=True
    )
    proposed_changes: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    raw_patch: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="confirmations")
