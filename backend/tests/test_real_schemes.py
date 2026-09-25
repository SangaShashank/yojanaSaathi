"""
Tests for Real Schemes from schemes_dataset_v2.json
===================================================
Tests deterministic eligibility on real government schemes:
1. PM-KISAN (pm_kisan_001)
2. Rythu Bharosa (ts_rythu_bharosa_001)
3. PM-KMY (pm_kisan_maandhan_001)
4. Soil Health Card (soil_health_card_001)
5. Multi-Scheme Evaluation across all 13 configured schemes
"""

import pytest
from backend.app.schemas.profile import CitizenProfile
from backend.app.schemas.eligibility import CriterionStatus, SchemeOutcome
from backend.app.services.scheme_loader import get_scheme, load_all_schemes
from backend.app.services.eligibility_engine import (
    evaluate_eligibility,
    evaluate_all_schemes,
)


class TestRealPMKisan:
    @pytest.fixture(autouse=True)
    def setup_scheme(self):
        self.scheme = get_scheme("pm_kisan_001")
        assert self.scheme is not None, "pm_kisan_001 must exist in schemes_dataset_v2.json"

    def test_pm_kisan_fully_eligible(self):
        """Standard eligible farmer meeting all criteria."""
        profile = CitizenProfile(
            age=42,
            land_ownership=True,
            land_record_date="2018-05-15",  # Prior to 2019-02-01 cutoff
            occupation="farmer",
            farmer_id_status="registered",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.FULLY_ELIGIBLE
        assert len(result.failed_criteria) == 0
        assert len(result.unresolved_criteria) == 0

    def test_pm_kisan_land_record_cutoff_failure(self):
        """Farmer acquired land after Feb 1, 2019 cutoff -> NOT_ELIGIBLE."""
        profile = CitizenProfile(
            age=42,
            land_ownership=True,
            land_record_date="2020-03-10",  # After 2019-02-01 cutoff
            occupation="farmer",
            farmer_id_status="registered",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        failed_fields = [c.field for c in result.failed_criteria]
        assert "land_record_date" in failed_fields
        assert result.failed_criteria[0].status == CriterionStatus.FAIL

    def test_pm_kisan_disqualified_occupation_failure(self):
        """Income tax payer is disqualified from PM-KISAN."""
        profile = CitizenProfile(
            age=42,
            land_ownership=True,
            land_record_date="2018-05-15",
            occupation="income_tax_payer",
            farmer_id_status="registered",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        failed_fields = [c.field for c in result.failed_criteria]
        assert "occupation" in failed_fields

    def test_pm_kisan_missing_farmer_id_unknown(self):
        """Mandatory 2026 farmer ID status missing -> INCOMPLETE / UNKNOWN."""
        profile = CitizenProfile(
            age=42,
            land_ownership=True,
            land_record_date="2018-05-15",
            occupation="farmer",
            # farmer_id_status not provided
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.INCOMPLETE_UNKNOWN
        assert any(c.field == "farmer_id_status" for c in result.unresolved_criteria)


class TestRealRythuBharosa:
    @pytest.fixture(autouse=True)
    def setup_scheme(self):
        self.scheme = get_scheme("ts_rythu_bharosa_001")
        assert self.scheme is not None, "ts_rythu_bharosa_001 must exist in schemes_dataset_v2.json"

    def test_rythu_bharosa_fully_eligible(self):
        """Eligible actively cultivating farmer in Telangana with Bhu Bharati verification."""
        profile = CitizenProfile(
            state="Telangana",
            active_cultivation_status=True,
            occupation_type="landowner",
            land_verification_source="bhu_bharati_portal",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.FULLY_ELIGIBLE
        assert len(result.failed_criteria) == 0

    def test_rythu_bharosa_state_restriction_failure(self):
        """Farmer residing outside Telangana is NOT_ELIGIBLE."""
        profile = CitizenProfile(
            state="Andhra Pradesh",
            active_cultivation_status=True,
            occupation_type="landowner",
            land_verification_source="bhu_bharati_portal",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        failed_fields = [c.field for c in result.failed_criteria]
        assert "state" in failed_fields

    def test_rythu_bharosa_non_cultivating_failure(self):
        """Rythu Bharosa requires active cultivation; inactive land is NOT_ELIGIBLE."""
        profile = CitizenProfile(
            state="Telangana",
            active_cultivation_status=False,  # Inactive cultivation
            occupation_type="landowner",
            land_verification_source="bhu_bharati_portal",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        failed_fields = [c.field for c in result.failed_criteria]
        assert "active_cultivation_status" in failed_fields


class TestRealPMKMY:
    @pytest.fixture(autouse=True)
    def setup_scheme(self):
        self.scheme = get_scheme("pm_kisan_maandhan_001")
        assert self.scheme is not None, "pm_kisan_maandhan_001 must exist in dataset"

    def test_pm_kmy_eligible(self):
        """Small farmer age 25 with 3 acres land."""
        profile = CitizenProfile(
            age=25,
            land_ownership=True,
            land_acres=3.0,
            occupation="small_farmer",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.FULLY_ELIGIBLE

    def test_pm_kmy_over_age_failure(self):
        """Applicant age 45 exceeds entry ceiling of 40."""
        profile = CitizenProfile(
            age=45,  # Exceeds max entry age 40
            land_ownership=True,
            land_acres=3.0,
            occupation="small_farmer",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        assert any(c.field == "age" and c.status == CriterionStatus.FAIL for c in result.failed_criteria)

    def test_pm_kmy_land_size_failure(self):
        """Applicant with 7.5 acres exceeds 5 acre (2 hectare) small/marginal farmer limit."""
        profile = CitizenProfile(
            age=30,
            land_ownership=True,
            land_acres=7.5,  # Exceeds 5.0 acres
            occupation="farmer",
        )
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        assert any(c.field == "land_acres" and c.status == CriterionStatus.FAIL for c in result.failed_criteria)


class TestRealSoilHealthCard:
    @pytest.fixture(autouse=True)
    def setup_scheme(self):
        self.scheme = get_scheme("soil_health_card_001")
        assert self.scheme is not None

    def test_soil_health_card_eligible(self):
        """Any farmer cultivating land is eligible."""
        profile = CitizenProfile(cultivates_land=True)
        result = evaluate_eligibility(profile, self.scheme)

        assert result.outcome == SchemeOutcome.FULLY_ELIGIBLE


class TestMultiSchemeEvaluation:
    def test_evaluate_all_13_schemes_independently(self):
        """
        Evaluates a Telangana small farmer against all configured schemes.
        Ensures multiple schemes evaluate independently without mutual interference.
        """
        all_schemes = load_all_schemes()
        assert len(all_schemes) == 13

        profile = CitizenProfile(
            gender="male",
            age=32,
            state="Telangana",
            occupation="farmer",
            occupation_type="landowner",
            land_ownership=True,
            land_acres=3.0,
            land_record_date="2018-01-10",
            farmer_id_status="registered",
            active_cultivation_status=True,
            cultivates_land=True,
            land_verification_source="bhu_bharati_portal",
        )

        results = evaluate_all_schemes(profile, all_schemes)

        assert results.total_schemes_evaluated == 13
        # Should be fully eligible for PM-KISAN, Rythu Bharosa, Soil Health Card, PM-KMY
        assert "pm_kisan_001" in results.fully_eligible_schemes
        assert "ts_rythu_bharosa_001" in results.fully_eligible_schemes
        assert "soil_health_card_001" in results.fully_eligible_schemes
        assert "pm_kisan_maandhan_001" in results.fully_eligible_schemes

        # Ineligible for schemes requiring female gender
        assert "sakhi_osc_001" in results.not_eligible_schemes
        assert "ts_kalyana_lakshmi_001" in results.not_eligible_schemes
        assert "ts_kcr_kit_001" in results.not_eligible_schemes
