"""
PostgreSQL Persistence Integration Tests
========================================
Validates:
- TEST DB 1: Connect successfully
- TEST DB 2: Create case
- TEST DB 3: Persist confirmed profile
- TEST DB 4: Read profile back
- TEST DB 5: Create pending confirmation
- TEST DB 6: Confirm profile transactionally
- TEST DB 7: Reject pending profile and ensure confirmed profile unchanged
- TEST DB 8: Create application for a scheme
- TEST DB 9: Persist scheme evaluation with profile fingerprint
- TEST DB 10: Change profile and verify old evaluation is stale
- TEST DB 11: Persist agent event
- TEST DB 12: Foreign keys prevent invalid records
- TEST DB 13: Unique(case_id, scheme_id) constraint works
- TEST DB 14: Rollback works on failed transaction
- TEST DB 15: Case reload reconstructs AgentState correctly
- Concurrency & FastAPI health endpoints
"""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.testclient import TestClient

from backend.app.agent.state import AgentState
from backend.app.db.models.case import Case
from backend.app.db.models.profile import Profile
from backend.app.db.models.application import Application
from backend.app.db.models.scheme_evaluation import SchemeEvaluation
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
from backend.app.db.session import SessionLocal, check_db_connection, engine
from backend.app.main import app


@pytest.fixture(scope="function")
def db_session():
    """Provides a fresh transactional session for each test and rolls back changes."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_db_1_connect_successfully():
    """TEST DB 1: Connect successfully to PostgreSQL."""
    assert check_db_connection() is True
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1;")).scalar()
        assert res == 1


def test_db_2_create_case(db_session):
    """TEST DB 2: Create case."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    case = CaseRepository.create_case(
        db=db_session,
        case_id=case_id,
        goal="Assist farmer with central schemes",
        candidate_schemes=["pm_kisan_001"],
    )
    assert case.id == case_id
    assert case.status == "ACTIVE"
    assert case.stage == "INTAKE"


def test_db_3_persist_confirmed_profile(db_session):
    """TEST DB 3: Persist confirmed profile."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    profile = ProfileRepository.upsert_profile(
        db=db_session,
        case_id=case_id,
        profile_data={"age": 42, "state": "Telangana", "occupation": "farmer"},
        fingerprint="fp12345678",
        confirmed=True,
    )
    assert profile.case_id == case_id
    assert profile.profile_data["age"] == 42
    assert profile.version == 1


def test_db_4_read_profile_back(db_session):
    """TEST DB 4: Read profile back."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)
    ProfileRepository.upsert_profile(
        db=db_session,
        case_id=case_id,
        profile_data={"age": 42, "state": "Telangana"},
        fingerprint="fp12345678",
    )

    loaded = ProfileRepository.get_by_case_id(db_session, case_id)
    assert loaded is not None
    assert loaded.profile_data["state"] == "Telangana"
    assert loaded.confirmed is True


def test_db_5_create_pending_confirmation(db_session):
    """TEST DB 5: Create pending confirmation."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)
    conf_id = f"CONF-{uuid.uuid4().hex[:8].upper()}"

    conf = ConfirmationRepository.create_confirmation(
        db=db_session,
        confirmation_id=conf_id,
        case_id=case_id,
        proposed_changes=[{"field": "land_holding_acres", "previous": 3, "proposed": 5}],
    )
    assert conf.id == conf_id
    assert conf.status == "PENDING"
    assert len(conf.proposed_changes) == 1


def test_db_6_confirm_profile_transactionally(db_session):
    """TEST DB 6: Confirm profile transactionally."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id, candidate_schemes=["pm_kisan_001"])
    conf_id = f"CONF-{uuid.uuid4().hex[:8].upper()}"

    ConfirmationRepository.create_confirmation(
        db=db_session,
        confirmation_id=conf_id,
        case_id=case_id,
        proposed_changes=[{"field": "state", "previous": None, "proposed": "Telangana"}],
        raw_patch={"state": "Telangana"},
    )

    state = AgentState(
        case_id=case_id,
        candidate_schemes=["pm_kisan_001"],
        pending_confirmation={
            "confirmation_id": conf_id,
            "status": "PENDING",
            "confirmation_required": True,
            "changes": [{"field": "state", "previous": None, "proposed": "Telangana"}],
            "raw_patch": {"state": "Telangana"},
        },
    )

    updated_profile, invalidated = confirm_and_persist_profile(db_session, state)
    assert updated_profile["state"] == "Telangana"

    # Verify confirmation status in DB is CONFIRMED
    db_conf = ConfirmationRepository.get_confirmation(db_session, conf_id)
    assert db_conf.status == "CONFIRMED"

    # Verify profile in DB
    db_profile = ProfileRepository.get_by_case_id(db_session, case_id)
    assert db_profile.profile_data["state"] == "Telangana"


def test_db_7_reject_pending_profile_ensures_profile_unchanged(db_session):
    """TEST DB 7: Reject pending profile and ensure confirmed profile unchanged."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)
    ProfileRepository.upsert_profile(
        db=db_session,
        case_id=case_id,
        profile_data={"land_holding_acres": 3.0},
        fingerprint="fp_orig",
    )
    conf_id = f"CONF-{uuid.uuid4().hex[:8].upper()}"
    ConfirmationRepository.create_confirmation(
        db=db_session,
        confirmation_id=conf_id,
        case_id=case_id,
        proposed_changes=[{"field": "land_holding_acres", "previous": 3.0, "proposed": 5.0}],
        raw_patch={"land_holding_acres": 5.0},
    )

    state = AgentState(
        case_id=case_id,
        profile={"land_holding_acres": 3.0},
        pending_confirmation={
            "confirmation_id": conf_id,
            "status": "PENDING",
            "changes": [{"field": "land_holding_acres", "previous": 3.0, "proposed": 5.0}],
            "raw_patch": {"land_holding_acres": 5.0},
        },
    )

    rejected_profile = reject_and_persist_profile(db_session, state)
    assert rejected_profile["land_holding_acres"] == 3.0

    # Profile in DB remains 3.0
    db_profile = ProfileRepository.get_by_case_id(db_session, case_id)
    assert db_profile.profile_data["land_holding_acres"] == 3.0

    # Confirmation in DB marked REJECTED
    db_conf = ConfirmationRepository.get_confirmation(db_session, conf_id)
    assert db_conf.status == "REJECTED"


def test_db_8_create_application_for_scheme(db_session):
    """TEST DB 8: Create application for a scheme."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    app_rec = ApplicationRepository.create_application(
        db=db_session, case_id=case_id, scheme_id="pm_kisan_001"
    )
    assert app_rec.case_id == case_id
    assert app_rec.scheme_id == "pm_kisan_001"
    assert app_rec.status == "ELIGIBLE_PENDING"


def test_db_9_persist_scheme_evaluation_with_fingerprint(db_session):
    """TEST DB 9: Persist scheme evaluation with profile fingerprint."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    eval_rec = SchemeEvaluationRepository.record_evaluation(
        db=db_session,
        case_id=case_id,
        scheme_id="pm_kisan_001",
        profile_fingerprint="fp_abc123",
        outcome="FULLY_ELIGIBLE",
        reasons={"summary": "All 5 criteria passed"},
    )
    assert eval_rec.profile_fingerprint == "fp_abc123"
    assert eval_rec.is_stale is False
    assert eval_rec.outcome == "FULLY_ELIGIBLE"


def test_db_10_change_profile_verifies_old_evaluation_is_stale(db_session):
    """TEST DB 10: Change profile and verify old evaluation is marked stale."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id, candidate_schemes=["pm_kisan_001"])
    ProfileRepository.upsert_profile(
        db=db_session,
        case_id=case_id,
        profile_data={"annual_income_inr": 200000.0},
        fingerprint="fp_v1",
    )
    SchemeEvaluationRepository.record_evaluation(
        db=db_session,
        case_id=case_id,
        scheme_id="pm_kisan_001",
        profile_fingerprint="fp_v1",
        outcome="FULLY_ELIGIBLE",
        reasons={"summary": "Eligible"},
    )

    conf_id = f"CONF-{uuid.uuid4().hex[:8].upper()}"
    ConfirmationRepository.create_confirmation(
        db=db_session,
        confirmation_id=conf_id,
        case_id=case_id,
        proposed_changes=[{"field": "annual_income_inr", "previous": 200000.0, "proposed": 1000000.0}],
        raw_patch={"annual_income_inr": 1000000.0},
    )

    state = AgentState(
        case_id=case_id,
        profile={"annual_income_inr": 200000.0},
        eligible_schemes=["pm_kisan_001"],
        evaluated_profile_fingerprint="fp_v1",
        candidate_schemes=["pm_kisan_001"],
        pending_confirmation={
            "confirmation_id": conf_id,
            "status": "PENDING",
            "changes": [{"field": "annual_income_inr", "previous": 200000.0, "proposed": 1000000.0}],
            "raw_patch": {"annual_income_inr": 1000000.0},
        },
    )

    _, invalidated = confirm_and_persist_profile(db_session, state)
    assert invalidated is True

    # In database, the evaluation must now be marked is_stale = True
    evals = SchemeEvaluationRepository.list_for_case(db_session, case_id, include_stale=True)
    assert len(evals) == 1
    assert evals[0].is_stale is True


def test_db_11_persist_agent_event(db_session):
    """TEST DB 11: Persist agent event."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    event = EventRepository.record_agent_event(
        db=db_session,
        case_id=case_id,
        iteration=1,
        stage="MISSING_INFO_COLLECTION",
        action="ASK_QUESTION",
        reason_code="MAX_EXPECTED_NARROWING",
        state_fingerprint="sf_1234",
        selected_field="annual_income_inr",
        event_data={"question": "What is your income?"},
    )
    assert event.action == "ASK_QUESTION"

    events = EventRepository.list_agent_events(db_session, case_id)
    assert len(events) >= 1
    assert events[-1].action == "ASK_QUESTION"


def test_db_12_foreign_keys_prevent_invalid_records(db_session):
    """TEST DB 12: Foreign keys prevent invalid records."""
    non_existent_case = "CASE-DOES-NOT-EXIST"
    invalid_profile = Profile(
        case_id=non_existent_case,
        profile_data={"age": 30},
        profile_fingerprint="fp_bad",
    )
    db_session.add(invalid_profile)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_13_unique_case_scheme_application(db_session):
    """TEST DB 13: Unique(case_id, scheme_id) constraint works."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    app1 = Application(case_id=case_id, scheme_id="pm_kisan_001")
    app2 = Application(case_id=case_id, scheme_id="pm_kisan_001")
    db_session.add(app1)
    db_session.commit()

    db_session.add(app2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_14_rollback_on_failed_transaction(db_session):
    """TEST DB 14: Rollback works on failed transaction."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)

    try:
        # Intentionally cause an error in a transaction block
        invalid_app = Application(case_id="INVALID-CASE-ID", scheme_id="foo")
        db_session.add(invalid_app)
        db_session.commit()
    except Exception:
        db_session.rollback()

    # Verify session is still healthy and database is uncorrupted
    case = CaseRepository.get_case(db_session, case_id)
    assert case is not None


def test_db_15_case_reload_reconstructs_agent_state(db_session):
    """TEST DB 15: Case reload reconstructs AgentState correctly."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(
        db=db_session,
        case_id=case_id,
        candidate_schemes=["pm_kisan_001"],
        goal="Reconstruct AgentState Test",
    )
    ProfileRepository.upsert_profile(
        db=db_session,
        case_id=case_id,
        profile_data={"age": 42, "state": "Telangana"},
        fingerprint="fp_reconstruct",
    )
    ApplicationRepository.create_application(db=db_session, case_id=case_id, scheme_id="pm_kisan_001")
    EventRepository.record_agent_event(
        db=db_session,
        case_id=case_id,
        iteration=1,
        stage="INTAKE",
        action="ASK_QUESTION",
        reason_code="MAX_EXPECTED_NARROWING",
        state_fingerprint="sf_rec",
        selected_field="age",
    )

    reconstructed_state = load_case(db_session, case_id)
    assert reconstructed_state is not None
    assert reconstructed_state.case_id == case_id
    assert reconstructed_state.profile["state"] == "Telangana"
    assert reconstructed_state.profile["age"] == 42
    assert "pm_kisan_001" in reconstructed_state.candidate_schemes
    assert "age" in reconstructed_state.asked_questions


def test_db_16_optimistic_concurrency_conflict(db_session):
    """TEST DB 16: Optimistic versioning detects conflicting concurrent updates."""
    case_id = f"CASE-TEST-{uuid.uuid4().hex[:8].upper()}"
    CaseRepository.create_case(db=db_session, case_id=case_id)
    p = ProfileRepository.upsert_profile(
        db=db_session,
        case_id=case_id,
        profile_data={"land_holding_acres": 3.0},
        fingerprint="fp1",
    )
    assert p.version == 1

    # Update with expected_version=1 -> succeeds and becomes version 2
    ProfileRepository.upsert_profile(
        db=db_session,
        case_id=case_id,
        profile_data={"land_holding_acres": 4.0},
        fingerprint="fp2",
        expected_version=1,
    )

    # Stale request attempting update with expected_version=1 must fail
    with pytest.raises(ProfileConcurrencyError):
        ProfileRepository.upsert_profile(
            db=db_session,
            case_id=case_id,
            profile_data={"land_holding_acres": 5.0},
            fingerprint="fp3",
            expected_version=1,
        )


def test_db_17_fastapi_endpoints():
    """TEST DB 17: Test FastAPI endpoints for health, case creation, and message intake."""
    client = TestClient(app)

    # 1. Health check
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok", "database": "ok"}

    health_db_resp = client.get("/health/db")
    assert health_db_resp.status_code == 200

    # 2. Create case
    case_resp = client.post(
        "/api/cases", json={"goal": "Test API case", "candidate_schemes": ["pm_kisan_001"]}
    )
    assert case_resp.status_code == 201
    case_data = case_resp.json()
    case_id = case_data["case_id"]

    # 3. Get case
    get_resp = client.get(f"/api/cases/{case_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["case_id"] == case_id

    # 4. Post message to case
    msg_resp = client.post(
        f"/api/cases/{case_id}/messages",
        json={"message": "I am a farmer from Telangana and I have 3 acres."},
    )
    assert msg_resp.status_code == 200
    msg_data = msg_resp.json()
    assert msg_data["confirmation_required"] is True

    # 5. Confirm profile
    confirm_resp = client.post(f"/api/cases/{case_id}/profile/confirm", json={})
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "CONFIRMED"
    assert confirm_resp.json()["confirmed_profile"]["state"] == "Telangana"

    # 6. Verify activity log
    act_resp = client.get(f"/api/cases/{case_id}/activity")
    assert act_resp.status_code == 200
    assert len(act_resp.json()["events"]) >= 1
