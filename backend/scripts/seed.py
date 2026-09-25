"""
Yojana Saathi - Database Seed Script
====================================
Idempotently seeds official government welfare scheme definitions from schemes_dataset_v2.json
into the PostgreSQL schemes table.
Running this script multiple times updates existing entries without creating duplicates.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.session import SessionLocal, check_db_connection
from backend.app.db.repositories.scheme_repository import SchemeCatalogRepository
from backend.app.services.scheme_loader import load_all_schemes


def seed_schemes(verbose: bool = True) -> int:
    """
    Seeds all 13 welfare schemes from schemes_dataset_v2.json into PostgreSQL.
    Returns the count of seeded schemes.
    """
    if not check_db_connection():
        raise RuntimeError("Cannot seed: database is not reachable. Verify PostgreSQL connection.")

    schemes = load_all_schemes()
    db = SessionLocal()
    count = 0
    try:
        for s in schemes:
            SchemeCatalogRepository.upsert_scheme(
                db=db,
                scheme_id=s.scheme_id,
                name=s.title_en,
                niche=s.niche,
                ministry=s.ministry,
                scope=s.state_restriction or "National",
                version=s.schema_version,
                active=True,
                metadata_json=s.model_dump(),
            )
            count += 1
            if verbose:
                print(f"  [SEED] {s.scheme_id}: {s.title_en}")

        print(f"\n[SUCCESS] Successfully seeded {count} scheme catalog records.")
        return count
    finally:
        db.close()


if __name__ == "__main__":
    print("Starting Yojana Saathi database seeding...")
    seed_schemes(verbose=True)
