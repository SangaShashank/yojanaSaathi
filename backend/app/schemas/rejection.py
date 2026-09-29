from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
class RejectionCategory(str, Enum):
    AADHAAR_BANK_NPCI_MAPPING="AADHAAR_BANK_NPCI_MAPPING"; INVALID_INACTIVE_BANK_ACCOUNT="INVALID_INACTIVE_BANK_ACCOUNT"; INVALID_BANK_OR_IFSC="INVALID_BANK_OR_IFSC"; BENEFICIARY_LAND_RECORD_MISMATCH="BENEFICIARY_LAND_RECORD_MISMATCH"; ELIGIBILITY_OR_VERIFICATION_ISSUE="ELIGIBILITY_OR_VERIFICATION_ISSUE"
class RejectionEvidenceRequest(BaseModel):
    source_type: str; raw_text: Optional[str]=None; rejection_code: Optional[str]=None; provided_by: str="CITIZEN"
class RejectionDecodeResult(BaseModel):
    evidence_id: str; status: str; categories: List[str]=Field(default_factory=list); matched_codes: List[str]=Field(default_factory=list); matched_signals: List[str]=Field(default_factory=list); requires_human_verification: bool=False
class RecoveryStateResponse(BaseModel):
    application_id: str; status: str; recovery_status: str; rejection_categories: List[str]=Field(default_factory=list); next_action: Optional[str]=None; human_verification_required: bool=False
class RecoveryActionRequest(BaseModel):
    action: str; evidence_note: Optional[str]=None
