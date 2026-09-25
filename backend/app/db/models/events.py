"""
Yojana Saathi - Application & Agent Observability Events
=======================================================
Audit and observability models for lifecycle changes and structured agent activity.
Strictly forbids logging raw sensitive profile credentials or LLM hidden thoughts.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


class ApplicationEvent(Base):
    """Lifecycle events on a scheme application (e.g., status changes, submissions)."""
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    event_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="events")


class AgentEvent(Base):
    """Structured Agent Activity events capturing state-driven decisions and tool dispatches."""
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    iteration: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    stage: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    selected_field: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    state_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    event_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="agent_events")
