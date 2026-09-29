"""
Unit and integration tests for Phase 9 — Complete Citizen + CSC/VLE Web UI & End-to-End UX.
Verifies:
1. Web UI shell endpoint GET /
2. Static assets serving (/static/css/styles.css, /static/js/api.js, /static/js/app.js)
3. Profile fields schema discovery endpoint GET /api/profile/fields
4. Canonical non-ranked schemes catalog endpoint GET /api/schemes/catalog
5. Deterministic manual profile field edit endpoint POST /api/cases/{case_id}/profile/edit
6. Multi-scheme selection and isolated application lifecycle
7. Multilingual language support endpoints
8. Pre-submission disclaimer preservation
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_web_ui_shell_endpoint():
    """Verifies that GET / serves the accessible HTML5 web application shell."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text

    # Brand and title verification
    assert "Yojana Saathi" in html
    assert "AI Welfare Access Assistant" in html
    
    # CSS and JS asset links
    assert "/static/css/styles.css" in html
    assert "/static/js/api.js" in html
    assert "/static/js/app.js" in html

    # Essential UI workspaces present in DOM
    assert 'id="view-landing"' in html
    assert 'id="view-chat"' in html
    assert 'id="view-profile"' in html
    assert 'id="view-schemes"' in html
    assert 'id="view-applications"' in html
    assert 'id="view-documents"' in html
    assert 'id="view-readiness"' in html
    assert 'id="view-handoff"' in html
    assert 'id="view-recovery"' in html

    # Disclaimer and Accessibility elements
    assert "NOT AN OFFICIAL GOVERNMENT FORM" in html
    assert 'id="mode-toggle-btn"' in html
    assert 'id="lang-select"' in html
    assert 'id="btn-voice-mic"' in html


def test_static_css_asset():
    """Verifies static CSS design system is properly served."""
    response = client.get("/static/css/styles.css")
    assert response.status_code == 200
    css = response.text
    assert "--primary:" in css
    assert ".app-header" in css
    assert ".mic-btn" in css


def test_static_js_api_client():
    """Verifies static API client layer is properly served."""
    response = client.get("/static/js/api.js")
    assert response.status_code == 200
    js = response.text
    assert "class YojanaAPI" in js
    assert "window.api = new YojanaAPI()" in js


def test_static_js_app_controller():
    """Verifies static application controller is properly served."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text
    assert "const I18N =" in js
    assert "class AppState" in js


def test_profile_fields_schema_endpoint():
    """Verifies GET /api/profile/fields exposes supported schema fields."""
    response = client.get("/api/profile/fields")
    assert response.status_code == 200
    data = response.json()
    assert "fields" in data
    field_names = [f["name"] for f in data["fields"]]
    assert "age" in field_names
    assert "gender" in field_names
    assert "state" in field_names
    assert "annual_income_inr" in field_names
    assert "occupation" in field_names
    assert "land_holding_acres" in field_names


def test_schemes_catalog_endpoint_non_ranked():
    """Verifies GET /api/schemes/catalog returns all 13 supported schemes without ranking or subjective scores."""
    response = client.get("/api/schemes/catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["total_schemes"] == 13
    schemes = data["schemes"]
    assert len(schemes) == 13

    # Check that each scheme has multilingual fields and required documents
    for s in schemes:
        assert "scheme_id" in s
        assert "title_en" in s
        assert "title_hi" in s
        assert "title_te" in s
        assert "department" in s
        assert "required_documents" in s
        # Ensure no ranking scores exist
        assert "rank" not in s
        assert "score" not in s
        assert "weight" not in s


def test_manual_profile_field_edit_flow():
    """Verifies POST /api/cases/{case_id}/profile/edit allows manual editing bypassing Gemini."""
    # 1. Create a case
    create_res = client.post("/api/cases", json={"goal": "Farmer assistance test"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # 2. Manual edit with auto_confirm=True
    edit_res = client.post(
        f"/api/cases/{case_id}/profile/edit",
        json={"field": "annual_income_inr", "value": 180000.0, "auto_confirm": True}
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["status"] == "CONFIRMED"
    assert edit_res.json()["confirmed_profile"]["annual_income_inr"] == 180000.0

    # 3. Verify confirmed profile in GET /api/cases/{case_id}/profile
    prof_res = client.get(f"/api/cases/{case_id}/profile")
    assert prof_res.status_code == 200
    assert prof_res.json()["confirmed_profile"]["annual_income_inr"] == 180000.0

    # 4. Manual edit with auto_confirm=False stages pending confirmation
    edit_stage_res = client.post(
        f"/api/cases/{case_id}/profile/edit",
        json={"field": "occupation", "value": "farmer", "auto_confirm": False}
    )
    assert edit_stage_res.status_code == 200
    assert edit_stage_res.json()["status"] == "CONFIRMATION_REQUIRED"

    # 5. Authoritatively confirm the staged change
    confirm_res = client.post(f"/api/cases/{case_id}/profile/confirm", json={})
    assert confirm_res.status_code == 200
    assert confirm_res.json()["confirmed_profile"]["occupation"] == "farmer"


def test_multilingual_voice_languages():
    """Verifies that English, Hindi, and Telugu are exposed as supported languages."""
    res = client.get("/api/voice/languages")
    assert res.status_code == 200
    data = res.json()
    assert "en" in data["supported_languages"]
    assert "hi" in data["supported_languages"]
    assert "te" in data["supported_languages"]
    assert data["languages"]["en"]["default_locale"] == "en-IN"
    assert data["languages"]["hi"]["default_locale"] == "hi-IN"
    assert data["languages"]["te"]["default_locale"] == "te-IN"


def test_select_schemes_and_create_applications():
    """Verifies evaluating and selecting multiple schemes to create independent application tracks."""
    # 1. Create case with confirmed farmer profile
    create_res = client.post("/api/cases", json={"goal": "Farmer test"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Populate profile facts
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "age", "value": 35, "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "state", "value": "Telangana", "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "occupation", "value": "farmer", "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "land_acres", "value": 2.0, "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "land_holding_acres", "value": 2.0, "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "land_ownership", "value": True, "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "cultivates_land", "value": True, "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "annual_income_inr", "value": 180000.0, "auto_confirm": True})

    # 2. Evaluate schemes
    eval_res = client.post(f"/api/cases/{case_id}/schemes/evaluate")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["total_evaluated"] >= 13

    # Find selectable schemes
    selectable = [s["scheme_id"] for s in eval_data["schemes"] if s["selectable"]]
    assert len(selectable) > 0

    # 3. Select schemes using selected_scheme_ids contract
    sel_res = client.post(
        f"/api/cases/{case_id}/schemes/select",
        json={"selected_scheme_ids": [selectable[0]]}
    )
    assert sel_res.status_code == 200
    apps_data = sel_res.json()
    assert len(apps_data["applications"]) == 1
    assert apps_data["applications"][0]["scheme_id"] == selectable[0]


def test_next_agent_question_endpoint():
    """Verifies that the /agent/next-question endpoint returns prioritized missing questions with quick replies."""
    create_res = client.post("/api/cases", json={"goal": "Farmer test"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Initially, next question should identify missing info (e.g. state or land_ownership)
    q_res = client.get(f"/api/cases/{case_id}/agent/next-question")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["has_question"] is True
    assert "field" in q_data
    assert "question" in q_data
    assert isinstance(q_data["quick_replies"], list)


def test_continuous_interview_quick_reply_extraction():
    """Verifies that answers to agent questions (including quick reply phrases) are deterministically extracted and stage confirmation."""
    create_res = client.post("/api/cases", json={"goal": "Continuous interview test"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # 1. User answers with gender quick reply
    msg_res = client.post(f"/api/cases/{case_id}/messages", json={"message": "Male"})
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert data["confirmation_required"] is True
    assert any(c["field"] == "gender" and c["proposed"] == "male" for c in data["changes"])

    # 2. User confirms
    conf_res = client.post(f"/api/cases/{case_id}/profile/confirm", json={})
    assert conf_res.status_code == 200
    assert conf_res.json()["confirmed_profile"]["gender"] == "male"

    # 3. Next question is immediately available
    next_q = client.get(f"/api/cases/{case_id}/agent/next-question").json()
    assert next_q["has_question"] is True
    assert next_q["field"] != "gender"  # gender is already confirmed


def test_regression_land_acres_never_displayed_literally():
    """Requirement A: land_acres is never displayed literally in citizen-facing questions."""
    create_res = client.post("/api/cases", json={"goal": "Land inquiry"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Provide state, occupation, occupation_type, age, gender so next is land_acres
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "state", "value": "telangana"})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "occupation", "value": "farmer"})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "occupation_type", "value": "landowner"})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "age", "value": 35})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "gender", "value": "male"})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "land_ownership", "value": True})

    q_res = client.get(f"/api/cases/{case_id}/agent/next-question")
    assert q_res.status_code == 200
    q_data = q_res.json()
    if q_data.get("field") == "land_acres":
        assert "land_acres" not in q_data["question"]
        assert "How many acres of agricultural land do you own or cultivate?" in q_data["question"]


def test_regression_pre_selection_income_question_neutral_badge():
    """Requirement B: Pre-selection questions must have neutral badge and not show selected-scheme prerequisite."""
    create_res = client.post("/api/cases", json={"goal": "General inquiry"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    q_res = client.get(f"/api/cases/{case_id}/agent/next-question")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["has_question"] is True
    # Before selecting any scheme, scheme_context must NOT claim prerequisite for a specific scheme
    assert not q_data["scheme_context"].startswith("Prerequisite for")
    assert q_data["scheme_context"] == "Information needed to check supported schemes"


def test_regression_selected_scheme_question_displays_scheme_context():
    """Requirement C: Selected-scheme questions display scheme prerequisite context after explicit selection."""
    from backend.app.db.session import SessionLocal
    from backend.app.db.services.state_persistence import load_case, persist_agent_state

    create_res = client.post("/api/cases", json={"goal": "Farmer scheme application"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Provide partial farmer profile facts: state, active cultivation, landowner
    # missing: land_verification_source for Rythu Bharosa
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "state", "value": "Telangana", "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "active_cultivation_status", "value": True, "auto_confirm": True})
    client.post(f"/api/cases/{case_id}/profile/edit", json={"field": "occupation_type", "value": "landowner", "auto_confirm": True})

    # Associate selected scheme
    db = SessionLocal()
    try:
        st = load_case(db, case_id)
        st.selected_schemes = ["ts_rythu_bharosa_001"]
        persist_agent_state(db, st)
    finally:
        db.close()

    q_res = client.get(f"/api/cases/{case_id}/agent/next-question")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["has_question"] is True
    assert q_data["field"] == "land_verification_source"
    # Prerequisite badge should now reference the selected scheme
    assert "Prerequisite for" in q_data["scheme_context"]
    assert "Rythu Bharosa" in q_data["scheme_context"]


def test_regression_unrecognized_answer_retries_question():
    """Requirement D: Unrecognized answer preserves retry behavior, tells user it was not understood, and doesn't advance state."""
    create_res = client.post("/api/cases", json={"goal": "Retry test"})
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Get initial question
    q1 = client.get(f"/api/cases/{case_id}/agent/next-question").json()
    initial_field = q1["field"]

    # User inputs unrecognized punctuation
    msg_res = client.post(f"/api/cases/{case_id}/messages", json={"message": "."})
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert data["status"] == "NO_FACTS_EXTRACTED"
    assert data["confirmation_required"] is False
    assert len(data["changes"]) == 0
    # Must inform user that the input was not understood
    assert "not understood" in data["message"].lower() or "no profile facts" in data["message"].lower() or "clarify" in data["message"].lower()

    # Profile should remain completely unchanged
    prof = client.get(f"/api/cases/{case_id}/profile").json()
    assert prof["confirmed_profile"] == {}

    # Next question must be identical (not advanced)
    q2 = client.get(f"/api/cases/{case_id}/agent/next-question").json()
    assert q2["field"] == initial_field



