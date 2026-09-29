"""Repository for Phase 6 package snapshots; no filesystem paths are returned to callers."""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models.handoff_package import HandoffPackage


class HandoffPackageRepository:
    @staticmethod
    def create(db: Session, **values) -> HandoffPackage:
        db.query(HandoffPackage).filter(
            HandoffPackage.application_id == values["application_id"],
            HandoffPackage.status == "GENERATED",
        ).update({"status": "SUPERSEDED"})
        package = HandoffPackage(**values)
        db.add(package)
        db.commit()
        db.refresh(package)
        return package

    @staticmethod
    def get(db: Session, package_id: str) -> Optional[HandoffPackage]:
        return db.query(HandoffPackage).filter(HandoffPackage.id == package_id).first()

    @staticmethod
    def get_current(db: Session, application_id: str) -> Optional[HandoffPackage]:
        return (db.query(HandoffPackage).filter(
            HandoffPackage.application_id == application_id,
            HandoffPackage.status == "GENERATED",
        ).order_by(HandoffPackage.generated_at.desc()).first())

    @staticmethod
    def list_for_application(db: Session, application_id: str) -> List[HandoffPackage]:
        return (db.query(HandoffPackage).filter(HandoffPackage.application_id == application_id)
                .order_by(HandoffPackage.generated_at.desc()).all())

    @staticmethod
    def invalidate_current(db: Session, application_id: str) -> int:
        count = (db.query(HandoffPackage).filter(
            HandoffPackage.application_id == application_id,
            HandoffPackage.status == "GENERATED",
        ).update({"status": "INVALIDATED"}))
        db.commit()
        return count
