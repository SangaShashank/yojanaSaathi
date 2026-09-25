"""
Yojana Saathi - Case Model
==========================
Persistent model for an assistance case/session.
Connects citizen profile, scheme applications, agent evaluations, and confirmation history.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class Case(Base):
    """Case session representing an end-to-end welfare assistance journey."""
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"CASE-{uuid.uuid4().hex[:12].upper()}"
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", index=True, nullable=False
    )
    goal: Mapped[str] = mapped_column(
        String(255), default="Identify applicable welfare schemes and orchestrate readiness", nullable=False
    )
    stage: Mapped[str] = mapped_column(
        String(64), default="INTAKE", nullable=False
    )
    iteration: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    max_iterations: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    candidate_schemes: Mapped[List[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    missing_information: Mapped[List[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="cases")
    profile: Mapped[Optional["Profile"]] = relationship(
        "Profile", uselist=False, back_populates="case", cascade="all, delete-orphan"
    )
    applications: Mapped[List["Application"]] = relationship(
        "Application", back_populates="case", cascade="all, delete-orphan"
    )
    evaluations: Mapped[List["SchemeEvaluation"]] = relationship(
        "SchemeEvaluation", back_populates="case", cascade="all, delete-orphan"
    )
    confirmations: Mapped[List["HumanConfirmation"]] = relationship(
        "HumanConfirmation", back_populates="case", cascade="all, delete-orphan"
    )
    agent_events: Mapped[List["AgentEvent"]] = relationship(
        "AgentEvent", back_populates="case", cascade="all, delete-orphan"
    )
