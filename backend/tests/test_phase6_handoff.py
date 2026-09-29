"""Phase 6 pre-submission package tests: preparation only, never official submission."""

import uuid
from pathlib import Path

import pytest
from pypdf import PdfReader

from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.dispatcher import ActionDispatcher
from backend.app.agent.state import AgentState
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.repositories.document_repository import DocumentDiscrepancyRepository, DocumentRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.handoff_package_repository import HandoffPackageRepository
from backend.app.db.repositories.profile_repository import ProfileRepository
from backend.app.db.services.state_persistence import load_case
from backend.app.db.session import SessionLocal
from backend.app.services.handoff_service import DISCLAIMER, HandoffService, PreSubmissionBlockedError


def ready_state(case_id="CASE-P6", app_id="APP-P6", scheme_id="soil_health_card_001"):
    profile = {"name": "Asha Farmer", "age": 35, "state": "Telangana", "district": "Hyderabad", "occupation": "farmer", "land_holding_acres": 2}
    state = AgentState(case_id=case_id, profile=profile, applications={scheme_id: {"id": app_id, "status": "READY_FOR_HANDOFF"}}, active_scheme_id=scheme_id, active_application_id=app_id, stage="READY_FOR_HANDOFF")
    state.scheme_evaluations = {scheme_id: {"outcome": "FULLY_ELIGIBLE", "profile_fingerprint": state.get_profile_fingerprint(), "summary": "Configured rule conditions satisfied"}}
    state.documents = [{"id": "DOC-LAND", "application_id": app_id, "document_type": "land_record", "status": "VERIFIED", "verification_status": "VERIFIED", "original_filename": "land-record.pdf", "extracted_data": {}}]
    return state


def pdf_text(package_id, filename):
    path = Path("backend/storage/handoff_packages") / package_id / filename
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def test_01_verification_succeeds_for_ready_application():
    result = HandoffService().verify(ready_state(), "APP-P6")
    assert result.passed and result.readiness_status == "READY_FOR_HANDOFF"


@pytest.mark.parametrize(("mutator", "expected"), [
    (lambda s: s.scheme_evaluations.update({"soil_health_card_001": {"outcome": "FULLY_ELIGIBLE", "profile_fingerprint": "stale"}}), "STALE_ELIGIBILITY"),
    (lambda s: setattr(s, "pending_confirmation", {"status": "PENDING"}), "PENDING_PROFILE_CONFIRMATION"),
    (lambda s: s.documents[0].update({"status": "REQUIRED", "verification_status": "PENDING"}), "MISSING_REQUIRED_DOCUMENT"),
])
def test_02_to_04_verification_blocks_current_state_failures(mutator, expected):
    state = ready_state(); mutator(state)
    assert expected in HandoffService().verify(state, "APP-P6").blocking_items


def test_05_verification_blocks_unresolved_discrepancy():
    state = ready_state(); state.documents[0]["discrepancies"] = [{"discrepancy_id": "DISC-1", "document_id": "DOC-LAND", "field_name": "land_holding_acres", "status": "OPEN"}]
    assert "UNRESOLVED_DISCREPANCY" in HandoffService().verify(state, "APP-P6").blocking_items


def test_06_to_13_reference_and_dossier_are_safe_and_printable():
    package = HandoffService().generate_handoff_package(ready_state(), "APP-P6")
    reference = pdf_text(package.package_id, "reference-sheet.pdf")
    dossier = pdf_text(package.package_id, "dossier.pdf")
    assert "NOT AN OFFICIAL GOVERNMENT FORM" in reference
    assert DISCLAIMER in dossier
    assert package.application_id in dossier and "Soil Health Card Scheme" in dossier
    assert "READY_FOR_HANDOFF" in dossier and "Required document checklist" in dossier
    assert "CSC/VLE handoff checklist" in dossier
    assert "Government has approved" not in dossier and "SUCCESSFULLY_APPLIED" not in dossier
    assert "Official Government Application / Reference Number: ________________________" in dossier
    assert "Asha Farmer" in reference and "pending Gemini" not in dossier
    assert len(PdfReader(str(Path("backend/storage/handoff_packages") / package.package_id / "dossier.pdf")).pages) > 0


def test_14_application_packages_are_isolated():
    a = ready_state("CASE-ISO", "APP-A")
    b = ready_state("CASE-ISO", "APP-B", "pm_kisan_001")
    b.documents = [
        {"id": "DOC-AAD", "application_id": "APP-B", "document_type": "aadhaar", "status": "VERIFIED", "verification_status": "VERIFIED"},
        {"id": "DOC-LAND-B", "application_id": "APP-B", "document_type": "land_record", "status": "VERIFIED", "verification_status": "VERIFIED"},
        {"id": "DOC-BANK", "application_id": "APP-B", "document_type": "bank_passbook", "status": "VERIFIED", "verification_status": "VERIFIED"},
        {"id": "DOC-FARM", "application_id": "APP-B", "document_type": "farmer_id", "status": "VERIFIED", "verification_status": "VERIFIED"},
    ]
    b.scheme_evaluations = {"pm_kisan_001": {"outcome": "FULLY_ELIGIBLE", "profile_fingerprint": b.get_profile_fingerprint(), "summary": "current"}}
    pa, pb = HandoffService().generate_handoff_package(a, "APP-A"), HandoffService().generate_handoff_package(b, "APP-B")
    assert "DOC-LAND-B" not in pdf_text(pa.package_id, "dossier.pdf")
    assert "DOC-LAND-B" in pdf_text(pb.package_id, "dossier.pdf")


def test_15_profile_change_makes_snapshot_stale():
    state = ready_state(); HandoffService().generate_handoff_package(state, "APP-P6")
    state.profile["land_holding_acres"] = 9
    assert "STALE_ELIGIBILITY" in HandoffService().verify(state, "APP-P6").blocking_items


def test_16_agent_blocks_generation_when_not_ready():
    state = ready_state(); state.documents[0].update({"status": "REQUIRED", "verification_status": "PENDING"})
    action = AgentAction(action=ActionType.GENERATE_HANDOFF_PACKAGE, field="APP-P6", reason_code=ReasonCode.HANDOFF_PACKAGE_READY)
    ok, result, error = ActionDispatcher().dispatch(action, state)
    assert ok and error is None and result["status"] == "BLOCKED"


def test_17_agent_generates_only_when_ready():
    state = ready_state()
    action = AgentAction(action=ActionType.GENERATE_HANDOFF_PACKAGE, field="APP-P6", reason_code=ReasonCode.HANDOFF_PACKAGE_READY)
    ok, result, error = ActionDispatcher().dispatch(action, state)
    assert ok and error is None and result["status"] == "GENERATED"


def test_18_to_20_postgres_metadata_persists_and_invalidates():
    db = SessionLocal(); case_id = f"CASE-P6-{uuid.uuid4().hex[:10]}"
    try:
        CaseRepository.create_case(db, case_id=case_id)
        profile_data = ready_state().profile
        temp = AgentState(profile=profile_data); fp = temp.get_profile_fingerprint()
        ProfileRepository.upsert_profile(db, case_id, profile_data, fp, confirmed=True)
        app = ApplicationRepository.create_application(db, case_id, "soil_health_card_001", status="READY_FOR_HANDOFF")
        evaluation = SchemeEvaluationRepository.record_evaluation(db, case_id, "soil_health_card_001", fp, "FULLY_ELIGIBLE", {"land": "satisfied"}, application_id=app.id)
        doc = DocumentRepository.create_document(db, app.id, "land_record", original_filename="record.pdf", status="VERIFIED", extraction_status="SUCCESS", verification_status="VERIFIED", extracted_data={})
        db.commit()
        state = load_case(db, case_id); service = HandoffService(); package = service.generate_handoff_package(state, app.id, db)
        stored = HandoffPackageRepository.get(db, package.package_id)
        assert stored and stored.status == "GENERATED" and stored.application_id == app.id
        reloaded = service.get_current_package(load_case(db, case_id), app.id, db)
        assert reloaded and reloaded.package_id == package.package_id
        DocumentRepository.update_document(db, doc.id, status="UNREADABLE", verification_status="UNREADABLE"); db.commit()
        assert service.get_current_package(load_case(db, case_id), app.id, db) is None
        assert HandoffPackageRepository.get(db, package.package_id).status == "INVALIDATED"
    finally:
        db.rollback(); db.close()


@pytest.mark.parametrize("required_text", [
    "YOJANA SAATHI", "PRE-SUBMISSION DOSSIER", "Yojana Saathi Application ID",
    "Yojana Saathi deterministic eligibility assessment", "Required document checklist",
    "Uploaded / verified document index", "CSC/VLE handoff checklist",
])
def test_21_to_27_dossier_has_required_preparation_content(required_text):
    package = HandoffService().generate_handoff_package(ready_state(), "APP-P6")
    assert required_text in pdf_text(package.package_id, "dossier.pdf")


@pytest.mark.parametrize(("mutation", "blocking_code"), [
    (lambda s: setattr(s, "profile", {}), "PROFILE_NOT_CONFIRMED"),
    (lambda s: s.applications["soil_health_card_001"].update({"status": "DRAFT"}), "APPLICATION_NOT_SELECTED"),
    (lambda s: setattr(s, "scheme_evaluations", {}), "NO_CURRENT_EVALUATION"),
    (lambda s: s.documents[0].update({"status": "UNREADABLE", "verification_status": "UNREADABLE"}), "UNREADABLE_DOCUMENT"),
    (lambda s: s.scheme_evaluations["soil_health_card_001"].update({"outcome": "ACTIONABLE_PREPARATION_REQUIRED"}), "ELIGIBILITY_NOT_FULLY_ELIGIBLE"),
    (lambda s: s.documents.__setitem__(slice(None), []), "READINESS_NOT_READY"),
    (lambda s: s.documents.__setitem__(slice(None), []), "MISSING_REQUIRED_DOCUMENT"),
    (lambda s: s.applications.clear(), "APPLICATION_NOT_FOUND"),
])
def test_28_to_35_verification_has_deterministic_blocking_codes(mutation, blocking_code):
    state = ready_state(); mutation(state)
    assert blocking_code in HandoffService().verify(state, "APP-P6").blocking_items


@pytest.mark.parametrize("artifact, expected", [
    ("reference-sheet.pdf", "APPLICATION REFERENCE SHEET"),
    ("reference-sheet.pdf", "Prepared by Yojana Saathi for pre-submission verification and CSC/VLE assistance."),
    ("dossier.pdf", "Official Government Application / Reference Number: ________________________"),
    ("dossier.pdf", "Yojana Saathi does not submit applications"),
])
def test_36_to_39_artifacts_have_non_official_boundary_text(artifact, expected):
    package = HandoffService().generate_handoff_package(ready_state(), "APP-P6")
    assert expected in pdf_text(package.package_id, artifact)
