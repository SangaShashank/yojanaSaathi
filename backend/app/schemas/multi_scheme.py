"""
Yojana Saathi - Multi-Scheme Schemas and Lifecycle Contracts
============================================================
Pydantic contracts for Phase 4 multi-scheme evaluation, selection,
and application lifecycle tracking.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ApplicationStatus(str, Enum):
    """
    Application lifecycle statuses.
    Keeps application workflow distinct from eligibility evaluation outcome.
    """
    ELIGIBILITY_PENDING = "ELIGIBILITY_PENDING"
    ELIGIBLE = "ELIGIBLE"
    ACTIONABLE = "ACTIONABLE"
    SELECTED = "SELECTED"
    PREPARING = "PREPARING"

    # Schema-compatible future states (Phase 5/6/7)
    READY_FOR_HANDOFF = "READY_FOR_HANDOFF"
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class SchemeOutcomeItem(BaseModel):
    """
    Per-scheme evaluation response item.
    STRICT RULE: Contains zero rank, score, or recommendation fields.
    """
    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    scheme_name: str
    outcome: str
    eligible: bool
    selectable: bool
    missing_information: List[str] = Field(default_factory=list)
    failed_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    unknown_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    summary_reason: str = ""
    profile_fingerprint: str = ""
    rules_version: str = "2.0"
    evaluated_at: Optional[str] = None
    application_id: Optional[str] = None


class SchemeEvaluationListResponse(BaseModel):
    """
    User/CSC-facing list of evaluated schemes.
    Does not rank or recommend.
    """
    model_config = ConfigDict(extra="forbid")

    case_id: str
    profile_fingerprint: str
    total_evaluated: int
    schemes: List[SchemeOutcomeItem] = Field(default_factory=list)


class SelectSchemesRequest(BaseModel):
    """
    Structured request for citizen/CSC scheme selection.
    """
    model_config = ConfigDict(extra="forbid")

    selected_scheme_ids: List[str] = Field(
        ..., min_length=1, description="List of unique selectable scheme IDs to create applications for"
    )


class ApplicationItemResponse(BaseModel):
    """
    Application track details for a single scheme.
    """
    model_config = ConfigDict(extra="forbid")

    application_id: str
    case_id: str
    scheme_id: str
    scheme_name: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ApplicationListResponse(BaseModel):
    """
    List of active scheme applications tied to a case.
    """
    model_config = ConfigDict(extra="forbid")

    case_id: str
    applications: List[ApplicationItemResponse] = Field(default_factory=list)


class UpdateApplicationStatusRequest(BaseModel):
    """
    Request to update a single application track status.
    """
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus
