"""Bounded deterministic decoder. Signals are intentionally conservative, never policy claims."""
import re
from backend.app.schemas.rejection import RejectionCategory, RejectionDecodeResult

SIGNALS = {
 RejectionCategory.AADHAAR_BANK_NPCI_MAPPING.value: ("aadhaar bank", "npci", "aadhaar mapping", "bank linking"),
 RejectionCategory.INVALID_INACTIVE_BANK_ACCOUNT.value: ("account inactive", "inactive bank account", "invalid account", "bank account inactive", "bank account is inactive", "account is inactive"),
 RejectionCategory.INVALID_BANK_OR_IFSC.value: ("invalid ifsc", "incorrect ifsc", "invalid bank", "bank details invalid"),
 RejectionCategory.BENEFICIARY_LAND_RECORD_MISMATCH.value: ("land record mismatch", "beneficiary mismatch", "land mismatch"),
 RejectionCategory.ELIGIBILITY_OR_VERIFICATION_ISSUE.value: ("eligibility verification", "verification failed", "eligibility issue"),
}

class RejectionDecoder:
 @classmethod
 def decode(cls,evidence_id,text,code=None):
  normalized=" ".join((text or "").lower().split()); hits=[]; signals=[]
  for category,terms in SIGNALS.items():
   found=next((term for term in terms if term in normalized),None)
   if found: hits.append(category); signals.append(found)
  # Unknown codes are intentionally never mapped; a known-code catalog is not configured.
  if code and not hits: return RejectionDecodeResult(evidence_id=evidence_id,status="UNSUPPORTED",matched_codes=[],matched_signals=[],requires_human_verification=True)
  if not hits: return RejectionDecodeResult(evidence_id=evidence_id,status="UNSUPPORTED",requires_human_verification=True)
  if "ambiguous" in normalized or "or" in normalized and len(hits)>1: return RejectionDecodeResult(evidence_id=evidence_id,status="AMBIGUOUS",categories=hits,matched_signals=signals,requires_human_verification=True)
  return RejectionDecodeResult(evidence_id=evidence_id,status="SUPPORTED",categories=hits,matched_signals=signals)
