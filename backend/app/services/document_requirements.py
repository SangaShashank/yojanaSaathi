"""
Yojana Saathi - Document Requirements Service
============================================
Determines scheme-specific document requirements strictly from verified source data
(schemes_dataset_v2.json) with ZERO fabricated government requirements.
Generates application-specific document checklists.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.schemas.document import (
    ApplicationDocumentChecklistItem,
    DocumentRequirement,
    DocumentRequirementSource,
    DocumentRequirementStatus,
)
from backend.app.services.scheme_loader import get_scheme, load_all_schemes


# Verification fields that can be cross-checked against citizen profile
DOCUMENT_VERIFICATION_FIELDS_MAP: Dict[str, List[str]] = {
    "aadhaar": ["name", "age", "gender", "district", "state"],
    "aadhaar_guardian": ["name"],
    "land_record": ["name", "land_holding_acres", "district", "state"],
    "land_records": ["name", "land_holding_acres", "district", "state"],
    "land_record_or_tenancy_proof": ["name", "land_holding_acres", "district", "state"],
    "bank_passbook": ["name"],
    "farmer_id": ["name", "farmer_id_status"],
    "income_certificate": ["name", "annual_income_inr"],
    "caste_community_certificate": ["name", "caste_category"],
    "birth_certificate": ["name", "age", "gender"],
    "age_proof": ["name", "age"],
    "hospital_registration": ["name"],
    "nominee_details": ["name"],
    "sowing_declaration": ["name", "cultivates_land"],
    "mcp_card": ["name"],
    "passport_photo": [],
    "consent_form": [],
    "marriage_proof": ["name"],
    "death_certificate_spouse": ["name"],
    "address_proof": ["state", "district"],
    "none_mandatory": [],
}


def get_scheme_document_requirements(scheme_id: str) -> List[DocumentRequirement]:
    """
    Retrieves verified document requirements for a scheme from the official catalog.
    If the scheme is not in catalog or has no configured documents, returns
    unverified/not-configured requirements without fabricating government policy.
    """
    scheme_def = get_scheme(scheme_id)
    if not scheme_def:
        return [
            DocumentRequirement(
                requirement_id=f"req_{scheme_id}_unconfigured",
                scheme_id=scheme_id,
                document_type="unconfigured",
                name="Document requirement information is not configured in current scheme dataset.",
                required=False,
                purpose="Scheme metadata unavailable",
                verification_fields=[],
                source_status=DocumentRequirementSource.NOT_CONFIGURED.value,
            )
        ]

    # Inspect raw dictionary or model for required_documents
    raw_docs = getattr(scheme_def, "required_documents", None)
    if raw_docs is None and hasattr(scheme_def, "model_extra") and scheme_def.model_extra:
        raw_docs = scheme_def.model_extra.get("required_documents")

    if not raw_docs:
        return [
            DocumentRequirement(
                requirement_id=f"req_{scheme_id}_none",
                scheme_id=scheme_id,
                document_type="none_configured",
                name="No official document requirements configured for this scheme.",
                required=False,
                purpose="No verified documents configured in dataset",
                verification_fields=[],
                source_status=DocumentRequirementSource.NOT_CONFIGURED.value,
            )
        ]

    requirements: List[DocumentRequirement] = []
    for doc in raw_docs:
        doc_id = getattr(doc, "doc_id", None) or (doc.get("doc_id") if isinstance(doc, dict) else "generic_doc")
        is_mandatory = getattr(doc, "is_mandatory", True) if hasattr(doc, "is_mandatory") else (doc.get("is_mandatory", True) if isinstance(doc, dict) else True)
        name_en = getattr(doc, "name_en", None) or (doc.get("name_en") if isinstance(doc, dict) else doc_id.replace("_", " ").title())
        source_office = getattr(doc, "source_office", None) or (doc.get("source_office") if isinstance(doc, dict) else None)

        # Map verification fields
        v_fields = DOCUMENT_VERIFICATION_FIELDS_MAP.get(doc_id, ["name"])

        # Distinguish non-mandatory or informative requirements
        if doc_id == "none_mandatory":
            is_mandatory = False
            v_fields = []

        requirements.append(
            DocumentRequirement(
                requirement_id=f"req_{scheme_id}_{doc_id}",
                scheme_id=scheme_id,
                document_type=doc_id,
                name=name_en,
                required=is_mandatory,
                purpose=f"Issued by {source_office}" if source_office else None,
                verification_fields=v_fields,
                source_status=DocumentRequirementSource.VERIFIED.value,
            )
        )

    return requirements


def generate_application_checklist(
    application_id: str,
    scheme_id: str,
    linked_documents: Optional[List[Any]] = None,
    db: Optional[Session] = None,
) -> List[ApplicationDocumentChecklistItem]:
    """
    Generates the application-specific document checklist.
    Checks linked documents to compute current status for each requirement.
    """
    requirements = get_scheme_document_requirements(scheme_id)
    checklist: List[ApplicationDocumentChecklistItem] = []

    # Map uploaded/linked documents by document_type or requirement_id
    docs_by_type: Dict[str, Any] = {}
    docs_by_req: Dict[str, Any] = {}

    if linked_documents:
        for d in linked_documents:
            d_type = getattr(d, "document_type", None) or (d.get("document_type") if isinstance(d, dict) else None)
            req_id = getattr(d, "requirement_id", None) or (d.get("requirement_id") if isinstance(d, dict) else None)
            if d_type:
                docs_by_type[d_type] = d
            if req_id:
                docs_by_req[req_id] = d

    for req in requirements:
        if req.source_status != DocumentRequirementSource.VERIFIED.value:
            checklist.append(
                ApplicationDocumentChecklistItem(
                    requirement_id=req.requirement_id,
                    document_type=req.document_type,
                    name=req.name,
                    required=req.required,
                    status=DocumentRequirementStatus.UNVERIFIED_REQUIREMENT.value,
                    source_status=req.source_status,
                )
            )
            continue

        if not req.required:
            checklist.append(
                ApplicationDocumentChecklistItem(
                    requirement_id=req.requirement_id,
                    document_type=req.document_type,
                    name=req.name,
                    required=False,
                    status=DocumentRequirementStatus.NOT_REQUIRED.value,
                    source_status=req.source_status,
                )
            )
            continue

        # Look for matching uploaded document
        matched_doc = docs_by_req.get(req.requirement_id) or docs_by_type.get(req.document_type)

        if not matched_doc:
            item_status = DocumentRequirementStatus.REQUIRED.value
            doc_id = None
            discrepancies = []
        else:
            doc_id = getattr(matched_doc, "id", None) or (matched_doc.get("id") if isinstance(matched_doc, dict) else None)
            d_status = getattr(matched_doc, "status", None) or (matched_doc.get("status") if isinstance(matched_doc, dict) else None)
            v_status = getattr(matched_doc, "verification_status", None) or (matched_doc.get("verification_status") if isinstance(matched_doc, dict) else None)

            # Determine requirement status from document status
            if v_status == "VERIFIED" or d_status == "VERIFIED":
                item_status = DocumentRequirementStatus.VERIFIED.value
            elif v_status == "MISMATCH" or d_status == "MISMATCH":
                item_status = DocumentRequirementStatus.MISMATCH.value
            elif d_status in ["INVALID", "UNREADABLE"]:
                item_status = DocumentRequirementStatus.INVALID.value
            elif d_status == "PROCESSING":
                item_status = DocumentRequirementStatus.PROCESSING.value
            elif d_status == "UPLOADED":
                item_status = DocumentRequirementStatus.UPLOADED.value
            else:
                item_status = DocumentRequirementStatus.UPLOADED.value

            discrepancies = []
            if hasattr(matched_doc, "discrepancies") and matched_doc.discrepancies:
                discrepancies = [disc.id for disc in matched_doc.discrepancies if getattr(disc, "status", "") == "OPEN"]
            elif isinstance(matched_doc, dict) and "discrepancies" in matched_doc:
                discrepancies = [d.get("id") or d.get("discrepancy_id") for d in matched_doc["discrepancies"] if d.get("status") == "OPEN"]

        checklist.append(
            ApplicationDocumentChecklistItem(
                requirement_id=req.requirement_id,
                document_type=req.document_type,
                name=req.name,
                required=req.required,
                status=item_status,
                source_status=req.source_status,
                document_id=doc_id,
                discrepancy_ids=[d for d in discrepancies if d],
            )
        )

    return checklist
