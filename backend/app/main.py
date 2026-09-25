"""
Yojana Saathi - FastAPI Application Entry Point
================================================
Exposes REST endpoints for case lifecycle, natural language intake, human confirmation,
and database-backed state synchronization.
"""

from contextlib import asynccontextmanager
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.agent.controller import AgentController
from backend.app.agent.provider import DeterministicActionProvider
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.repositories.confirmation_repository import ConfirmationRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.profile_repository import (
    ProfileConcurrencyError,
    ProfileRepository,
)
from backend.app.db.services.profile_persistence import (
    confirm_and_persist_profile,
    reject_and_persist_profile,
)
from backend.app.db.services.state_persistence import load_case, persist_agent_state
from backend.app.db.session import check_db_connection, engine, get_db
from backend.app.profile.coordinator import ProfileCoordinator
from backend.app.schemas.multi_scheme import (
    ApplicationItemResponse,
    ApplicationListResponse,
    SchemeEvaluationListResponse,
    SchemeOutcomeItem,
    SelectSchemesRequest,
    UpdateApplicationStatusRequest,
)
from backend.app.services.multi_scheme_coordinator import MultiSchemeCoordinator
from backend.app.services.scheme_loader import load_all_schemes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup: verify database connection
    db_ok = check_db_connection()
    if db_ok:
        logger.info("Connected to PostgreSQL database successfully.")
    else:
        logger.warning("Database connection failed during startup.")
    yield
    # Shutdown: clean up connection pool
    engine.dispose()
    logger.info("PostgreSQL engine connection pool disposed.")


app = FastAPI(
    title="Yojana Saathi API",
    description="Welfare Intelligence & Scheme Eligibility Orchestration Engine",
    version="1.0.0",
    lifespan=lifespan,
)

profile_coordinator = ProfileCoordinator()
agent_controller = AgentController(provider=DeterministicActionProvider())


# =========================================================================
# HEALTH ENDPOINTS
# =========================================================================

@app.get("/health", tags=["Health"])
@app.get("/health/db", tags=["Health"])
def health_check():
    """
    Performs real database ping query (SELECT 1).
    Never exposes database passwords, hosts, or connection URLs.
    """
    db_ok = check_db_connection()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "unreachable"},
        )
    return {"status": "ok", "database": "ok"}


# =========================================================================
# SCHEMAS FOR API REQUESTS / RESPONSES
# =========================================================================

class CreateCaseRequest(BaseModel):
    goal: Optional[str] = "Identify applicable welfare schemes and orchestrate readiness"
    candidate_schemes: Optional[List[str]] = Field(default_factory=list)
    user_id: Optional[str] = None


class CaseResponse(BaseModel):
    case_id: str
    status: str
    goal: str
    stage: str
    iteration: int
    missing_information: List[str]
    candidate_schemes: List[str]
    eligible_schemes: List[str]
    eliminated_schemes: List[str]
    has_pending_confirmation: bool


class UserMessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    case_id: str
    status: str
    message: str
    confirmation_required: bool
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    ambiguous_fields: List[str] = Field(default_factory=list)
    stage: str


class ProfileResponse(BaseModel):
    case_id: str
    confirmed_profile: Dict[str, Any]
    fingerprint: Optional[str] = None
    version: Optional[int] = None
    pending_confirmation: Optional[Dict[str, Any]] = None


class ConfirmProfileRequest(BaseModel):
    expected_version: Optional[int] = None


# =========================================================================
# CASE MANAGEMENT ENDPOINTS
# =========================================================================

@app.post("/api/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED, tags=["Cases"])
def create_case_endpoint(payload: CreateCaseRequest, db: Session = Depends(get_db)):
    """Creates a new assistance case and persists it to PostgreSQL."""
    candidate_schemes = payload.candidate_schemes or []
    case = CaseRepository.create_case(
        db=db,
        user_id=payload.user_id,
        goal=payload.goal,
        candidate_schemes=candidate_schemes,
    )
    return CaseResponse(
        case_id=case.id,
        status=case.status,
        goal=case.goal,
        stage=case.stage,
        iteration=case.iteration,
        missing_information=case.missing_information,
        candidate_schemes=case.candidate_schemes,
        eligible_schemes=[],
        eliminated_schemes=[],
        has_pending_confirmation=False,
    )


@app.get("/api/cases/{case_id}", response_model=CaseResponse, tags=["Cases"])
def get_case_endpoint(case_id: str, db: Session = Depends(get_db)):
    """Retrieves full case status and current eligibility state from PostgreSQL."""
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_db = CaseRepository.get_case(db, case_id)
    return CaseResponse(
        case_id=state.case_id,
        status=case_db.status if case_db else "ACTIVE",
        goal=state.goal,
        stage=state.stage,
        iteration=state.iteration,
        missing_information=state.missing_information,
        candidate_schemes=state.candidate_schemes,
        eligible_schemes=state.eligible_schemes,
        eliminated_schemes=state.eliminated_schemes,
        has_pending_confirmation=bool(state.pending_confirmation),
    )


@app.post("/api/cases/{case_id}/messages", response_model=MessageResponse, tags=["Cases"])
def process_message_endpoint(
    case_id: str, payload: UserMessageRequest, db: Session = Depends(get_db)
):
    """
    Submits user text to the case:
    1. Extracts structured profile facts.
    2. Proposes patch and stages for human confirmation.
    3. Persists state updates to PostgreSQL.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    coord_result = profile_coordinator.process_user_message(state, payload.message)

    # If changes were proposed, stage confirmation in DB
    if state.pending_confirmation:
        ConfirmationRepository.create_confirmation(
            db=db,
            confirmation_id=state.pending_confirmation["confirmation_id"],
            case_id=case_id,
            proposed_changes=state.pending_confirmation.get("changes", []),
            raw_patch=state.pending_confirmation.get("raw_patch", {}),
        )

    persist_agent_state(db, state)

    return MessageResponse(
        case_id=case_id,
        status=coord_result.get("status", "SUCCESS"),
        message=coord_result.get("message", "Message processed."),
        confirmation_required=coord_result.get("confirmation_required", False),
        changes=coord_result.get("changes", []),
        ambiguous_fields=coord_result.get("ambiguous_fields", []),
        stage=state.stage,
    )


# =========================================================================
# PROFILE & CONFIRMATION ENDPOINTS
# =========================================================================

@app.get("/api/cases/{case_id}/profile", response_model=ProfileResponse, tags=["Profile"])
def get_profile_endpoint(case_id: str, db: Session = Depends(get_db)):
    """Retrieves confirmed profile facts and any pending confirmation request."""
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    profile_db = ProfileRepository.get_by_case_id(db, case_id)
    return ProfileResponse(
        case_id=case_id,
        confirmed_profile=state.profile,
        fingerprint=profile_db.profile_fingerprint if profile_db else None,
        version=profile_db.version if profile_db else None,
        pending_confirmation=state.pending_confirmation,
    )


@app.post("/api/cases/{case_id}/profile/confirm", tags=["Profile"])
def confirm_profile_endpoint(
    case_id: str, payload: ConfirmProfileRequest, db: Session = Depends(get_db)
):
    """
    Authoritatively confirms pending profile facts.
    Applies patch, updates PostgreSQL transactionally, and invalidates stale evaluations.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    if not state.pending_confirmation:
        raise HTTPException(status_code=400, detail="No pending profile changes to confirm.")

    try:
        updated_profile, invalidated = confirm_and_persist_profile(
            db=db, state=state, expected_version=payload.expected_version
        )
    except ProfileConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "status": "CONFIRMED",
        "confirmed_profile": updated_profile,
        "missing_information": state.missing_information,
        "stage": state.stage,
        "eligibility_invalidated": invalidated,
    }


@app.post("/api/cases/{case_id}/profile/reject", tags=["Profile"])
def reject_profile_endpoint(case_id: str, db: Session = Depends(get_db)):
    """
    Rejects pending proposed facts.
    Confirmed profile in PostgreSQL remains completely untouched.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    if not state.pending_confirmation:
        raise HTTPException(status_code=400, detail="No pending profile changes to reject.")

    rejected_profile = reject_and_persist_profile(db=db, state=state)
    return {
        "status": "REJECTED",
        "confirmed_profile": rejected_profile,
        "message": "Proposed profile facts rejected. Confirmed profile unchanged.",
    }


# =========================================================================
# OBSERVABILITY ENDPOINTS
# =========================================================================

@app.get("/api/cases/{case_id}/activity", tags=["Observability"])
def get_activity_endpoint(case_id: str, db: Session = Depends(get_db)):
    """Retrieves chronological Agent Activity audit log for the case."""
    events = EventRepository.list_agent_events(db, case_id)
    return {
        "case_id": case_id,
        "events": [
            {
                "id": ev.id,
                "iteration": ev.iteration,
                "stage": ev.stage,
                "action": ev.action,
                "reason_code": ev.reason_code,
                "selected_field": ev.selected_field,
                "state_fingerprint": ev.state_fingerprint,
                "event_data": ev.event_data,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in events
        ],
    }


# =========================================================================
# MULTI-SCHEME EVALUATION & SELECTION ENDPOINTS
# =========================================================================

@app.post(
    "/api/cases/{case_id}/schemes/evaluate",
    response_model=SchemeEvaluationListResponse,
    tags=["Multi-Scheme"],
)
def evaluate_case_schemes_endpoint(case_id: str, db: Session = Depends(get_db)):
    """
    Evaluates all supported candidate schemes independently for the case.
    Persists evaluation outcomes with current profile fingerprint.
    Does not rank or recommend schemes.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    if state.pending_confirmation:
        raise HTTPException(
            status_code=400,
            detail="Cannot evaluate schemes while profile changes are pending human confirmation.",
        )

    try:
        items = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db)
        persist_agent_state(db, state)
        return SchemeEvaluationListResponse(
            case_id=case_id,
            profile_fingerprint=state.get_profile_fingerprint(),
            total_evaluated=len(items),
            schemes=items,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/cases/{case_id}/schemes",
    response_model=SchemeEvaluationListResponse,
    tags=["Multi-Scheme"],
)
def get_case_schemes_endpoint(case_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the latest evaluations for the case.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    evals = SchemeEvaluationRepository.list_active_for_case(db, case_id)
    all_catalog = {s.scheme_id: s for s in load_all_schemes()}

    outcome_items: List[SchemeOutcomeItem] = []
    for ev in evals:
        s_def = all_catalog.get(ev.scheme_id)
        s_name = s_def.title_en if s_def else ev.scheme_id
        is_selectable = ev.outcome in ["FULLY_ELIGIBLE", "ACTIONABLE_PREPARATION_REQUIRED"]
        existing_app_id = state.applications.get(ev.scheme_id, {}).get("id")

        outcome_items.append(
            SchemeOutcomeItem(
                scheme_id=ev.scheme_id,
                scheme_name=s_name,
                outcome=ev.outcome,
                eligible=is_selectable,
                selectable=is_selectable,
                missing_information=ev.reasons.get("missing_critical", []) if isinstance(ev.reasons, dict) else [],
                reasons=[ev.reasons.get("summary", "")] if isinstance(ev.reasons, dict) and ev.reasons.get("summary") else [],
                summary_reason=ev.reasons.get("summary", "") if isinstance(ev.reasons, dict) else "",
                profile_fingerprint=ev.profile_fingerprint,
                rules_version=ev.rules_version,
                evaluated_at=ev.evaluated_at.isoformat() if ev.evaluated_at else None,
                application_id=existing_app_id,
            )
        )

    return SchemeEvaluationListResponse(
        case_id=case_id,
        profile_fingerprint=state.get_profile_fingerprint(),
        total_evaluated=len(outcome_items),
        schemes=outcome_items,
    )


@app.post(
    "/api/cases/{case_id}/schemes/select",
    response_model=ApplicationListResponse,
    tags=["Multi-Scheme"],
)
def select_schemes_endpoint(
    case_id: str, payload: SelectSchemesRequest, db: Session = Depends(get_db)
):
    """
    Allows the citizen/CSC operator to select multiple eligible/actionable schemes.
    Creates independent application tracks atomically.
    Rejects invalid, duplicate, stale, or not-eligible selections.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    try:
        created_apps = MultiSchemeCoordinator.select_schemes(
            state=state,
            selected_scheme_ids=payload.selected_scheme_ids,
            db=db,
        )
        persist_agent_state(db, state)
        all_catalog = {s.scheme_id: s for s in load_all_schemes()}

        return ApplicationListResponse(
            case_id=case_id,
            applications=[
                ApplicationItemResponse(
                    application_id=app.id,
                    case_id=app.case_id,
                    scheme_id=app.scheme_id,
                    scheme_name=all_catalog[app.scheme_id].title_en if app.scheme_id in all_catalog else app.scheme_id,
                    status=app.status,
                    created_at=app.created_at.isoformat() if app.created_at else None,
                    updated_at=app.updated_at.isoformat() if app.updated_at else None,
                )
                for app in created_apps
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/cases/{case_id}/applications",
    response_model=ApplicationListResponse,
    tags=["Multi-Scheme"],
)
def list_case_applications_endpoint(case_id: str, db: Session = Depends(get_db)):
    """
    Lists all active application tracks for the case.
    """
    case = CaseRepository.get_case_with_relations(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    all_catalog = {s.scheme_id: s for s in load_all_schemes()}
    return ApplicationListResponse(
        case_id=case_id,
        applications=[
            ApplicationItemResponse(
                application_id=app.id,
                case_id=app.case_id,
                scheme_id=app.scheme_id,
                scheme_name=all_catalog[app.scheme_id].title_en if app.scheme_id in all_catalog else app.scheme_id,
                status=app.status,
                created_at=app.created_at.isoformat() if app.created_at else None,
                updated_at=app.updated_at.isoformat() if app.updated_at else None,
            )
            for app in case.applications
        ],
    )


@app.get(
    "/api/cases/{case_id}/applications/{application_id}",
    response_model=ApplicationItemResponse,
    tags=["Multi-Scheme"],
)
def get_application_endpoint(
    case_id: str, application_id: str, db: Session = Depends(get_db)
):
    """
    Retrieves details for a single application track.
    """
    app = ApplicationRepository.get_application(db, application_id)
    if not app or app.case_id != case_id:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found.")

    all_catalog = {s.scheme_id: s for s in load_all_schemes()}
    return ApplicationItemResponse(
        application_id=app.id,
        case_id=app.case_id,
        scheme_id=app.scheme_id,
        scheme_name=all_catalog[app.scheme_id].title_en if app.scheme_id in all_catalog else app.scheme_id,
        status=app.status,
        created_at=app.created_at.isoformat() if app.created_at else None,
        updated_at=app.updated_at.isoformat() if app.updated_at else None,
    )


@app.post(
    "/api/cases/{case_id}/applications/{application_id}/activate",
    tags=["Multi-Scheme"],
)
def activate_application_endpoint(
    case_id: str, application_id: str, db: Session = Depends(get_db)
):
    """
    Switches conversational active context to this application track without modifying other tracks.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    try:
        scheme_id, app_id = MultiSchemeCoordinator.switch_active_application(state, application_id)
        persist_agent_state(db, state)
        return {
            "status": "ACTIVATED",
            "case_id": case_id,
            "active_scheme_id": scheme_id,
            "active_application_id": app_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post(
    "/api/cases/{case_id}/applications/{application_id}/status",
    response_model=ApplicationItemResponse,
    tags=["Multi-Scheme"],
)
def update_application_status_endpoint(
    case_id: str,
    application_id: str,
    payload: UpdateApplicationStatusRequest,
    db: Session = Depends(get_db),
):
    """
    Updates the lifecycle status of a specific application track.
    Leaves other tracks for the same case completely unchanged.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    try:
        updated_app = MultiSchemeCoordinator.update_application_status(
            state=state,
            application_id=application_id,
            new_status=payload.status.value,
            db=db,
        )
        persist_agent_state(db, state)
        all_catalog = {s.scheme_id: s for s in load_all_schemes()}
        return ApplicationItemResponse(
            application_id=updated_app.id,
            case_id=updated_app.case_id,
            scheme_id=updated_app.scheme_id,
            scheme_name=all_catalog[updated_app.scheme_id].title_en if updated_app.scheme_id in all_catalog else updated_app.scheme_id,
            status=updated_app.status,
            created_at=updated_app.created_at.isoformat() if updated_app.created_at else None,
            updated_at=updated_app.updated_at.isoformat() if updated_app.updated_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# PHASE 5: DOCUMENTS & READINESS ENDPOINTS
# =========================================================================

from fastapi import File, Form, UploadFile
from backend.app.schemas.document import (
    ApplicationDocumentChecklistItem,
    ApplicationReadiness,
    DiscrepancyResolutionRequest,
    DocumentDiscrepancyItem,
    DocumentItemResponse,
    DocumentUploadResponse,
    LinkDocumentRequest,
)
from backend.app.services.document_coordinator import DocumentCoordinator

doc_coordinator = DocumentCoordinator()


@app.get(
    "/api/cases/{case_id}/applications/{application_id}/documents",
    tags=["Documents & Readiness"],
)
def get_application_documents_endpoint(
    case_id: str, application_id: str, db: Session = Depends(get_db)
):
    """
    Returns the scheme-specific document checklist and linked documents for an application.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    checklist = doc_coordinator.get_application_checklist(state, application_id, db=db)
    from backend.app.db.repositories.document_repository import DocumentRepository
    docs = DocumentRepository.list_by_application(db, application_id)

    return {
        "case_id": case_id,
        "application_id": application_id,
        "checklist": checklist,
        "uploaded_documents": [
            {
                "document_id": d.id,
                "document_type": d.document_type,
                "status": d.status,
                "original_filename": d.original_filename,
                "size_bytes": d.size_bytes,
                "sha256": d.sha256_hash,
                "extraction_status": d.extraction_status,
                "verification_status": d.verification_status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
    }


@app.post(
    "/api/cases/{case_id}/applications/{application_id}/documents",
    response_model=DocumentUploadResponse,
    tags=["Documents & Readiness"],
)
async def upload_document_endpoint(
    case_id: str,
    application_id: str,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    requirement_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Validates, deduplicates, stores, and attaches an uploaded document to an application.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    content = await file.read()
    try:
        res = doc_coordinator.upload_document(
            state=state,
            application_id=application_id,
            document_type=document_type,
            filename=file.filename or "upload.pdf",
            file_bytes=content,
            mime_type=file.content_type,
            requirement_id=requirement_id,
            db=db,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/cases/{case_id}/applications/{application_id}/documents/{document_id}",
    response_model=DocumentItemResponse,
    tags=["Documents & Readiness"],
)
def get_document_details_endpoint(
    case_id: str, application_id: str, document_id: str, db: Session = Depends(get_db)
):
    """
    Retrieves document metadata, extraction details, and any surfaced discrepancies.
    """
    from backend.app.db.repositories.document_repository import (
        DocumentDiscrepancyRepository,
        DocumentRepository,
    )
    doc = DocumentRepository.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    discs = DocumentDiscrepancyRepository.list_by_document(db, document_id)
    disc_items = [
        DocumentDiscrepancyItem(
            discrepancy_id=d.id,
            document_id=d.document_id,
            application_id=d.application_id,
            field_name=d.field_name,
            profile_value=d.profile_value,
            document_value=d.document_value,
            discrepancy_type=d.discrepancy_type or "VALUE_MISMATCH",
            status=d.status,
            created_at=d.created_at.isoformat() if d.created_at else None,
            resolved_at=d.resolved_at.isoformat() if d.resolved_at else None,
        )
        for d in discs
    ]

    return DocumentItemResponse(
        document_id=doc.id,
        application_id=doc.application_id,
        requirement_id=doc.requirement_id,
        document_type=doc.document_type,
        status=doc.status,
        original_filename=doc.original_filename,
        size_bytes=doc.size_bytes,
        mime_type=doc.mime_type,
        sha256=doc.sha256_hash,
        extracted_data=doc.extracted_data,
        extraction_status=doc.extraction_status or "PENDING",
        verification_status=doc.verification_status or "PENDING",
        discrepancies=disc_items,
    )


@app.post(
    "/api/cases/{case_id}/applications/{application_id}/documents/{document_id}/process",
    response_model=DocumentItemResponse,
    tags=["Documents & Readiness"],
)
def process_document_endpoint(
    case_id: str, application_id: str, document_id: str, db: Session = Depends(get_db)
):
    """
    Processes an uploaded document, extracts fields, and performs comparison against confirmed profile.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    try:
        res = doc_coordinator.process_and_verify_document(
            state=state,
            document_id=document_id,
            application_id=application_id,
            db=db,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post(
    "/api/cases/{case_id}/applications/{application_id}/documents/{document_id}/resolve",
    tags=["Documents & Readiness"],
)
def resolve_discrepancy_endpoint(
    case_id: str,
    application_id: str,
    document_id: str,
    payload: DiscrepancyResolutionRequest,
    discrepancy_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Resolves a document discrepancy without auto-rejecting.
    If USE_DOCUMENT is chosen, updates confirmed profile, invalidates stale evaluations, and reevaluates.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    # Find discrepancy ID
    from backend.app.db.repositories.document_repository import DocumentDiscrepancyRepository
    target_disc_id = discrepancy_id
    if not target_disc_id:
        discs = DocumentDiscrepancyRepository.list_by_document(db, document_id)
        open_d = next((d for d in discs if d.status == "OPEN"), None)
        if not open_d:
            raise HTTPException(status_code=404, detail="No open discrepancy found for this document.")
        target_disc_id = open_d.id

    try:
        res = doc_coordinator.resolve_discrepancy(
            state=state,
            discrepancy_id=target_disc_id,
            resolution=payload.resolution,
            db=db,
        )
        persist_agent_state(db, state)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/cases/{case_id}/applications/{application_id}/readiness",
    response_model=ApplicationReadiness,
    tags=["Documents & Readiness"],
)
def get_application_readiness_endpoint(
    case_id: str, application_id: str, db: Session = Depends(get_db)
):
    """
    Calculates and returns deterministic readiness for an application track.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    readiness = doc_coordinator.compute_readiness(state, application_id, db=db)
    return readiness


@app.post(
    "/api/cases/{case_id}/applications/{application_id}/documents/{document_id}/link",
    tags=["Documents & Readiness"],
)
def link_document_endpoint(
    case_id: str,
    application_id: str,
    document_id: str,
    payload: LinkDocumentRequest,
    db: Session = Depends(get_db),
):
    """
    Explicitly links an existing document to another application track.
    Application A remains completely isolated and unchanged.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    try:
        res = doc_coordinator.link_document_to_application(
            state=state,
            source_document_id=document_id,
            target_application_id=payload.target_application_id,
            requirement_id=payload.requirement_id,
            db=db,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


