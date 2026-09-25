"""
Yojana Saathi - Database and Application Configuration
======================================================
Centralized configuration loader supporting local .env and environment variables.
Safely constructs DATABASE_URL with URL-encoded credentials when needed.
Passwords and API keys are strictly forbidden from being logged.
"""

import os
import urllib.parse
from typing import Optional
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()


class Settings:
    """Application and database settings."""

    # Environment
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    # PostgreSQL Credentials
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.environ.get("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "yojana_saathi")
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "yojana_saathi")
    POSTGRES_PASSWORD: Optional[str] = os.environ.get("POSTGRES_PASSWORD")

    # Gemini & AI Providers
    GEMINI_API_KEY: Optional[str] = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemma-4-31b-it")
    GROQ_API_KEY: Optional[str] = os.environ.get("GROQ_API_KEY")

    @property
    def DATABASE_URL(self) -> str:
        """
        Returns the SQLAlchemy connection URL.
        Defaults to postgresql+psycopg driver.
        """
        raw_url = os.environ.get("DATABASE_URL")
        if raw_url and raw_url.strip():
            # If the URL already specifies a dialect, ensure it's psycopg
            url = raw_url.strip()
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url

        # Construct safely from parts with URL-encoded password
        password_part = ""
        if self.POSTGRES_PASSWORD:
            encoded_password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
            password_part = f":{encoded_password}"

        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}{password_part}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
