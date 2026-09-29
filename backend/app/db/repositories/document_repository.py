"""
Yojana Saathi - Document & Discrepancy Repositories
===================================================
Database operations for documents, discrepancies, and application document requirements.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.document import Document
from backend.app.db.models.document_discrepancy import DocumentDiscrepancy
from backend.app.db.models.application_requirement import ApplicationDocumentRequirement


class DocumentRepository:
    """Handles persistence and retrieval of document records."""

    @classmethod
    def create_document(
        cls,
        db: Session,
        application_id: str,
        document_type: str,
        file_reference: Optional[str] = None,
        requirement_id: Optional[str] = None,
        original_filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        sha256_hash: Optional[str] = None,
        status: str = "UPLOADED",
        extraction_status: str = "PENDING",
        verification_status: str = "PENDING",
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> Document:
        doc = Document(
            id=str(uuid.uuid4()),
            application_id=application_id,
            document_type=document_type,
            file_reference=file_reference,
            requirement_id=requirement_id,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256_hash=sha256_hash,
            status=status,
            extraction_status=extraction_status,
            verification_status=verification_status,
            extracted_data=extracted_data,
        )
        db.add(doc)
        db.flush()
        return doc

    @classmethod
    def get_document(cls, db: Session, document_id: str) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        return db.scalar(stmt)

    @classmethod
    def find_by_hash(
        cls, db: Session, application_id: str, sha256_hash: str
    ) -> Optional[Document]:
        stmt = select(Document).where(
            Document.application_id == application_id,
            Document.sha256_hash == sha256_hash,
        )
        return db.scalar(stmt)

    @classmethod
    def find_processed_by_hash(cls, db: Session, sha256_hash: str) -> Optional[Document]:
        """Finds any successfully processed document with matching content hash."""
        stmt = select(Document).where(
            Document.sha256_hash == sha256_hash,
            Document.extraction_status == "SUCCESS",
        ).order_by(Document.created_at.desc())
        return db.scalar(stmt)

    @classmethod
    def list_by_application(cls, db: Session, application_id: str) -> List[Document]:
        stmt = select(Document).where(Document.application_id == application_id).order_by(Document.created_at.desc())
        return list(db.scalars(stmt).all())

    @classmethod
    def update_document(
        cls,
        db: Session,
        document_id: str,
        status: Optional[str] = None,
        extraction_status: Optional[str] = None,
        verification_status: Optional[str] = None,
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Document]:
        doc = cls.get_document(db, document_id)
        if not doc:
            return None
        if status is not None:
            doc.status = status
        if extraction_status is not None:
            doc.extraction_status = extraction_status
        if verification_status is not None:
            doc.verification_status = verification_status
        if extracted_data is not None:
            doc.extracted_data = extracted_data
            doc.processed_at = datetime.utcnow()
        db.flush()
        return doc


class DocumentDiscrepancyRepository:
    """Handles persistence of factual discrepancies between documents and profiles."""

    @classmethod
    def create_discrepancy(
        cls,
        db: Session,
        document_id: str,
        field_name: str,
        profile_value: Any,
        document_value: Any,
        application_id: Optional[str] = None,
        discrepancy_type: str = "VALUE_MISMATCH",
        status: str = "OPEN",
    ) -> DocumentDiscrepancy:
        disc = DocumentDiscrepancy(
            id=str(uuid.uuid4()),
            document_id=document_id,
            application_id=application_id,
            field_name=field_name,
            profile_value=profile_value,
            document_value=document_value,
            discrepancy_type=discrepancy_type,
            status=status,
        )
        db.add(disc)
        db.flush()
        return disc

    @classmethod
    def get_discrepancy(cls, db: Session, discrepancy_id: str) -> Optional[DocumentDiscrepancy]:
        stmt = select(DocumentDiscrepancy).where(DocumentDiscrepancy.id == discrepancy_id)
        return db.scalar(stmt)

    @classmethod
    def list_by_document(cls, db: Session, document_id: str) -> List[DocumentDiscrepancy]:
        stmt = select(DocumentDiscrepancy).where(DocumentDiscrepancy.document_id == document_id)
        return list(db.scalars(stmt).all())

    @classmethod
    def list_by_application(cls, db: Session, application_id: str) -> List[DocumentDiscrepancy]:
        stmt = select(DocumentDiscrepancy).where(DocumentDiscrepancy.application_id == application_id)
        return list(db.scalars(stmt).all())

    @classmethod
    def resolve_discrepancy(
        cls, db: Session, discrepancy_id: str, new_status: str
    ) -> Optional[DocumentDiscrepancy]:
        disc = cls.get_discrepancy(db, discrepancy_id)
        if not disc:
            return None
        disc.status = new_status
        disc.resolved_at = datetime.utcnow()
        db.flush()
        return disc


class ApplicationRequirementRepository:
    """Handles persistence of application-specific document requirement links."""

    @classmethod
    def get_or_create_requirement(
        cls,
        db: Session,
        application_id: str,
        requirement_id: str,
        document_type: str,
        status: str = "REQUIRED",
        source_status: str = "VERIFIED",
        document_id: Optional[str] = None,
    ) -> ApplicationDocumentRequirement:
        stmt = select(ApplicationDocumentRequirement).where(
            ApplicationDocumentRequirement.application_id == application_id,
            ApplicationDocumentRequirement.requirement_id == requirement_id,
        )
        existing = db.scalar(stmt)
        if existing:
            return existing

        req = ApplicationDocumentRequirement(
            id=str(uuid.uuid4()),
            application_id=application_id,
            requirement_id=requirement_id,
            document_type=document_type,
            status=status,
            source_status=source_status,
            document_id=document_id,
        )
        db.add(req)
        db.flush()
        return req

    @classmethod
    def list_by_application(
        cls, db: Session, application_id: str
    ) -> List[ApplicationDocumentRequirement]:
        stmt = (
            select(ApplicationDocumentRequirement)
            .where(ApplicationDocumentRequirement.application_id == application_id)
            .order_by(ApplicationDocumentRequirement.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    @classmethod
    def update_requirement(
        cls,
        db: Session,
        application_id: str,
        requirement_id: str,
        status: str,
        document_id: Optional[str] = None,
    ) -> Optional[ApplicationDocumentRequirement]:
        stmt = select(ApplicationDocumentRequirement).where(
            ApplicationDocumentRequirement.application_id == application_id,
            ApplicationDocumentRequirement.requirement_id == requirement_id,
        )
        req = db.scalar(stmt)
        if not req:
            return None
        req.status = status
        if document_id is not None:
            req.document_id = document_id
        db.flush()
        return req
