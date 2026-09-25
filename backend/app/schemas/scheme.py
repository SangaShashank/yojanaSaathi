"""
Yojana Saathi - Scheme Definition Schemas
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConditionDefinition(BaseModel):
    """
    Single eligibility condition definition from the dataset.
    """
    model_config = ConfigDict(extra="allow")

    field: str
    op: str
    value: Any = None
    scope: Optional[str] = None
    applies_only_if: Optional[str] = None
    then_requires: Optional[str] = None
    exception: Optional[str] = None
    exception_value: Optional[Any] = None
    disputed: Optional[bool] = False
    note: Optional[str] = None
    conflicting_values_months: Optional[List[int]] = None


class EligibilityDefinition(BaseModel):
    """
    Eligibility block of a scheme.
    """
    model_config = ConfigDict(extra="allow")

    critical_fields: List[str] = Field(default_factory=list)
    conditions: List[ConditionDefinition] = Field(default_factory=list)
    notes: Optional[str] = None


class RequiredDocument(BaseModel):
    """
    Document required for a scheme application.
    """
    model_config = ConfigDict(extra="allow")

    doc_id: str
    name_en: str
    name_hi: Optional[str] = None
    name_te: Optional[str] = None
    is_mandatory: bool = True
    source_office: Optional[str] = None


class SchemeDefinition(BaseModel):
    """
    Complete scheme definition matching schemes_dataset_v2.json schema.
    """
    model_config = ConfigDict(extra="allow")

    scheme_id: str
    schema_version: str = "2.0"
    niche: str
    title_en: str
    title_hi: Optional[str] = None
    title_te: Optional[str] = None
    ministry: str
    target_audience: List[str] = Field(default_factory=list)
    state_restriction: Optional[str] = None
    benefit: Dict[str, Any] = Field(default_factory=dict)
    eligibility: EligibilityDefinition = Field(default_factory=EligibilityDefinition)
    relationships: Dict[str, Any] = Field(default_factory=dict)
    required_documents: List[RequiredDocument] = Field(default_factory=list)
    official_portal_url: Optional[str] = None
    last_verified: Optional[str] = None
    disputed_fields: List[str] = Field(default_factory=list)
    verify_before_demo: List[str] = Field(default_factory=list)
