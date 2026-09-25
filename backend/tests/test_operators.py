"""
Tests for Yojana Saathi Deterministic Rule Operators
"""

import pytest
from backend.app.rules.operators import (
    get_operator,
    op_eq,
    op_gt,
    op_gte,
    op_lt,
    op_lte,
    op_in,
    op_not_in,
)


class TestEqualityOperator:
    def test_numeric_equality(self):
        passed, _ = op_eq(18, 18)
        assert passed is True
        passed, _ = op_eq(18.0, 18)
        assert passed is True
        passed, _ = op_eq(17, 18)
        assert passed is False

    def test_boolean_equality(self):
        passed, _ = op_eq(True, True)
        assert passed is True
        passed, _ = op_eq(False, False)
        assert passed is True
        passed, _ = op_eq(True, False)
        assert passed is False

    def test_string_equality_case_and_whitespace_insensitive(self):
        passed, _ = op_eq("Telangana", "telangana")
        assert passed is True
        passed, _ = op_eq(" farmer ", "farmer")
        assert passed is True
        passed, _ = op_eq("Maharashtra", "Telangana")
        assert passed is False

    def test_date_equality(self):
        passed, _ = op_eq("2019-02-01", "2019-02-01")
        assert passed is True
        passed, _ = op_eq("2019-02-02", "2019-02-01")
        assert passed is False


class TestNumericAndDateComparisonOperators:
    def test_gt_numeric(self):
        assert op_gt(19, 18)[0] is True
        assert op_gt(18, 18)[0] is False
        assert op_gt(17, 18)[0] is False

    def test_gte_numeric(self):
        assert op_gte(19, 18)[0] is True
        assert op_gte(18, 18)[0] is True
        assert op_gte(17, 18)[0] is False

    def test_lt_numeric(self):
        assert op_lt(17, 18)[0] is True
        assert op_lt(18, 18)[0] is False
        assert op_lt(19, 18)[0] is False

    def test_lte_numeric(self):
        assert op_lte(17, 18)[0] is True
        assert op_lte(18, 18)[0] is True
        assert op_lte(19, 18)[0] is False

    def test_date_comparisons(self):
        # PM-KISAN cut-off: 2019-02-01
        cutoff = "2019-02-01"
        assert op_lte("2018-06-15", cutoff)[0] is True   # Acquired before cutoff -> eligible
        assert op_lte("2019-02-01", cutoff)[0] is True   # Exactly on cutoff -> eligible
        assert op_lte("2019-02-02", cutoff)[0] is False  # Acquired after cutoff -> ineligible

        assert op_gt("2020-01-01", cutoff)[0] is True
        assert op_lt("2018-12-31", cutoff)[0] is True


class TestInAndNotInOperators:
    def test_in_operator(self):
        allowed = ["landowner", "tenant_farmer", "sharecropper"]
        assert op_in("landowner", allowed)[0] is True
        assert op_in("LANDOWNER", allowed)[0] is True   # Case-insensitive
        assert op_in("tenant_farmer", allowed)[0] is True
        assert op_in("business_owner", allowed)[0] is False

    def test_not_in_operator(self):
        disqualified = ["institutional_landholder", "income_tax_payer"]
        assert op_not_in("farmer", disqualified)[0] is True
        assert op_not_in("income_tax_payer", disqualified)[0] is False
        assert op_not_in("INCOME_TAX_PAYER", disqualified)[0] is False


class TestOperatorResolutionAndAliases:
    def test_all_standard_operators_resolved(self):
        for op in ["eq", "gt", "gte", "lt", "lte", "in", "not_in"]:
            assert get_operator(op) is not None

    def test_uppercase_aliases_resolved(self):
        assert get_operator("EQUALS") is not None
        assert get_operator("GREATER_THAN") is not None
        assert get_operator("GREATER_THAN_OR_EQUAL") is not None
        assert get_operator("LESS_THAN") is not None
        assert get_operator("LESS_THAN_OR_EQUAL") is not None
        assert get_operator("IN") is not None
        assert get_operator("NOT_IN") is not None
