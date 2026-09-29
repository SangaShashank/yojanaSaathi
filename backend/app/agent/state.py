"""
Yojana Saathi - Agent State Contract
"""

import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from backend.app.agent.actions import AgentAction


class StageEnum(str, Enum):
    INTAKE = "INTAKE"
    MISSING_INFO_COLLECTION = "MISSING_INFO_COLLECTION"
    CONTRADICTION_RESOLUTION = "CONTRADICTION_RESOLUTION"
    WAITING_FOR_PROFILE_CONFIRMATION = "WAITING_FOR_PROFILE_CONFIRMATION"
    PROFILE_CONFIRMED = "PROFILE_CONFIRMED"
    ELIGIBILITY_READY = "ELIGIBILITY_READY"
    ELIGIBILITY_EVALUATED = "ELIGIBILITY_EVALUATED"
    WAITING_FOR_USER_INPUT = "WAITING_FOR_USER_INPUT"
    ESCALATED = "ESCALATED"
    TERMINAL = "TERMINAL"


class TerminationReason(str, Enum):
    OBJECTIVE_COMPLETE = "OBJECTIVE_COMPLETE"
    NO_ACTIONABLE_INFORMATION = "NO_ACTIONABLE_INFORMATION"
    HUMAN_VERIFICATION_REQUIRED = "HUMAN_VERIFICATION_REQUIRED"
    CONTRADICTION_UNRESOLVED = "CONTRADICTION_UNRESOLVED"
    NO_SUPPORTED_MATCH = "NO_SUPPORTED_MATCH"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    INVALID_ACTION_FALLBACK = "INVALID_ACTION_FALLBACK"
    NO_PROGRESS = "NO_PROGRESS"


class Contradiction(BaseModel):
    """Represents a factual conflict in citizen input."""
    field: str
    existing_value: Any
    conflicting_value: Any
    source_turn_earlier: Optional[int] = None
    source_turn_current: Optional[int] = None
    resolved: bool = False


class AgentState(BaseModel):
    """
    Central persistent state observed and updated by the Agent Controller.
    Strictly isolated per case / session.
    """
    model_config = ConfigDict(extra="allow")

    case_id: str = "CASE-DEFAULT"
    goal: str = "Identify applicable welfare schemes and orchestrate readiness"

    # Profile & Knowledge state (Confirmed profile only)
    profile: Dict[str, Any] = Field(default_factory=dict)
    candidate_schemes: List[str] = Field(default_factory=list)
    evaluated_schemes: List[str] = Field(default_factory=list)
    scheme_evaluations: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    eliminated_schemes: List[str] = Field(default_factory=list)
    eligible_schemes: List[str] = Field(default_factory=list)
    selected_schemes: List[str] = Field(default_factory=list)

    # Multi-application tracking
    applications: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    active_scheme_id: Optional[str] = None
    active_application_id: Optional[str] = None

    # Language preference (Phase 8 Multilingual Voice & Audio: 'en', 'hi', 'te')
    language_preference: str = "en"

    # Information gaps & conditions
    missing_information: List[str] = Field(default_factory=list)
    scheme_missing_information: Dict[str, List[str]] = Field(default_factory=dict)
    unresolved_conditions: List[Dict[str, Any]] = Field(default_factory=list)

    # Interaction history
    asked_questions: List[str] = Field(default_factory=list)
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Contradictions & uncertainties
    contradictions: List[Contradiction] = Field(default_factory=list)
    uncertain_fields: List[str] = Field(default_factory=list)

    # Document tracking (prepared for Phase 5)
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    document_discrepancies: List[Dict[str, Any]] = Field(default_factory=list)

    # Phase 3 Confirmation & Staleness tracking
    pending_confirmation: Optional[Dict[str, Any]] = None
    evaluated_profile_fingerprint: Optional[str] = None

    # Loop control & observability
    stage: str = StageEnum.INTAKE.value
    iteration: int = 0
    max_iterations: int = 10

    last_action: Optional[AgentAction] = None
    last_state_fingerprint: Optional[str] = None
    consecutive_unchanged_iterations: int = 0
    termination_reason: Optional[str] = None
    is_terminated: bool = False

    def get_profile_fingerprint(self) -> str:
        """
        Computes a stable deterministic SHA-256 fingerprint of the confirmed profile.
        Used to detect when profile changes invalidate previous eligibility results.
        """
        clean_facts = {}
        for k, v in sorted(self.profile.items()):
            if v is not None and v != "UNKNOWN" and v != "unknown":
                clean_facts[k] = str(v)
        serialized = json.dumps(clean_facts, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def recompute_missing_information(self, all_schemes: Optional[List[Any]] = None) -> List[str]:
        """
        Recomputes missing critical fields based on candidate schemes and confirmed profile facts.
        """
        from backend.app.schemas.profile import CitizenProfile
        from backend.app.services.scheme_loader import load_all_schemes

        profile_obj = CitizenProfile.model_validate(self.profile)
        schemes = all_schemes or load_all_schemes()
        if len(self.candidate_schemes) > 0:
            schemes = [s for s in schemes if s.scheme_id in self.candidate_schemes]

        required_fields = set()
        unresolved_conds = []
        for scheme in schemes:
            for cond in scheme.eligibility.conditions:
                val, is_known = profile_obj.get_field_value(cond.field)
                if not is_known:
                    required_fields.add(cond.field)
                    unresolved_conds.append({
                        "scheme_id": scheme.scheme_id,
                        "field": cond.field,
                        "op": cond.op,
                    })

        self.missing_information = sorted(list(required_fields))
        self.unresolved_conditions = unresolved_conds
        return self.missing_information

    def invalidate_eligibility_if_stale(self) -> bool:
        """
        Checks if the confirmed profile fingerprint differs from the profile used during evaluation.
        If changed, marks previous eligibility evaluations as stale and clears cached results.
        Applications and selected schemes remain preserved.
        """
        current_fp = self.get_profile_fingerprint()
        if self.evaluated_profile_fingerprint and self.evaluated_profile_fingerprint != current_fp:
            has_results = (
                len(self.eligible_schemes) > 0
                or len(self.eliminated_schemes) > 0
                or len(self.evaluated_schemes) > 0
            )
            if has_results:
                self.eligible_schemes = []
                self.eliminated_schemes = []
                self.evaluated_schemes = []
                self.scheme_evaluations = {}
                self.scheme_missing_information = {}
                self.stage = (
                    StageEnum.ELIGIBILITY_READY.value
                    if len(self.missing_information) == 0
                    else StageEnum.MISSING_INFO_COLLECTION.value
                )
                return True
        return False

    def get_fingerprint(self) -> str:
        """
        Computes a stable deterministic SHA-256 fingerprint of the current state.
        Used to detect stale state and prevent infinite loops when actions produce no progress.
        """
        canonical_state = {
            "profile": {k: str(v) for k, v in sorted(self.profile.items())},
            "missing": sorted(self.missing_information),
            "candidates": sorted(self.candidate_schemes),
            "evaluated": sorted(self.evaluated_schemes),
            "eligible": sorted(self.eligible_schemes),
            "selected": sorted(self.selected_schemes),
            "active_scheme": str(self.active_scheme_id),
            "contradictions": [c.model_dump() for c in self.contradictions if not c.resolved],
            "stage": self.stage,
            "asked_questions": sorted(self.asked_questions),
        }
        serialized = json.dumps(canonical_state, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def mark_terminated(self, reason: TerminationReason | str) -> None:
        """Marks the Agent Controller state as safely terminated."""
        self.is_terminated = True
        self.termination_reason = reason.value if isinstance(reason, TerminationReason) else str(reason)
        self.stage = StageEnum.TERMINAL.value

    def add_asked_question(self, field_name: str, question_text: str) -> None:
        """Records an asked question to guard against repeated asking."""
        if field_name not in self.asked_questions:
            self.asked_questions.append(field_name)
        self.conversation_history.append({
            "speaker": "agent",
            "field": field_name,
            "text": question_text,
            "iteration": self.iteration,
        })
