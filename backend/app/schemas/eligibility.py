"""
Yojana Saathi - Deterministic Eligibility Result Schemas
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CriterionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class SchemeOutcome(str, Enum):
    FULLY_ELIGIBLE = "FULLY_ELIGIBLE"
    ACTIONABLE_PREPARATION_REQUIRED = "ACTIONABLE_PREPARATION_REQUIRED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INCOMPLETE_UNKNOWN = "INCOMPLETE / UNKNOWN"


class CriterionResult(BaseModel):
    """
    Detailed result for a single eligibility condition.
    """
    model_config = ConfigDict(extra="allow")

    field: str
    status: CriterionStatus
    actual: Any = None
    expected: Any = None
    reason: str
    operator: str
    is_disputed: bool = False
    note: Optional[str] = None


class SchemeEvaluationResult(BaseModel):
    """
    Result of deterministic evaluation for a single scheme.
    """
    model_config = ConfigDict(extra="allow")

    scheme_id: str
    scheme_title: str
    outcome: SchemeOutcome
    criterion_results: List[CriterionResult] = Field(default_factory=list)
    passed_criteria: List[CriterionResult] = Field(default_factory=list)
    failed_criteria: List[CriterionResult] = Field(default_factory=list)
    unresolved_criteria: List[CriterionResult] = Field(default_factory=list)
    missing_critical_fields: List[str] = Field(default_factory=list)
    summary_reason: str = ""
    disputed_fields: List[str] = Field(default_factory=list)


class MultiSchemeEvaluationResult(BaseModel):
    """
    Result of evaluating a citizen profile across multiple schemes.
    """
    model_config = ConfigDict(extra="allow")

    total_schemes_evaluated: int = 0
    evaluations: Dict[str, SchemeEvaluationResult] = Field(default_factory=dict)
    fully_eligible_schemes: List[str] = Field(default_factory=list)
    actionable_schemes: List[str] = Field(default_factory=list)
    not_eligible_schemes: List[str] = Field(default_factory=list)
    incomplete_schemes: List[str] = Field(default_factory=list)
