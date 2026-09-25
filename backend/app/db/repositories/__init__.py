"""
Yojana Saathi - Repositories Package
===================================
Exports all repository classes for clean, layered database access.
"""

from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.repositories.profile_repository import (
    ProfileConcurrencyError,
    ProfileRepository,
)
from backend.app.db.repositories.confirmation_repository import ConfirmationRepository
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.scheme_repository import SchemeCatalogRepository
from backend.app.db.repositories.document_repository import (
    ApplicationRequirementRepository,
    DocumentDiscrepancyRepository,
    DocumentRepository,
)

__all__ = [
    "CaseRepository",
    "ProfileRepository",
    "ProfileConcurrencyError",
    "ConfirmationRepository",
    "ApplicationRepository",
    "SchemeEvaluationRepository",
    "EventRepository",
    "SchemeCatalogRepository",
    "DocumentRepository",
    "DocumentDiscrepancyRepository",
    "ApplicationRequirementRepository",
]

