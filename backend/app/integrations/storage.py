"""
Yojana Saathi - Storage Integration Adapter
===========================================
File and document storage reference interface (Phase 5).
Avoids storing raw binary files directly in PostgreSQL.
Includes file validation, MIME and magic-bytes verification, SHA-256 deduplication,
and path-traversal prevention.
"""

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple


# Maximum allowed upload size (10 MB default)
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

# Allowed file extensions and corresponding MIME types
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# Magic bytes (file signatures)
MAGIC_SIGNATURES = {
    "application/pdf": [b"%PDF"],
    "image/jpeg": [b"\xFF\xD8\xFF"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}


class StorageAdapter:
    """Manages file storage references and uploads securely."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or "backend/storage").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        """Computes SHA-256 hash of binary content."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Strips path traversal sequences and dangerous characters.
        Returns a clean base filename.
        """
        # Take basename only
        clean_name = os.path.basename(filename)
        # Remove any path separators or null bytes
        clean_name = re.sub(r"[^\w\.\-\_]", "_", clean_name)
        # Prevent hidden files
        if clean_name.startswith("."):
            clean_name = f"doc_{clean_name.lstrip('.')}"
        return clean_name or "uploaded_document"

    @classmethod
    def validate_file_upload(
        cls,
        filename: str,
        content: bytes,
        mime_type: Optional[str] = None,
        max_size: int = MAX_UPLOAD_SIZE_BYTES,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates uploaded file for:
        1. Non-empty content
        2. Maximum size limit
        3. Allowed file extension
        4. Matching magic bytes (file signature)
        5. Rejection of executable/script payloads

        Returns: (is_valid, error_message, detected_mime_type)
        """
        # 1. Empty check
        if not content or len(content) == 0:
            return False, "Uploaded file is empty (0 bytes).", None

        # 2. Size check
        if len(content) > max_size:
            size_mb = round(len(content) / (1024 * 1024), 2)
            max_mb = round(max_size / (1024 * 1024), 2)
            return False, f"File size ({size_mb} MB) exceeds maximum allowed limit ({max_mb} MB).", None

        # 3. Extension check
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(ALLOWED_EXTENSIONS.keys())
            return False, f"Unsupported file extension '{ext}'. Allowed formats: {allowed_list}.", None

        expected_mime = ALLOWED_EXTENSIONS[ext]

        # 4. Magic signature verification
        signatures = MAGIC_SIGNATURES.get(expected_mime, [])
        matches_signature = any(content.startswith(sig) for sig in signatures)
        if not matches_signature:
            return (
                False,
                f"File signature does not match extension '{ext}'. Potential corrupted or disguised file.",
                None,
            )

        # 5. Executable detection check (Windows PE, ELF, shell scripts)
        if content.startswith(b"MZ") or content.startswith(b"\x7fELF") or content.startswith(b"#!"):
            return False, "Executable or script files are strictly prohibited.", None

        return True, None, expected_mime

    def save_file(self, filename: str, content: bytes, subfolder: Optional[str] = None) -> str:
        """
        Saves content securely and returns the file storage reference.
        Prevents directory traversal by enforcing base_dir containment.
        """
        clean_name = self.sanitize_filename(filename)
        unique_prefix = uuid.uuid4().hex[:12]
        unique_filename = f"{unique_prefix}_{clean_name}"

        target_dir = self.base_dir
        if subfolder:
            safe_sub = re.sub(r"[^\w\-]", "_", subfolder)
            target_dir = self.base_dir / safe_sub
            target_dir.mkdir(parents=True, exist_ok=True)

        file_path = (target_dir / unique_filename).resolve()

        # Enforce containment
        if not str(file_path).startswith(str(self.base_dir)):
            raise ValueError("Path traversal attempt detected.")

        with open(file_path, "wb") as f:
            f.write(content)

        # Return storage reference relative to project root or base_dir
        try:
            rel_path = file_path.relative_to(Path.cwd())
            return str(rel_path).replace("\\", "/")
        except ValueError:
            return str(file_path).replace("\\", "/")

    def get_file_bytes(self, file_reference: str) -> Optional[bytes]:
        """Retrieves file bytes from storage reference."""
        path = Path(file_reference)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            # Try directly under base_dir
            alt_path = self.base_dir / Path(file_reference).name
            if alt_path.exists():
                path = alt_path
            else:
                return None

        with open(path, "rb") as f:
            return f.read()
