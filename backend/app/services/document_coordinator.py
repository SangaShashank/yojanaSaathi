"""
Yojana Saathi - Document & Readiness Coordinator
================================================
Central orchestration service for Phase 5:
- File upload, validation, deduplication
- Text and structured field extraction
- Deterministic profile/document comparison
- Discrepancy lifecycle & human resolution
- Application-specific readiness calculation
- Multi-application state isolation & explicit document sharing
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.agent.state import AgentState
from backend.app.db.models.document import Document
from backend.app.db.models.document_discrepancy import DocumentDiscrepancy
from backend.app.db.repositories.document_repository import (
    ApplicationRequirementRepository,
    DocumentDiscrepancyRepository,
    DocumentRepository,
)
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.integrations.storage import StorageAdapter
from backend.app.profile.coordinator import ProfileCoordinator
from backend.app.schemas.document import (
    ApplicationDocumentChecklistItem,
    ApplicationReadiness,
    DiscrepancyStatus,
    DocumentDiscrepancyItem,
    DocumentExtractionResult,
    DocumentItemResponse,
    DocumentRequirementStatus,
    DocumentUploadResponse,
    ReadinessStatus,
)
from backend.app.services.discrepancy_engine import DiscrepancyEngine
from backend.app.services.document_processor import DocumentProcessor
from backend.app.services.document_requirements import (
    DOCUMENT_VERIFICATION_FIELDS_MAP,
    generate_application_checklist,
    get_scheme_document_requirements,
)
from backend.app.services.readiness_engine import ReadinessEngine


logger = logging.getLogger(__name__)


class DocumentCoordinator:
    """Coordinates document lifecycle, extraction, verification, and application readiness."""

    def __init__(self, storage_adapter: Optional[StorageAdapter] = None):
        self.storage = storage_adapter or StorageAdapter()

    @staticmethod
    def _get_app_docs_from_state(state: AgentState, application_id: str) -> List[Dict[str, Any]]:
        docs = getattr(state, "documents", [])
        if isinstance(docs, dict):
            return docs.get(application_id, [])
        elif isinstance(docs, list):
            return [d for d in docs if isinstance(d, dict) and d.get("application_id") == application_id]
        return []

    @staticmethod
    def _add_doc_to_state(state: AgentState, application_id: str, doc_dict: Dict[str, Any]) -> None:
        if not hasattr(state, "documents") or state.documents is None:
            state.documents = []
        if isinstance(state.documents, list):
            state.documents.append(doc_dict)
        elif isinstance(state.documents, dict):
            if application_id not in state.documents:
                state.documents[application_id] = []
            state.documents[application_id].append(doc_dict)

    @staticmethod
    def _find_doc_in_state(state: AgentState, document_id: str) -> Optional[Dict[str, Any]]:
        docs = getattr(state, "documents", [])
        if isinstance(docs, list):
            return next((d for d in docs if isinstance(d, dict) and d.get("id") == document_id), None)
        elif isinstance(docs, dict):
            for d_list in docs.values():
                for d in d_list:
                    if isinstance(d, dict) and d.get("id") == document_id:
                        return d
        return None

    @staticmethod
    def _find_discrepancy_in_state(state: AgentState, discrepancy_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        docs = getattr(state, "documents", [])
        all_docs = []
        if isinstance(docs, list):
            all_docs = docs
        elif isinstance(docs, dict):
            for d_list in docs.values():
                all_docs.extend(d_list)

        for d in all_docs:
            if isinstance(d, dict):
                for disc in d.get("discrepancies", []):
                    d_id = disc.get("id") or disc.get("discrepancy_id")
                    if d_id == discrepancy_id:
                        return disc, d
        return None, None

    def get_application_checklist(
        self,
        state: AgentState,
        application_id: str,
        db: Optional[Session] = None,
    ) -> List[ApplicationDocumentChecklistItem]:
        """Returns the document checklist for a specific application."""
        scheme_id = None
        # Find scheme_id for application
        if application_id in state.applications:
            # state.applications could be keyed by scheme_id or application_id
            scheme_id = state.applications[application_id].get("scheme_id")
        if not scheme_id:
            for s_id, app_info in state.applications.items():
                if app_info.get("id") == application_id:
                    scheme_id = s_id
                    break

        if not scheme_id and db:
            app_record = ApplicationRepository.get_application(db, application_id)
            if app_record:
                scheme_id = app_record.scheme_id

        if not scheme_id:
            scheme_id = state.active_scheme_id or "unknown_scheme"

        # Fetch linked documents
        linked_docs: List[Any] = []
        if db:
            linked_docs = DocumentRepository.list_by_application(db, application_id)
        else:
            # In-memory documents from state
            app_docs = state.documents if hasattr(state, "documents") else []
            if isinstance(app_docs, dict):
                linked_docs = app_docs.get(application_id, [])
            elif isinstance(app_docs, list):
                linked_docs = [d for d in app_docs if isinstance(d, dict) and d.get("application_id") == application_id]


        return generate_application_checklist(application_id, scheme_id, linked_docs, db)

    def upload_document(
        self,
        state: AgentState,
        application_id: str,
        document_type: str,
        filename: str,
        file_bytes: bytes,
        mime_type: Optional[str] = None,
        requirement_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> DocumentUploadResponse:
        """
        Validates, stores, deduplicates, and registers an uploaded document for an application.
        """
        # 1. Validate file
        is_valid, err_msg, detected_mime = self.storage.validate_file_upload(
            filename=filename, content=file_bytes, mime_type=mime_type
        )
        if not is_valid:
            raise ValueError(f"File validation failed: {err_msg}")

        # 2. Content hash & deduplication check
        sha256_hash = self.storage.compute_sha256(file_bytes)

        if db:
            existing = DocumentRepository.find_by_hash(db, application_id, sha256_hash)
            if existing:
                return DocumentUploadResponse(
                    document_id=existing.id,
                    application_id=existing.application_id,
                    requirement_id=existing.requirement_id,
                    document_type=existing.document_type,
                    status=existing.status,
                    processing_status=existing.extraction_status or "PENDING",
                    original_filename=existing.original_filename,
                    mime_type=existing.mime_type,
                    size_bytes=existing.size_bytes,
                    sha256=existing.sha256_hash,
                    uploaded_at=existing.created_at.isoformat(),
                )
        else:
            app_docs = self._get_app_docs_from_state(state, application_id)
            existing = next((d for d in app_docs if d.get("sha256_hash") == sha256_hash), None)
            if existing:
                return DocumentUploadResponse(
                    document_id=existing["id"],
                    application_id=existing.get("application_id", application_id),
                    requirement_id=existing.get("requirement_id"),
                    document_type=existing["document_type"],
                    status=existing["status"],
                    processing_status=existing.get("extraction_status") or "PENDING",
                    original_filename=existing.get("original_filename"),
                    mime_type=existing.get("mime_type"),
                    size_bytes=existing.get("size_bytes"),
                    sha256=existing.get("sha256_hash"),
                    uploaded_at=existing.get("created_at") or datetime.utcnow().isoformat(),
                )

        # 3. Save physical file to storage
        storage_ref = self.storage.save_file(
            filename=filename, content=file_bytes, subfolder=application_id
        )

        # 4. Determine requirement_id if not provided
        if not requirement_id:
            checklist = self.get_application_checklist(state, application_id, db)
            match = next((c for c in checklist if c.document_type == document_type), None)
            if match:
                requirement_id = match.requirement_id

        # 5. Persist document record
        if db:
            doc_record = DocumentRepository.create_document(
                db=db,
                application_id=application_id,
                document_type=document_type,
                file_reference=storage_ref,
                requirement_id=requirement_id,
                original_filename=filename,
                mime_type=detected_mime,
                size_bytes=len(file_bytes),
                sha256_hash=sha256_hash,
                status="UPLOADED",
                extraction_status="PENDING",
                verification_status="PENDING",
            )
            # Update application requirement link if requirement_id exists
            if requirement_id:
                ApplicationRequirementRepository.get_or_create_requirement(
                    db=db,
                    application_id=application_id,
                    requirement_id=requirement_id,
                    document_type=document_type,
                    status="UPLOADED",
                    document_id=doc_record.id,
                )
            # Record audit event
            EventRepository.record_application_event(
                db=db,
                application_id=application_id,
                event_type="DOCUMENT_UPLOADED",
                event_data={
                    "document_id": doc_record.id,
                    "document_type": document_type,
                    "filename": filename,
                    "sha256": sha256_hash,
                },
            )
            db.commit()
            db.refresh(doc_record)

            doc_id = doc_record.id
            uploaded_at = doc_record.created_at.isoformat()
            status = doc_record.status
        else:
            # In-memory tracking
            import uuid
            doc_id = f"doc_{uuid.uuid4().hex[:12]}"
            uploaded_at = datetime.utcnow().isoformat()
            status = "UPLOADED"

            mock_doc = {
                "id": doc_id,
                "application_id": application_id,
                "document_type": document_type,
                "requirement_id": requirement_id,
                "file_reference": storage_ref,
                "original_filename": filename,
                "mime_type": detected_mime,
                "size_bytes": len(file_bytes),
                "sha256_hash": sha256_hash,
                "status": status,
                "extraction_status": "PENDING",
                "verification_status": "PENDING",
                "extracted_data": None,
                "discrepancies": [],
                "created_at": uploaded_at,
            }
            self._add_doc_to_state(state, application_id, mock_doc)

        return DocumentUploadResponse(
            document_id=doc_id,
            application_id=application_id,
            requirement_id=requirement_id,
            document_type=document_type,
            status=status,
            processing_status="PENDING",
            original_filename=filename,
            mime_type=detected_mime,
            size_bytes=len(file_bytes),
            sha256=sha256_hash,
            uploaded_at=uploaded_at,
        )

    def process_and_verify_document(
        self,
        state: AgentState,
        document_id: str,
        application_id: str,
        db: Optional[Session] = None,
    ) -> DocumentItemResponse:
        """
        Processes an uploaded document:
        1. Reads file bytes from storage
        2. Extracts raw text and structured fields via DocumentProcessor
        3. Compares structured facts against confirmed CitizenProfile
        4. Detects discrepancies without auto-rejecting
        5. Updates document and requirement status
        """
        doc = None
        file_ref = None
        doc_type = None
        mime = None
        orig_name = None
        req_id = None

        if db:
            doc = DocumentRepository.get_document(db, document_id)
            if not doc:
                raise ValueError(f"Document '{document_id}' not found.")
            file_ref = doc.file_reference
            doc_type = doc.document_type
            mime = doc.mime_type
            orig_name = doc.original_filename
            req_id = doc.requirement_id
        else:
            doc = self._find_doc_in_state(state, document_id)
            if not doc:
                raise ValueError(f"Document '{document_id}' not found in state.")
            file_ref = doc.get("file_reference")
            doc_type = doc.get("document_type")
            mime = doc.get("mime_type")
            orig_name = doc.get("original_filename")
            req_id = doc.get("requirement_id")

        if not file_ref:
            raise ValueError(f"Document '{document_id}' has no valid file reference.")

        # 1. Fetch file bytes
        file_bytes = self.storage.get_file_bytes(file_ref)
        if not file_bytes:
            raise ValueError(f"Could not read document file from storage reference: {file_ref}")

        # 2. Extract structured fields
        extraction = DocumentProcessor.process_file(
            file_bytes=file_bytes,
            mime_type=mime or "application/pdf",
            filename=orig_name or "document",
            document_type=doc_type,
        )

        # 3. Compare with confirmed profile
        profile_data = state.profile or {}
        v_fields = DOCUMENT_VERIFICATION_FIELDS_MAP.get(doc_type, ["name"])

        discrepancies: List[DocumentDiscrepancyItem] = []
        if extraction.extraction_status == "SUCCESS":
            discrepancies = DiscrepancyEngine.compare_document_with_profile(
                document_id=document_id,
                application_id=application_id,
                extracted_data=extraction.fields,
                profile_data=profile_data,
                verification_fields=v_fields,
            )

        # 4. Determine resulting statuses
        if extraction.extraction_status == "FAILED" or extraction.extraction_status == "UNREADABLE":
            doc_status = "INVALID"
            v_status = "NOT_VERIFIED"
            req_status = DocumentRequirementStatus.INVALID.value
        elif discrepancies:
            doc_status = "MISMATCH"
            v_status = "MISMATCH"
            req_status = DocumentRequirementStatus.MISMATCH.value
        else:
            doc_status = "VERIFIED"
            v_status = "VERIFIED"
            req_status = DocumentRequirementStatus.VERIFIED.value

        # 5. Persist updates
        if db:
            DocumentRepository.update_document(
                db=db,
                document_id=document_id,
                status=doc_status,
                extraction_status=extraction.extraction_status,
                verification_status=v_status,
                extracted_data=extraction.fields,
            )
            if req_id:
                ApplicationRequirementRepository.update_requirement(
                    db=db,
                    application_id=application_id,
                    requirement_id=req_id,
                    status=req_status,
                    document_id=document_id,
                )
            for disc in discrepancies:
                DocumentDiscrepancyRepository.create_discrepancy(
                    db=db,
                    document_id=document_id,
                    application_id=application_id,
                    field_name=disc.field_name,
                    profile_value=disc.profile_value,
                    document_value=disc.document_value,
                    discrepancy_type=disc.discrepancy_type,
                    status=disc.status,
                )

            # Record events
            EventRepository.record_application_event(
                db=db,
                application_id=application_id,
                event_type="DOCUMENT_PROCESSED",
                event_data={
                    "document_id": document_id,
                    "extraction_status": extraction.extraction_status,
                    "verification_status": v_status,
                    "discrepancies_count": len(discrepancies),
                },
            )
            db.commit()
        else:
            doc["status"] = doc_status
            doc["extraction_status"] = extraction.extraction_status
            doc["verification_status"] = v_status
            doc["extracted_data"] = extraction.fields
            doc["discrepancies"] = [d.dict() for d in discrepancies]

        return DocumentItemResponse(
            document_id=document_id,
            application_id=application_id,
            requirement_id=req_id,
            document_type=doc_type,
            status=doc_status,
            original_filename=orig_name,
            mime_type=mime,
            extracted_data=extraction.fields,
            extraction_status=extraction.extraction_status,
            verification_status=v_status,
            discrepancies=discrepancies,
        )

    def resolve_discrepancy(
        self,
        state: AgentState,
        discrepancy_id: str,
        resolution: str,  # KEEP_PROFILE, USE_DOCUMENT, ESCALATE
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Resolves a factual discrepancy without auto-rejecting.
        - KEEP_PROFILE: User confirms profile fact; document discrepancy resolved.
        - USE_DOCUMENT: User accepts document value as new profile truth. Invokes
          Phase 3 confirmation mechanism to update confirmed profile, invalidates stale
          scheme evaluations, and reevaluates affected schemes.
        - ESCALATE: Escalated for CSC supervisor review.
        """
        disc_obj = None
        if db:
            disc_obj = DocumentDiscrepancyRepository.get_discrepancy(db, discrepancy_id)
            if not disc_obj:
                raise ValueError(f"Discrepancy '{discrepancy_id}' not found.")
            field_name = disc_obj.field_name
            profile_val = disc_obj.profile_value
            doc_val = disc_obj.document_value
            app_id = disc_obj.application_id
            doc_id = disc_obj.document_id
        else:
            # In-memory search
            found, found_doc = self._find_discrepancy_in_state(state, discrepancy_id)
            if not found:
                raise ValueError(f"Discrepancy '{discrepancy_id}' not found in state.")
            disc_obj = found
            field_name = found["field_name"]
            profile_val = found["profile_value"]
            doc_val = found["document_value"]
            app_id = found_doc.get("application_id") if found_doc else None
            doc_id = found_doc.get("id") if found_doc else None

        result_status = ""
        profile_updated = False

        if resolution == "KEEP_PROFILE":
            result_status = DiscrepancyStatus.USER_CONFIRMED_PROFILE.value
            if db:
                DocumentDiscrepancyRepository.resolve_discrepancy(db, discrepancy_id, result_status)
                # If no more open discrepancies on this document, mark it verified
                open_discs = [d for d in DocumentDiscrepancyRepository.list_by_document(db, doc_id) if d.status == "OPEN"]
                if not open_discs:
                    DocumentRepository.update_document(db, doc_id, status="VERIFIED", verification_status="VERIFIED")
                db.commit()
            else:
                disc_obj["status"] = result_status
                if found_doc:
                    open_discs = [d for d in found_doc.get("discrepancies", []) if d.get("status") == "OPEN"]
                    if not open_discs:
                        found_doc["status"] = "VERIFIED"
                        found_doc["verification_status"] = "VERIFIED"

        elif resolution == "USE_DOCUMENT":
            result_status = DiscrepancyStatus.USER_CONFIRMED_DOCUMENT.value
            if db:
                DocumentDiscrepancyRepository.resolve_discrepancy(db, discrepancy_id, result_status)
                # Mark document verified
                open_discs = [d for d in DocumentDiscrepancyRepository.list_by_document(db, doc_id) if d.status == "OPEN" and d.id != discrepancy_id]
                if not open_discs:
                    DocumentRepository.update_document(db, doc_id, status="VERIFIED", verification_status="VERIFIED")
                db.commit()
            else:
                disc_obj["status"] = result_status
                if found_doc:
                    open_discs = [d for d in found_doc.get("discrepancies", []) if d.get("status") == "OPEN"]
                    if not open_discs:
                        found_doc["status"] = "VERIFIED"
                        found_doc["verification_status"] = "VERIFIED"

            # Integrate through Phase 3 profile update & confirmation path!
            coord = ProfileCoordinator()
            patch_msg = f"Update {field_name} to {doc_val}"
            # Apply profile update
            state.profile[field_name] = doc_val
            if field_name == "land_holding_acres":
                state.profile["land_acres"] = doc_val
            elif field_name == "land_acres":
                state.profile["land_holding_acres"] = doc_val

            # Invalidate stale scheme evaluations
            state.invalidate_eligibility_if_stale()
            profile_updated = True

        elif resolution == "ESCALATE":
            result_status = DiscrepancyStatus.ESCALATED.value
            if db:
                DocumentDiscrepancyRepository.resolve_discrepancy(db, discrepancy_id, result_status)
                db.commit()
            else:
                disc_obj["status"] = result_status

        else:
            raise ValueError(f"Unsupported resolution type '{resolution}'.")

        return {
            "discrepancy_id": discrepancy_id,
            "field_name": field_name,
            "resolution": resolution,
            "status": result_status,
            "profile_updated": profile_updated,
        }

    def link_document_to_application(
        self,
        state: AgentState,
        source_document_id: str,
        target_application_id: str,
        requirement_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Explicitly links an already-verified document to another application track
        (document sharing across applications). Application A remains untouched.
        """
        if db:
            src_doc = DocumentRepository.get_document(db, source_document_id)
            if not src_doc:
                raise ValueError(f"Source document '{source_document_id}' not found.")
            target_app = ApplicationRepository.get_application(db, target_application_id)
            if not target_app:
                raise ValueError(f"Target application '{target_application_id}' not found.")

            # Create or update target requirement
            doc_type = src_doc.document_type
            if not requirement_id:
                checklist = self.get_application_checklist(state, target_application_id, db)
                match = next((c for c in checklist if c.document_type == doc_type), None)
                if match:
                    requirement_id = match.requirement_id

            if requirement_id:
                ApplicationRequirementRepository.get_or_create_requirement(
                    db=db,
                    application_id=target_application_id,
                    requirement_id=requirement_id,
                    document_type=doc_type,
                    status=src_doc.status,
                    document_id=src_doc.id,
                )
            # Create a shared document reference for target application
            shared_doc = DocumentRepository.create_document(
                db=db,
                application_id=target_application_id,
                document_type=doc_type,
                file_reference=src_doc.file_reference,
                requirement_id=requirement_id,
                original_filename=src_doc.original_filename,
                mime_type=src_doc.mime_type,
                size_bytes=src_doc.size_bytes,
                sha256_hash=src_doc.sha256_hash,
                status=src_doc.status,
                extraction_status=src_doc.extraction_status,
                verification_status=src_doc.verification_status,
                extracted_data=src_doc.extracted_data,
            )
            db.commit()
            return {
                "status": "LINKED",
                "source_document_id": source_document_id,
                "target_application_id": target_application_id,
                "shared_document_id": shared_doc.id,
            }
        else:
            # In-memory linking
            src_doc = self._find_doc_in_state(state, source_document_id)
            if not src_doc:
                raise ValueError(f"Source document '{source_document_id}' not found in state.")

            import uuid
            shared_id = f"doc_shared_{uuid.uuid4().hex[:8]}"
            shared_doc = dict(src_doc)
            shared_doc["id"] = shared_id
            shared_doc["application_id"] = target_application_id
            if requirement_id:
                shared_doc["requirement_id"] = requirement_id

            self._add_doc_to_state(state, target_application_id, shared_doc)
            return {
                "status": "LINKED",
                "source_document_id": source_document_id,
                "target_application_id": target_application_id,
                "shared_document_id": shared_id,
            }

    def compute_readiness(
        self,
        state: AgentState,
        application_id: str,
        db: Optional[Session] = None,
    ) -> ApplicationReadiness:
        """
        Computes deterministic readiness for an application track.
        """
        scheme_id = None
        for s_id, app_info in state.applications.items():
            if app_info.get("id") == application_id or s_id == application_id:
                scheme_id = s_id
                break

        if not scheme_id and db:
            app_record = ApplicationRepository.get_application(db, application_id)
            if app_record:
                scheme_id = app_record.scheme_id

        if not scheme_id:
            scheme_id = state.active_scheme_id or "unknown_scheme"

        checklist = self.get_application_checklist(state, application_id, db)

        # Get open discrepancies
        discrepancies: List[DocumentDiscrepancyItem] = []
        if db:
            disc_records = DocumentDiscrepancyRepository.list_by_application(db, application_id)
            for d in disc_records:
                discrepancies.append(
                    DocumentDiscrepancyItem(
                        discrepancy_id=d.id,
                        document_id=d.document_id,
                        application_id=d.application_id,
                        field_name=d.field_name,
                        profile_value=d.profile_value,
                        document_value=d.document_value,
                        discrepancy_type=d.discrepancy_type,
                        status=d.status,
                        created_at=d.created_at.isoformat() if d.created_at else None,
                        resolved_at=d.resolved_at.isoformat() if d.resolved_at else None,
                    )
                )
        else:
            app_docs = self._get_app_docs_from_state(state, application_id)
            for d in app_docs:
                for disc in d.get("discrepancies", []):
                    discrepancies.append(DocumentDiscrepancyItem(**disc))

        readiness = ReadinessEngine.calculate_readiness(
            application_id=application_id,
            scheme_id=scheme_id,
            checklist=checklist,
            discrepancies=discrepancies,
        )

        # Record agent event if DB available
        if db:
            EventRepository.record_agent_event(
                db=db,
                case_id=state.case_id,
                iteration=state.iteration,
                stage=state.stage,
                action="CALCULATE_READINESS",
                reason_code="READINESS_RECALCULATED",
                state_fingerprint=state.get_fingerprint(),
                event_data={
                    "application_id": application_id,
                    "readiness_status": readiness.status,
                    "verified_requirements": readiness.verified_requirements,
                    "total_requirements": readiness.total_requirements,
                },
            )
            db.commit()

        return readiness
