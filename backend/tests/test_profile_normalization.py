"""
Unit Tests for Deterministic Profile Normalizer
===============================================
Tests:
- Indian currency normalization (Lakhs, k, Crores, symbols)
- Land measurement normalization (acres, hectares)
- Age normalization
- State title-casing and canonical lookup
- Ambiguous inputs detection
"""

import pytest
from backend.app.profile.normalizer import (
    normalize_age,
    normalize_boolean,
    normalize_field,
    normalize_income,
    normalize_land_acres,
    normalize_occupation,
    normalize_state,
)


def test_normalize_income_variations():
    # Various formats for 2 lakh
    val, ambig = normalize_income("₹2 lakh")
    assert val == 200000.0 and not ambig

    val, ambig = normalize_income("2 lakh")
    assert val == 200000.0 and not ambig

    val, ambig = normalize_income("200000")
    assert val == 200000.0 and not ambig

    val, ambig = normalize_income("Rs. 2,00,000")
    assert val == 200000.0 and not ambig

    val, ambig = normalize_income("1.8 lakh")
    assert val == 180000.0 and not ambig

    val, ambig = normalize_income("50,000")
    assert val == 50000.0 and not ambig

    val, ambig = normalize_income("50k")
    assert val == 50000.0 and not ambig


def test_normalize_income_ambiguity():
    # Ambiguous phrases without unit must flag ambiguous
    val, ambig = normalize_income("about two")
    assert ambig is True or val is None

    val, ambig = normalize_income("two")
    assert ambig is True or val is None

    # Small number without units
    val, ambig = normalize_income(2)
    assert ambig is True


def test_normalize_land_acres():
    val, ambig = normalize_land_acres("3 acres")
    assert val == 3.0 and not ambig

    val, ambig = normalize_land_acres("3 acre")
    assert val == 3.0 and not ambig

    val, ambig = normalize_land_acres("3 ac")
    assert val == 3.0 and not ambig

    val, ambig = normalize_land_acres("5.5 acres")
    assert val == 5.5 and not ambig

    val, ambig = normalize_land_acres(3)
    assert val == 3.0 and not ambig


def test_normalize_land_ambiguity():
    # "I have five" without acre unit
    val, ambig = normalize_land_acres("five")
    assert ambig is True


def test_normalize_age():
    val, ambig = normalize_age("42 years old")
    assert val == 42 and not ambig

    val, ambig = normalize_age("45")
    assert val == 45 and not ambig

    val, ambig = normalize_age("age 30")
    assert val == 30 and not ambig


def test_normalize_state():
    val, ambig = normalize_state("telangana")
    assert val == "Telangana" and not ambig

    val, ambig = normalize_state("TELANGANA")
    assert val == "Telangana" and not ambig

    val, ambig = normalize_state("Andhra Pradesh")
    assert val == "Andhra Pradesh" and not ambig


def test_normalize_occupation():
    val, ambig = normalize_occupation("farmer")
    assert val == "farmer" and not ambig

    val, ambig = normalize_occupation("kisan")
    assert val == "farmer" and not ambig

    val, ambig = normalize_occupation("agriculture")
    assert val == "farmer" and not ambig


def test_normalize_boolean():
    val, ambig = normalize_boolean("yes")
    assert val is True and not ambig

    val, ambig = normalize_boolean("false")
    assert val is False and not ambig
