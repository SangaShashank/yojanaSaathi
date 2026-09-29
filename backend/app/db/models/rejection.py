"""Application-scoped Phase 7 rejection evidence and recovery history."""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base

class RejectionEvent(Base):
    __tablename__ = "rejection_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="REJECTION_EVIDENCE_REQUIRED")
    recovery_status: Mapped[str] = mapped_column(String(48), nullable=False, default="REJECTION_EVIDENCE_REQUIRED")
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    decoded_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class RejectionEvidence(Base):
    __tablename__ = "rejection_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rejection_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("rejection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provided_by: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="VERIFIED")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class RejectionDecode(Base):
    __tablename__ = "rejection_decodes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("rejection_evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    categories: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    matched_codes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    matched_signals: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class RecoveryActionRecord(Base):
    __tablename__ = "recovery_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rejection_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("rejection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="REQUESTED")
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
