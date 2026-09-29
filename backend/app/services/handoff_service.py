"""Phase 6 deterministic pre-submission verification and printable package service.

This module intentionally ends at CSC/VLE handoff. It has no government portal,
submission, approval, payment, or official-reference-number capability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from sqlalchemy.orm import Session

from backend.app.agent.state import AgentState
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.confirmation_repository import ConfirmationRepository
from backend.app.db.repositories.document_repository import DocumentDiscrepancyRepository, DocumentRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.handoff_package_repository import HandoffPackageRepository
from backend.app.db.repositories.profile_repository import ProfileRepository
from backend.app.schemas.handoff import HandoffPackageData, HandoffPackageResponse, PackageArtifact, PreSubmissionVerification
from backend.app.services.document_coordinator import DocumentCoordinator
from backend.app.services.scheme_loader import get_scheme


DISCLAIMER = "NOT AN OFFICIAL GOVERNMENT FORM OR GOVERNMENT SUBMISSION"
REFERENCE_DISCLAIMER = "NOT AN OFFICIAL GOVERNMENT FORM"
PREPARATION_NOTICE = "Prepared by Yojana Saathi for pre-submission verification and CSC/VLE assistance."
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "storage" / "handoff_packages"


class PreSubmissionBlockedError(ValueError):
    """Raised when a package would misrepresent an incomplete or stale application."""


class HandoffService:
    """Builds application-isolated Phase 6 package snapshots and PDFs."""

    def __init__(self, document_coordinator: Optional[DocumentCoordinator] = None):
        self.document_coordinator = document_coordinator or DocumentCoordinator()

    def verify(self, state: AgentState, application_id: str, db: Optional[Session] = None) -> PreSubmissionVerification:
        now = datetime.now(timezone.utc)
        blocking: List[str] = []
        warnings: List[str] = []
        app, scheme_id, app_status = self._application(state, application_id, db)
        if not app:
            return PreSubmissionVerification(application_id=application_id, scheme_id="unknown", profile_confirmed=False,
                eligibility_current=False, blocking_items=["APPLICATION_NOT_FOUND"], warnings=[], verified_at=now)

        profile, profile_confirmed, fingerprint = self._profile(state, db)
        if not profile_confirmed:
            blocking.append("PROFILE_NOT_CONFIRMED")
        if self._has_pending_confirmation(state, db):
            blocking.append("PENDING_PROFILE_CONFIRMATION")

        if app_status not in {"SELECTED", "PREPARING", "READY_FOR_HANDOFF"}:
            blocking.append("APPLICATION_NOT_SELECTED")

        evaluation, eligibility_current = self._evaluation(state, scheme_id, application_id, fingerprint, db)
        outcome = self._get(evaluation, "outcome") if evaluation else None
        if not evaluation:
            blocking.append("NO_CURRENT_EVALUATION")
        elif not eligibility_current:
            blocking.append("STALE_ELIGIBILITY")
        elif outcome != "FULLY_ELIGIBLE":
            blocking.append("ELIGIBILITY_NOT_FULLY_ELIGIBLE")

        readiness = self.document_coordinator.compute_readiness(state, application_id, db=db)
        if readiness.status != "READY_FOR_HANDOFF":
            blocking.append("READINESS_NOT_READY")
        for item in readiness.requirements:
            if item.source_status != "VERIFIED":
                blocking.append("UNCONFIGURED_REQUIREMENT")
                warnings.append("Document requirement information is not configured in the current scheme dataset.")
            elif item.required and item.status != "VERIFIED":
                # A submitted, unreadable, invalid, or otherwise unverified required
                # document never satisfies the pre-submission gate.
                blocking.append("UNREADABLE_DOCUMENT" if item.status == "UNREADABLE" else "MISSING_REQUIRED_DOCUMENT")
        open_discrepancies = self._open_discrepancies(state, application_id, db)
        if open_discrepancies:
            blocking.append("UNRESOLVED_DISCREPANCY")

        return PreSubmissionVerification(
            application_id=application_id, scheme_id=scheme_id, profile_confirmed=profile_confirmed,
            eligibility_current=eligibility_current, eligibility_outcome=outcome,
            readiness_status=readiness.status, blocking_items=sorted(set(blocking)),
            warnings=sorted(set(warnings)), verified_at=now,
        )

    def generate_handoff_package(self, state: AgentState, application_id: str, db: Optional[Session] = None) -> HandoffPackageResponse:
        verification = self.verify(state, application_id, db)
        if not verification.passed:
            raise PreSubmissionBlockedError("Pre-submission requirements incomplete: " + ", ".join(verification.blocking_items))
        data, evaluation_id = self._snapshot(state, application_id, verification, db)
        # Re-check immediately before persistence so no mixed state is materialized.
        final_check = self.verify(state, application_id, db)
        if not final_check.passed or final_check.eligibility_current != verification.eligibility_current:
            raise PreSubmissionBlockedError("Application changed during package generation; regenerate from a current snapshot.")

        package_id = self._new_package_id()
        reference_key, dossier_key = self._write_pdfs(package_id, data)
        self._validate_pdf(self._path_for(reference_key), [REFERENCE_DISCLAIMER, data.application_id, data.scheme_name, data.readiness["status"]])
        self._validate_pdf(self._path_for(dossier_key), [DISCLAIMER, data.application_id, data.scheme_name, data.readiness["status"]])

        if db:
            package = HandoffPackageRepository.create(
                db, id=package_id, case_id=data.case_id, application_id=data.application_id, scheme_id=data.scheme_id,
                profile_fingerprint=data.profile_fingerprint, evaluation_id=evaluation_id,
                readiness_status=data.readiness["status"], reference_sheet_key=reference_key, dossier_key=dossier_key,
                status="GENERATED",
            )
            EventRepository.record_application_event(db, application_id, "PRE_SUBMISSION_VERIFIED", {"scheme_id": data.scheme_id, "profile_fingerprint": data.profile_fingerprint, "readiness_status": data.readiness["status"]})
            EventRepository.record_application_event(db, application_id, "REFERENCE_SHEET_GENERATED", {"package_id": package.id})
            EventRepository.record_application_event(db, application_id, "DOSSIER_GENERATED", {"package_id": package.id})
            EventRepository.record_application_event(db, application_id, "HANDOFF_PACKAGE_GENERATED", {"package_id": package.id})
            generated_at = package.generated_at
        else:
            generated_at = data.generated_at
        return self._response(package_id, data, generated_at, reference_key, dossier_key)

    def get_current_package(self, state: AgentState, application_id: str, db: Session) -> Optional[HandoffPackageResponse]:
        package = HandoffPackageRepository.get_current(db, application_id)
        if not package:
            return None
        verification = self.verify(state, application_id, db)
        if (not verification.passed or package.profile_fingerprint != self._profile(state, db)[2]
                or package.readiness_status != verification.readiness_status):
            HandoffPackageRepository.invalidate_current(db, application_id)
            EventRepository.record_application_event(db, application_id, "HANDOFF_PACKAGE_INVALIDATED", {"package_id": package.id})
            return None
        data, _ = self._snapshot(state, application_id, verification, db)
        return self._response(package.id, data, package.generated_at, package.reference_sheet_key, package.dossier_key)

    def package_file(self, state: AgentState, application_id: str, package_id: str, artifact: str, db: Session) -> Path:
        current = self.get_current_package(state, application_id, db)
        if not current or current.package_id != package_id:
            raise FileNotFoundError("No current handoff package is available.")
        key = self._key_from_response(current, artifact)
        if not key:
            raise FileNotFoundError("Requested package artifact is unavailable.")
        path = self._path_for(key)
        if not path.is_file():
            raise FileNotFoundError("Package artifact is unavailable.")
        return path

    def _snapshot(self, state: AgentState, application_id: str, verification: PreSubmissionVerification, db: Optional[Session]) -> Tuple[HandoffPackageData, Optional[str]]:
        app, scheme_id, app_status = self._application(state, application_id, db)
        profile, _, fingerprint = self._profile(state, db)
        evaluation, _ = self._evaluation(state, scheme_id, application_id, fingerprint, db)
        scheme = get_scheme(scheme_id)
        relevant = set((scheme.eligibility.critical_fields if scheme else []) + [c.field for c in (scheme.eligibility.conditions if scheme else [])])
        relevant.update(k for k in ("name", "full_name", "age", "state", "district", "occupation", "land_holding_acres", "annual_income") if k in profile)
        safe_profile = {k: profile[k] for k in sorted(relevant) if k in profile and profile[k] not in (None, "", "unknown", "UNKNOWN")}
        readiness = self.document_coordinator.compute_readiness(state, application_id, db=db).model_dump()
        documents = self._documents(state, application_id, db)
        discrepancies = self._all_discrepancies(state, application_id, db)
        raw_reasons = self._get(evaluation, "reasons") or self._get(evaluation, "summary") or {}
        reasons = raw_reasons if isinstance(raw_reasons, dict) else {"assessment_summary": str(raw_reasons)}
        return HandoffPackageData(
            case_id=state.case_id, application_id=application_id, scheme_id=scheme_id,
            scheme_name=scheme.title_en if scheme else scheme_id, application_status=app_status,
            profile_fingerprint=fingerprint, profile=safe_profile,
            eligibility_outcome=verification.eligibility_outcome or "UNKNOWN",
            eligibility_reasons=reasons,
            readiness=readiness, documents=documents, discrepancies=discrepancies, generated_at=datetime.now(timezone.utc),
        ), self._get(evaluation, "id")

    def _application(self, state, application_id, db):
        if db:
            app = ApplicationRepository.get_application(db, application_id)
            if not app or app.case_id != state.case_id:
                return None, "unknown", "unknown"
            return app, app.scheme_id, app.status
        for scheme_id, info in state.applications.items():
            if info.get("id") == application_id or scheme_id == application_id:
                return info, scheme_id, info.get("status", "SELECTED")
        return None, "unknown", "unknown"

    def _profile(self, state, db):
        if db:
            p = ProfileRepository.get_by_case_id(db, state.case_id)
            return (dict(p.profile_data), bool(p.confirmed), p.profile_fingerprint) if p else ({}, False, "")
        return dict(state.profile), bool(state.profile), state.get_profile_fingerprint()

    def _has_pending_confirmation(self, state, db):
        return bool(ConfirmationRepository.get_pending_by_case_id(db, state.case_id)) if db else bool(state.pending_confirmation)

    def _evaluation(self, state, scheme_id, application_id, fingerprint, db):
        if db:
            candidates = [e for e in SchemeEvaluationRepository.list_for_case(db, state.case_id, include_stale=True)
                          if e.scheme_id == scheme_id and (e.application_id in (None, application_id))]
            ev = candidates[0] if candidates else None
            return ev, bool(ev and not ev.is_stale and ev.profile_fingerprint == fingerprint)
        ev = state.scheme_evaluations.get(scheme_id)
        return ev, bool(ev and ev.get("profile_fingerprint") == fingerprint)

    def _open_discrepancies(self, state, application_id, db):
        return [d for d in self._all_discrepancies(state, application_id, db) if self._get(d, "status") in {"OPEN", "UNRESOLVED", "ESCALATED"}]

    def _all_discrepancies(self, state, application_id, db):
        if db:
            return DocumentDiscrepancyRepository.list_by_application(db, application_id)
        docs = getattr(state, "documents", [])
        app_docs = docs.get(application_id, []) if isinstance(docs, dict) else [d for d in docs if d.get("application_id") == application_id]
        return [disc for d in app_docs for disc in d.get("discrepancies", [])]

    def _documents(self, state, application_id, db):
        if db:
            docs = DocumentRepository.list_by_application(db, application_id)
        else:
            raw_docs = getattr(state, "documents", [])
            docs = raw_docs.get(application_id, []) if isinstance(raw_docs, dict) else [d for d in raw_docs if d.get("application_id") == application_id]
        return [{"document_id": self._get(d, "id"), "document_type": self._get(d, "document_type"),
                 "filename": self._get(d, "original_filename"), "status": self._get(d, "status"),
                 "verification_status": self._get(d, "verification_status"), "uploaded_at": self._iso(self._get(d, "created_at")),
                 "extracted_fields": self._get(d, "extracted_data") or {}} for d in docs]

    @staticmethod
    def _get(obj, name): return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
    @staticmethod
    def _iso(value): return value.isoformat() if hasattr(value, "isoformat") else value
    @staticmethod
    def _new_package_id():
        import uuid
        return str(uuid.uuid4())
    @staticmethod
    def _path_for(key: str) -> Path: return OUTPUT_ROOT / key
    @staticmethod
    def _key_from_response(response, artifact):
        return None if artifact not in {"reference-sheet", "dossier"} else (f"{response.package_id}/reference-sheet.pdf" if artifact == "reference-sheet" else f"{response.package_id}/dossier.pdf")

    def _response(self, package_id, data, generated_at, reference_key, dossier_key):
        base = f"/api/cases/{data.case_id}/applications/{data.application_id}/handoff-package/{package_id}"
        return HandoffPackageResponse(package_id=package_id, case_id=data.case_id, application_id=data.application_id,
            scheme_id=data.scheme_id, status="GENERATED", readiness=data.readiness["status"],
            reference_sheet_available=bool(reference_key), dossier_available=bool(dossier_key), generated_at=generated_at,
            reference_sheet=PackageArtifact(package_id=package_id, download_url=base + "/reference-sheet") if reference_key else None,
            dossier=PackageArtifact(package_id=package_id, download_url=base + "/dossier") if dossier_key else None)

    def _write_pdfs(self, package_id, data):
        folder = OUTPUT_ROOT / package_id
        folder.mkdir(parents=True, exist_ok=True)
        ref_key, dossier_key = f"{package_id}/reference-sheet.pdf", f"{package_id}/dossier.pdf"
        self._render_reference(folder / "reference-sheet.pdf", data)
        self._render_dossier(folder / "dossier.pdf", data)
        return ref_key, dossier_key

    def _doc(self, path):
        return SimpleDocTemplate(str(path), pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=18*mm)

    def _styles(self):
        styles = getSampleStyleSheet()
        return styles, ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, leading=10), ParagraphStyle("Notice", parent=styles["BodyText"], textColor=colors.darkred, fontSize=10, leading=13, spaceAfter=8)

    def _header_footer(self, canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 8)
        canvas.drawString(15*mm, 10*mm, "Yojana Saathi - pre-submission preparation material")
        canvas.drawRightString(195*mm, 10*mm, f"Page {doc.page}")
        canvas.restoreState()

    def _table(self, rows, widths=None):
        normalized = [[Paragraph(str(v if v not in (None, "") else "Unknown"), self._styles()[1]) for v in r] for r in rows]
        table = Table(normalized, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E8EEF7")), ("GRID", (0,0), (-1,-1), .35, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
        return table

    def _render_reference(self, path, data):
        styles, small, notice = self._styles(); story = [Paragraph("YOJANA SAATHI", styles["Title"]), Paragraph("APPLICATION REFERENCE SHEET", styles["Heading1"]), Paragraph(REFERENCE_DISCLAIMER, notice), Paragraph(PREPARATION_NOTICE, styles["BodyText"]), Spacer(1, 6)]
        story.append(self._table([["Field", "Current value / source"], ["Case ID", data.case_id], ["Yojana Saathi Application ID", data.application_id], ["Scheme", f"{data.scheme_name} ({data.scheme_id})"], ["Yojana Saathi eligibility assessment", data.eligibility_outcome], ["Readiness check", data.readiness["status"]], ["Application status", data.application_status], ["Applicant name", data.profile.get("name") or data.profile.get("full_name") or "Unknown"]], [55*mm, 120*mm]))
        story += [Spacer(1, 8), Paragraph("Required document status", styles["Heading2"])]
        rows = [["Requirement", "Status", "Document"]] + [[r.get("name"), r.get("status"), r.get("document_id") or "None"] for r in data.readiness.get("requirements", [])]
        story += [self._table(rows, [75*mm, 42*mm, 58*mm]), Spacer(1, 8), Paragraph("CSC/VLE notes", styles["Heading2"]), Paragraph("Complete the official government application separately through the appropriate government process or CSC portal. Yojana Saathi does not submit applications.", styles["BodyText"]), Spacer(1, 10), Paragraph("Official Government Application / Reference Number: ________________________", styles["BodyText"])]
        self._doc(path).build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)

    def _render_dossier(self, path, data):
        styles, small, notice = self._styles(); story = [Paragraph("YOJANA SAATHI", styles["Title"]), Paragraph("PRE-SUBMISSION DOSSIER", styles["Heading1"]), Paragraph(DISCLAIMER, notice), Paragraph(PREPARATION_NOTICE, styles["BodyText"]), Spacer(1, 8)]
        story += [self._table([["Identification", "Value"], ["Scheme", data.scheme_name], ["Scheme ID", data.scheme_id], ["Case ID", data.case_id], ["Yojana Saathi Application ID", data.application_id], ["Prepared", data.generated_at.isoformat()], ["Application status", data.application_status]]), Spacer(1, 8), Paragraph("Citizen confirmed profile", styles["Heading2"])]
        story.append(self._table([["Neutral Yojana Saathi field", "Confirmed value"]] + [[k.replace("_", " ").title(), v] for k, v in data.profile.items()]))
        story += [Spacer(1, 8), Paragraph("Eligibility summary", styles["Heading2"]), Paragraph("Yojana Saathi deterministic eligibility assessment: " + data.eligibility_outcome, styles["BodyText"]), Paragraph("Profile fingerprint: " + data.profile_fingerprint, small)]
        if data.eligibility_reasons: story.append(self._table([["Criterion", "Configured result"]] + [[k, v] for k, v in data.eligibility_reasons.items()]))
        story += [Spacer(1, 8), Paragraph("Required document checklist", styles["Heading2"])]
        rows = [["Requirement", "Status", "Document", "Verification"]] + [[r.get("name"), r.get("status"), r.get("document_id") or "None", r.get("source_status")] for r in data.readiness.get("requirements", [])]
        story.append(self._table(rows, [58*mm, 36*mm, 40*mm, 40*mm]))
        story += [Spacer(1, 8), Paragraph("Uploaded / verified document index", styles["Heading2"])]
        docs = [["Document ID", "Type", "Filename", "Status"]] + [[d["document_id"], d["document_type"], d["filename"] or "Not retained", d["verification_status"] or d["status"]] for d in data.documents]
        story.append(self._table(docs, [40*mm, 42*mm, 56*mm, 36*mm]))
        story += [Spacer(1, 8), Paragraph("Discrepancy record", styles["Heading2"])]
        if data.discrepancies:
            disc = [["Field", "Status", "Profile value", "Document value"]] + [[self._get(d,"field_name"), self._get(d,"status"), self._get(d,"profile_value"), self._get(d,"document_value")] for d in data.discrepancies]
            story.append(self._table(disc, [38*mm, 42*mm, 47*mm, 47*mm]))
        else: story.append(Paragraph("No document/profile discrepancies detected.", styles["BodyText"]))
        story += [Spacer(1, 8), Paragraph("Current readiness", styles["Heading2"]), self._table([["Eligibility", data.eligibility_outcome], ["Readiness", data.readiness["status"]]]), Spacer(1, 8), Paragraph("CSC/VLE handoff checklist", styles["Heading2"])]
        for item in ["Confirm applicant identity.", "Confirm citizen profile.", "Confirm scheme selected.", "Verify required documents.", "Review any warnings and unresolved items.", "Complete the official government application separately through the appropriate government process/CSC portal.", "Record the official government application/reference number after actual submission."]:
            story.append(Paragraph("[ ] " + item, styles["BodyText"]))
        story += [Spacer(1, 10), Paragraph("Official Government Application / Reference Number: ________________________", styles["BodyText"]), Paragraph("Yojana Saathi does not submit applications and this dossier is not proof of government submission, approval, payment, or acceptance.", notice)]
        self._doc(path).build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)

    @staticmethod
    def _validate_pdf(path: Path, required: List[str]):
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not reader.pages or any(value not in text for value in required):
            raise RuntimeError("Generated PDF validation failed.")
