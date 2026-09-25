"""
Yojana Saathi - Deterministic Rule Operators
"""

from datetime import date, datetime
import re
from typing import Any, Callable, Dict, List, Optional, Tuple


DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _try_parse_date(val: Any) -> Optional[date]:
    """Attempts to parse an ISO date string (YYYY-MM-DD) into a date object."""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str) and DATE_REGEX.match(val.strip()):
        try:
            return date.fromisoformat(val.strip())
        except ValueError:
            return None
    return None


def _normalize_string(val: Any) -> str:
    """Normalizes string for comparison (trimmed, lowercased)."""
    return str(val).strip().lower()


def op_eq(actual: Any, expected: Any) -> Tuple[bool, str]:
    """
    Equality operator. Supports boolean, case-insensitive string, date, and numeric equality.
    """
    if actual is None or expected is None:
        return (actual == expected), f"Expected {expected}, actual was {actual}"

    # Boolean comparison
    if isinstance(expected, bool) or isinstance(actual, bool):
        match = bool(actual) is bool(expected)
        return match, f"Expected {expected}, actual was {actual}"

    # Date comparison
    d_actual = _try_parse_date(actual)
    d_expected = _try_parse_date(expected)
    if d_actual and d_expected:
        match = d_actual == d_expected
        return match, f"Expected date {d_expected}, actual date was {d_actual}"

    # Numeric comparison
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        match = float(actual) == float(expected)
        return match, f"Expected {expected}, actual was {actual}"

    # String comparison (case-insensitive)
    if isinstance(actual, str) and isinstance(expected, str):
        match = _normalize_string(actual) == _normalize_string(expected)
        return match, f"Expected '{expected}', actual was '{actual}'"

    match = actual == expected
    return match, f"Expected {expected}, actual was {actual}"


def op_gt(actual: Any, expected: Any) -> Tuple[bool, str]:
    """Greater than operator (numeric and date)."""
    d_actual = _try_parse_date(actual)
    d_expected = _try_parse_date(expected)
    if d_actual and d_expected:
        match = d_actual > d_expected
        return match, f"Expected date > {d_expected}, actual was {d_actual}"

    try:
        match = float(actual) > float(expected)
        return match, f"Expected > {expected}, actual was {actual}"
    except (ValueError, TypeError):
        return False, f"Cannot perform greater-than on types {type(actual).__name__} and {type(expected).__name__}"


def op_gte(actual: Any, expected: Any) -> Tuple[bool, str]:
    """Greater than or equal to operator (numeric and date)."""
    d_actual = _try_parse_date(actual)
    d_expected = _try_parse_date(expected)
    if d_actual and d_expected:
        match = d_actual >= d_expected
        return match, f"Expected date >= {d_expected}, actual was {d_actual}"

    try:
        match = float(actual) >= float(expected)
        return match, f"Expected >= {expected}, actual was {actual}"
    except (ValueError, TypeError):
        return False, f"Cannot perform gte on types {type(actual).__name__} and {type(expected).__name__}"


def op_lt(actual: Any, expected: Any) -> Tuple[bool, str]:
    """Less than operator (numeric and date)."""
    d_actual = _try_parse_date(actual)
    d_expected = _try_parse_date(expected)
    if d_actual and d_expected:
        match = d_actual < d_expected
        return match, f"Expected date < {d_expected}, actual was {d_actual}"

    try:
        match = float(actual) < float(expected)
        return match, f"Expected < {expected}, actual was {actual}"
    except (ValueError, TypeError):
        return False, f"Cannot perform less-than on types {type(actual).__name__} and {type(expected).__name__}"


def op_lte(actual: Any, expected: Any) -> Tuple[bool, str]:
    """Less than or equal to operator (numeric and date)."""
    d_actual = _try_parse_date(actual)
    d_expected = _try_parse_date(expected)
    if d_actual and d_expected:
        match = d_actual <= d_expected
        return match, f"Expected date <= {d_expected}, actual was {d_actual}"

    try:
        match = float(actual) <= float(expected)
        return match, f"Expected <= {expected}, actual was {actual}"
    except (ValueError, TypeError):
        return False, f"Cannot perform lte on types {type(actual).__name__} and {type(expected).__name__}"


def op_in(actual: Any, expected: Any) -> Tuple[bool, str]:
    """Inclusion operator (case-insensitive string matching when elements are strings)."""
    if not isinstance(expected, (list, tuple, set)):
        return False, f"Expected collection for 'in' operator, got {type(expected).__name__}"

    if isinstance(actual, str):
        norm_actual = _normalize_string(actual)
        norm_list = [_normalize_string(x) if isinstance(x, str) else x for x in expected]
        match = norm_actual in norm_list
        return match, f"Expected '{actual}' to be in {expected}"

    match = actual in expected
    return match, f"Expected {actual} to be in {expected}"


def op_not_in(actual: Any, expected: Any) -> Tuple[bool, str]:
    """Exclusion operator (case-insensitive string matching when elements are strings)."""
    match_in, _ = op_in(actual, expected)
    match = not match_in
    return match, f"Expected '{actual}' to NOT be in {expected}"


# Operator registry mapping operator strings to execution functions
OPERATORS: Dict[str, Callable[[Any, Any], Tuple[bool, str]]] = {
    "eq": op_eq,
    "equals": op_eq,
    "gt": op_gt,
    "greater_than": op_gt,
    "gte": op_gte,
    "greater_than_or_equal": op_gte,
    "lt": op_lt,
    "less_than": op_lt,
    "lte": op_lte,
    "less_than_or_equal": op_lte,
    "in": op_in,
    "not_in": op_not_in,
}


def get_operator(op_name: str) -> Optional[Callable[[Any, Any], Tuple[bool, str]]]:
    """Resolves an operator by name or alias."""
    return OPERATORS.get(op_name.strip().lower())
