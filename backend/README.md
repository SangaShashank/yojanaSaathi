# Yojana Saathi - Deterministic Eligibility Core (Phase 1)

This module implements **Phase 1: Deterministic Core** of **Yojana Saathi**. It is a standalone, deterministic Python rules engine that evaluates citizen profiles against versioned government scheme definitions from `schemes_dataset_v2.json`.

**ZERO LLM or probabilistic reasoning is involved in eligibility evaluation.**

---

## 1. Directory Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── profile.py       # CitizenProfile schema & field alias resolver
│   │   ├── scheme.py        # SchemeDefinition & Condition models
│   │   └── eligibility.py   # CriterionResult, SchemeOutcome & Evaluation models
│   ├── rules/
│   │   ├── __init__.py
│   │   └── operators.py     # Pure deterministic operators (eq, gte, lte, gt, in, not_in)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── scheme_loader.py # Loader & validator for schemes_dataset_v2.json
│   │   └── eligibility_engine.py # Core deterministic eligibility engine
│   └── data/
│       ├── __init__.py
│       └── schemes_dataset_v2.json # Embedded dataset copy
├── tests/
│   ├── __init__.py
│   ├── test_operators.py    # Unit tests for all comparison and inclusion operators
│   ├── test_eligibility_engine.py # Core engine tests, UNKNOWN semantics, boundaries
│   └── test_real_schemes.py # Tests evaluating real schemes from schemes_dataset_v2.json
├── run_demo.py              # Interactive CLI demo runner
└── README.md
```

---

## 2. Core API

The engine provides two primary entry points in `backend.app.services.eligibility_engine`:

```python
from backend.app.schemas.profile import CitizenProfile
from backend.app.services.scheme_loader import get_scheme, load_all_schemes
from backend.app.services.eligibility_engine import evaluate_eligibility, evaluate_all_schemes

# 1. Evaluate single scheme
profile = CitizenProfile(
    age=35,
    state="Telangana",
    land_ownership=True,
    land_record_date="2018-05-15",
    occupation="farmer",
    farmer_id_status="registered"
)
scheme = get_scheme("pm_kisan_001")
result = evaluate_eligibility(profile, scheme)

print(result.outcome)  # SchemeOutcome.FULLY_ELIGIBLE
for c in result.criterion_results:
    print(c.field, c.status, c.reason)

# 2. Evaluate all 13 configured schemes independently
all_results = evaluate_all_schemes(profile)
print("Eligible:", all_results.fully_eligible_schemes)
print("Not eligible:", all_results.not_eligible_schemes)
print("Incomplete:", all_results.incomplete_schemes)
```

---

## 3. Supported Rule Operators

The engine supports all operators required by `schemes_dataset_v2.json` and master specification aliases:

| Operator | Aliases | Description |
|---|---|---|
| `eq` | `EQUALS` | Value equality. Supports numbers, booleans, dates (`YYYY-MM-DD`), and case-insensitive strings. |
| `gte` | `GREATER_THAN_OR_EQUAL` | Greater than or equal to (numeric and chronological dates). |
| `lte` | `LESS_THAN_OR_EQUAL` | Less than or equal to (numeric and chronological dates, e.g. PM-KISAN cutoff). |
| `gt` | `GREATER_THAN` | Strictly greater than (numeric and chronological dates). |
| `lt` | `LESS_THAN` | Strictly less than (numeric and chronological dates). |
| `in` | `IN` | Collection membership (case-insensitive for string collections). |
| `not_in` | `NOT_IN` | Collection exclusion (case-insensitive for string collections). |
| `any_of` | - | Compound evaluation: passes if any qualifying sub-condition is satisfied. |

### Condition Extensions Handled:
- `then_requires`: Implication rules ($P \to Q$). For example, KCC requires a co-borrower only if applicant age $> 60$. If applicant age $\le 60$, the rule is skipped/satisfied.
- `applies_only_if`: Prerequisite filters (e.g. `user_state == Telangana` or `category == widow`). Skipped if the applicant profile does not match.
- `scope`: Geographic or demographic sub-caps (e.g. rural vs. urban income ceilings).
- `exception`: Specific occupational exemptions (e.g. Anganwadi/ASHA workers under PMMVY).

---

## 4. Strict UNKNOWN Semantics

`UNKNOWN` represents missing or unverified information. It is **never** treated as `0`, `False`, empty string, or "pass by default":

1. If a required field is missing from `CitizenProfile` or set to `None`/`"UNKNOWN"`:
   - The criterion status evaluates to `UNKNOWN`.
   - The criterion reason explicitly states that the field is missing.
2. Scheme Outcome Decision:
   - **`NOT_ELIGIBLE`**: Triggered if any single rule evaluates to `FAIL` (failure is decisive even if other fields are unknown).
   - **`INCOMPLETE / UNKNOWN`**: Triggered if zero rules fail, but one or more required rules are `UNKNOWN`.
   - **`FULLY_ELIGIBLE`**: Triggered if and only if **all** configured conditions evaluate to `PASS` (or `SKIPPED`).
   - **`ACTIONABLE_PREPARATION_REQUIRED`**: Reserved for cases where core eligibility is satisfied, but readiness or mandatory documents require preparation.

---

## 5. Disputed Fields Safety

`schemes_dataset_v2.json` flags disputed government rules (e.g. `application_days_after_marriage` in Kalyana Lakshmi with conflicting values between 3 and 6 months, and `value: null`).

The engine:
- Never hallucinates an unverified government threshold.
- Flags conditions with `value: null` and `disputed: true` as `UNKNOWN`, with a reason citing the unresolved official dispute.
- Preserves all `disputed_fields` in the evaluation output.

---

## 6. Phase 2: Agent Controller Loop

Phase 2 implements the central **Agent Controller** (`backend/app/agent/controller.py`). The Agent dynamically decides the next valid action based on the current `AgentState`, avoiding any fixed linear questionnaire (`for question in questions`).

### The Real Agentic Loop:
```text
OBSERVE STATE
    ↓
IDENTIFY UNRESOLVED CONDITIONS
    ↓
GENERATE VALID ACTIONS
    ↓
SELECT NEXT ACTION (Gemini or Deterministic Policy)
    ↓
VALIDATE ACTION (ActionValidator)
    ↓ (if invalid: fallback policy or ESCALATE_HUMAN)
EXECUTE ACTION / CONTROLLED TOOL (ActionDispatcher)
    ↓
UPDATE STATE & CHECK PROGRESS (Fingerprint verification)
    ↓
CHECK TERMINATION
    ↓
OBSERVE AGAIN
```

### Action Types & Reason Codes:
- `ASK_QUESTION` (`MAX_EXPECTED_NARROWING`): Triggered when critical fields are missing.
- `RUN_ELIGIBILITY` (`ELIGIBILITY_READY`): Invokes the Phase 1 deterministic rules engine as an authoritative tool.
- `RESOLVE_CONTRADICTION` (`RESOLVE_CONTRADICTION`): Reconciles factual contradictions in citizen input.
- `NO_SUPPORTED_MATCH` (`NO_SUPPORTED_MATCH`): Terminal workflow state when zero configured schemes match.
- `FINISH` (`TERMINAL_STATE`): Reached when the objective is complete.
- `ESCALATE_HUMAN` (`HUMAN_VERIFICATION_REQUIRED`): Safe escape hatch to CSC operator.

### Loop-Safety Guards:
1. **Max Iterations Protection**: Halts the loop if `iteration > max_iterations` (`TerminationReason.MAX_ITERATIONS`).
2. **Stale-State / No-Progress Detection**: Computes a SHA-256 state fingerprint on canonical fields. If consecutive iterations produce no state changes, terminates safely with `TerminationReason.NO_PROGRESS`.
3. **Repeated-Question Protection**: Prevents re-asking the exact same question if the citizen has not answered.
4. **Validation Fallback**: Bounded fallback to deterministic policy if Gemini proposes an invalid action.

---

## 7. Phase 3: Profile Extraction, Correction & Human Confirmation

Phase 3 implements the profile acquisition and human-in-the-loop confirmation layer. It converts natural-language user text into structured profile facts, manages field-level patches, gates all updates behind explicit Human/CSC confirmation, supports natural-language and manual corrections, and guarantees that only confirmed profile facts flow into the deterministic Phase 1 eligibility engine.

### Core Architectural Flow:
```text
USER MESSAGE
    ↓
PROFILE EXTRACTION (Gemini Structured Output / Deterministic Fallback)
    ↓
PROPOSED PROFILE CHANGES (ProfilePatch & ProfileChangeItem list)
    ↓
HUMAN / CSC CONFIRMATION (CONFIRM / REJECT / CORRECT)
    ↓
CONFIRMED PROFILE (CitizenProfile in AgentState)
    ↓
UPDATE AGENT STATE (Fingerprint update & Eligibility staleness check)
    ↓
AGENT OBSERVES NEW STATE (AgentController)
    ↓
NEXT ACTION (ASK_QUESTION or RUN_ELIGIBILITY when ready)
```

### Safety Boundaries:
1. **Gemini is Never Authoritative**: Gemini extracts or proposes facts. Only explicit Human/CSC confirmation can update `state.profile`.
2. **Deterministic Eligibility Protection**: The Phase 1 engine evaluates **only confirmed facts**. Unconfirmed proposals or ambiguous claims cannot enter eligibility.
3. **Eligibility Staleness & Invalidation**: When an eligibility-relevant confirmed field changes after evaluation, cached results are marked stale, cleared, and recomputed when ready.
4. **Field-Level Patches**: Updates are targeted (`ProfilePatch`). Unrelated confirmed fields are strictly preserved.
5. **No Hallucination**: Missing fields stay `UNKNOWN`. Ambiguous phrases (e.g., "I have five") trigger clarification instead of arbitrary assignment.
6. **Prompt Injection Defense**: User messages are treated as untrusted data; attempts to alter rules or force eligibility are ignored.

---

---

## 8. Database Persistence Layer (PostgreSQL + SQLAlchemy 2.x + Alembic)

Yojana Saathi features a persistent relational data layer built with **PostgreSQL**, **SQLAlchemy 2.x**, **Psycopg 3**, and **Alembic**. It provides atomic persistence for cases, profiles, applications, evaluations, confirmations, and agent observability events.

### Entity Architecture:
```text
  users (Citizen / Operator accounts)
    │
    ▼
  cases (Assistance sessions)
    ├── profiles (Authoritative confirmed profile, JSONB, fingerprint, version)
    ├── applications (Multi-scheme application tracking, Unique(case_id, scheme_id))
    │     ├── documents (Document metadata & file storage references)
    │     │     └── document_discrepancies (Field-level mismatches)
    │     └── application_events (Lifecycle changes)
    ├── scheme_evaluations (Deterministic eligibility results, profile fingerprint, staleness)
    ├── human_confirmations (Proposed profile patches, diffs, human review status)
    └── agent_events (Structured agent activity audit log)

  schemes (Catalog of official welfare schemes seeded from schemes_dataset_v2.json)
```

---

## 9. Development Setup & Database Workflow

Follow these exact steps to initialize and run the persistent backend:

### Step 1: Install Dependencies
```bash
pip install "sqlalchemy>=2.0.0" "psycopg[binary]>=3.1.0" "alembic>=1.13.0" "fastapi>=0.110.0" "uvicorn>=0.28.0" python-dotenv
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and fill in your real credentials:
```bash
# In .env (Git-ignored)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=yojana_saathi
POSTGRES_USER=yojana_saathi
POSTGRES_PASSWORD=your_secure_password
DATABASE_URL=postgresql+psycopg://yojana_saathi:your_secure_password@localhost:5432/yojana_saathi
```

### Step 3: Start PostgreSQL
Ensure local PostgreSQL service is running, or start via Docker:
```bash
docker compose up -d
```

### Step 4: Run Alembic Database Migrations
Create all 11 tables, foreign keys, unique constraints, and indexes:
```bash
alembic upgrade head
```

To rollback:
```bash
alembic downgrade -1
```

### Step 5: Seed Scheme Catalog
Idempotently seed all 13 welfare schemes from `schemes_dataset_v2.json` into PostgreSQL:
```bash
python -m backend.scripts.seed
```

### Step 6: Start FastAPI Application Server
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 7: Verify Database Health Endpoint
```bash
curl http://127.0.0.1:8000/health/db
# Returns: {"status": "ok", "database": "ok"}
```

---

---

## 10. Phase 4 — Multi-Scheme Handling & Parallel Application Tracks

Phase 4 enables Yojana Saathi to evaluate all relevant supported schemes independently, present unranked outcomes to citizens/operators, support multi-scheme selection, and create independent application tracks with strict state isolation.

### Core Architectural Principles:
1. **Zero Ranking / Zero Scoring**: Schemes are presented with factual eligibility status without "best", "top", "winner", or priority ordering. The citizen/CSC operator decides which eligible/actionable schemes to pursue.
2. **Distinct Semantic Outcomes**:
   - `FULLY_ELIGIBLE`: All core eligibility conditions satisfied.
   - `ACTIONABLE_PREPARATION_REQUIRED`: Core eligibility satisfied, but downstream preparation/readiness remains. (Not failed eligibility).
   - `NOT_ELIGIBLE`: One or more core criteria failed.
   - `INCOMPLETE / UNKNOWN`: Missing eligibility-critical information.
3. **Candidate Schemes vs. Selected Schemes**: Being eligible does not mean selected. Applications are only created for schemes explicitly chosen by the citizen/operator.
4. **Parallel Processing & State Isolation**: Each selected scheme creates an independent `Application` record (`UNIQUE(case_id, scheme_id)`). Transitioning Application A (e.g. to `PREPARING`) leaves Application B (e.g. `SELECTED`) untouched.
5. **Profile Fingerprinting & Application Preservation**: When confirmed profile data changes, affected evaluations are marked stale, but application records survive intact and can be cleanly re-evaluated against the new profile fingerprint.
6. **Scheme-Specific Missing Information**: The agent tracks missing fields per scheme (e.g. `pm_kisan_001` requires `farmer_id_status`, `ts_rythu_bharosa_001` requires `land_record_date`) and prioritizes questions accordingly.

### Multi-Scheme REST API Endpoints:
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/cases/{case_id}/schemes/evaluate` | Evaluates all supported candidate schemes independently against confirmed profile. |
| `GET` | `/api/cases/{case_id}/schemes` | Returns current per-scheme evaluation outcomes and selectability without ranking. |
| `POST` | `/api/cases/{case_id}/schemes/select` | Transactionally selects schemes and creates independent application records. |
| `GET` | `/api/cases/{case_id}/applications` | Lists all active applications for the case. |
| `GET` | `/api/cases/{case_id}/applications/{application_id}` | Retrieves a single application track. |
| `POST` | `/api/cases/{case_id}/applications/{application_id}/activate` | Sets the application as the active conversational track. |
| `POST` | `/api/cases/{case_id}/applications/{application_id}/status` | Updates the application status (isolated to that application). |

---

## 11. Phase 5 — Documents & Readiness Subsystem

Phase 5 introduces an end-to-end, scheme-aware document and readiness subsystem that guides citizens and CSC operators from application selection through document collection, structured validation, profile cross-checking, discrepancy resolution, and deterministic handoff readiness.

### Core Architectural Principles:
1. **Scheme-Aware Document Requirements (Truthfulness & No Fabrication)**:
   - Official document requirements are sourced strictly from `schemes_dataset_v2.json`.
   - If a scheme has no verified document configuration, it is explicitly flagged as `UNVERIFIED` / `NOT_CONFIGURED`.
   - The system NEVER presents an invented requirement as an official government policy.
2. **Secure Upload & Storage Abstraction**:
   - Files are validated for size (<= 10MB), supported MIME types (`application/pdf`, `image/jpeg`, `image/png`), safe sanitized filenames, and file magic bytes (`%PDF`, `\xFF\xD8\xFF`, `\x89PNG`).
   - Physical storage is abstracted via `StorageAdapter` (`backend/app/integrations/storage.py`), isolating local storage from public URLs and preventing path traversal attacks.
   - SHA-256 content hashing provides deduplication and tamper detection.
3. **Structured Document Extraction & Prompt Injection Defense**:
   - `DocumentProcessor` uses `pypdf` to extract text from PDFs and maps them into structured fields (`name`, `land_holding_acres`, `survey_number`, `district`, `state`).
   - Unknown values remain strictly unknown; missing fields are never hallucinated.
   - Malicious prompt injection strings (e.g., `IGNORE ALL PREVIOUS INSTRUCTIONS`) embedded within document text are treated as unparsed text and cannot manipulate system instructions, tool dispatch, or eligibility outcomes.
4. **Hard Non-Negotiable Rule: Document Mismatch is NEVER an Eligibility Failure**:
   - A discrepancy between a document and the citizen profile (e.g., profile says 3.0 acres, document says 4.5 acres) does **NOT** reject or disqualify the application (`NOT_ELIGIBLE`, `REJECTED`, or `FAILED` are forbidden).
   - The discrepancy is surfaced as `HUMAN_VERIFICATION_REQUIRED`.
   - The citizen or CSC operator chooses the resolution:
     - `KEEP_PROFILE`: Confirms profile data remains authoritative.
     - `USE_DOCUMENT`: Accepts document fact as the new profile fact. Routed through the existing Phase 3 confirmation mechanism (`ProfileCoordinator`), updating the confirmed profile, invalidating stale scheme evaluations, and triggering re-evaluation and readiness recomputation.
     - `ESCALATE`: Flagged for CSC supervisor review.
5. **Deterministic Readiness vs. Eligibility Separation**:
   - Eligibility is determined solely by the Phase 1 deterministic rules engine.
   - Readiness is computed per application by `ReadinessEngine`:
     - `READY_FOR_HANDOFF`: All configured mandatory requirements are verified with zero open discrepancies.
     - `PREPARATION_REQUIRED`: One or more mandatory documents are missing or pending upload/processing.
     - `HUMAN_VERIFICATION_REQUIRED`: An open discrepancy or ambiguous document requires human intervention.
     - `NOT_READY`: Unconfigured or invalid prerequisites.
6. **Strict Multi-Application State Isolation**:
   - Uploading or verifying a document on Application A (e.g., PM-KISAN) does NOT leak into or alter Application B (e.g., Rythu Bharosa) unless explicitly shared via `/link`.
7. **Agent Actions**:
   - Controlled, allowlisted actions: `REQUEST_DOCUMENT`, `PROCESS_DOCUMENT`, `VERIFY_DOCUMENT`, `RESOLVE_DOCUMENT_DISCREPANCY`, `CALCULATE_READINESS`, `READY_FOR_HANDOFF`, `ESCALATE_HUMAN`.

### Document & Readiness REST API Endpoints:
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/cases/{case_id}/applications/{application_id}/documents` | Retrieves the application-specific document checklist and linked documents. |
| `POST` | `/api/cases/{case_id}/applications/{application_id}/documents` | Secure multipart file upload with validation, SHA-256 deduplication, and storage. |
| `GET` | `/api/cases/{case_id}/applications/{application_id}/documents/{document_id}` | Retrieves document detail, extraction results, and verification status. |
| `POST` | `/api/cases/{case_id}/applications/{application_id}/documents/{document_id}/process` | Processes document, extracts structured fields, and runs profile comparison. |
| `POST` | `/api/cases/{case_id}/applications/{application_id}/documents/{document_id}/resolve` | Resolves a discrepancy (`KEEP_PROFILE`, `USE_DOCUMENT`, or `ESCALATE`). |
| `GET` | `/api/cases/{case_id}/applications/{application_id}/readiness` | Returns deterministic readiness status, requirements checklist, and open mismatches. |
| `POST` | `/api/cases/{case_id}/applications/{application_id}/documents/{document_id}/link` | Explicitly shares a verified document with another application track. |

---

## 12. How to Run Tests and Demo

### Run Full Test Suite (164 Tests: Phase 1, Phase 2, Phase 3, Persistence, Phase 4 Multi-Scheme, and Phase 5 Documents & Readiness):
```bash
pytest -v
```

### Run Dedicated Phase 5 Documents & Readiness Tests (32 Tests):
```bash
pytest backend/tests/test_documents_and_readiness.py -v
```

### Run Dedicated Phase 4 Multi-Scheme Tests (24 Tests):
```bash
pytest backend/tests/test_multi_scheme.py -v
```

### Run Dedicated Database Integration Tests:
```bash
pytest backend/tests/test_database_integration.py -v
```

### Run Unified CLI Demo (Phases 1–5 End-to-End):
```bash
python backend/run_demo.py
```

