"""
Yojana Saathi - Scheme Catalog Model
====================================
Persistent catalog seeded directly from schemes_dataset_v2.json.
Enables relational queries while preserving the exact schema and rules versioning.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class SchemeCatalog(Base):
    """Catalog of official welfare scheme definitions."""
    __tablename__ = "schemes"

    scheme_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    niche: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    ministry: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    scope: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    version: Mapped[str] = mapped_column(
        String(32), default="2.0", nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
