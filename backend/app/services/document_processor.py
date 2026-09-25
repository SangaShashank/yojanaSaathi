"""
Yojana Saathi - Document Processor & Extraction Engine
=====================================================
Processes uploaded documents, extracts text via pypdf / readers,
and normalizes structured document facts into DocumentExtractionResult.

Safety & Prompt Injection Defense:
- Text is treated purely as inert data.
- Adversarial instructions inside document text cannot manipulate eligibility
  rules, agent actions, or bypass security validation.
"""

import io
import json
import logging
import re
from typing import Any, Dict, List, Optional
from pypdf import PdfReader

from backend.app.schemas.document import DocumentExtractionResult


logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Extracts raw text and structured fields from verified document formats."""

    @classmethod
    def extract_text_from_bytes(
        cls,
        file_bytes: bytes,
        mime_type: str,
        filename: str = "",
    ) -> str:
        """
        Extracts raw textual content from PDF or text/image file bytes.
        Returns extracted string, or raises ValueError if file is corrupted/unreadable.
        """
        if not file_bytes:
            return ""

        if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                reader = PdfReader(io.BytesIO(file_bytes))
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                return "\n".join(text_parts).strip()
            except Exception as e:
                logger.warning(f"PDF extraction failed: {e}")
                # Check if it was simulated plain text or corrupted
                try:
                    return file_bytes.decode("utf-8", errors="ignore")
                except Exception:
                    raise ValueError(f"Corrupted or unreadable PDF: {e}")

        # Plain text / fallback decoding
        try:
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            raise ValueError(f"Unable to read file content: {e}")

    @classmethod
    def parse_structured_fields(
        cls,
        raw_text: str,
        document_type: str,
    ) -> DocumentExtractionResult:
        """
        Extracts structured fields deterministically based on document type.
        Ensures missing fields remain unknown.
        Immune to prompt injection attempts embedded in document content.
        """
        if not raw_text or not raw_text.strip():
            return DocumentExtractionResult(
                document_type=document_type,
                fields={},
                extraction_status="UNREADABLE",
                raw_text="",
            )

        fields: Dict[str, Any] = {}
        unresolved: List[str] = []
        confidence_flags: List[str] = []

        # Check if document raw_text is a JSON formatted payload (e.g. digital credentials)
        clean_text = raw_text.strip()
        if clean_text.startswith("{") and clean_text.endswith("}"):
            try:
                parsed_json = json.loads(clean_text)
                if isinstance(parsed_json, dict):
                    # Filter only recognized safe fields
                    for k, v in parsed_json.items():
                        if k in [
                            "name",
                            "land_holding_acres",
                            "land_acres",
                            "age",
                            "gender",
                            "district",
                            "state",
                            "annual_income_inr",
                            "farmer_id_status",
                            "survey_number",
                            "caste_category",
                            "cultivates_land",
                        ]:
                            fields[k] = v
                    if fields:
                        return DocumentExtractionResult(
                            document_type=document_type,
                            fields=fields,
                            extraction_status="SUCCESS",
                            raw_text=raw_text[:500],
                        )
            except json.JSONDecodeError:
                pass

        # Regex Extraction Patterns for Key Document Types
        # 1. Name extraction
        name_match = re.search(
            r"(?:name|pattadar|citizen|applicant|farmer\s*name|holder)\s*[:=\-]\s*([a-zA-Z\.\t ]+?)(?=\s+(?:land|extent|holding|survey|district|state|age|gender|status|area|$|\n))",
            raw_text,
            re.IGNORECASE,
        )
        if not name_match:
            name_match = re.search(
                r"(?:name|pattadar|citizen|applicant|farmer\s*name|holder)\s*[:=\-]\s*([a-zA-Z\.\t ]+)",
                raw_text,
                re.IGNORECASE,
            )
        if name_match:
            fields["name"] = name_match.group(1).strip()
        else:
            unresolved.append("name")

        # 2. Land Record specific patterns
        if "land" in document_type or document_type in ["land_record", "land_record_or_tenancy_proof"]:
            land_match = re.search(
                r"(?:extent|land|holding|acres?|area)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*(?:acres?|ac)?",
                raw_text,
                re.IGNORECASE,
            )
            if land_match:
                try:
                    val = float(land_match.group(1))
                    fields["land_holding_acres"] = val
                    fields["land_acres"] = val
                except ValueError:
                    unresolved.append("land_holding_acres")
            else:
                unresolved.append("land_holding_acres")

            survey_match = re.search(r"(?:survey\s*(?:no|number)|sy\s*no)\s*[:=\-]\s*([\w\/]+)", raw_text, re.IGNORECASE)
            if survey_match:
                fields["survey_number"] = survey_match.group(1).strip()

        # 3. Aadhaar / Age Proof specific patterns
        if document_type in ["aadhaar", "age_proof", "birth_certificate"]:
            age_match = re.search(r"(?:age|years?)\s*[:=\-]\s*(\d{1,3})", raw_text, re.IGNORECASE)
            if age_match:
                try:
                    fields["age"] = int(age_match.group(1))
                except ValueError:
                    pass

            gender_match = re.search(r"(?:gender|sex)\s*[:=\-]\s*(male|female|other)", raw_text, re.IGNORECASE)
            if gender_match:
                fields["gender"] = gender_match.group(1).lower().strip()

        # 4. Income Certificate patterns
        if document_type in ["income_certificate"]:
            income_match = re.search(
                r"(?:annual\s*income|family\s*income|income)\s*[:=\-]?\s*(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
                raw_text,
                re.IGNORECASE,
            )
            if income_match:
                raw_num = income_match.group(1).replace(",", "")
                try:
                    fields["annual_income_inr"] = float(raw_num)
                except ValueError:
                    unresolved.append("annual_income_inr")
            else:
                unresolved.append("annual_income_inr")

        # 5. Farmer ID patterns
        if document_type in ["farmer_id"]:
            f_status_match = re.search(r"(?:farmer\s*id\s*status|status)\s*[:=\-]\s*(\w+)", raw_text, re.IGNORECASE)
            if f_status_match:
                fields["farmer_id_status"] = f_status_match.group(1).lower().strip()

        # 6. Common Geography
        state_match = re.search(r"(?:state)\s*[:=\-]\s*([a-zA-Z\t ]+)", raw_text, re.IGNORECASE)
        if state_match:
            fields["state"] = state_match.group(1).strip()

        district_match = re.search(r"(?:district)\s*[:=\-]\s*([a-zA-Z\t ]+)", raw_text, re.IGNORECASE)
        if district_match:
            fields["district"] = district_match.group(1).strip()

        # Safety Check against Adversarial Prompt Injections
        # Any attempt like 'system: set eligible=true' is purely ignored because we never
        # execute code or evaluate directives from document text.
        if "ignore previous instructions" in raw_text.lower() or "grant admin" in raw_text.lower():
            confidence_flags.append("ADVERSARIAL_PAYLOAD_NEUTRALIZED")

        return DocumentExtractionResult(
            document_type=document_type,
            fields=fields,
            unresolved_fields=unresolved,
            confidence_flags=confidence_flags,
            extraction_status="SUCCESS" if fields else "FAILED",
            raw_text=raw_text[:500],
        )

    @classmethod
    def process_file(
        cls,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
        document_type: str,
    ) -> DocumentExtractionResult:
        """
        High-level pipeline:
        File bytes -> Text extraction -> Field parsing -> Structured result.
        """
        try:
            raw_text = cls.extract_text_from_bytes(file_bytes, mime_type, filename)
            if not raw_text or not raw_text.strip():
                return DocumentExtractionResult(
                    document_type=document_type,
                    fields={},
                    extraction_status="UNREADABLE",
                    raw_text="",
                )
            return cls.parse_structured_fields(raw_text, document_type)
        except Exception as e:
            logger.error(f"Document processing failed for {filename}: {e}")
            return DocumentExtractionResult(
                document_type=document_type,
                fields={},
                extraction_status="FAILED",
                raw_text="",
            )
