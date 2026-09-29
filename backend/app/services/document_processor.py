"""
Yojana Saathi - Document Processor & Extraction Engine
=====================================================
Processes uploaded documents, extracts text via pypdf (for native text PDFs)
or real OCR (for scanned PDFs, JPG, JPEG, PNG), and normalizes structured
document facts into DocumentExtractionResult.

Deterministic Scanned-PDF Detection Rule:
- PDFs are first parsed with pypdf.
- If extracted text contains at least MIN_TEXT_CHARS_FOR_NATIVE_PDF (30) alphanumeric
  characters, the native text is accepted directly and OCR is NOT invoked.
- If fewer than 30 alphanumeric characters are detected, the document is classified as a
  scanned/image-only PDF and routed to the OCR fallback pipeline.

Safety & Prompt Injection Defense:
- Text is treated purely as inert data.
- Adversarial instructions inside document text cannot manipulate eligibility
  rules, agent actions, or bypass security validation.
"""

import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
from pypdf import PdfReader
import pymupdf

from backend.app.integrations.ocr import OCRProvider, get_ocr_provider
from backend.app.schemas.document import DocumentExtractionResult

logger = logging.getLogger(__name__)

# Deterministic threshold: A PDF must contain at least 30 alphanumeric characters to be
# processed via native text extraction. Below this, OCR fallback is triggered.
MIN_TEXT_CHARS_FOR_NATIVE_PDF = 30

# Maximum pages permitted for OCR processing to prevent resource exhaustion.
MAX_OCR_PAGES_DEFAULT = 20


class DocumentProcessor:
    """Extracts raw text and structured fields from verified document formats."""

    @classmethod
    def extract_text_and_metadata(
        cls,
        file_bytes: bytes,
        mime_type: str,
        filename: str = "",
        ocr_provider: Optional[OCRProvider] = None,
        max_ocr_pages: Optional[int] = None,
    ) -> Tuple[str, str, Optional[str], int, List[str]]:
        """
        Extracts raw textual content and metadata from PDF or image file bytes.
        Returns: (raw_text, extraction_method, ocr_provider_name, pages_processed, confidence_flags)
        """
        if not file_bytes:
            return "", "NATIVE_PDF", None, 0, []

        is_pdf = mime_type == "application/pdf" or filename.lower().endswith(".pdf")
        is_image = (
            mime_type in ("image/jpeg", "image/png")
            or filename.lower().endswith((".jpg", ".jpeg", ".png"))
        )

        max_pages = max_ocr_pages or int(os.environ.get("MAX_OCR_PAGES", str(MAX_OCR_PAGES_DEFAULT)))
        provider = ocr_provider or get_ocr_provider()

        # -------------------------------------------------------------
        # 1. PDF Documents: Native Text vs. Scanned Fallback
        # -------------------------------------------------------------
        if is_pdf:
            pypdf_text = ""
            pypdf_success = False
            page_count = 1

            try:
                reader = PdfReader(io.BytesIO(file_bytes))
                page_count = len(reader.pages)
                text_parts = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
                pypdf_text = "\n".join(text_parts).strip()
                pypdf_success = True
            except Exception as e:
                logger.debug(f"pypdf extraction failed on PDF: {e}")

            # Deterministic rule: count alphanumeric characters
            alphanumeric_count = len(re.findall(r"[a-zA-Z0-9]", pypdf_text))

            if pypdf_success and alphanumeric_count >= MIN_TEXT_CHARS_FOR_NATIVE_PDF:
                # Selectable / native text PDF: Use pypdf directly, ZERO OCR overhead
                return pypdf_text, "NATIVE_PDF", None, page_count, []

            # Scanned / image-only / sparse-text PDF -> Trigger real OCR fallback
            logger.info(
                f"PDF '{filename}' yielded {alphanumeric_count} alphanumeric chars (< {MIN_TEXT_CHARS_FOR_NATIVE_PDF}). "
                "Triggering OCR fallback."
            )

            if not provider.is_available():
                raise RuntimeError("OCR provider is not available or unconfigured for scanned PDF processing.")

            try:
                doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            except Exception as e:
                raise ValueError(f"Corrupted or invalid PDF: {e}")

            total_pages = len(doc)
            if total_pages > max_pages:
                doc.close()
                raise OverflowError(
                    f"PROCESSING_LIMIT_EXCEEDED: Document has {total_pages} pages, exceeding the limit of {max_pages} pages."
                )

            ocr_page_texts = []
            for page_idx in range(total_pages):
                page = doc[page_idx]
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = provider.extract_text_from_pdf_page(img)
                if page_text and page_text.strip():
                    ocr_page_texts.append(page_text.strip())

            doc.close()
            combined_ocr_text = "\n\n".join(ocr_page_texts).strip()
            return combined_ocr_text, "OCR", "tesseract", total_pages, ["SCANNED_PDF_OCR_FALLBACK"]

        # -------------------------------------------------------------
        # 2. Image Documents: JPG, JPEG, PNG
        # -------------------------------------------------------------
        if is_image:
            if not provider.is_available():
                raise RuntimeError("OCR provider is not available or unconfigured for image processing.")

            try:
                img = Image.open(io.BytesIO(file_bytes))
                img.load()
            except Exception as e:
                raise ValueError(f"Invalid or corrupt image content for OCR: {e}")

            raw_text = provider.extract_text_from_image(img)
            return raw_text, "OCR", "tesseract", 1, []

        # Plain text fallback
        try:
            return file_bytes.decode("utf-8", errors="ignore"), "PLAIN_TEXT", None, 1, []
        except Exception as e:
            raise ValueError(f"Unable to read file content: {e}")

    @classmethod
    def extract_text_from_bytes(
        cls,
        file_bytes: bytes,
        mime_type: str,
        filename: str = "",
    ) -> str:
        """
        Backward-compatible helper returning purely raw text string.
        """
        raw_text, _, _, _, _ = cls.extract_text_and_metadata(
            file_bytes=file_bytes,
            mime_type=mime_type,
            filename=filename,
        )
        return raw_text

    @classmethod
    def parse_structured_fields(
        cls,
        raw_text: str,
        document_type: str,
        extraction_method: str = "NATIVE_PDF",
        ocr_provider: Optional[str] = None,
        pages_processed: int = 1,
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
                extraction_method=extraction_method,
                ocr_provider=ocr_provider,
                pages_processed=pages_processed,
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
                            extraction_method=extraction_method,
                            ocr_provider=ocr_provider,
                            pages_processed=pages_processed,
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
        if "land" in document_type or document_type in ["land_record", "land_record_or_tenancy_proof", "land_records"]:
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
        lower_raw = raw_text.lower()
        if (
            "ignore previous instructions" in lower_raw
            or "ignore all previous instructions" in lower_raw
            or "grant admin" in lower_raw
            or "mark this person eligible" in lower_raw
        ):
            confidence_flags.append("ADVERSARIAL_PAYLOAD_NEUTRALIZED")

        return DocumentExtractionResult(
            document_type=document_type,
            fields=fields,
            unresolved_fields=unresolved,
            confidence_flags=confidence_flags,
            extraction_status="SUCCESS" if fields else "FAILED",
            raw_text=raw_text[:500],
            extraction_method=extraction_method,
            ocr_provider=ocr_provider,
            pages_processed=pages_processed,
        )

    @classmethod
    def process_file(
        cls,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
        document_type: str,
        ocr_provider: Optional[OCRProvider] = None,
        max_ocr_pages: Optional[int] = None,
    ) -> DocumentExtractionResult:
        """
        High-level pipeline:
        File bytes -> Format detection / OCR -> Field parsing -> Structured result.
        """
        try:
            raw_text, method, prov_name, pages, flags = cls.extract_text_and_metadata(
                file_bytes=file_bytes,
                mime_type=mime_type,
                filename=filename,
                ocr_provider=ocr_provider,
                max_ocr_pages=max_ocr_pages,
            )
            if not raw_text or not raw_text.strip():
                return DocumentExtractionResult(
                    document_type=document_type,
                    fields={},
                    extraction_status="UNREADABLE",
                    raw_text="",
                    extraction_method=method,
                    ocr_provider=prov_name,
                    pages_processed=pages,
                    confidence_flags=flags,
                )

            res = cls.parse_structured_fields(
                raw_text=raw_text,
                document_type=document_type,
                extraction_method=method,
                ocr_provider=prov_name,
                pages_processed=pages,
            )
            if flags:
                res.confidence_flags.extend(flags)
            return res
        except OverflowError as e:
            logger.warning(f"Document processing page limit exceeded for {filename}: {e}")
            return DocumentExtractionResult(
                document_type=document_type,
                fields={},
                extraction_status="PROCESSING_LIMIT_EXCEEDED",
                raw_text="",
                confidence_flags=[str(e)],
                extraction_method="OCR",
                ocr_provider="tesseract",
                pages_processed=0,
            )
        except Exception as e:
            logger.error(f"Document processing failed for {filename}: {e}")
            return DocumentExtractionResult(
                document_type=document_type,
                fields={},
                extraction_status="FAILED",
                raw_text="",
                confidence_flags=[str(e)],
                extraction_method="OCR" if mime_type.startswith("image/") else "NATIVE_PDF",
            )
