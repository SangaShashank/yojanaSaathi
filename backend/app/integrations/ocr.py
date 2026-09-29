"""
Yojana Saathi - OCR Integration Provider
========================================
Clean abstraction layer for optical character recognition (Phase 5.1).
Supports extracting text from images (JPG, JPEG, PNG) and rendered PDF pages.
Defaults to local Tesseract OCR engine with environment-based configuration.
"""

import io
import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union
from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)


class OCRProvider(ABC):
    """Abstract interface for Optical Character Recognition engines."""

    @abstractmethod
    def extract_text_from_image(
        self,
        image: Union[bytes, Image.Image],
        lang: Optional[str] = None,
    ) -> str:
        """Extracts text from an image (bytes or PIL Image)."""
        pass

    @abstractmethod
    def extract_text_from_pdf_page(
        self,
        page_image: Image.Image,
        lang: Optional[str] = None,
    ) -> str:
        """Extracts text from a rendered PDF page image."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying OCR engine is installed and operational."""
        pass

    @abstractmethod
    def get_available_languages(self) -> List[str]:
        """Returns the list of installed/supported OCR language codes."""
        pass


class TesseractOCRProvider(OCRProvider):
    """
    Tesseract OCR implementation using pytesseract and PIL.
    Safely discovers Tesseract binary across standard paths and environment variables.
    """

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        default_lang: Optional[str] = None,
    ):
        self.default_lang = default_lang or os.environ.get("OCR_LANGUAGES", "eng")
        self.tesseract_cmd = self._resolve_tesseract_cmd(tesseract_cmd)
        self._configure_pytesseract()

    def _resolve_tesseract_cmd(self, explicit_cmd: Optional[str] = None) -> Optional[str]:
        """
        Resolves the tesseract binary location:
        1. Explicit argument
        2. TESSERACT_CMD environment variable
        3. PATH lookup via shutil.which('tesseract')
        4. Standard Windows install locations
        """
        if explicit_cmd and os.path.isfile(explicit_cmd):
            return explicit_cmd

        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd and os.path.isfile(env_cmd):
            return env_cmd

        which_cmd = shutil.which("tesseract")
        if which_cmd:
            return which_cmd

        # Check standard Windows candidate locations
        user_home = Path.home()
        candidates = [
            Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
            Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
            user_home / "AppData/Local/Programs/Tesseract-OCR/tesseract.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

        return None

    def _configure_pytesseract(self) -> None:
        """Configures pytesseract command and tessdata prefix if available."""
        if not self.tesseract_cmd:
            return

        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            # Check for tessdata directory alongside tesseract executable
            tess_dir = Path(self.tesseract_cmd).parent / "tessdata"
            if tess_dir.is_dir() and "TESSDATA_PREFIX" not in os.environ:
                os.environ["TESSDATA_PREFIX"] = str(tess_dir)
        except ImportError:
            logger.warning("pytesseract package is not installed.")

    def is_available(self) -> bool:
        """Checks if Tesseract binary is callable and functional."""
        if not self.tesseract_cmd or not os.path.isfile(self.tesseract_cmd):
            return False
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.debug(f"Tesseract availability check failed: {e}")
            return False

    def get_available_languages(self) -> List[str]:
        """Returns installed language models."""
        if not self.is_available():
            return []
        try:
            import pytesseract
            langs = pytesseract.get_languages(config="")
            return [l for l in langs if l != "osd"]
        except Exception:
            # Fallback inspection of tessdata directory
            if "TESSDATA_PREFIX" in os.environ:
                tessdata = Path(os.environ["TESSDATA_PREFIX"])
                if tessdata.is_dir():
                    return [p.stem for p in tessdata.glob("*.traineddata") if p.stem != "osd"]
            return ["eng"]

    @staticmethod
    def preprocess_image(image: Image.Image) -> Image.Image:
        """
        Applies basic preprocessing for optimal OCR clarity:
        1. Converts RGBA / Palette images to RGB
        2. Converts to Grayscale
        3. Enhances contrast
        """
        if image.mode in ("RGBA", "LA", "P"):
            # Create white background for transparent images
            bg = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "RGBA":
                bg.paste(image, mask=image.split()[-1])
            else:
                bg.paste(image.convert("RGB"))
            img = bg
        else:
            img = image.convert("RGB")

        # Convert to grayscale
        gray = img.convert("L")
        # Enhance contrast slightly to sharpen scan text
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.4)
        return enhanced

    def extract_text_from_image(
        self,
        image: Union[bytes, Image.Image],
        lang: Optional[str] = None,
    ) -> str:
        """
        Performs OCR on an image.
        Accepts raw bytes or PIL Image object.
        """
        if not self.is_available():
            raise RuntimeError(
                f"Tesseract OCR is not available. Please verify installation or TESSERACT_CMD configuration."
            )

        import pytesseract

        # Load image if bytes provided
        if isinstance(image, bytes):
            try:
                pil_image = Image.open(io.BytesIO(image))
                pil_image.load()
            except Exception as e:
                raise ValueError(f"Invalid or corrupt image content for OCR: {e}")
        elif isinstance(image, Image.Image):
            pil_image = image
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        # Preprocess
        preprocessed = self.preprocess_image(pil_image)

        # Run OCR with safe argument list under pytesseract
        ocr_lang = lang or self.default_lang
        try:
            text = pytesseract.image_to_string(preprocessed, lang=ocr_lang)
            return text.strip()
        except Exception as e:
            logger.error(f"Tesseract OCR extraction failed: {e}")
            raise RuntimeError(f"OCR extraction failed: {e}")

    def extract_text_from_pdf_page(
        self,
        page_image: Image.Image,
        lang: Optional[str] = None,
    ) -> str:
        """Extracts text from a single rendered PDF page image."""
        return self.extract_text_from_image(page_image, lang=lang)


# Global default provider instance
_default_ocr_provider: Optional[OCRProvider] = None


def get_ocr_provider(provider_type: Optional[str] = None) -> OCRProvider:
    """Factory retrieving the configured OCR provider."""
    global _default_ocr_provider
    ptype = provider_type or os.environ.get("OCR_PROVIDER", "tesseract").lower()

    if ptype == "tesseract":
        if _default_ocr_provider is None:
            _default_ocr_provider = TesseractOCRProvider()
        return _default_ocr_provider

    raise ValueError(f"Unsupported OCR provider '{ptype}'. Supported: 'tesseract'")
