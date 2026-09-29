"""Public Phase 6 contracts. All values describe preparation, never government submission."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PreSubmissionVerification(BaseModel):
    application_id: str
    scheme_id: str
    profile_confirmed: bool
    eligibility_current: bool
    eligibility_outcome: Optional[str] = None
    readiness_status: Optional[str] = None
    blocking_items: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    verified_at: datetime

    @property
    def passed(self) -> bool:
        return not self.blocking_items


class PackageArtifact(BaseModel):
    package_id: str
    download_url: str
    format: str = "PDF"


class HandoffPackageResponse(BaseModel):
    package_id: str
    case_id: str
    application_id: str
    scheme_id: str
    status: str
    readiness: str
    reference_sheet_available: bool
    dossier_available: bool
    generated_at: datetime
    reference_sheet: Optional[PackageArtifact] = None
    dossier: Optional[PackageArtifact] = None


class HandoffPackageData(BaseModel):
    """Structured snapshot used to render both printable artifacts."""
    case_id: str
    application_id: str
    scheme_id: str
    scheme_name: str
    application_status: str
    profile_fingerprint: str
    profile: Dict[str, Any]
    eligibility_outcome: str
    eligibility_reasons: Dict[str, Any] = Field(default_factory=dict)
    readiness: Dict[str, Any]
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    discrepancies: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime
