"""Phase 7 bounded decoder and application-scoped recovery tests."""
import uuid
import pytest
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.session import SessionLocal
from backend.app.schemas.rejection import RejectionEvidenceRequest
from backend.app.services.rejection_recovery_service import RejectionRecoveryService

@pytest.fixture()
def recovery_case():
 db=SessionLocal(); case=f"CASE-R7-{uuid.uuid4().hex[:8]}"
 try:
  CaseRepository.create_case(db,case_id=case); a=ApplicationRepository.create_application(db,case,"pm_kisan_001",status="READY_FOR_HANDOFF"); b=ApplicationRepository.create_application(db,case,"soil_health_card_001",status="READY_FOR_HANDOFF")
  yield db,case,a,b
 finally: db.rollback(); db.close()

def test_01_claim_requests_official_evidence(recovery_case):
 db,case,a,_=recovery_case; state=RejectionRecoveryService().claim(db,case,a.id)
 assert state.recovery_status=="REJECTION_EVIDENCE_REQUIRED" and state.next_action=="REQUEST_REJECTION_EVIDENCE"

@pytest.mark.parametrize("text,category",[
 ("Official notice: Aadhaar bank NPCI mapping issue", "AADHAAR_BANK_NPCI_MAPPING"),
 ("Official notice: beneficiary bank account is inactive", "INVALID_INACTIVE_BANK_ACCOUNT"),
 ("Official notice: invalid IFSC", "INVALID_BANK_OR_IFSC"),
 ("Official notice: beneficiary land record mismatch", "BENEFICIARY_LAND_RECORD_MISMATCH"),
 ("Official notice: eligibility verification failed", "ELIGIBILITY_OR_VERIFICATION_ISSUE"),
])
def test_02_to_06_supported_categories_are_bounded(recovery_case,text,category):
 db,case,a,_=recovery_case; service=RejectionRecoveryService(); service.claim(db,case,a.id)
 event=db.query(__import__('backend.app.db.models.rejection',fromlist=['RejectionEvent']).RejectionEvent).filter_by(application_id=a.id).first()
 service.evidence(db,case,a.id,event.id,RejectionEvidenceRequest(source_type="SMS",raw_text=text)); result=service.decode(db,case,a.id,event.id)
 assert result.status=="SUPPORTED" and result.categories==[category]

def test_07_multiple_and_unsupported_are_not_guessed(recovery_case):
 db,case,a,_=recovery_case; s=RejectionRecoveryService(); s.claim(db,case,a.id); event=db.query(__import__('backend.app.db.models.rejection',fromlist=['RejectionEvent']).RejectionEvent).filter_by(application_id=a.id).first()
 s.evidence(db,case,a.id,event.id,RejectionEvidenceRequest(source_type="SMS",raw_text="NPCI mapping issue and account inactive")); assert len(s.decode(db,case,a.id,event.id).categories)==2
 s.claim(db,case,a.id); second=db.query(__import__('backend.app.db.models.rejection',fromlist=['RejectionEvent']).RejectionEvent).order_by(__import__('backend.app.db.models.rejection',fromlist=['RejectionEvent']).RejectionEvent.received_at.desc()).first(); s.evidence(db,case,a.id,second.id,RejectionEvidenceRequest(source_type="CODE",rejection_code="X7A9")); result=s.decode(db,case,a.id,second.id); assert result.status=="UNSUPPORTED" and not result.categories and result.requires_human_verification

def test_08_application_isolation_and_ownership(recovery_case):
 db,case,a,b=recovery_case; s=RejectionRecoveryService(); s.claim(db,case,a.id)
 event=db.query(__import__('backend.app.db.models.rejection',fromlist=['RejectionEvent']).RejectionEvent).filter_by(application_id=a.id).first()
 with pytest.raises(ValueError): s.evidence(db,case,b.id,event.id,RejectionEvidenceRequest(source_type="SMS",raw_text="invalid IFSC"))
 assert ApplicationRepository.get_application(db,b.id).status=="READY_FOR_HANDOFF"

def test_09_fixed_claim_does_not_resolve_without_evidence(recovery_case):
 db,case,a,_=recovery_case; s=RejectionRecoveryService(); s.claim(db,case,a.id); event=db.query(__import__('backend.app.db.models.rejection',fromlist=['RejectionEvent']).RejectionEvent).filter_by(application_id=a.id).first(); s.evidence(db,case,a.id,event.id,RejectionEvidenceRequest(source_type="SMS",raw_text="invalid IFSC")); s.decode(db,case,a.id,event.id)
 with pytest.raises(ValueError): s.recovery_action(db,case,a.id,event.id,"RESOLVE_REJECTION")
 assert s.recovery_action(db,case,a.id,event.id,"RESOLVE_REJECTION","bank confirmation received").recovery_status=="RECOVERY_COMPLETED"

def test_10_duplicate_evidence_and_reload_are_stable(recovery_case):
 db,case,a,_=recovery_case; s=RejectionRecoveryService(); s.claim(db,case,a.id); event=db.query(__import__('backend.app.db.models.rejection',fromlist=['RejectionEvent']).RejectionEvent).filter_by(application_id=a.id).first(); p=RejectionEvidenceRequest(source_type="SMS",raw_text="invalid bank account")
 assert s.evidence(db,case,a.id,event.id,p).id==s.evidence(db,case,a.id,event.id,p).id
 db.expire_all(); assert s.state(db,case,a.id).application_id==a.id


def test_11_agent_controller_observes_rejection_and_orchestrates_recovery(recovery_case):
    db, case, a, b = recovery_case
    from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
    from backend.app.agent.dispatcher import ActionDispatcher
    from backend.app.agent.policies import DeterministicPolicy
    from backend.app.agent.state import AgentState

    # Set up AgentState with Application A in REJECTION_EVIDENCE_REQUIRED
    state = AgentState(
        case_id=case,
        applications={
            a.id: {"id": a.id, "scheme_id": "pm_kisan_001", "status": "REJECTION_EVIDENCE_REQUIRED"},
            b.id: {"id": b.id, "scheme_id": "soil_health_card_001", "status": "READY_FOR_HANDOFF"},
        },
        active_application_id=a.id,
        stage="REJECTION_EVIDENCE_REQUIRED",
    )

    policy = DeterministicPolicy()
    dispatcher = ActionDispatcher(db=db)

    # 1. Agent observes state -> Proposes REQUEST_REJECTION_EVIDENCE (never guesses from user statement)
    action = policy.select_action(state)
    assert action is not None
    assert action.action == ActionType.REQUEST_REJECTION_EVIDENCE
    assert action.field == a.id

    # 2. Dispatch action
    success, res, err = dispatcher.dispatch(action, state)
    assert success is True
    assert res.get("status") == "REJECTION_EVIDENCE_REQUIRED"

    # 3. Official evidence submitted & decoded
    s = RejectionRecoveryService()
    s.claim(db, case, a.id)
    event = db.query(__import__('backend.app.db.models.rejection', fromlist=['RejectionEvent']).RejectionEvent).filter_by(application_id=a.id).first()
    s.evidence(db, case, a.id, event.id, RejectionEvidenceRequest(source_type="SMS", raw_text="Official notice: beneficiary bank account is inactive"))
    decode_result = s.decode(db, case, a.id, event.id)
    assert decode_result.status == "SUPPORTED"
    assert "INVALID_INACTIVE_BANK_ACCOUNT" in decode_result.categories

    # 4. Agent observes RECOVERY_REQUIRED state -> Proposes REQUEST_RECOVERY_DOCUMENT
    state.applications[a.id]["status"] = "RECOVERY_REQUIRED"
    state.applications[a.id]["rejection_event_id"] = event.id
    rec_action = policy.select_action(state)
    assert rec_action is not None
    assert rec_action.action == ActionType.REQUEST_RECOVERY_DOCUMENT

    # 5. Dispatch recovery document request
    rec_success, rec_res, _ = dispatcher.dispatch(rec_action, state)
    assert rec_success is True
    assert rec_res.get("status") == "RECOVERY_IN_PROGRESS"

    # 6. Resolve rejection with evidence note
    resolve_action = AgentAction(
        action=ActionType.RESOLVE_REJECTION,
        field=a.id,
        arguments={"application_id": a.id, "rejection_event_id": event.id, "recovery_evidence": "Updated passbook re-verified at bank"},
        reason_code=ReasonCode.RECOVERY_REQUIRED,
    )
    res_success, res_val, _ = dispatcher.dispatch(resolve_action, state)
    assert res_success is True
    assert res_val.get("status") == "RECOVERY_COMPLETED"

    # 7. Strict Application Isolation: Application B remains in READY_FOR_HANDOFF throughout
    assert state.applications[b.id]["status"] == "READY_FOR_HANDOFF"

