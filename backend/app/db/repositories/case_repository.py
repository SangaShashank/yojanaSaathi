"""
Yojana Saathi - Case Repository
===============================
CRUD operations and relational querying for Case models.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session, joinedload
from backend.app.db.models.case import Case


class CaseRepository:
    """Data access layer for citizen assistance cases."""

    @staticmethod
    def create_case(
        db: Session,
        case_id: Optional[str] = None,
        user_id: Optional[str] = None,
        goal: Optional[str] = None,
        candidate_schemes: Optional[List[str]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> Case:
        kwargs: Dict[str, Any] = {
            "user_id": user_id,
            "candidate_schemes": candidate_schemes or [],
            "missing_information": [],
            "metadata_json": metadata_json or {},
        }
        if case_id:
            kwargs["id"] = case_id
        if goal:
            kwargs["goal"] = goal

        case = Case(**kwargs)
        db.add(case)
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def get_case(db: Session, case_id: str) -> Optional[Case]:
        return db.query(Case).filter(Case.id == case_id).first()

    @staticmethod
    def get_case_with_relations(db: Session, case_id: str) -> Optional[Case]:
        return (
            db.query(Case)
            .options(
                joinedload(Case.profile),
                joinedload(Case.applications),
                joinedload(Case.evaluations),
                joinedload(Case.confirmations),
                joinedload(Case.agent_events),
            )
            .filter(Case.id == case_id)
            .first()
        )

    @staticmethod
    def update_case(
        db: Session,
        case_id: str,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        iteration: Optional[int] = None,
        candidate_schemes: Optional[List[str]] = None,
        missing_information: Optional[List[str]] = None,
    ) -> Optional[Case]:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            return None

        if status is not None:
            case.status = status
        if stage is not None:
            case.stage = stage
        if iteration is not None:
            case.iteration = iteration
        if candidate_schemes is not None:
            case.candidate_schemes = candidate_schemes
        if missing_information is not None:
            case.missing_information = missing_information

        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def list_cases(db: Session, limit: int = 50, offset: int = 0) -> List[Case]:
        return db.query(Case).order_by(Case.created_at.desc()).offset(offset).limit(limit).all()
