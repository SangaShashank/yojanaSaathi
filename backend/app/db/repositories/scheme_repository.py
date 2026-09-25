"""
Yojana Saathi - Scheme Catalog Repository
=========================================
Data access layer for official welfare scheme metadata catalog.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models.scheme_catalog import SchemeCatalog


class SchemeCatalogRepository:
    """Manages the persistent catalog of government welfare schemes."""

    @staticmethod
    def upsert_scheme(
        db: Session,
        scheme_id: str,
        name: str,
        niche: str,
        metadata_json: Dict[str, Any],
        ministry: Optional[str] = None,
        scope: Optional[str] = None,
        version: str = "2.0",
        active: bool = True,
    ) -> SchemeCatalog:
        existing = db.query(SchemeCatalog).filter(SchemeCatalog.scheme_id == scheme_id).first()
        if existing:
            existing.name = name
            existing.niche = niche
            existing.ministry = ministry
            existing.scope = scope
            existing.version = version
            existing.active = active
            existing.metadata_json = metadata_json
            db.commit()
            db.refresh(existing)
            return existing

        scheme = SchemeCatalog(
            scheme_id=scheme_id,
            name=name,
            niche=niche,
            ministry=ministry,
            scope=scope,
            version=version,
            active=active,
            metadata_json=metadata_json,
        )
        db.add(scheme)
        db.commit()
        db.refresh(scheme)
        return scheme

    @staticmethod
    def get_scheme(db: Session, scheme_id: str) -> Optional[SchemeCatalog]:
        return db.query(SchemeCatalog).filter(SchemeCatalog.scheme_id == scheme_id).first()

    @staticmethod
    def list_active_schemes(db: Session) -> List[SchemeCatalog]:
        return db.query(SchemeCatalog).filter(SchemeCatalog.active == True).all()  # noqa: E712


# Convenient alias
SchemeRepository = SchemeCatalogRepository
