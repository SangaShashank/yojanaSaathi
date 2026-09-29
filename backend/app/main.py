"""
Yojana Saathi - FastAPI Application Entry Point
================================================
Exposes REST endpoints for case lifecycle, natural language intake, human confirmation,
and database-backed state synchronization.
"""

from contextlib import asynccontextmanager
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, status, File, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pathlib import Path
from fastapi.staticfiles import StaticFiles

from backend.app.agent.controller import AgentController
from backend.app.agent.provider import DeterministicActionProvider
from backend.app.agent.policies import STANDARD_QUESTIONS
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
from backend.app.schemas.profile import CitizenProfile
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
from backend.app.schemas.handoff import HandoffPackageResponse, PreSubmissionVerification
from backend.app.services.handoff_service import HandoffService, PreSubmissionBlockedError
from backend.app.schemas.rejection import RejectionEvidenceRequest, RejectionDecodeResult, RecoveryActionRequest, RecoveryStateResponse
from backend.app.services.rejection_recovery_service import RejectionRecoveryService
from backend.app.schemas.voice import (
    LANGUAGE_METADATA,
    SUPPORTED_LANGUAGES,
    SupportedLanguagesResponse,
    VoiceTurnResponse,
)
from backend.app.services.voice_service import VoiceService
from backend.app.services.voice_ui import VOICE_UI_HTML

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
handoff_service = HandoffService()
rejection_recovery_service = RejectionRecoveryService()
voice_service = VoiceService(
    profile_coordinator=profile_coordinator,
    agent_controller=agent_controller,
)

# Mount static directory for frontend assets
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse, tags=["Web UI"])
def web_ui_endpoint():
    """
    Renders the complete unified citizen + CSC/VLE web application shell.
    """
    template_path = Path(__file__).resolve().parent / "templates" / "index.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Web UI template missing.")
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


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


QUICK_REPLIES_MAP = {
    "land_ownership": [
        {"label": "🌱 Yes, I own land", "text": "Yes, I own cultivable agricultural land"},
        {"label": "❌ No, tenant / landless", "text": "No, I am a tenant farmer or landless"},
    ],
    "cultivates_land": [
        {"label": "🌾 Yes, I cultivate", "text": "Yes, I actively cultivate the land myself"},
        {"label": "❌ No, I don't cultivate", "text": "No, I do not cultivate"},
    ],
    "residence_type": [
        {"label": "🏡 Rural village", "text": "I reside in a rural area"},
        {"label": "🏙️ Urban city", "text": "I reside in an urban area"},
    ],
    "is_bpl": [
        {"label": "📄 Yes, BPL card holder", "text": "Yes, my family has a BPL ration card"},
        {"label": "❌ No BPL card", "text": "No, we do not have a BPL card"},
    ],
    "category": [
        {"label": "General", "text": "My category is General"},
        {"label": "OBC / BC", "text": "My category is OBC"},
        {"label": "SC", "text": "My category is SC"},
        {"label": "ST", "text": "My category is ST"},
    ],
    "gender": [
        {"label": "Male", "text": "I am male"},
        {"label": "Female", "text": "I am female"},
    ],
    "farmer_id_status": [
        {"label": "✓ Yes, registered Farmer ID", "text": "Yes, I have an active registered Farmer ID"},
        {"label": "❌ No Farmer ID", "text": "No, I do not have a Farmer ID"},
    ],
    "co_borrower_legal_heir": [
        {"label": "✓ Yes, co-borrower available", "text": "Yes, I have a co-borrower or legal heir"},
        {"label": "❌ No co-borrower", "text": "No, I do not have a co-borrower"},
    ],
    "marriage_status": [
        {"label": "💍 Married", "text": "I am married"},
        {"label": "Single / Unmarried", "text": "I am single"},
        {"label": "Widowed", "text": "I am a widow"},
    ],
}


@app.get("/api/cases/{case_id}/agent/next-question", tags=["Cases"])
def get_next_agent_question_endpoint(case_id: str, db: Session = Depends(get_db)):
    """
    Computes the next high-value question the agent needs to ask the user,
    prioritizing missing fields for selected schemes and active candidate programs.
    Returns the natural-language question and 1-click quick response options.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    state.recompute_missing_information()

    from backend.app.agent.policies import score_missing_field, STANDARD_QUESTIONS, FIELD_PRIORITY
    all_catalog = {s.scheme_id: s for s in load_all_schemes()}
    profile_obj = CitizenProfile.model_validate(state.profile)

    # 1. Determine active target schemes: selected schemes first, then candidate schemes, then all
    target_schemes = []
    if state.selected_schemes:
        target_schemes = [all_catalog[sid] for sid in state.selected_schemes if sid in all_catalog]
    elif state.candidate_schemes:
        target_schemes = [all_catalog[sid] for sid in state.candidate_schemes if sid in all_catalog]

    # Find missing fields specifically needed by these active target schemes
    scheme_specific_missing = set()
    scheme_field_map = {}
    for scheme in target_schemes:
        for cond in scheme.eligibility.conditions:
            val, is_known = profile_obj.get_field_value(cond.field)
            if not is_known:
                scheme_specific_missing.add(cond.field)
                if cond.field not in scheme_field_map:
                    scheme_field_map[cond.field] = []
                if scheme.title_en not in scheme_field_map[cond.field]:
                    scheme_field_map[cond.field].append(scheme.title_en)

    # If active schemes have missing fields, prioritize them!
    if scheme_specific_missing:
        candidate_fields = list(scheme_specific_missing)
    else:
        # Otherwise fall back to overall missing information
        state.recompute_missing_information()
        candidate_fields = list(state.missing_information)

    if not candidate_fields:
        return {
            "has_question": False,
            "message": "All required profile facts are confirmed! Your profile is ready for scheme evaluation.",
            "field": None,
            "question": None,
            "quick_replies": [],
        }

    # Sort candidates by policy priority score
    scored = sorted(candidate_fields, key=lambda f: score_missing_field(f, state), reverse=True)
    target_field = scored[0]

    question = STANDARD_QUESTIONS.get(target_field, f"Could you please share your {target_field.replace('_', ' ')}?")
    quick_replies = QUICK_REPLIES_MAP.get(target_field, [])

    # Pre-selection vs Post-selection scheme context badge
    if state.selected_schemes:
        selected_titles = [all_catalog[sid].title_en for sid in state.selected_schemes if sid in all_catalog]
        needed_selected = [s for s in scheme_field_map.get(target_field, []) if s in selected_titles]
        if not needed_selected:
            # Check conditions of selected schemes directly
            for sid in state.selected_schemes:
                if sid in all_catalog:
                    sch = all_catalog[sid]
                    for cond in sch.eligibility.conditions:
                        if cond.field == target_field and sch.title_en not in needed_selected:
                            needed_selected.append(sch.title_en)
        if needed_selected:
            scheme_context = f"Prerequisite for {', '.join(needed_selected[:2])}"
        else:
            scheme_context = "Information needed to check supported schemes"
    else:
        scheme_context = "Information needed to check supported schemes"

    return {
        "has_question": True,
        "field": target_field,
        "question": question,
        "scheme_context": scheme_context,
        "quick_replies": quick_replies,
        "remaining_gaps_count": len(candidate_fields),
    }



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

    agent_message = None
    try:
        decision = agent_controller.run_step(state)
        persist_agent_state(db, state)
        if decision and getattr(decision, "explanation", None):
            agent_message = decision.explanation
    except Exception as e:
        logger.debug(f"Agent step execution note: {e}")

    return {
        "status": "CONFIRMED",
        "confirmed_profile": updated_profile,
        "missing_information": state.missing_information,
        "stage": state.stage,
        "eligibility_invalidated": invalidated,
        "agent_message": agent_message,
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


class ManualEditProfileRequest(BaseModel):
    field: str
    value: Any
    auto_confirm: bool = False


@app.get("/api/profile/fields", tags=["Profile"])
def get_supported_profile_fields_endpoint():
    """Lists supported citizen profile fields with friendly questions and types."""
    fields_meta = []
    boolean_fields = {
        "land_ownership", "cultivates_land", "active_cultivation_status",
        "is_bpl", "widow_status", "facing_violence_or_abuse_flag",
        "pregnancy_or_lactation_status", "co_borrower_legal_heir",
    }
    number_fields = {
        "age", "land_acres", "land_holding_acres", "annual_income_inr",
        "annual_family_income_inr", "girl_child_age", "existing_ssy_accounts_count",
    }

    for f_name, f_info in CitizenProfile.model_fields.items():
        question = STANDARD_QUESTIONS.get(f_name, f"What is your {f_name.replace('_', ' ')}?")
        kind = "string"
        options = None
        if f_name in boolean_fields or "bool" in str(f_info.annotation).lower():
            kind = "boolean"
            options = [
                {"label": "Yes (True)", "value": "true"},
                {"label": "No (False)", "value": "false"},
            ]
        elif f_name in number_fields or "int" in str(f_info.annotation).lower() or "float" in str(f_info.annotation).lower():
            kind = "number"

        fields_meta.append({
            "name": f_name,
            "label": f_name.replace("_", " ").title(),
            "question": question,
            "kind": kind,
            "options": options,
            "type": str(f_info.annotation),
            "description": question,
        })
    return {"fields": fields_meta}


@app.post("/api/cases/{case_id}/profile/edit", tags=["Profile"])
def edit_profile_field_endpoint(
    case_id: str, payload: ManualEditProfileRequest, db: Session = Depends(get_db)
):
    """
    Directly updates a profile field manually:
    - Bypasses Gemini fact extraction.
    - Uses deterministic schema validation.
    - If auto_confirm=True, confirms immediately and invalidates stale evaluations.
    - Otherwise stages as pending confirmation.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    try:
        res = profile_coordinator.apply_manual_edit(
            state=state,
            field=payload.field,
            value=payload.value,
            auto_confirm=payload.auto_confirm,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if state.pending_confirmation:
        ConfirmationRepository.create_confirmation(
            db=db,
            confirmation_id=state.pending_confirmation["confirmation_id"],
            case_id=case_id,
            proposed_changes=state.pending_confirmation.get("changes", []),
            raw_patch=state.pending_confirmation.get("raw_patch", {}),
        )

    persist_agent_state(db, state)
    return res


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


@app.get("/api/schemes/catalog", tags=["Multi-Scheme"])
def get_schemes_catalog_endpoint():
    """Returns the full curated catalog of all 13 supported welfare schemes in canonical order."""
    schemes = load_all_schemes()
    return {
        "total_schemes": len(schemes),
        "schemes": [
            {
                "scheme_id": s.scheme_id,
                "title_en": s.title_en,
                "title_hi": getattr(s, "title_hi", None) or s.title_en,
                "title_te": getattr(s, "title_te", None) or s.title_en,
                "department": getattr(s, "department", getattr(s, "ministry", "Government Welfare")),
                "ministry": getattr(s, "ministry", "Government of India"),
                "target_beneficiary": getattr(s, "target_beneficiary", ""),
                "benefit_summary": getattr(s, "benefit_summary", ""),
                "required_fields": [c.field for c in s.eligibility.conditions],
                "required_documents": [
                    {
                        "doc_id": d.doc_id,
                        "name_en": d.name_en,
                        "is_mandatory": getattr(d, "is_mandatory", True),
                    }
                    for d in getattr(s, "required_documents", [])
                ],
            }
            for s in schemes
        ],
    }


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


# =========================================================================
# PHASE 6: PRE-SUBMISSION DOSSIER & CSC/VLE HANDOFF
# =========================================================================

@app.get("/api/cases/{case_id}/applications/{application_id}/pre-submission-verification", response_model=PreSubmissionVerification, tags=["Pre-Submission Handoff"])
def pre_submission_verification_endpoint(case_id: str, application_id: str, db: Session = Depends(get_db)):
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return handoff_service.verify(state, application_id, db)


def _generate_handoff(case_id: str, application_id: str, db: Session) -> HandoffPackageResponse:
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    try:
        return handoff_service.generate_handoff_package(state, application_id, db)
    except PreSubmissionBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/api/cases/{case_id}/applications/{application_id}/reference-sheet", response_model=HandoffPackageResponse, tags=["Pre-Submission Handoff"])
def generate_reference_sheet_endpoint(case_id: str, application_id: str, db: Session = Depends(get_db)):
    """Generates the concise reference sheet and its matching dossier snapshot."""
    return _generate_handoff(case_id, application_id, db)


@app.post("/api/cases/{case_id}/applications/{application_id}/dossier", response_model=HandoffPackageResponse, tags=["Pre-Submission Handoff"])
def generate_dossier_endpoint(case_id: str, application_id: str, db: Session = Depends(get_db)):
    return _generate_handoff(case_id, application_id, db)


@app.post("/api/cases/{case_id}/applications/{application_id}/handoff-package", response_model=HandoffPackageResponse, tags=["Pre-Submission Handoff"])
def generate_handoff_package_endpoint(case_id: str, application_id: str, db: Session = Depends(get_db)):
    return _generate_handoff(case_id, application_id, db)


@app.get("/api/cases/{case_id}/applications/{application_id}/handoff-package", response_model=HandoffPackageResponse, tags=["Pre-Submission Handoff"])
def get_handoff_package_endpoint(case_id: str, application_id: str, db: Session = Depends(get_db)):
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    package = handoff_service.get_current_package(state, application_id, db)
    if not package:
        raise HTTPException(status_code=404, detail="No current handoff package is available.")
    return package


@app.get("/api/cases/{case_id}/applications/{application_id}/handoff-package/{package_id}/{artifact}", tags=["Pre-Submission Handoff"])
def download_handoff_artifact_endpoint(case_id: str, application_id: str, package_id: str, artifact: str, db: Session = Depends(get_db)):
    """Streams a controlled PDF download and never reveals a server filesystem path."""
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    try:
        path = handoff_service.package_file(state, application_id, package_id, artifact, db)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Requested current package artifact is unavailable.")
    return FileResponse(path, media_type="application/pdf", filename=f"yojana-saathi-{artifact}.pdf")


# Phase 7: external evidence only; no portal polling or submission is performed.
@app.post("/api/cases/{case_id}/applications/{application_id}/rejection", response_model=RecoveryStateResponse, tags=["Rejection Recovery"])
def claim_rejection_endpoint(case_id: str, application_id: str, db: Session = Depends(get_db)):
    try: return rejection_recovery_service.claim(db, case_id, application_id)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc))

@app.post("/api/cases/{case_id}/applications/{application_id}/rejection/{event_id}/evidence", tags=["Rejection Recovery"])
def add_rejection_evidence_endpoint(case_id: str, application_id: str, event_id: str, payload: RejectionEvidenceRequest, db: Session = Depends(get_db)):
    try:
        evidence=rejection_recovery_service.evidence(db,case_id,application_id,event_id,payload)
        return {"evidence_id":evidence.id,"application_id":application_id,"status":evidence.status}
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc))

@app.post("/api/cases/{case_id}/applications/{application_id}/rejection/{event_id}/decode", response_model=RejectionDecodeResult, tags=["Rejection Recovery"])
def decode_rejection_endpoint(case_id: str, application_id: str, event_id: str, db: Session = Depends(get_db)):
    try: return rejection_recovery_service.decode(db,case_id,application_id,event_id)
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc))

@app.get("/api/cases/{case_id}/applications/{application_id}/rejection", response_model=RecoveryStateResponse, tags=["Rejection Recovery"])
@app.get("/api/cases/{case_id}/applications/{application_id}/recovery", response_model=RecoveryStateResponse, tags=["Rejection Recovery"])
def get_recovery_state_endpoint(case_id: str, application_id: str, db: Session = Depends(get_db)):
    try: return rejection_recovery_service.state(db,case_id,application_id)
    except ValueError as exc: raise HTTPException(status_code=404,detail=str(exc))

@app.post("/api/cases/{case_id}/applications/{application_id}/rejection/{event_id}/recovery/action", response_model=RecoveryStateResponse, tags=["Rejection Recovery"])
def recovery_action_endpoint(case_id: str, application_id: str, event_id: str, payload: RecoveryActionRequest, db: Session = Depends(get_db)):
    try: return rejection_recovery_service.recovery_action(db,case_id,application_id,event_id,payload.action,payload.evidence_note)
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc))


# =========================================================================
# PHASE 8 — MULTILINGUAL VOICE & AUDIO ENDPOINTS
# =========================================================================

@app.get("/voice", response_class=HTMLResponse, tags=["Voice"])
def voice_ui_endpoint():
    """
    Renders the accessible browser voice interface with client-side SpeechSynthesis TTS,
    recording status indicators, transcript review/editing, and typed text fallback.
    """
    return HTMLResponse(content=VOICE_UI_HTML)


@app.get("/api/voice/languages", response_model=SupportedLanguagesResponse, tags=["Voice"])
@app.get("/api/cases/{case_id}/voice/languages", response_model=SupportedLanguagesResponse, tags=["Voice"])
def get_supported_languages_endpoint(case_id: Optional[str] = None):
    """Returns allowlisted interaction languages (en, hi, te) and browser locale metadata."""
    return SupportedLanguagesResponse(
        supported_languages=SUPPORTED_LANGUAGES,
        languages=LANGUAGE_METADATA,
    )


@app.post("/api/cases/{case_id}/voice", response_model=VoiceTurnResponse, tags=["Voice"])
async def process_voice_turn_endpoint(
    case_id: str,
    audio: UploadFile = File(..., description="Speech audio file (WAV, MP3, WebM, OGG, M4A, FLAC)"),
    language: Optional[str] = Form("en", description="Preferred language code: en, hi, or te"),
    turn_id: Optional[str] = Form(None, description="Optional idempotency turn identifier"),
    db: Session = Depends(get_db),
):
    """
    Processes citizen voice recording through the existing message and profile pipeline:
    1. Validates audio upload constraints (size <= 10MB, non-executable, audio MIME).
    2. Transcribes speech audio using Groq Whisper.
    3. Passes raw transcript into existing message pipeline (ProfileCoordinator / AgentController).
    4. Evaluates or updates case state without bypassing human confirmation.
    5. Returns structured speakable response for browser SpeechSynthesis.
    """
    state = load_case(db, case_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio recording received.")

    try:
        response = voice_service.process_voice_turn(
            db=db,
            case_id=case_id,
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.wav",
            content_type=audio.content_type,
            language=language,
            turn_id=turn_id,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing voice turn for case {case_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {e}")



