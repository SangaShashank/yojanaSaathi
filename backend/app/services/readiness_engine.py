"""
Yojana Saathi - Application Readiness Engine
============================================
Computes deterministic per-application readiness based on:
1. Document requirement satisfaction
2. Verification status
3. Open document/profile discrepancies

Key Rules:
- Readiness is strictly separate from Phase 1 eligibility.
- A missing document produces PREPARATION_REQUIRED, never NOT_ELIGIBLE.
- An open discrepancy produces HUMAN_VERIFICATION_REQUIRED, never auto-rejection.
- READY_FOR_HANDOFF is awarded ONLY when all configured mandatory documents
  are verified with zero open discrepancies.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.schemas.document import (
    ApplicationDocumentChecklistItem,
    ApplicationReadiness,
    DocumentDiscrepancyItem,
    DocumentRequirementSource,
    DocumentRequirementStatus,
    ReadinessStatus,
)
from backend.app.services.document_requirements import generate_application_checklist


class ReadinessEngine:
    """Computes deterministic readiness for an application track."""

    @classmethod
    def calculate_readiness(
        cls,
        application_id: str,
        scheme_id: str,
        checklist: List[ApplicationDocumentChecklistItem],
        discrepancies: Optional[List[DocumentDiscrepancyItem]] = None,
    ) -> ApplicationReadiness:
        """
        Pure deterministic computation of application readiness.
        """
        discrepancies = discrepancies or []
        open_discrepancies = [d for d in discrepancies if d.status == "OPEN"]

        mandatory_reqs = [r for r in checklist if r.required and r.status != DocumentRequirementStatus.NOT_REQUIRED.value]
        total_mandatory = len(mandatory_reqs)

        verified_reqs = [r for r in mandatory_reqs if r.status == DocumentRequirementStatus.VERIFIED.value]
        missing_docs = [r.name for r in mandatory_reqs if r.status in [
            DocumentRequirementStatus.REQUIRED.value,
            DocumentRequirementStatus.UPLOADED.value,
            DocumentRequirementStatus.PROCESSING.value,
            DocumentRequirementStatus.INVALID.value,
        ]]

        unresolved_items: List[str] = []

        # Check for unverified / not configured scheme metadata
        for r in checklist:
            if r.source_status != DocumentRequirementSource.VERIFIED.value:
                unresolved_items.append(f"Requirement '{r.name}' is {r.source_status} in official dataset.")

        # Determine Readiness Status
        # 1. Open discrepancies -> HUMAN_VERIFICATION_REQUIRED
        if open_discrepancies or any(r.status == DocumentRequirementStatus.MISMATCH.value for r in checklist):
            status = ReadinessStatus.HUMAN_VERIFICATION_REQUIRED.value
            for d in open_discrepancies:
                unresolved_items.append(f"Discrepancy on {d.field_name}: profile={d.profile_value}, document={d.document_value}")

        # 2. Any invalid/unreadable document -> HUMAN_VERIFICATION_REQUIRED
        elif any(r.status in [DocumentRequirementStatus.INVALID.value, DocumentRequirementStatus.UNREADABLE.value] for r in checklist):
            status = ReadinessStatus.HUMAN_VERIFICATION_REQUIRED.value
            unresolved_items.append("One or more uploaded documents are invalid or unreadable.")

        # 3. Missing mandatory documents -> PREPARATION_REQUIRED
        elif missing_docs or len(verified_reqs) < total_mandatory:
            status = ReadinessStatus.PREPARATION_REQUIRED.value
            unresolved_items.extend([f"Missing document: {m}" for m in missing_docs])

        # 4. All mandatory requirements verified, no open discrepancies -> READY_FOR_HANDOFF
        elif len(verified_reqs) == total_mandatory:
            status = ReadinessStatus.READY_FOR_HANDOFF.value

        else:
            status = ReadinessStatus.NOT_READY.value

        return ApplicationReadiness(
            application_id=application_id,
            scheme_id=scheme_id,
            status=status,
            total_requirements=total_mandatory,
            verified_requirements=len(verified_reqs),
            missing_documents=missing_docs,
            mismatches=open_discrepancies,
            unresolved_items=unresolved_items,
            requirements=checklist,
        )
