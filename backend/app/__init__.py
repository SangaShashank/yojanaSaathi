"""
Yojana Saathi - Backend Application Package
"""

from pathlib import Path

# Automatically load environment variables from .env if present
try:
    from dotenv import load_dotenv

    # Search in project root and backend folder
    _env_candidates = [
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(".env"),
    ]
    for _p in _env_candidates:
        if _p.is_file():
            load_dotenv(_p)
            break
except ImportError:
    pass

__version__ = "0.1.0"
