"""
Yojana Saathi - Application Repository
======================================
Data access layer for scheme applications within an assistance case.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models.application import Application


class ApplicationRepository:
    """Manages scheme-specific application records."""

    @staticmethod
    def create_application(
        db: Session, case_id: str, scheme_id: str, status: str = "ELIGIBLE_PENDING"
    ) -> Application:
        app = Application(
            case_id=case_id,
            scheme_id=scheme_id,
            status=status,
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    @staticmethod
    def get_by_case_and_scheme(
        db: Session, case_id: str, scheme_id: str
    ) -> Optional[Application]:
        return (
            db.query(Application)
            .filter(Application.case_id == case_id, Application.scheme_id == scheme_id)
            .first()
        )

    @staticmethod
    def get_application(db: Session, application_id: str) -> Optional[Application]:
        return db.query(Application).filter(Application.id == application_id).first()

    @staticmethod
    def list_by_case_id(db: Session, case_id: str) -> List[Application]:
        return db.query(Application).filter(Application.case_id == case_id).all()

    @staticmethod
    def list_by_case(db: Session, case_id: str) -> List[Application]:
        return db.query(Application).filter(Application.case_id == case_id).all()

    @staticmethod
    def update_status(
        db: Session, application_id: str, status: str
    ) -> Optional[Application]:
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            return None
        app.status = status
        db.commit()
        db.refresh(app)
        return app
