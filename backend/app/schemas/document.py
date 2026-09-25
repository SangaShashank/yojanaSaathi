"""
Yojana Saathi - Document & Readiness Schemas
============================================
Pydantic contracts for scheme-specific document requirements, upload metadata,
structured extraction results, discrepancies, and application readiness.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class DocumentRequirementStatus(str, Enum):
    REQUIRED = "REQUIRED"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    INVALID = "INVALID"
    UNREADABLE = "UNREADABLE"
    REJECTED = "REJECTED"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNVERIFIED_REQUIREMENT = "UNVERIFIED_REQUIREMENT"


class DocumentRequirementSource(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class DiscrepancyType(str, Enum):
    VALUE_MISMATCH = "VALUE_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    MISSING_DOCUMENT_FIELD = "MISSING_DOCUMENT_FIELD"
    UNREADABLE = "UNREADABLE"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED_VERIFICATION = "UNSUPPORTED_VERIFICATION"


class DiscrepancyStatus(str, Enum):
    OPEN = "OPEN"
    USER_CONFIRMED_DOCUMENT = "USER_CONFIRMED_DOCUMENT"
    USER_CONFIRMED_PROFILE = "USER_CONFIRMED_PROFILE"
    UNRESOLVED = "UNRESOLVED"
    ESCALATED = "ESCALATED"


class ReadinessStatus(str, Enum):
    NOT_READY = "NOT_READY"
    PREPARATION_REQUIRED = "PREPARATION_REQUIRED"
    READY_FOR_HANDOFF = "READY_FOR_HANDOFF"
    HUMAN_VERIFICATION_REQUIRED = "HUMAN_VERIFICATION_REQUIRED"


class DocumentRequirement(BaseModel):
    requirement_id: str
    scheme_id: str
    document_type: str
    name: str
    required: bool = True
    purpose: Optional[str] = None
    verification_fields: List[str] = Field(default_factory=list)
    source_status: str = DocumentRequirementSource.VERIFIED.value


class ApplicationDocumentChecklistItem(BaseModel):
    requirement_id: str
    document_type: str
    name: str
    required: bool = True
    status: str = DocumentRequirementStatus.REQUIRED.value
    source_status: str = DocumentRequirementSource.VERIFIED.value
    document_id: Optional[str] = None
    discrepancy_ids: List[str] = Field(default_factory=list)


class DocumentExtractionResult(BaseModel):
    document_type: str
    fields: Dict[str, Any] = Field(default_factory=dict)
    unresolved_fields: List[str] = Field(default_factory=list)
    confidence_flags: List[str] = Field(default_factory=list)
    extraction_status: str = "SUCCESS"  # SUCCESS, FAILED, UNREADABLE, INVALID
    raw_text: Optional[str] = None


class DocumentDiscrepancyItem(BaseModel):
    discrepancy_id: str
    document_id: str
    application_id: Optional[str] = None
    field_name: str
    profile_value: Optional[Any] = None
    document_value: Optional[Any] = None
    discrepancy_type: str = DiscrepancyType.VALUE_MISMATCH.value
    status: str = DiscrepancyStatus.OPEN.value
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    document_id: str
    application_id: str
    requirement_id: Optional[str] = None
    document_type: str
    status: str
    processing_status: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    uploaded_at: str


class DocumentItemResponse(BaseModel):
    document_id: str
    application_id: str
    requirement_id: Optional[str] = None
    document_type: str
    status: str
    original_filename: Optional[str] = None
    size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    sha256: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    extraction_status: str
    verification_status: str
    discrepancies: List[DocumentDiscrepancyItem] = Field(default_factory=list)


class ApplicationReadiness(BaseModel):
    application_id: str
    scheme_id: str
    status: str  # ReadinessStatus
    total_requirements: int
    verified_requirements: int
    missing_documents: List[str] = Field(default_factory=list)
    mismatches: List[DocumentDiscrepancyItem] = Field(default_factory=list)
    unresolved_items: List[str] = Field(default_factory=list)
    requirements: List[ApplicationDocumentChecklistItem] = Field(default_factory=list)


class DiscrepancyResolutionRequest(BaseModel):
    resolution: Literal["KEEP_PROFILE", "USE_DOCUMENT", "ESCALATE"]
    reason: Optional[str] = None


class LinkDocumentRequest(BaseModel):
    target_application_id: str
    requirement_id: Optional[str] = None
