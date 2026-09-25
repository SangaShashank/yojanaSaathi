"""
Yojana Saathi - Profile Extraction & Confirmation Schemas
=========================================================
Strict Pydantic contracts for:
- Profile fact extraction results
- Field-level profile patches
- Human/CSC confirmation requests and items
- Profile observability events
"""

from enum import Enum
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.app.schemas.profile import CitizenProfile


class ConfirmationStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    REQUIRES_CORRECTION = "REQUIRES_CORRECTION"


# Set of valid citizen profile field names from CitizenProfile schema
SUPPORTED_PROFILE_FIELDS = set(CitizenProfile.model_fields.keys())


class ProfileChangeItem(BaseModel):
    """
    User/CSC-facing representation of a single field change.
    Judge- and demo-friendly: shows what was understood, what changed, and what needs confirmation.
    """
    field: str
    previous: Optional[Any] = None
    proposed: Any


class ProfilePatch(BaseModel):
    """
    Field-level patch representing proposed modifications to a CitizenProfile.
    Strictly forbids arbitrary or unsupported fields.
    """
    model_config = ConfigDict(extra="forbid")

    changes: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("changes")
    @classmethod
    def validate_supported_fields(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        unsupported = [k for k in v.keys() if k not in SUPPORTED_PROFILE_FIELDS]
        if unsupported:
            raise ValueError(
                f"Unsupported profile field(s) rejected: {unsupported}. "
                f"Only fields defined in CitizenProfile are allowed."
            )
        return v


class ProfileExtractionResult(BaseModel):
    """
    Structured fact extraction output returned by the ProfileExtractor.
    Ensures that LLM output adheres to strict types and canonical schema fields.
    """
    model_config = ConfigDict(extra="forbid")

    changes: Dict[str, Any] = Field(default_factory=dict)
    explicitly_stated_fields: List[str] = Field(default_factory=list)
    ambiguous_fields: List[str] = Field(default_factory=list)
    unresolved_fields: List[str] = Field(default_factory=list)
    needs_confirmation: bool = True

    @field_validator("changes")
    @classmethod
    def validate_changes(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        unsupported = [k for k in v.keys() if k not in SUPPORTED_PROFILE_FIELDS]
        if unsupported:
            raise ValueError(
                f"Unsupported profile field(s) in extraction: {unsupported}."
            )
        return v


class ProfileConfirmation(BaseModel):
    """
    Structured confirmation state presenting proposed changes for human/CSC review.
    """
    confirmation_id: str = Field(default_factory=lambda: f"CONF-{uuid.uuid4().hex[:8].upper()}")
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    confirmation_required: bool = True
    changes: List[ProfileChangeItem] = Field(default_factory=list)
    raw_patch: Dict[str, Any] = Field(default_factory=dict)


class ProfileActivityEvent(BaseModel):
    """
    Observability event for profile extraction, confirmation, correction, and rejection.
    Ensures safe structured telemetry without leaking raw sensitive data or chain-of-thought.
    """
    event_type: str  # e.g., 'PROFILE_EXTRACTION', 'PROFILE_CONFIRMATION', 'PROFILE_CORRECTION', 'PROFILE_REJECTION'
    fields_detected: List[str] = Field(default_factory=list)
    fields_confirmed: List[str] = Field(default_factory=list)
    field: Optional[str] = None
    status: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
