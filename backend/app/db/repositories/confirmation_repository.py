"""
Yojana Saathi - Human Confirmation Repository
=============================================
Manages lifecycle of pending, confirmed, and rejected human confirmations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models.human_confirmation import HumanConfirmation


class ConfirmationRepository:
    """Data access layer for human-in-the-loop profile confirmations."""

    @staticmethod
    def create_confirmation(
        db: Session,
        confirmation_id: str,
        case_id: str,
        proposed_changes: List[Dict[str, Any]],
        raw_patch: Optional[Dict[str, Any]] = None,
        confirmation_type: str = "PROFILE_PATCH",
    ) -> HumanConfirmation:
        existing = db.query(HumanConfirmation).filter(HumanConfirmation.id == confirmation_id).first()
        if existing:
            existing.proposed_changes = proposed_changes
            existing.raw_patch = raw_patch or {}
            existing.status = "PENDING"
            db.commit()
            db.refresh(existing)
            return existing

        confirmation = HumanConfirmation(
            id=confirmation_id,
            case_id=case_id,
            confirmation_type=confirmation_type,
            status="PENDING",
            proposed_changes=proposed_changes,
            raw_patch=raw_patch or {},
        )
        db.add(confirmation)
        db.commit()
        db.refresh(confirmation)
        return confirmation

    @staticmethod
    def get_confirmation(db: Session, confirmation_id: str) -> Optional[HumanConfirmation]:
        return db.query(HumanConfirmation).filter(HumanConfirmation.id == confirmation_id).first()

    @staticmethod
    def get_pending_by_case_id(db: Session, case_id: str) -> Optional[HumanConfirmation]:
        return (
            db.query(HumanConfirmation)
            .filter(
                HumanConfirmation.case_id == case_id,
                HumanConfirmation.status == "PENDING",
            )
            .order_by(HumanConfirmation.created_at.desc())
            .first()
        )

    @staticmethod
    def resolve_confirmation(
        db: Session, confirmation_id: str, status: str
    ) -> Optional[HumanConfirmation]:
        confirmation = db.query(HumanConfirmation).filter(HumanConfirmation.id == confirmation_id).first()
        if not confirmation:
            return None

        confirmation.status = status
        confirmation.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(confirmation)
        return confirmation
