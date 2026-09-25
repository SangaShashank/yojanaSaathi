"""
Yojana Saathi - Event Repository
================================
Data access layer for Agent Activity events and Application lifecycle events.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models.events import AgentEvent, ApplicationEvent


class EventRepository:
    """Manages persistence of structured audit and agent observability events."""

    @staticmethod
    def record_agent_event(
        db: Session,
        case_id: str,
        iteration: int,
        stage: str,
        action: str,
        reason_code: str,
        state_fingerprint: str,
        selected_field: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> AgentEvent:
        event = AgentEvent(
            case_id=case_id,
            iteration=iteration,
            stage=stage,
            action=action,
            reason_code=reason_code,
            selected_field=selected_field,
            state_fingerprint=state_fingerprint,
            event_data=event_data or {},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def list_agent_events(db: Session, case_id: str) -> List[AgentEvent]:
        return (
            db.query(AgentEvent)
            .filter(AgentEvent.case_id == case_id)
            .order_by(AgentEvent.created_at.asc())
            .all()
        )

    @staticmethod
    def record_application_event(
        db: Session,
        application_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> ApplicationEvent:
        event = ApplicationEvent(
            application_id=application_id,
            event_type=event_type,
            event_data=event_data or {},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def list_application_events(db: Session, application_id: str) -> List[ApplicationEvent]:
        return (
            db.query(ApplicationEvent)
            .filter(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.created_at.asc())
            .all()
        )
