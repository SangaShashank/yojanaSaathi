"""
Yojana Saathi - Scheme Dataset Loader
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from backend.app.schemas.scheme import SchemeDefinition


DEFAULT_SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent / "data" / "schemes_dataset_v2.json",
    Path(__file__).resolve().parent.parent.parent.parent / "schemes_dataset_v2.json",
    Path("schemes_dataset_v2.json"),
]


class SchemeLoader:
    """
    Loads and caches configured government schemes from schemes_dataset_v2.json.
    """

    def __init__(self, dataset_path: Optional[str | Path] = None):
        self._dataset_path = self._resolve_path(dataset_path)
        self._schemes: Dict[str, SchemeDefinition] = {}
        self._loaded = False

    def _resolve_path(self, path: Optional[str | Path]) -> Path:
        if path:
            p = Path(path)
            if p.is_file():
                return p

        for candidate in DEFAULT_SEARCH_PATHS:
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(
            f"Could not locate schemes_dataset_v2.json in paths: {[str(p) for p in DEFAULT_SEARCH_PATHS]}"
        )

    def load(self, force_reload: bool = False) -> List[SchemeDefinition]:
        """Loads and parses all scheme definitions from the dataset."""
        if self._loaded and not force_reload:
            return list(self._schemes.values())

        with open(self._dataset_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self._schemes.clear()
        for item in raw_data:
            scheme = SchemeDefinition.model_validate(item)
            self._schemes[scheme.scheme_id] = scheme

        self._loaded = True
        return list(self._schemes.values())

    def get_by_id(self, scheme_id: str) -> Optional[SchemeDefinition]:
        """Looks up a scheme definition by its unique identifier or known alias."""
        if not self._loaded:
            self.load()
        if scheme_id in self._schemes:
            return self._schemes[scheme_id]

        # Case-insensitive direct match
        for sid, scheme in self._schemes.items():
            if sid.lower() == scheme_id.lower():
                return scheme

        # Common friendly aliases
        aliases = {
            "pm_kisan": "pm_kisan_001",
            "pmkisan": "pm_kisan_001",
            "rythu_bharosa": "ts_rythu_bharosa_001",
            "ts_rythu_bharosa": "ts_rythu_bharosa_001",
            "pm_kmy": "pm_kisan_maandhan_001",
            "pmkmy": "pm_kisan_maandhan_001",
            "pmfby": "pmfby_001",
            "kcc": "kcc_001",
            "soil_health_card": "soil_health_card_001",
            "pmmvy": "pmmvy_001",
            "sukanya_samriddhi": "sukanya_samriddhi_001",
            "rythu_bima": "ts_rythu_bima_001",
            "kalyana_lakshmi": "ts_kalyana_lakshmi_001",
            "kcr_kit": "ts_kcr_kit_001",
            "aasara_pension": "ts_aasara_pension_001",
            "sakhi_osc": "sakhi_osc_001",
        }
        clean_id = scheme_id.lower().strip()
        target_id = aliases.get(clean_id)
        if target_id and target_id in self._schemes:
            return self._schemes[target_id]

        return None

    def get_all(self) -> List[SchemeDefinition]:
        """Returns all loaded schemes."""
        if not self._loaded:
            self.load()
        return list(self._schemes.values())

    def get_by_niche(self, niche: str) -> List[SchemeDefinition]:
        """Filters schemes by audience niche (e.g. 'farmers', 'women')."""
        return [s for s in self.get_all() if s.niche.lower() == niche.strip().lower()]


# Default singleton loader instance
default_loader = SchemeLoader()


def load_all_schemes(dataset_path: Optional[str | Path] = None) -> List[SchemeDefinition]:
    """Helper function to load all schemes using the default or provided path."""
    if dataset_path:
        return SchemeLoader(dataset_path).load()
    return default_loader.load()


def get_scheme(scheme_id: str) -> Optional[SchemeDefinition]:
    """Helper function to get a scheme by ID."""
    return default_loader.get_by_id(scheme_id)
