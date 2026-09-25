"""
Yojana Saathi - Profile Repository
==================================
Data access layer for confirmed citizen profiles with optimistic concurrency protection.
"""

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from backend.app.db.models.profile import Profile


class ProfileConcurrencyError(Exception):
    """Raised when an update conflicts with a newer profile version in the database."""
    pass


class ProfileRepository:
    """Manages persistence of authoritative confirmed citizen profiles."""

    @staticmethod
    def get_by_case_id(db: Session, case_id: str) -> Optional[Profile]:
        return db.query(Profile).filter(Profile.case_id == case_id).first()

    @staticmethod
    def upsert_profile(
        db: Session,
        case_id: str,
        profile_data: Dict[str, Any],
        fingerprint: str,
        confirmed: bool = True,
        expected_version: Optional[int] = None,
    ) -> Profile:
        """
        Upserts confirmed profile for a case.
        Enforces optimistic concurrency checks if expected_version is provided.
        """
        existing = db.query(Profile).filter(Profile.case_id == case_id).first()
        if existing:
            if expected_version is not None and existing.version != expected_version:
                raise ProfileConcurrencyError(
                    f"Conflict detected on profile for case {case_id}: "
                    f"expected version {expected_version} but database version is {existing.version}."
                )

            existing.profile_data = profile_data
            existing.profile_fingerprint = fingerprint
            existing.confirmed = confirmed
            existing.version += 1
            db.commit()
            db.refresh(existing)
            return existing

        profile = Profile(
            case_id=case_id,
            profile_data=profile_data,
            profile_fingerprint=fingerprint,
            confirmed=confirmed,
            version=1,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
