"""
Yojana Saathi - Scheme Evaluation Repository
============================================
Data access layer for deterministic eligibility evaluation results and staleness tracking.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models.scheme_evaluation import SchemeEvaluation


class SchemeEvaluationRepository:
    """Manages persistence of deterministic eligibility evaluations."""

    @staticmethod
    def record_evaluation(
        db: Session,
        case_id: str,
        scheme_id: str,
        profile_fingerprint: str,
        outcome: str,
        reasons: Dict[str, Any],
        application_id: Optional[str] = None,
        rules_version: str = "2.0",
    ) -> SchemeEvaluation:
        evaluation = SchemeEvaluation(
            case_id=case_id,
            scheme_id=scheme_id,
            application_id=application_id,
            profile_fingerprint=profile_fingerprint,
            outcome=outcome,
            reasons=reasons,
            rules_version=rules_version,
            is_stale=False,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        return evaluation

    @staticmethod
    def list_for_case(
        db: Session, case_id: str, include_stale: bool = False
    ) -> List[SchemeEvaluation]:
        query = db.query(SchemeEvaluation).filter(SchemeEvaluation.case_id == case_id)
        if not include_stale:
            query = query.filter(SchemeEvaluation.is_stale == False)  # noqa: E712
        return query.order_by(SchemeEvaluation.evaluated_at.desc()).all()

    @staticmethod
    def list_active_for_case(db: Session, case_id: str) -> List[SchemeEvaluation]:
        return SchemeEvaluationRepository.list_for_case(db, case_id, include_stale=False)

    @staticmethod
    def mark_evaluations_stale(db: Session, case_id: str) -> int:
        """
        Marks all current evaluations for a case as stale when the confirmed profile changes.
        """
        count = (
            db.query(SchemeEvaluation)
            .filter(SchemeEvaluation.case_id == case_id, SchemeEvaluation.is_stale == False)  # noqa: E712
            .update({"is_stale": True})
        )
        db.commit()
        return count
