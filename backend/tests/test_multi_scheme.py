"""
Phase 4 - Multi-Scheme Handling Test Suite
==========================================
Comprehensive tests for multi-scheme evaluation, selection, application tracking,
stale evaluation invalidation, and independent parallel application lifecycles.
Includes all 20 required tests, critical proof test, and no-ranking assertion.
"""

import uuid
import pytest
from starlette.testclient import TestClient

from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.controller import AgentController
from backend.app.agent.provider import DeterministicActionProvider
from backend.app.agent.state import AgentState, StageEnum, TerminationReason
from backend.app.db.models.case import Case
from backend.app.db.models.application import Application
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.repositories.confirmation_repository import ConfirmationRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.profile_repository import ProfileRepository
from backend.app.db.services.profile_persistence import confirm_and_persist_profile
from backend.app.db.services.state_persistence import load_case, persist_agent_state
from backend.app.db.session import SessionLocal
from backend.app.main import app
from backend.app.schemas.eligibility import SchemeOutcome
from backend.app.schemas.multi_scheme import ApplicationStatus, SchemeOutcomeItem
from backend.app.schemas.profile import CitizenProfile
from backend.app.schemas.scheme import ConditionDefinition, EligibilityDefinition, SchemeDefinition
from backend.app.services.eligibility_engine import evaluate_all_schemes
from backend.app.services.multi_scheme_coordinator import MultiSchemeCoordinator
from backend.app.services.scheme_loader import get_scheme, load_all_schemes


@pytest.fixture
def db_session():
    """Provides a transactional database session rolled back after each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def api_client():
    return TestClient(app)


# =========================================================================
# TEST 1: One eligible scheme
# =========================================================================
def test_test_1_one_eligible_scheme():
    """TEST 1: One eligible scheme yields one FULLY_ELIGIBLE result."""
    # Profile strictly tailored only for Soil Health Card (not farmer in Telangana, no land record cutoff)
    profile = {
        "cultivates_land": True,
        "age": 16,  # Ineligible for PM-KISAN, PM-KMY, Rythu Bima
        "state": "Kerala",  # Ineligible for Telangana schemes
        "gender": "male",  # Ineligible for women schemes
    }
    state = AgentState(profile=profile)
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)

    eligible_items = [o for o in outcomes if o.outcome == SchemeOutcome.FULLY_ELIGIBLE.value]
    eligible_ids = [o.scheme_id for o in eligible_items]

    assert "soil_health_card_001" in eligible_ids
    # Verify that soil_health_card is fully eligible
    soil_res = next(o for o in outcomes if o.scheme_id == "soil_health_card_001")
    assert soil_res.outcome == SchemeOutcome.FULLY_ELIGIBLE.value
    assert soil_res.selectable is True


# =========================================================================
# TEST 2: Multiple eligible schemes
# =========================================================================
def test_test_2_multiple_eligible_schemes():
    """TEST 2: Multiple eligible schemes are evaluated independently without mutual interference."""
    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-05-10",
        "farmer_id_status": "registered",
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    state = AgentState(profile=profile)
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)

    eligible_ids = [o.scheme_id for o in outcomes if o.selectable]
    # Farmer qualifies for PM-KISAN, Rythu Bharosa, Soil Health Card, PM-KMY
    assert "pm_kisan_001" in eligible_ids
    assert "ts_rythu_bharosa_001" in eligible_ids
    assert "soil_health_card_001" in eligible_ids
    assert "pm_kisan_maandhan_001" in eligible_ids
    assert len(eligible_ids) >= 4


# =========================================================================
# TEST 3: Mixed outcomes
# =========================================================================
def test_test_3_mixed_outcomes():
    """TEST 3: Schemes with varied criteria retain their distinct outcomes independently."""
    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-05-10",
        # farmer_id_status omitted -> PM-KISAN becomes INCOMPLETE
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    state = AgentState(profile=profile)
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)
    outcome_map = {o.scheme_id: o.outcome for o in outcomes}

    # Rythu Bharosa: FULLY_ELIGIBLE
    assert outcome_map["ts_rythu_bharosa_001"] == SchemeOutcome.FULLY_ELIGIBLE.value
    # PM-KISAN: INCOMPLETE / UNKNOWN (missing farmer_id_status)
    assert outcome_map["pm_kisan_001"] == SchemeOutcome.INCOMPLETE_UNKNOWN.value
    # Sakhi OSC: NOT_ELIGIBLE (requires female gender)
    assert outcome_map["sakhi_osc_001"] == SchemeOutcome.NOT_ELIGIBLE.value


# =========================================================================
# TEST 4: No supported match
# =========================================================================
def test_test_4_no_supported_match():
    """TEST 4: When all evaluated schemes are NOT_ELIGIBLE, Agent marks NO_SUPPORTED_MATCH."""
    # Profile completely disqualified from all 13 schemes
    profile = {
        "age": 85,  # Exceeds PM-KMY (40), KCC (75), Rythu Bima (59)
        "occupation": "income_tax_payer",  # Disqualified from PM-KISAN, PM-KMY
        "land_ownership": False,
        "cultivates_land": False,
        "gender": "male",
        "state": "Punjab",  # Disqualified from Telangana schemes
        "facing_violence_or_abuse_flag": False,
        "is_bpl": False,
    }
    state = AgentState(profile=profile)
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)

    selectable = [o for o in outcomes if o.selectable]
    assert len(selectable) == 0

    controller = AgentController(provider=DeterministicActionProvider())
    activity, result = controller.step(state)

    assert activity.selected_action == ActionType.NO_SUPPORTED_MATCH.value
    assert state.is_terminated is True
    assert state.termination_reason == TerminationReason.NO_SUPPORTED_MATCH.value


# =========================================================================
# TEST 5: Multiple selection
# =========================================================================
def test_test_5_multiple_selection(db_session):
    """TEST 5: Citizen/CSC operator selects multiple eligible schemes; independent application tracks created."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-05-10",
        "farmer_id_status": "registered",
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    # Select PM-KISAN and Rythu Bharosa
    apps = MultiSchemeCoordinator.select_schemes(
        state=state,
        selected_scheme_ids=["pm_kisan_001", "ts_rythu_bharosa_001"],
        db=db_session,
    )

    assert len(apps) == 2
    app_schemes = {a.scheme_id for a in apps}
    assert app_schemes == {"pm_kisan_001", "ts_rythu_bharosa_001"}
    assert all(a.status == ApplicationStatus.SELECTED.value for a in apps)
    assert len(state.selected_schemes) == 2


# =========================================================================
# TEST 6: Partial selection
# =========================================================================
def test_test_6_partial_selection(db_session):
    """TEST 6: Out of 4 eligible schemes, selecting only 2 creates applications ONLY for the 2 selected."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-05-10",
        "farmer_id_status": "registered",
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    state = AgentState(case_id=case_id, profile=profile)
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)
    selectable = [o.scheme_id for o in outcomes if o.selectable]
    assert len(selectable) >= 4

    # Select only PM-KISAN and Soil Health Card
    apps = MultiSchemeCoordinator.select_schemes(
        state=state,
        selected_scheme_ids=["pm_kisan_001", "soil_health_card_001"],
        db=db_session,
    )
    assert len(apps) == 2
    created_schemes = [a.scheme_id for a in apps]
    assert "pm_kisan_001" in created_schemes
    assert "soil_health_card_001" in created_schemes
    assert "ts_rythu_bharosa_001" not in created_schemes

    # DB verification
    db_apps = ApplicationRepository.list_by_case(db_session, case_id)
    assert len(db_apps) == 2


# =========================================================================
# TEST 7: Duplicate selection
# =========================================================================
def test_test_7_duplicate_selection(db_session):
    """TEST 7: Request containing duplicate scheme IDs is rejected, and selecting an already selected scheme is idempotent."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {"cultivates_land": True}
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    # 1. Duplicates within single request are rejected
    with pytest.raises(ValueError, match="Duplicate scheme IDs"):
        MultiSchemeCoordinator.select_schemes(
            state=state,
            selected_scheme_ids=["soil_health_card_001", "soil_health_card_001"],
            db=db_session,
        )

    # 2. Sequential selection is idempotent (no duplicate DB row created)
    apps1 = MultiSchemeCoordinator.select_schemes(
        state=state, selected_scheme_ids=["soil_health_card_001"], db=db_session
    )
    apps2 = MultiSchemeCoordinator.select_schemes(
        state=state, selected_scheme_ids=["soil_health_card_001"], db=db_session
    )
    assert len(apps1) == 1
    assert len(apps2) == 1
    assert apps1[0].id == apps2[0].id

    all_db_apps = ApplicationRepository.list_by_case(db_session, case_id)
    assert len(all_db_apps) == 1


# =========================================================================
# TEST 8: Invalid scheme selection
# =========================================================================
def test_test_8_invalid_scheme_selection(db_session):
    """TEST 8: Unknown or arbitrary scheme ID selection is strictly rejected."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    state = AgentState(case_id=case_id, profile={"age": 30})
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    with pytest.raises(ValueError, match="does not exist in the configured catalog"):
        MultiSchemeCoordinator.select_schemes(
            state=state,
            selected_scheme_ids=["fake_arbitrary_scheme_999"],
            db=db_session,
        )


# =========================================================================
# TEST 9: Not-eligible selection
# =========================================================================
def test_test_9_not_eligible_selection(db_session):
    """TEST 9: Selecting a NOT_ELIGIBLE scheme is rejected."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {"gender": "male", "cultivates_land": True}
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    # sakhi_osc_001 is NOT_ELIGIBLE for male
    with pytest.raises(ValueError, match="cannot be selected"):
        MultiSchemeCoordinator.select_schemes(
            state=state,
            selected_scheme_ids=["sakhi_osc_001"],
            db=db_session,
        )


# =========================================================================
# TEST 10: Stale evaluation selection
# =========================================================================
def test_test_10_stale_evaluation_selection(db_session):
    """TEST 10: Changing profile invalidates evaluations; selecting on stale evaluation is rejected."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile_v1 = {"cultivates_land": True, "age": 30}
    state = AgentState(case_id=case_id, profile=profile_v1)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    # Profile changes to version 2 (fingerprint changes)
    state.profile["age"] = 31
    state.invalidate_eligibility_if_stale()

    with pytest.raises(ValueError, match="stale"):
        MultiSchemeCoordinator.select_schemes(
            state=state,
            selected_scheme_ids=["soil_health_card_001"],
            db=db_session,
        )


# =========================================================================
# TEST 11: Independent application states
# =========================================================================
def test_test_11_independent_application_states(db_session):
    """TEST 11: Changing Application A status leaves Application B strictly unchanged."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-05-10",
        "farmer_id_status": "registered",
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    apps = MultiSchemeCoordinator.select_schemes(
        state=state,
        selected_scheme_ids=["pm_kisan_001", "ts_rythu_bharosa_001"],
        db=db_session,
    )
    app_a = next(a for a in apps if a.scheme_id == "pm_kisan_001")
    app_b = next(a for a in apps if a.scheme_id == "ts_rythu_bharosa_001")

    assert app_a.status == ApplicationStatus.SELECTED.value
    assert app_b.status == ApplicationStatus.SELECTED.value

    # Update App A to PREPARING
    MultiSchemeCoordinator.update_application_status(
        state=state,
        application_id=app_a.id,
        new_status=ApplicationStatus.PREPARING.value,
        db=db_session,
    )

    # Verify in DB and state
    db_app_a = ApplicationRepository.get_application(db_session, app_a.id)
    db_app_b = ApplicationRepository.get_application(db_session, app_b.id)

    assert db_app_a.status == ApplicationStatus.PREPARING.value
    assert db_app_b.status == ApplicationStatus.SELECTED.value  # B remains UNCHANGED!
    assert state.applications["pm_kisan_001"]["status"] == ApplicationStatus.PREPARING.value
    assert state.applications["ts_rythu_bharosa_001"]["status"] == ApplicationStatus.SELECTED.value


# =========================================================================
# TEST 12: Profile change invalidates multiple evaluations
# =========================================================================
def test_test_12_profile_change_invalidates_multiple_evaluations(db_session):
    """TEST 12: Confirmed profile change marks all active evaluations for the case as stale."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {"cultivates_land": True, "age": 30}
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    active_evals_before = SchemeEvaluationRepository.list_active_for_case(db_session, case_id)
    assert len(active_evals_before) > 0

    # User proposes and confirms profile update
    conf_id = f"CONF-{uuid.uuid4().hex[:8].upper()}"
    ConfirmationRepository.create_confirmation(
        db=db_session,
        confirmation_id=conf_id,
        case_id=case_id,
        proposed_changes=[{"field": "age", "previous": 30, "proposed": 45}],
        raw_patch={"age": 45},
    )
    state.pending_confirmation = {
        "confirmation_id": conf_id,
        "status": "PENDING",
        "changes": [{"field": "age", "previous": 30, "proposed": 45}],
        "raw_patch": {"age": 45},
    }

    _, invalidated = confirm_and_persist_profile(db_session, state)
    assert invalidated is True

    # Check database: active evaluations now empty because all marked stale
    active_evals_after = SchemeEvaluationRepository.list_active_for_case(db_session, case_id)
    assert len(active_evals_after) == 0


# =========================================================================
# TEST 13: Reevaluation
# =========================================================================
def test_test_13_reevaluation_replaces_stale_evaluations(db_session):
    """TEST 13: Reevaluation refreshes stale state and connects evaluations to new profile fingerprint."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile_v1 = {"cultivates_land": True, "age": 30}
    state = AgentState(case_id=case_id, profile=profile_v1)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)
    fp1 = state.get_profile_fingerprint()

    # Invalidate and update profile
    state.profile["age"] = 65
    fp2 = state.get_profile_fingerprint()
    assert fp1 != fp2
    state.invalidate_eligibility_if_stale()

    # Reevaluate
    new_outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)
    assert len(new_outcomes) > 0
    assert state.evaluated_profile_fingerprint == fp2

    # Active evaluations in DB now all have fp2
    active_evals = SchemeEvaluationRepository.list_active_for_case(db_session, case_id)
    assert len(active_evals) > 0
    assert all(e.profile_fingerprint == fp2 for e in active_evals)


# =========================================================================
# TEST 14: Scheme-specific missing information
# =========================================================================
def test_test_14_scheme_specific_missing_information():
    """TEST 14: Agent knows WHICH scheme requires WHICH missing field."""
    # Farmer profile with missing fields for different schemes
    profile = {
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "age": 35,
        # missing: farmer_id_status (for PM-KISAN), active_cultivation_status (for Rythu Bharosa)
    }
    state = AgentState(profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)

    missing_map = state.scheme_missing_information

    # PM-KISAN requires farmer_id_status and land_record_date
    assert "farmer_id_status" in missing_map["pm_kisan_001"]
    assert "land_record_date" in missing_map["pm_kisan_001"]

    # Rythu Bharosa requires active_cultivation_status and land_verification_source
    assert "active_cultivation_status" in missing_map["ts_rythu_bharosa_001"]
    assert "land_verification_source" in missing_map["ts_rythu_bharosa_001"]

    # Rythu Bharosa does NOT require farmer_id_status
    assert "farmer_id_status" not in missing_map["ts_rythu_bharosa_001"]


# =========================================================================
# TEST 15: Actionable preparation
# =========================================================================
def test_test_15_actionable_preparation():
    """TEST 15: Scheme with core eligibility satisfied but downstream preparation required produces ACTIONABLE_PREPARATION_REQUIRED."""
    # Profile has preparation_required set for a scheme
    profile = {
        "cultivates_land": True,
        "preparation_required": True,
    }
    state = AgentState(profile=profile)
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)

    soil_res = next(o for o in outcomes if o.scheme_id == "soil_health_card_001")
    assert soil_res.outcome == SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED.value
    assert soil_res.outcome != SchemeOutcome.NOT_ELIGIBLE.value
    assert soil_res.selectable is True


# =========================================================================
# TEST 16: Actionable selected scheme with missing eligibility-critical information
# =========================================================================
def test_test_16_actionable_selected_scheme_with_missing_critical_info(db_session):
    """TEST 16: When selected scheme has missing eligibility info, Agent asks for missing field then reevaluates."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    # Rythu Bharosa is selected, missing land_verification_source
    profile = {
        "state": "Telangana",
        "active_cultivation_status": True,
        "occupation_type": "landowner",
        # missing: land_verification_source
    }
    state = AgentState(
        case_id=case_id,
        profile=profile,
        candidate_schemes=["ts_rythu_bharosa_001"],
        selected_schemes=["ts_rythu_bharosa_001"],
        active_scheme_id="ts_rythu_bharosa_001",
    )
    state.recompute_missing_information()

    controller = AgentController(provider=DeterministicActionProvider())
    activity, _ = controller.step(state)

    # Agent should ask for the missing field
    assert activity.selected_action == ActionType.ASK_QUESTION.value
    assert activity.selected_field in ["land_verification_source", "state", "occupation_type", "active_cultivation_status"]


# =========================================================================
# TEST 17: Actionable selected scheme without missing eligibility-critical information
# =========================================================================
def test_test_17_actionable_selected_scheme_without_missing_info(db_session):
    """TEST 17: When actionable scheme has NO missing eligibility info, Agent does NOT reopen general profile questioning."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {
        "cultivates_land": True,
        "preparation_required": True,
    }
    state = AgentState(case_id=case_id, profile=profile, candidate_schemes=["soil_health_card_001"])
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)
    assert outcomes[0].outcome == SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED.value

    MultiSchemeCoordinator.select_schemes(
        state=state, selected_scheme_ids=["soil_health_card_001"], db=db_session
    )
    assert len(state.missing_information) == 0

    controller = AgentController(provider=DeterministicActionProvider())
    activity, _ = controller.step(state)

    # Agent must NOT ask questions, it finishes or marks preparing
    assert activity.selected_action != ActionType.ASK_QUESTION.value
    assert activity.selected_action in [ActionType.FINISH.value, ActionType.ESCALATE_HUMAN.value, ActionType.REQUEST_DOCUMENT.value]



# =========================================================================
# TEST 18: Transaction rollback on failure
# =========================================================================
def test_test_18_transaction_rollback_on_failure(db_session):
    """TEST 18: If one application in a multi-scheme selection fails, the entire transaction rolls back."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {"cultivates_land": True}
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)

    # soil_health_card_001 is eligible, but bad_scheme_999 is invalid
    with pytest.raises(ValueError):
        MultiSchemeCoordinator.select_schemes(
            state=state,
            selected_scheme_ids=["soil_health_card_001", "bad_scheme_999"],
            db=db_session,
        )

    # Verify zero applications were created
    apps = ApplicationRepository.list_by_case(db_session, case_id)
    assert len(apps) == 0


# =========================================================================
# TEST 19: Agent activity & application events
# =========================================================================
def test_test_19_agent_and_application_events_persisted(db_session):
    """TEST 19: Scheme evaluation and selection create structured observability events."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {"cultivates_land": True}
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)
    MultiSchemeCoordinator.select_schemes(
        state=state, selected_scheme_ids=["soil_health_card_001"], db=db_session
    )

    # Verify Agent events
    agent_events = EventRepository.list_agent_events(db_session, case_id)
    actions = [e.action for e in agent_events]
    assert "EVALUATE_SCHEMES" in actions
    assert "SELECT_SCHEMES" in actions

    # Verify Application events
    apps = ApplicationRepository.list_by_case(db_session, case_id)
    assert len(apps) == 1
    app_events = EventRepository.list_application_events(db_session, apps[0].id)
    event_types = [e.event_type for e in app_events]
    assert "APPLICATION_CREATED" in event_types
    assert "SCHEME_SELECTED" in event_types


# =========================================================================
# TEST 20: PostgreSQL persistence reload
# =========================================================================
def test_test_20_case_reload_reconstructs_multi_scheme_state(db_session):
    """TEST 20: Case reload reconstructs multi-scheme evaluated and application state correctly."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-05-10",
        "farmer_id_status": "registered",
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    state = AgentState(case_id=case_id, profile=profile)
    MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)
    MultiSchemeCoordinator.select_schemes(
        state=state,
        selected_scheme_ids=["pm_kisan_001", "ts_rythu_bharosa_001"],
        db=db_session,
    )
    persist_agent_state(db_session, state)

    # Reload from database
    reloaded_state = load_case(db_session, case_id)
    assert reloaded_state is not None
    assert len(reloaded_state.selected_schemes) == 2
    assert "pm_kisan_001" in reloaded_state.selected_schemes
    assert "ts_rythu_bharosa_001" in reloaded_state.selected_schemes
    assert "pm_kisan_001" in reloaded_state.applications
    assert "ts_rythu_bharosa_001" in reloaded_state.applications
    assert len(reloaded_state.evaluated_schemes) >= 2


# =========================================================================
# TEST 21: CRITICAL MULTI-SCHEME PARALLEL PROOF TEST (Section 35)
# =========================================================================
def test_critical_multi_scheme_parallel_proof(db_session):
    """
    CRITICAL MULTI-SCHEME PROOF TEST (Prompt Section 35):
    1. Create case.
    2. Confirm profile.
    3. Evaluate all schemes.
    4. Get at least two selectable schemes.
    5. Select Scheme A + Scheme B.
    6. Create two separate applications.
    7. Change Application A status (e.g. to PREPARING).
    8. Verify Application B is unchanged (remains SELECTED).
    9. Reload the case from PostgreSQL.
    10. Verify both application tracks remain independent.
    """
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-05-10",
        "farmer_id_status": "registered",
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    state = AgentState(case_id=case_id, profile=profile)

    # Step 3: Evaluate all schemes
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state, db=db_session)
    selectable = [o.scheme_id for o in outcomes if o.selectable]
    assert len(selectable) >= 2
    assert "pm_kisan_001" in selectable
    assert "ts_rythu_bharosa_001" in selectable

    # Step 5 & 6: Select Scheme A (PM-KISAN) + Scheme B (Rythu Bharosa)
    apps = MultiSchemeCoordinator.select_schemes(
        state=state,
        selected_scheme_ids=["pm_kisan_001", "ts_rythu_bharosa_001"],
        db=db_session,
    )
    assert len(apps) == 2

    app_a = next(a for a in apps if a.scheme_id == "pm_kisan_001")
    app_b = next(a for a in apps if a.scheme_id == "ts_rythu_bharosa_001")

    assert app_a.status == ApplicationStatus.SELECTED.value
    assert app_b.status == ApplicationStatus.SELECTED.value

    # Step 7: Change Application A status to PREPARING
    MultiSchemeCoordinator.update_application_status(
        state=state,
        application_id=app_a.id,
        new_status=ApplicationStatus.PREPARING.value,
        db=db_session,
    )

    # Step 8: Verify Application B is unchanged
    db_app_b_check = ApplicationRepository.get_application(db_session, app_b.id)
    assert db_app_b_check.status == ApplicationStatus.SELECTED.value

    # Persist state
    persist_agent_state(db_session, state)

    # Step 9: Reload case from PostgreSQL
    reloaded_state = load_case(db_session, case_id)
    assert reloaded_state is not None

    # Step 10: Verify both application tracks remain independent in reloaded state
    reloaded_apps = reloaded_state.applications
    assert reloaded_apps["pm_kisan_001"]["status"] == ApplicationStatus.PREPARING.value
    assert reloaded_apps["ts_rythu_bharosa_001"]["status"] == ApplicationStatus.SELECTED.value

    # Output representation matching specification:
    proof_trace = (
        f"\n--- PARALLEL APPLICATION PROOF ---\n"
        f"Case: {case_id}\n"
        f"Application A:\n"
        f"  scheme = pm_kisan_001\n"
        f"  status = {reloaded_apps['pm_kisan_001']['status']}\n"
        f"Application B:\n"
        f"  scheme = ts_rythu_bharosa_001\n"
        f"  status = {reloaded_apps['ts_rythu_bharosa_001']['status']}\n"
        f"Result: Application A changed to PREPARING. Application B remains SELECTED.\n"
        f"Tracks are strictly isolated and independent.\n"
        f"----------------------------------"
    )
    print(proof_trace)


# =========================================================================
# TEST 22: NO RANKING ASSERTION (Section 36)
# =========================================================================
def test_no_ranking_assertion():
    """TEST 22: Explicitly asserts that the evaluation schema and output contain zero ranking or score fields."""
    profile = {
        "gender": "male",
        "age": 35,
        "state": "Telangana",
        "occupation": "farmer",
        "cultivates_land": True,
    }
    state = AgentState(profile=profile)
    outcomes = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)

    forbidden_fields = [
        "rank",
        "ranking",
        "score",
        "best",
        "best_scheme",
        "priority",
        "priority_number",
        "recommendation_rank",
        "recommendation_order",
        "winner",
    ]

    for item in outcomes:
        dumped = item.model_dump()
        for forbidden in forbidden_fields:
            assert forbidden not in dumped, f"Forbidden ranking field '{forbidden}' found in scheme evaluation output!"


# =========================================================================
# TEST 23: FASTAPI MULTI-SCHEME ENDPOINTS
# =========================================================================
def test_fastapi_multi_scheme_endpoints(api_client, db_session):
    """TEST 23: Verifies all new FastAPI multi-scheme endpoints via HTTP client."""
    # 1. Create Case
    create_res = api_client.post("/api/cases", json={"goal": "Multi-scheme API Test"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # 2. Stage and confirm a profile
    api_client.post(
        f"/api/cases/{case_id}/messages",
        json={"message": "I am a 35 year old male farmer residing in Telangana with 3 acres land."},
    )
    api_client.post(f"/api/cases/{case_id}/profile/confirm", json={})

    # 3. Evaluate schemes
    eval_res = api_client.post(f"/api/cases/{case_id}/schemes/evaluate")
    assert eval_res.status_code == 200
    eval_json = eval_res.json()
    assert "schemes" in eval_json
    assert eval_json["total_evaluated"] >= 13

    # Check GET /api/cases/{case_id}/schemes
    get_schemes_res = api_client.get(f"/api/cases/{case_id}/schemes")
    assert get_schemes_res.status_code == 200
    assert len(get_schemes_res.json()["schemes"]) >= 13

    # Find a selectable scheme
    selectable_schemes = [
        s["scheme_id"] for s in eval_json["schemes"] if s["selectable"]
    ]
    assert len(selectable_schemes) >= 1
    selected_target = selectable_schemes[:2]

    # 4. Select schemes
    select_res = api_client.post(
        f"/api/cases/{case_id}/schemes/select",
        json={"selected_scheme_ids": selected_target},
    )
    assert select_res.status_code == 200
    apps_data = select_res.json()["applications"]
    assert len(apps_data) == len(selected_target)

    # 5. List applications
    list_res = api_client.get(f"/api/cases/{case_id}/applications")
    assert list_res.status_code == 200
    assert len(list_res.json()["applications"]) == len(selected_target)
    app1_id = apps_data[0]["application_id"]

    # 6. Get single application
    single_res = api_client.get(f"/api/cases/{case_id}/applications/{app1_id}")
    assert single_res.status_code == 200
    assert single_res.json()["application_id"] == app1_id

    # 7. Activate application
    activate_res = api_client.post(f"/api/cases/{case_id}/applications/{app1_id}/activate")
    assert activate_res.status_code == 200
    assert activate_res.json()["active_application_id"] == app1_id

    # 8. Update status
    status_res = api_client.post(
        f"/api/cases/{case_id}/applications/{app1_id}/status",
        json={"status": "PREPARING"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "PREPARING"
