"""
Yojana Saathi - Scheme Evaluation Model
=======================================
Persists deterministic eligibility evaluation results.
Guarantees traceability by linking evaluations to the specific profile fingerprint evaluated.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class SchemeEvaluation(Base):
    """Deterministic eligibility evaluation result linked to an immutable profile fingerprint."""
    __tablename__ = "scheme_evaluations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scheme_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    profile_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    outcome: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    reasons: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    rules_version: Mapped[str] = mapped_column(
        String(32), default="2.0", nullable=False
    )
    is_stale: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="evaluations")
