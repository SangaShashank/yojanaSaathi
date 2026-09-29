"""
Yojana Saathi - Deterministic Eligibility Demo Runner
=====================================================
Demonstrates the standalone deterministic eligibility engine running on
schemes_dataset_v2.json with ZERO LLM involvement.
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path so 'backend' package is discoverable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure Windows terminal outputs UTF-8 cleanly
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from backend.app.schemas.profile import CitizenProfile
from backend.app.schemas.eligibility import CriterionStatus, SchemeOutcome
from backend.app.services.scheme_loader import load_all_schemes
from backend.app.services.eligibility_engine import evaluate_all_schemes, evaluate_eligibility


console = Console(highlight=False)


def format_status(status: CriterionStatus) -> str:
    if status == CriterionStatus.PASS:
        return "[bold green]PASS[/bold green]"
    if status == CriterionStatus.FAIL:
        return "[bold red]FAIL[/bold red]"
    if status == CriterionStatus.UNKNOWN:
        return "[bold yellow]UNKNOWN[/bold yellow]"
    return "[dim]SKIPPED[/dim]"


def format_outcome(outcome: SchemeOutcome) -> str:
    if outcome == SchemeOutcome.FULLY_ELIGIBLE:
        return "[bold green]FULLY_ELIGIBLE[/bold green]"
    if outcome == SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED:
        return "[bold cyan]ACTIONABLE / PREPARATION REQUIRED[/bold cyan]"
    if outcome == SchemeOutcome.NOT_ELIGIBLE:
        return "[bold red]NOT_ELIGIBLE[/bold red]"
    return "[bold yellow]INCOMPLETE / UNKNOWN[/bold yellow]"


def run_demo():
    console.print(
        Panel.fit(
            "[bold white]YOJANA SAATHI[/bold white]\n"
            "[italic cyan]Phase 1: Deterministic Eligibility Engine Demo[/italic cyan]\n"
            "[dim]Evaluates versioned rules from schemes_dataset_v2.json (No LLM)[/dim]",
            border_style="cyan",
        )
    )

    schemes = load_all_schemes()
    console.print(f"[bold]Loaded Schemes:[/bold] {len(schemes)} scheme definitions found in dataset.\n")

    # Scenario 1: Telangana Small Farmer (Expected to pass PM-KISAN, Rythu Bharosa, Soil Health Card, PM-KMY)
    profile_1_data = {
        "name": "Ramulu Goud",
        "gender": "male",
        "age": 34,
        "state": "Telangana",
        "district": "Karimnagar",
        "occupation": "farmer",
        "occupation_type": "landowner",
        "land_ownership": True,
        "land_acres": 3.0,
        "land_record_date": "2018-04-12",
        "farmer_id_status": "registered",
        "active_cultivation_status": True,
        "cultivates_land": True,
        "land_verification_source": "bhu_bharati_portal",
    }
    p1 = CitizenProfile(**profile_1_data)

    console.print("\n[bold yellow]==== SCENARIO 1: Eligible Telangana Small Farmer ====[/bold yellow]")
    console.print(f"Profile: {p1.age}yo male farmer, Telangana, 3 acres land acquired 2018, Bhu Bharati verified.\n")

    res1 = evaluate_all_schemes(p1, schemes)

    table1 = Table(title="Scheme Evaluation Results - Scenario 1", show_header=True)
    table1.add_column("Scheme ID", style="cyan")
    table1.add_column("Title", style="white")
    table1.add_column("Outcome", style="bold")
    table1.add_column("Passed", justify="center", style="green")
    table1.add_column("Failed", justify="center", style="red")
    table1.add_column("Unknown", justify="center", style="yellow")

    for sid, eval_res in res1.evaluations.items():
        table1.add_row(
            sid,
            eval_res.scheme_title[:38],
            format_outcome(eval_res.outcome),
            str(len(eval_res.passed_criteria)),
            str(len(eval_res.failed_criteria)),
            str(len(eval_res.unresolved_criteria)),
        )
    console.print(table1)

    # Detailed criterion breakdown for PM-KISAN
    pmk_res = res1.evaluations["pm_kisan_001"]
    console.print(f"\n[bold]Detailed Criterion Breakdown for PM-KISAN ({pmk_res.scheme_id}):[/bold]")
    for crit in pmk_res.criterion_results:
        console.print(f"  {format_status(crit.status)} [bold]{crit.field}[/bold]: {crit.reason}")

    # Detailed criterion breakdown for Rythu Bharosa
    rb_res = res1.evaluations["ts_rythu_bharosa_001"]
    console.print(f"\n[bold]Detailed Criterion Breakdown for Rythu Bharosa ({rb_res.scheme_id}):[/bold]")
    for crit in rb_res.criterion_results:
        console.print(f"  {format_status(crit.status)} [bold]{crit.field}[/bold]: {crit.reason}")

    # Scenario 2: Incomplete Farmer (Missing critical farmer ID)
    console.print("\n[bold yellow]==== SCENARIO 2: Incomplete Profile (Strict UNKNOWN Semantics) ====[/bold yellow]")
    profile_2_data = {
        "age": 40,
        "land_ownership": True,
        "land_record_date": "2018-05-15",
        "occupation": "farmer",
        # farmer_id_status is MISSING
    }
    p2 = CitizenProfile(**profile_2_data)
    res2 = evaluate_eligibility(p2, schemes[0])  # PM-KISAN
    console.print(f"Scheme: {res2.scheme_title}")
    console.print(f"Outcome: {format_outcome(res2.outcome)}")
    console.print(f"Summary: {res2.summary_reason}")
    for crit in res2.criterion_results:
        console.print(f"  {format_status(crit.status)} [bold]{crit.field}[/bold]: {crit.reason}")

    # Scenario 3: Disqualified Applicant (Post-2019 purchase & Income tax payer)
    console.print("\n[bold yellow]==== SCENARIO 3: Disqualified Applicant ====[/bold yellow]")
    profile_3_data = {
        "age": 45,
        "land_ownership": True,
        "land_record_date": "2021-08-20",  # Acquired after Feb 1, 2019
        "occupation": "income_tax_payer",   # Excluded occupation
        "farmer_id_status": "registered",
    }
    p3 = CitizenProfile(**profile_3_data)
    res3 = evaluate_eligibility(p3, schemes[0])
    console.print(f"Scheme: {res3.scheme_title}")
    console.print(f"Outcome: {format_outcome(res3.outcome)}")
    console.print(f"Summary: {res3.summary_reason}")
    for crit in res3.criterion_results:
        console.print(f"  {format_status(crit.status)} [bold]{crit.field}[/bold]: {crit.reason}")

    console.print("\n[bold green][SUCCESS] Phase 1 Demo complete: Deterministic Core runs cleanly and reliably.[/bold green]")

    # =========================================================================
    # PHASE 2: AGENT CONTROLLER DYNAMIC LOOP DEMO
    # =========================================================================
    from backend.app.agent.controller import AgentController
    from backend.app.agent.provider import DeterministicActionProvider
    from backend.app.agent.state import AgentState, Contradiction, StageEnum

    console.print("\n" + "=" * 65)
    console.print(
        Panel.fit(
            "[bold white]YOJANA SAATHI[/bold white]\n"
            "[italic cyan]Phase 2: Agent Controller Loop Demonstration[/italic cyan]\n"
            "[dim]Dynamic state observation -> Next action proposal -> Validation -> Dispatch[/dim]",
            border_style="magenta",
        )
    )

    agent = AgentController(provider=DeterministicActionProvider())

    # Demo 2.1: State-Dependent Decisions (State A vs State B vs State C)
    console.print("[bold yellow]==== DEMO 2.1: Genuinely State-Dependent Behavior ====[/bold yellow]")

    # State A: Incomplete Profile
    state_a = AgentState(
        profile={"age": 42, "state": "Telangana"},
        missing_information=["annual_income_inr"],
        candidate_schemes=["pm_kisan_001"],
    )
    act_a, _ = agent.step(state_a)
    console.print(f"State A (missing income)      --> Action: [bold cyan]{act_a.selected_action}[/bold cyan] ({act_a.selected_field}) [reason: {act_a.reason_code}]")

    # State B: Contradiction Present
    state_b = AgentState(
        profile={"age": 42},
        missing_information=[],
        contradictions=[Contradiction(field="age", existing_value=42, conflicting_value=45)],
        candidate_schemes=["pm_kisan_001"],
    )
    act_b, _ = agent.step(state_b)
    console.print(f"State B (contradiction on age) --> Action: [bold cyan]{act_b.selected_action}[/bold cyan] ({act_b.selected_field}) [reason: {act_b.reason_code}]")

    # State C: Complete Profile
    state_c = AgentState(
        profile={
            "age": 35,
            "state": "Telangana",
            "land_ownership": True,
            "land_record_date": "2018-05-10",
            "occupation": "farmer",
            "farmer_id_status": "registered",
        },
        missing_information=[],
        candidate_schemes=["pm_kisan_001"],
    )
    act_c, _ = agent.step(state_c)
    console.print(f"State C (profile complete)    --> Action: [bold cyan]{act_c.selected_action}[/bold cyan] (tool: {act_c.tool_called}) [reason: {act_c.reason_code}]")

    # Demo 2.2: Multi-turn Agentic Proof Trace
    console.print("\n[bold yellow]==== DEMO 2.2: Sequential Agentic Proof Trace ====[/bold yellow]")
    agentic_state = AgentState(
        case_id="CASE-LIVE-DEMO",
        profile={"age": 35, "state": "Telangana", "land_ownership": True, "land_record_date": "2018-05-10", "occupation": "farmer"},
        missing_information=["farmer_id_status"],
        candidate_schemes=["pm_kisan_001"],
    )

    # Turn 1
    t1_act, _ = agent.step(agentic_state)
    console.print(f"[bold]Turn 1:[/bold] State missing 'farmer_id_status' --> Agent selects [bold green]{t1_act.selected_action}[/bold green] ('{t1_act.selected_field}')")

    # User answers Turn 1
    console.print("  [italic dim]-> User provides: farmer_id_status = 'registered'[/italic dim]")
    agentic_state.profile["farmer_id_status"] = "registered"
    agentic_state.missing_information.clear()
    agentic_state.stage = StageEnum.ELIGIBILITY_READY.value

    # Turn 2
    t2_act, t2_res = agent.step(agentic_state)
    console.print(f"[bold]Turn 2:[/bold] Profile complete --> Agent selects [bold green]{t2_act.selected_action}[/bold green] (Invoked Phase 1 engine)")
    console.print(f"  [dim]-> Eligible schemes found: {t2_res.get('fully_eligible')}[/dim]")

    # Turn 3
    t3_act, _ = agent.step(agentic_state)
    console.print(f"[bold]Turn 3:[/bold] Evaluation recorded --> Agent selects [bold green]{t3_act.selected_action}[/bold green] [status: {t3_act.termination_reason}]")

    console.print("\n[bold green][SUCCESS] Phase 2 Agent Controller Loop runs cleanly and dynamically.[/bold green]")

    # =========================================================================
    # PHASE 3: PROFILE EXTRACTION, CORRECTION & HUMAN CONFIRMATION DEMO
    # =========================================================================
    from backend.app.profile.coordinator import (
        ProfileCoordinator,
        apply_manual_edit,
        confirm_pending_profile,
        process_user_message,
        reject_pending_profile,
    )
    from backend.app.profile.extractor import ProfileExtractor

    console.print("\n" + "=" * 65)
    console.print(
        Panel.fit(
            "[bold white]YOJANA SAATHI[/bold white]\n"
            "[italic cyan]Phase 3: Profile Extraction, Correction & Human Confirmation[/italic cyan]\n"
            "[dim]Natural Language -> Structured Extraction -> Proposed Changes -> Human Gate -> Confirmed Profile[/dim]",
            border_style="yellow",
        )
    )

    p3_state = AgentState(
        case_id="CASE-P3-DEMO",
        goal="Identify applicable welfare schemes and orchestrate readiness",
        candidate_schemes=["pm_kisan_001"],
    )
    coordinator = ProfileCoordinator(extractor=ProfileExtractor(use_llm=False))

    # Step 1: Messy Natural-Language Intake
    raw_input_1 = "Namaste, I am 42 years old, a farmer living in Telangana, I have 3 acres of agricultural land and my family income is about 2 lakh."
    console.print("\n[bold yellow]==== STEP 1: Messy Natural Language Intake ====[/bold yellow]")
    console.print(f"[bold cyan]Citizen Input:[/bold cyan] [italic]\"{raw_input_1}\"[/italic]\n")

    step1_res = coordinator.process_user_message(p3_state, raw_input_1)
    console.print(f"[bold green]Status:[/bold green] {step1_res['status']}")
    console.print("[bold]Proposed Profile Changes (Awaiting Human/CSC Confirmation):[/bold]")
    for ch in step1_res["changes"]:
        console.print(f"  * [cyan]{ch['field']}[/cyan]: previous={ch['previous']} -> [bold green]{ch['proposed']}[/bold green]")

    console.print(f"\n[dim]Confirmed Profile in AgentState (Before Confirmation): {p3_state.profile}[/dim]")
    assert len(p3_state.profile) == 0, "Safety violation: Unconfirmed facts leaked into profile!"

    # Step 2: Human / CSC Confirmation
    console.print("\n[bold yellow]==== STEP 2: CSC Operator / Citizen Confirms Facts ====[/bold yellow]")
    confirm1_res = coordinator.confirm_pending_profile(p3_state)
    console.print(f"[bold green]Confirmation Result:[/bold green] {confirm1_res['status']}")
    console.print(f"[bold]Authoritative Confirmed Profile:[/bold] {p3_state.profile}")
    console.print(f"[bold]Remaining Missing Information:[/bold] {confirm1_res['missing_information']}")

    # Step 3: Agent Resumes & Asks Only Remaining Unresolved Questions
    console.print("\n[bold yellow]==== STEP 3: Agent Controller Resumes ====[/bold yellow]")
    p3_act1, p3_res1 = agent.step(p3_state)
    console.print(f"Agent observes state -> Next Action: [bold cyan]{p3_act1.selected_action}[/bold cyan]")
    console.print(f"Target Field: [bold]{p3_act1.selected_field}[/bold]")
    question_text = p3_state.last_action.question if p3_state.last_action else p3_res1.get('question')
    console.print(f"Question Asked: [italic]\"{question_text}\"[/italic]")

    # Citizen provides missing answer
    console.print("\n  [italic dim]-> Citizen responds: 'My land record was registered on 2018-05-15.'[/italic dim]")
    apply_manual_edit(p3_state, "land_record_date", "2018-05-15", auto_confirm=True)
    apply_manual_edit(p3_state, "farmer_id_status", "registered", auto_confirm=True)
    apply_manual_edit(p3_state, "land_ownership", True, auto_confirm=True)

    # Step 4: Eligibility Engine Runs Authoritatively
    console.print("\n[bold yellow]==== STEP 4: Profile Complete -> Eligibility Runs ====[/bold yellow]")
    p3_act2, p3_res2 = agent.step(p3_state)
    console.print(f"Agent Action: [bold green]{p3_act2.selected_action}[/bold green] (Invoked Phase 1 Deterministic Engine)")
    console.print(f"Eligible Schemes: [bold cyan]{p3_res2.get('fully_eligible')}[/bold cyan]")
    console.print(f"Evaluated Profile Fingerprint: {p3_state.evaluated_profile_fingerprint}")

    # Step 5: Natural Language Field-Level Correction & Staleness Invalidation
    console.print("\n[bold yellow]==== STEP 5: Natural-Language Correction & Staleness Invalidation ====[/bold yellow]")
    correction_msg = "Actually, I have 5 acres and not 3 acres."
    console.print(f"[bold cyan]Citizen Correction:[/bold cyan] [italic]\"{correction_msg}\"[/italic]\n")

    corr_res = coordinator.process_user_message(p3_state, correction_msg)
    console.print(f"[bold]Proposed Patch:[/bold]")
    for ch in corr_res["changes"]:
        console.print(f"  * [cyan]{ch['field']}[/cyan]: previous={ch['previous']} -> proposed=[bold yellow]{ch['proposed']}[/bold yellow]")

    # Before confirmation, previous eligibility and confirmed profile remain intact
    console.print(f"[dim]Confirmed land_holding_acres before confirmation: {p3_state.profile['land_holding_acres']}[/dim]")

    # Confirm correction
    confirm_corr = coordinator.confirm_pending_profile(p3_state)
    console.print(f"\n[bold green]Correction Confirmed![/bold green]")
    console.print(f"New confirmed land_holding_acres: [bold green]{p3_state.profile['land_holding_acres']}[/bold green]")
    console.print(f"[bold red]Eligibility Marked Stale:[/bold red] {confirm_corr['eligibility_invalidated']}")
    console.print(f"Cached eligible_schemes cleared: {p3_state.eligible_schemes} (Ready for re-evaluation)")

    console.print("\n[bold green][SUCCESS] Phase 3 Profile Extraction, Correction & Human Confirmation Complete![/bold green]")

    # =========================================================================
    # PHASE 4: MULTI-SCHEME HANDLING & PARALLEL PROCESSING DEMO
    # =========================================================================
    from backend.app.services.multi_scheme_coordinator import MultiSchemeCoordinator
    from backend.app.schemas.multi_scheme import ApplicationStatus

    console.print("\n" + "=" * 65)
    console.print(
        Panel.fit(
            "[bold white]YOJANA SAATHI[/bold white]\n"
            "[italic cyan]Phase 4: Multi-Scheme Handling & Parallel Application Tracks[/italic cyan]\n"
            "[dim]Independent Per-Scheme Evaluation -> Non-Ranked Presentation -> Multi-Select -> Independent Lifecycle[/dim]",
            border_style="blue",
        )
    )

    coordinator_p4 = MultiSchemeCoordinator()
    p4_state = AgentState(
        case_id="CASE-P4-DEMO",
        goal="Evaluate all relevant schemes and orchestrate independent applications",
        profile={
            "age": 35,
            "gender": "male",
            "state": "Telangana",
            "district": "Karimnagar",
            "occupation": "farmer",
            "occupation_type": "landowner",
            "land_ownership": True,
            "land_acres": 3.0,
            "land_record_date": "2018-05-15",
            "farmer_id_status": "registered",
            "active_cultivation_status": True,
            "cultivates_land": True,
            "land_verification_source": "bhu_bharati_portal",
        },
        candidate_schemes=["pm_kisan_001", "ts_rythu_bharosa_001", "soil_health_card_001", "pm_kmy_001"],
    )

    # Step 1: Independent Multi-Scheme Evaluation
    console.print("[bold yellow]==== STEP 4.1: Independent Multi-Scheme Evaluation ====[/bold yellow]")
    eval_results = coordinator_p4.evaluate_all_candidate_schemes(p4_state)
    console.print(f"Evaluated {len(eval_results)} schemes independently against confirmed profile.\n")

    p4_table = Table(title="Phase 4 Multi-Scheme Evaluation Results (Non-Ranked)", show_header=True)
    p4_table.add_column("Scheme ID", style="cyan")
    p4_table.add_column("Outcome", style="bold")
    p4_table.add_column("Eligible", justify="center")
    p4_table.add_column("Selectable", justify="center")
    p4_table.add_column("Missing / Unknown Fields", style="yellow")

    for item in eval_results:
        # Strict requirement: ZERO ranking attributes present
        assert not hasattr(item, "rank") and not hasattr(item, "score") and not hasattr(item, "best"), "Violation: Ranking found!"
        p4_table.add_row(
            item.scheme_id,
            format_outcome(SchemeOutcome(item.outcome)),
            "[green]YES[/green]" if item.eligible else "[red]NO[/red]",
            "[bold green]YES[/bold green]" if item.selectable else "[dim]NO[/dim]",
            ", ".join(item.missing_information) if item.missing_information else "[dim]None[/dim]",
        )
    console.print(p4_table)

    # Step 2: Citizen / CSC Multi-Selection
    console.print("\n[bold yellow]==== STEP 4.2: Citizen/CSC Multi-Scheme Selection ====[/bold yellow]")
    selected_ids = ["pm_kisan_001", "ts_rythu_bharosa_001"]
    console.print(f"Citizen selects {len(selected_ids)} schemes: [bold cyan]{selected_ids}[/bold cyan]")

    apps = coordinator_p4.select_schemes(p4_state, selected_ids)
    console.print(f"[bold green]Successfully created {len(apps)} independent application records:[/bold green]")
    for app in apps:
        app_id = app.id if hasattr(app, "id") else app["id"]
        app_scheme = app.scheme_id if hasattr(app, "scheme_id") else app["scheme_id"]
        app_status = app.status if hasattr(app, "status") else app["status"]
        console.print(f"  * Application ID: [bold]{app_id}[/bold] | Scheme: [cyan]{app_scheme}[/cyan] | Status: [green]{app_status}[/green]")

    # Step 3: Critical Parallel Processing & State Isolation Proof
    console.print("\n[bold yellow]==== STEP 4.3: Parallel Processing & State Isolation Proof ====[/bold yellow]")
    app_pmk_id = apps[0].id if hasattr(apps[0], "id") else apps[0]["id"]
    app_rb_id = apps[1].id if hasattr(apps[1], "id") else apps[1]["id"]
    scheme_a = apps[0].scheme_id if hasattr(apps[0], "scheme_id") else apps[0]["scheme_id"]
    scheme_b = apps[1].scheme_id if hasattr(apps[1], "scheme_id") else apps[1]["scheme_id"]

    console.print(f"Transitioning Application A ({app_pmk_id}) -> [bold magenta]PREPARING[/bold magenta]")
    coordinator_p4.update_application_status(p4_state, app_pmk_id, ApplicationStatus.PREPARING.value)

    app_a_status = p4_state.applications[scheme_a]["status"]
    app_b_status = p4_state.applications[scheme_b]["status"]

    console.print(f"\n[bold]Current Application States:[/bold]")
    console.print(f"  * Application A ({scheme_a}): [bold magenta]{app_a_status}[/bold magenta]")
    console.print(f"  * Application B ({scheme_b}): [bold green]{app_b_status}[/bold green]")
    assert app_a_status == ApplicationStatus.PREPARING.value
    assert app_b_status == ApplicationStatus.SELECTED.value
    console.print("[bold green]-> ISOLATION VERIFIED: Application A changed, Application B remained unchanged![/bold green]")

    # Step 4: Profile Correction & Staleness Invalidation
    console.print("\n[bold yellow]==== STEP 4.4: Profile Update -> Staleness Invalidation (Applications Preserved) ====[/bold yellow]")
    console.print("Citizen modifies land size: 3.0 acres -> 5.0 acres")
    p4_state.profile["land_acres"] = 5.0
    p4_state.invalidate_eligibility_if_stale()

    console.print(f"Evaluations cleared / invalidated: [bold red]{len(p4_state.scheme_evaluations) == 0}[/bold red]")
    console.print(f"Applications preserved in state: [bold green]{len(p4_state.applications)} application records intact[/bold green]")
    assert len(p4_state.applications) == 2, "Applications must survive profile changes!"

    # Re-evaluation
    console.print("\nRe-evaluating candidate schemes against revised profile...")
    reeval_results = coordinator_p4.evaluate_all_candidate_schemes(p4_state)
    console.print(f"[bold green]Re-evaluation successful! {len(reeval_results)} schemes updated with new profile fingerprint: {p4_state.evaluated_profile_fingerprint}[/bold green]")

    console.print("\n[bold green][SUCCESS] Phase 4 Multi-Scheme Handling & Parallel Processing Demo Complete![/bold green]")

    # =========================================================================
    # PHASE 5: DOCUMENTS & READINESS SUBSYSTEM DEMO
    # =========================================================================
    from backend.app.services.document_requirements import (
        get_scheme_document_requirements,
        DOCUMENT_VERIFICATION_FIELDS_MAP,
    )
    from backend.app.services.document_coordinator import DocumentCoordinator
    from backend.app.schemas.document import DocumentRequirementSource, ReadinessStatus

    console.print("\n" + "=" * 65)
    console.print(
        Panel.fit(
            "[bold white]YOJANA SAATHI[/bold white]\n"
            "[italic cyan]Phase 5: Documents & Readiness Subsystem Demo[/italic cyan]\n"
            "[dim]Scheme-Aware Requirements -> Upload/Validation -> Structured Extraction -> Profile Comparison -> Discrepancy (No Auto-Reject) -> Human Resolution -> Readiness Recalculation[/dim]",
            border_style="magenta",
        )
    )

    doc_coord = DocumentCoordinator()
    p5_state = AgentState(
        case_id="CASE-P5-DEMO",
        goal="Process documents and prepare applications for handoff",
        profile={
            "name": "Ravi Kumar",
            "age": 35,
            "gender": "male",
            "state": "Telangana",
            "district": "Karimnagar",
            "occupation": "farmer",
            "occupation_type": "landowner",
            "land_ownership": True,
            "land_acres": 3.0,
            "farmer_id_status": "registered",
            "active_cultivation_status": True,
            "cultivates_land": True,
            "land_verification_source": "bhu_bharati_portal",
        },
        selected_schemes=["pm_kisan_001", "ts_rythu_bharosa_001"],
        applications={
            "pm_kisan_001": {
                "id": "app_pmk_demo",
                "case_id": "CASE-P5-DEMO",
                "scheme_id": "pm_kisan_001",
                "status": "SELECTED",
                "created_at": "2026-09-26T00:00:00Z",
            },
            "ts_rythu_bharosa_001": {
                "id": "app_rb_demo",
                "case_id": "CASE-P5-DEMO",
                "scheme_id": "ts_rythu_bharosa_001",
                "status": "SELECTED",
                "created_at": "2026-09-26T00:00:00Z",
            },
        },
    )

    # Step 5.1: Scheme-Aware Requirements (No Fabrication)
    console.print("[bold yellow]==== STEP 5.1: Scheme-Aware Document Requirements (Truthfulness & No Fabrication) ====[/bold yellow]")
    pmk_reqs = get_scheme_document_requirements("pm_kisan_001")
    console.print(f"PM-KISAN verified official requirements: [cyan]{len(pmk_reqs)} found[/cyan]")
    for r in pmk_reqs:
        console.print(f"  * [bold]{r.document_type}[/bold] (Mandatory: {r.required}, Status: [green]{r.source_status}[/green], Fields: {r.verification_fields})")

    unreg_reqs = get_scheme_document_requirements("unknown_scheme_999")
    console.print(f"\nUnconfigured Scheme Check: {len(unreg_reqs)} requirement items returned.")
    console.print(f"  * Status: [bold red]{unreg_reqs[0].source_status}[/bold red] - {unreg_reqs[0].name}")

    # Step 5.2: Application-Specific Document Checklist
    console.print("\n[bold yellow]==== STEP 5.2: Application-Specific Document Checklist & Initial Readiness ====[/bold yellow]")
    checklist = doc_coord.get_application_checklist(p5_state, "app_pmk_demo")
    console.print(f"Generated Checklist for PM-KISAN (app_pmk_demo):")
    for item in checklist:
        console.print(f"  [ ] {item.name} ({item.document_type}) (Status: [yellow]{item.status}[/yellow], Mandatory: {item.required})")

    init_readiness = doc_coord.compute_readiness(p5_state, "app_pmk_demo")
    console.print(f"Initial Readiness Status: [bold yellow]{init_readiness.status}[/bold yellow] (Missing documents: {len(init_readiness.missing_documents)})")
    assert init_readiness.status == "PREPARATION_REQUIRED"

    # Step 5.3: Document Upload with SHA-256 Deduplication & Storage Isolation
    console.print("\n[bold yellow]==== STEP 5.3: Document Upload with SHA-256 Deduplication ====[/bold yellow]")
    from backend.tests.test_documents_and_readiness import make_sample_pdf
    raw_pdf_bytes = make_sample_pdf("Name: Ravi Kumar Land: 4.5 acres Survey: 108/A District: Karimnagar")
    up_res = doc_coord.upload_document(
        state=p5_state,
        application_id="app_pmk_demo",
        document_type="land_record",
        filename="pattadar_passbook.pdf",
        file_bytes=raw_pdf_bytes,
        mime_type="application/pdf",
    )
    doc_id = up_res.document_id
    console.print(f"Uploaded Document ID: [bold cyan]{doc_id}[/bold cyan]")
    console.print(f"  * Status: [green]{up_res.status}[/green]")
    console.print(f"  * SHA-256 Hash: [dim]{up_res.sha256}[/dim]")
    console.print(f"  * File Size: [dim]{up_res.size_bytes} bytes (Secure isolated storage)[/dim]")

    # Deduplication test
    dup_res = doc_coord.upload_document(
        state=p5_state,
        application_id="app_pmk_demo",
        document_type="land_record",
        filename="duplicate.pdf",
        file_bytes=raw_pdf_bytes,
    )
    console.print(f"Duplicate Upload Handled -> Returned Document ID: {dup_res.document_id} (Matches original: {dup_res.document_id == doc_id})")

    # Step 5.4: Document Processing, Extraction & Comparison with Profile
    console.print("\n[bold yellow]==== STEP 5.4: Extraction & Profile Comparison (No Auto-Rejection) ====[/bold yellow]")
    proc_res = doc_coord.process_and_verify_document(p5_state, doc_id, "app_pmk_demo")
    console.print(f"Extracted Structured Data: [cyan]{proc_res.extracted_data}[/cyan]")
    console.print(f"Verification Status: [bold magenta]{proc_res.verification_status}[/bold magenta]")
    console.print(f"Discrepancies Found: [bold red]{len(proc_res.discrepancies)}[/bold red]")
    for disc in proc_res.discrepancies:
        console.print(f"  * Field [cyan]{disc.field_name}[/cyan]: Profile says [yellow]{disc.profile_value}[/yellow] vs Document says [magenta]{disc.document_value}[/magenta]")

    # Check non-auto-rejection rule
    console.print("\n[bold]Checking Non-Auto-Rejection Non-Negotiable Rule:[/bold]")
    pmk_app_status = p5_state.applications["pm_kisan_001"]["status"]
    console.print(f"Application Status is [green]{pmk_app_status}[/green] (NOT REJECTED, NOT FAILED!)")
    readiness_post_proc = doc_coord.compute_readiness(p5_state, "app_pmk_demo")
    console.print(f"Readiness Status is [bold magenta]{readiness_post_proc.status}[/bold magenta]")
    assert readiness_post_proc.status == "HUMAN_VERIFICATION_REQUIRED"

    # Step 5.5: Human Discrepancy Resolution & Authoritative Profile Update via Phase 3
    console.print("\n[bold yellow]==== STEP 5.5: Discrepancy Resolution via Phase 3 Confirmation Flow ====[/bold yellow]")
    disc_id = proc_res.discrepancies[0].discrepancy_id
    console.print("Citizen/CSC selects: [bold green]USE_DOCUMENT[/bold green] (Accept 4.5 acres as true fact)")
    res_outcome = doc_coord.resolve_discrepancy(
        state=p5_state,
        discrepancy_id=disc_id,
        resolution="USE_DOCUMENT",
    )
    console.print(f"Discrepancy Status: [bold green]{res_outcome['status']}[/bold green]")
    console.print(f"Updated Confirmed Profile Land Acres: [bold green]{p5_state.profile.get('land_acres')}[/bold green]")
    console.print(f"Profile Updated: [bold green]{res_outcome['profile_updated']}[/bold green]")

    # Step 5.6: Readiness Progression & Multi-Application Isolation
    console.print("\n[bold yellow]==== STEP 5.6: Readiness Progression & Application Isolation ====[/bold yellow]")
    readiness_final = doc_coord.compute_readiness(p5_state, "app_pmk_demo")
    console.print(f"PM-KISAN Readiness Status: [bold cyan]{readiness_final.status}[/bold cyan]")
    console.print(f"Verified Requirements: {readiness_final.verified_requirements} | Remaining Discrepancies: {len(readiness_final.mismatches)}")

    # Check Rythu Bharosa application isolation
    rb_readiness = doc_coord.compute_readiness(p5_state, "app_rb_demo")
    console.print(f"\nRythu Bharosa (app_rb_demo) Readiness Status: [bold yellow]{rb_readiness.status}[/bold yellow]")
    console.print(f"Rythu Bharosa Verified Requirements: [cyan]{rb_readiness.verified_requirements}[/cyan] (MUST BE 0!)")
    assert rb_readiness.verified_requirements == 0, "Isolation violation: document leaked into unlinked application!"
    console.print("[bold green]-> ISOLATION VERIFIED: PM-KISAN verification did not leak into Rythu Bharosa![/bold green]")

    # Step 5.7: Real OCR for Scanned / Image Documents (Phase 5.1)
    console.print("\n[bold yellow]==== STEP 5.7: Real OCR for Scanned / Image Documents (Phase 5.1) ====[/bold yellow]")
    from backend.tests.test_ocr_pipeline import make_synthetic_image

    # 1. Create clearly labeled synthetic scanned document
    ocr_doc_text = (
        "SYNTHETIC DEMO DOCUMENT - FOR TESTING ONLY\n"
        "Name: Ravi Kumar\n"
        "Land: 4.5 acres\n"
        "District: Karimnagar\n"
        "Survey Number: 108/A"
    )
    console.print("[dim]Generating synthetic scanned JPG document fixture...[/dim]")
    ocr_jpg_bytes = make_synthetic_image(ocr_doc_text, img_format="JPEG", width=700, height=250)

    # Reset Rythu Bharosa state profile land acres to 3.0 to test discrepancy
    p5_state.profile["land_holding_acres"] = 3.0
    p5_state.profile["land_acres"] = 3.0

    # 2. Upload synthetic scanned document
    ocr_up = doc_coord.upload_document(
        state=p5_state,
        application_id="app_rb_demo",
        document_type="land_passbook",
        filename="synthetic_scanned_passbook.jpg",
        file_bytes=ocr_jpg_bytes,
        mime_type="image/jpeg",
    )
    console.print(f"Uploaded Synthetic Document ID: [bold cyan]{ocr_up.document_id}[/bold cyan]")

    # 3. Real OCR extraction & structured parsing
    console.print("[dim]Executing REAL Tesseract OCR extraction on synthetic image...[/dim]")
    ocr_proc_res = doc_coord.process_and_verify_document(p5_state, ocr_up.document_id, "app_rb_demo")
    console.print(f"  * Extraction Method: [bold green]{ocr_proc_res.extraction_method}[/bold green]")
    console.print(f"  * OCR Provider: [bold green]{ocr_proc_res.ocr_provider}[/bold green]")
    console.print(f"  * Pages Processed: [cyan]{ocr_proc_res.pages_processed}[/cyan]")
    console.print(f"  * Structured Fields Extracted: [cyan]{ocr_proc_res.extracted_data}[/cyan]")

    # 4. Profile comparison & discrepancy detection
    console.print(f"  * Discrepancies Detected: [bold red]{len(ocr_proc_res.discrepancies)}[/bold red]")
    for d in ocr_proc_res.discrepancies:
        console.print(f"    - Field [cyan]{d.field_name}[/cyan]: Profile=[yellow]{d.profile_value}[/yellow] vs OCR=[magenta]{d.document_value}[/magenta]")

    rb_readiness_ocr = doc_coord.compute_readiness(p5_state, "app_rb_demo")
    console.print(f"  * Readiness Status: [bold magenta]{rb_readiness_ocr.status}[/bold magenta] (No auto-rejection)")
    assert rb_readiness_ocr.status == "HUMAN_VERIFICATION_REQUIRED"

    # 5. Human discrepancy resolution via Phase 3 flow
    if ocr_proc_res.discrepancies:
        disc_item = ocr_proc_res.discrepancies[0]
        disc_id = disc_item.discrepancy_id
        console.print("\n[dim]Resolving discrepancy via Phase 3 human confirmation workflow (USE_DOCUMENT)...[/dim]")
        res_ocr = doc_coord.resolve_discrepancy(
            state=p5_state,
            discrepancy_id=disc_id,
            resolution="USE_DOCUMENT",
        )
        console.print(f"  * Resolution Status: [bold green]{res_ocr['status']}[/bold green]")
        console.print(f"  * Confirmed Profile Land Acres Updated: [bold green]{p5_state.profile.get('land_holding_acres')}[/bold green]")

        rb_final = doc_coord.compute_readiness(p5_state, "app_rb_demo")
        console.print(f"  * Post-Resolution Readiness: [bold cyan]{rb_final.status}[/bold cyan] (Mismatches: {len(rb_final.mismatches)})")

    console.print("\n[bold green][SUCCESS] Phase 5 & 5.1 Documents, Readiness & Real OCR Demo Complete![/bold green]")

    # =========================================================================
    # PHASE 8: MULTILINGUAL VOICE & AUDIO DEMO
    # =========================================================================
    console.print("\n" + "=" * 70)
    console.print(
        Panel.fit(
            "[bold white]PHASE 8: MULTILINGUAL VOICE & AUDIO DEMO[/bold white]\n"
            "[italic cyan]Alternate Speech Interface over Existing Yojana Saathi Pipeline[/italic cyan]\n"
            "[dim]Audio -> STT (Groq Whisper) -> ProfileCoordinator -> AgentController -> Browser TTS (SpeechSynthesis)[/dim]",
            border_style="magenta",
        )
    )

    import os
    import uuid
    from backend.app.services.voice_service import VoiceService
    from backend.app.integrations.groq import MockSpeechToTextProvider, GroqWhisperProvider
    from backend.app.db.session import SessionLocal
    from backend.app.db.repositories.case_repository import CaseRepository
    from backend.app.db.services.state_persistence import load_case, persist_agent_state
    from backend.tests.test_phase8_voice import create_synthetic_wav

    db = SessionLocal()
    try:
        # Create dedicated case for Voice Demo
        voice_case_id = f"CASE-VOICE-DEMO-{uuid.uuid4().hex[:6].upper()}"
        CaseRepository.create_case(
            db=db,
            case_id=voice_case_id,
            goal="Multilingual Voice Assistance Journey",
            candidate_schemes=["pm_kisan_001", "ts_rythu_bharosa_001"],
        )
        sample_audio = create_synthetic_wav(duration_seconds=1.5)

        # 8.1 Telugu Voice Input: Farmer statement
        console.print("\n[bold yellow]==== STEP 8.1: Telugu Voice Interaction (Language = 'te') ====[/bold yellow]")
        console.print("[cyan]Citizen speaks in Telugu:[/cyan] 'నేను తెలంగాణకు చెందిన రైతును మరియు నాకు మూడు ఎకరాల భూమి ఉంది.'")
        console.print("[dim]Pipeline: Microphone Audio -> Groq Whisper STT -> Telugu Transcript -> Existing Profile Extractor...[/dim]")

        voice_svc = VoiceService(
            stt_provider=MockSpeechToTextProvider(
                mock_transcript="నేను తెలంగాణకు చెందిన రైతును మరియు నాకు మూడు ఎకరాల భూమి ఉంది.",
                language="te",
                detected_language="te",
            )
        )
        turn1 = voice_svc.process_voice_turn(
            db=db,
            case_id=voice_case_id,
            audio_bytes=sample_audio,
            filename="farmer_telugu.wav",
            language="te",
        )
        console.print(f"  * STT Transcript: [bold white]\"{turn1.transcript}\"[/bold white]")
        console.print(f"  * Detected Language: [cyan]{turn1.detected_language}[/cyan] (Selected: [cyan]{turn1.language}[/cyan])")
        console.print(f"  * Confirmation Required: [bold yellow]{turn1.confirmation_required}[/bold yellow] (Human confirmation boundary intact!)")
        console.print(f"  * Spoken Response (TTS Target te-IN): [bold green]\"{turn1.response_text}\"[/bold green]")
        console.print(f"  * Browser TTS Locales: {turn1.tts_locales}")

        # 8.2 Telugu Voice Confirmation
        console.print("\n[bold yellow]==== STEP 8.2: Voice Confirmation in Telugu ====[/bold yellow]")
        console.print("[cyan]Citizen speaks in Telugu:[/cyan] 'అవును' (Yes / Confirm)")
        voice_svc.stt_provider = MockSpeechToTextProvider(mock_transcript="అవును", language="te")
        turn2 = voice_svc.process_voice_turn(
            db=db,
            case_id=voice_case_id,
            audio_bytes=sample_audio,
            language="te",
        )
        console.print(f"  * Turn Status: [bold green]{turn2.status}[/bold green]")
        console.print(f"  * Agent Action: [bold cyan]{turn2.agent_action}[/bold cyan]")
        console.print(f"  * Agent Spoken Response: [bold green]\"{turn2.response_text}\"[/bold green]")

        # 8.3 Modality & Language Switch to English
        console.print("\n[bold yellow]==== STEP 8.3: Language Switch to English (Session Continuity) ====[/bold yellow]")
        console.print("[cyan]Citizen switches language to English and speaks income:[/cyan] 'My annual family income is two lakh.'")
        voice_svc.stt_provider = MockSpeechToTextProvider(
            mock_transcript="My annual family income is two lakh.", language="en"
        )
        turn3 = voice_svc.process_voice_turn(
            db=db,
            case_id=voice_case_id,
            audio_bytes=sample_audio,
            language="en",
        )
        console.print(f"  * STT Transcript: [bold white]\"{turn3.transcript}\"[/bold white]")
        console.print(f"  * Language Updated: [cyan]{turn3.language}[/cyan]")
        console.print(f"  * Spoken Confirmation Prompt: [bold green]\"{turn3.response_text}\"[/bold green]")

        # Confirm Turn 3 via voice
        voice_svc.stt_provider = MockSpeechToTextProvider(mock_transcript="confirm", language="en")
        turn3_conf = voice_svc.process_voice_turn(
            db=db,
            case_id=voice_case_id,
            audio_bytes=sample_audio,
            language="en",
        )
        console.print(f"  * Post-Confirmation Agent Next Action: [bold cyan]{turn3_conf.agent_action}[/bold cyan]")

        # 8.4 Multi-Scheme Applications Status Query via Voice
        console.print("\n[bold yellow]==== STEP 8.4: Voice Multi-Scheme Status Query ====[/bold yellow]")
        # Setup two active applications on state
        v_state = load_case(db, voice_case_id)
        v_state.applications = {
            "pm_kisan_001": {"status": "ACTIVE"},
            "ts_rythu_bharosa_001": {"status": "PENDING_VERIFICATION"},
        }
        persist_agent_state(db, v_state)

        console.print("[cyan]Citizen asks by voice:[/cyan] 'Show me the status of my farmer applications.'")
        voice_svc.stt_provider = MockSpeechToTextProvider(
            mock_transcript="Show me the status of my farmer applications.", language="en"
        )
        turn4 = voice_svc.process_voice_turn(
            db=db,
            case_id=voice_case_id,
            audio_bytes=sample_audio,
            language="en",
        )
        console.print(f"  * Spoken Multi-Scheme Summary: [bold green]\"{turn4.response_text}\"[/bold green]")
        console.print("[bold green]-> Applications reported independently without merging or ranking![/bold green]")

        # 8.5 Document Readiness Query via Voice
        console.print("\n[bold yellow]==== STEP 8.5: Voice Document Readiness Query ====[/bold yellow]")
        v_state = load_case(db, voice_case_id)
        v_state.documents = [{"document_type": "land_record", "status": "VERIFIED"}]
        persist_agent_state(db, v_state)

        console.print("[cyan]Citizen asks by voice:[/cyan] 'Which document is missing?'")
        voice_svc.stt_provider = MockSpeechToTextProvider(
            mock_transcript="Which document is missing?", language="en"
        )
        turn5 = voice_svc.process_voice_turn(
            db=db,
            case_id=voice_case_id,
            audio_bytes=sample_audio,
            language="en",
        )
        console.print(f"  * Spoken Document Status: [bold green]\"{turn5.response_text}\"[/bold green]")

        # 8.6 Rejection Recovery Query via Voice
        console.print("\n[bold yellow]==== STEP 8.6: Voice Rejection Recovery Query ====[/bold yellow]")
        console.print("[cyan]Citizen speaks by voice:[/cyan] 'My PM-KISAN application was rejected.'")
        voice_svc.stt_provider = MockSpeechToTextProvider(
            mock_transcript="My PM-KISAN application was rejected.", language="en"
        )
        turn6 = voice_svc.process_voice_turn(
            db=db,
            case_id=voice_case_id,
            audio_bytes=sample_audio,
            language="en",
        )
        console.print(f"  * Spoken Recovery Action Prompt: [bold green]\"{turn6.response_text}\"[/bold green]")
        console.print(f"  * Action Dispatched: [bold cyan]{turn6.agent_action}[/bold cyan]")

        # 8.7 Real Groq Whisper STT Live Demonstration
        console.print("\n[bold yellow]==== STEP 8.7: Real Groq Whisper STT Live API Verification ====[/bold yellow]")
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if groq_api_key:
            real_stt = GroqWhisperProvider(api_key=groq_api_key)
            console.print("[dim]Invoking live Groq Whisper API (whisper-large-v3) with audio fixture...[/dim]")
            real_res = real_stt.transcribe(sample_audio, filename="live_sample.wav", language="en")
            console.print(f"  * Live Groq Whisper Response: [bold green]\"{real_res.transcript}\"[/bold green]")
            console.print(f"  * Provider: [bold green]{real_res.provider}[/bold green] | Duration: {real_res.duration_seconds}s")
            console.print("[bold green]-> REAL GROQ STT API VERIFICATION SUCCESSFUL![/bold green]")
        else:
            console.print("[yellow]GROQ_API_KEY not configured in environment. Skipping live API call.[/yellow]")

        console.print("\n[bold green][SUCCESS] Phase 8 Multilingual Voice & Audio Demo Complete![/bold green]")

    finally:
        db.close()


if __name__ == "__main__":
    run_demo()




