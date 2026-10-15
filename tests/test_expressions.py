"""Tests for the select expression evaluator."""

from __future__ import annotations

import pytest
from ws4.io.expressions import ExpressionError, _parse, evaluate

_CONSTANTS = {"managed": "C", "operable": "Operable"}


def test_the_parse_is_cached_across_calls() -> None:
    """A repeated statement reuses its parsed tree."""
    _parse.cache_clear()
    assert evaluate("a eq 1", {"a": 1}, {}) is True
    assert evaluate("a eq 1", {"a": 2}, {}) is False
    assert _parse.cache_info().hits >= 1


def test_lookup_table_maps_a_key_to_a_value() -> None:
    """``lookupTable`` returns the value aligned with the key."""
    from ws4.io.expressions import evaluate_value

    assert evaluate_value("lookupTable(Int(cov),'1,2,3','a,b,c')", {"cov": 2}, {}) == "b"
    assert evaluate_value("lookupTable(Int(cov),'1,2,3','a,b,c')", {"cov": 9}, {}) == ""
    assert evaluate_value("lookupTable(au,'x,y','p,q')", {"au": "y"}, {}) == "q"


def test_lookup_table_nests_in_if() -> None:
    """``lookupTable`` composes with ``if`` and comparisons."""
    from ws4.io.expressions import evaluate_value

    text = "if(lookupTable(Int(cov),'1,2','Y,N') eq 'Y','yes','no')"
    assert evaluate_value(text, {"cov": 2}, {}) == "no"
    assert evaluate_value(text, {"cov": 1}, {}) == "yes"


def test_comparisons_and_booleans() -> None:
    """Equality, inequality, and the boolean operators evaluate."""
    row = {"status": "C", "oper": "Operable", "ct": "Y", "au": "2121"}
    assert evaluate("status eq 'C' and ct eq 'Y'", row, _CONSTANTS)
    assert evaluate("status ne 'N'", row, _CONSTANTS)
    assert evaluate("status eq 'N' or ct eq 'Y'", row, _CONSTANTS)
    assert not evaluate("status eq 'N'", row, _CONSTANTS)


def test_in_resolves_a_constant() -> None:
    """``in`` resolves a constant name to its value."""
    assert evaluate("status in managed", {"status": "C"}, _CONSTANTS)
    assert not evaluate("status in managed", {"status": "N"}, _CONSTANTS)


def test_functions() -> None:
    """The string and numeric functions evaluate."""
    assert evaluate("startswith(au, 'thn')", {"au": "thn_2121"}, _CONSTANTS)
    assert not evaluate("not startswith(au, 't')", {"au": "thn_2121"}, _CONSTANTS)
    assert evaluate("not startswith(au, 't')", {"au": "2121"}, _CONSTANTS)
    assert evaluate("endswith(au, '21')", {"au": "2121"}, _CONSTANTS)
    assert evaluate("substring('abcde', 0, 1) eq 'a'", {}, _CONSTANTS)
    assert evaluate("length(au) eq 4", {"au": "2121"}, _CONSTANTS)
    assert evaluate("int(au) gt 2000 and int(au) lt 2200", {"au": "2121"}, _CONSTANTS)
    assert evaluate("if(int(au) gt 2000, 'a', 'b') eq 'a'", {"au": "2121"}, _CONSTANTS)


def test_numeric_field_matches_integer_literal() -> None:
    """An integral number matches a numeric string of the same value."""
    assert evaluate("au eq 985501000", {"au": "985501000"}, _CONSTANTS)
    assert not evaluate("au eq 985501000", {"au": "985501001"}, _CONSTANTS)


def test_the_ct_eligibility_expression() -> None:
    """The CT eligibility expression excludes the thinned lane."""
    expression = "status in managed and oper in operable and ct eq 'Y' and not startswith(au,'t')"
    assert evaluate(
        expression, {"status": "C", "oper": "Operable", "ct": "Y", "au": "2121"}, _CONSTANTS
    )
    assert not evaluate(
        expression, {"status": "C", "oper": "Operable", "ct": "Y", "au": "thn_2121"}, _CONSTANTS
    )


def test_unknown_field_raises() -> None:
    """A reference to an unknown field raises."""
    with pytest.raises(ExpressionError):
        evaluate("missing eq 'x'", {"status": "C"}, _CONSTANTS)


def test_unparseable_expression_raises() -> None:
    """A malformed expression raises."""
    with pytest.raises(ExpressionError):
        evaluate("status eq", {"status": "C"}, _CONSTANTS)


def test_curve_reference_survives_arithmetic() -> None:
    """A curve scaled or offset by a constant stays that curve."""
    from ws4.io.expressions import evaluate_value

    assert evaluate_value("curveId('Yield') * 55.0", {}, {}) == "Yield"
    assert evaluate_value("(curveId('Yield') * 89.87) + 2963.0", {}, {}) == "Yield"
    assert evaluate_value("curveId('Yield') - 5", {}, {}) == "Yield"


def test_string_concatenation_still_joins() -> None:
    """``+`` concatenates a label fragment with a (possibly numeric) field."""
    from ws4.io.expressions import evaluate_value

    assert evaluate_value("'Yield_'+au", {"au": 2001}, {}) == "Yield_2001"
    assert evaluate_value("curveId('Yield_'+au)", {"au": 2001}, {}) == "Yield_2001"


def test_numeric_field_arithmetic_is_numeric() -> None:
    """A numeric field divided by a number stays numeric."""
    from ws4.io.expressions import evaluate_value

    assert evaluate_value("Shape_Area/10000", {"Shape_Area": 50000.0}, {}) == 5.0


def test_operable_and_attribute_resolve() -> None:
    """``attribute`` resolves to a curve and ``operable`` keeps its identity."""
    from ws4.io.expressions import evaluate_value

    attributes = {"feature.yield.managed.total": "MG_CWH"}
    assert (
        evaluate_value("operable(attribute('feature.yield.managed.total'))", {}, {}, attributes)
        == "MG_CWH"
    )
    assert evaluate_value("attribute('missing')", {}, {}, {}) == "missing"
