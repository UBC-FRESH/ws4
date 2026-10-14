"""Tests for the ForestModelXML parser."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.io.forest_model_xml import ForestModelXMLError, parse_recipe, parse_statement

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic" / "recipe.xml"


def test_parse_recipe_reads_the_structure() -> None:
    """The synthetic recipe parses into the expected structure."""
    recipe = parse_recipe(_FIXTURE)
    assert recipe.horizon == 120
    assert recipe.match == "single"
    assert "unity" in recipe.curves
    assert len(recipe.selects) == 3
    product_select = recipe.selects[2]
    assert product_select.treatment_context == "CC"
    assert product_select.products[0].label == "product.Volume"
    treatment = recipe.selects[0].treatments[0]
    assert treatment.label == "CC"
    assert treatment.transition == {"IFM": "'managed'"}
    feature = recipe.selects[0].features[0]
    assert feature.label == "feature.Volume"
    assert feature.curve == "natural_volume"


def test_parse_statement_reads_a_conjunction() -> None:
    """A statement of ``field eq 'value'`` terms parses into terms."""
    terms = parse_statement("IFM eq 'managed' and AU eq 1")
    assert [(term.field, term.op, term.value) for term in terms] == [
        ("IFM", "eq", "managed"),
        ("AU", "eq", "1"),
    ]


def test_parse_statement_supports_in_ne_and_opaque_terms() -> None:
    """The parser handles ``in``, ``ne``, and opaque (function/``not``) terms."""
    terms = parse_statement("status in managed and ct eq 'Y' and not startswith(au,'t')")
    assert (terms[0].field, terms[0].op, terms[0].value) == ("status", "in", "managed")
    assert terms[1].op == "eq"
    assert terms[2].op == "?"


def test_missing_unity_curve_is_rejected(tmp_path: Path) -> None:
    """A recipe without a unity curve is rejected."""
    bad = tmp_path / "bad.xml"
    bad.write_text(
        '<ForestModel horizon="1" year="0" match="single">'
        '<input block="B" area="A" age="G"/><output/></ForestModel>',
        encoding="utf-8",
    )
    with pytest.raises(ForestModelXMLError):
        parse_recipe(bad)


def test_unknown_curve_reference_is_rejected(tmp_path: Path) -> None:
    """A feature that references an undefined curve is rejected."""
    bad = tmp_path / "bad.xml"
    bad.write_text(
        '<ForestModel horizon="1" year="0" match="single">'
        '<curve id="unity"><point x="0" y="1.0"/></curve>'
        '<input block="B" area="A" age="G"/><output/>'
        "<select statement=\"IFM eq 'x'\">"
        '<features><attribute label="feature.X"><curve idref="missing"/></attribute></features>'
        '<track><treatment label="CC" minage="0" maxage="1"/></track>'
        "</select></ForestModel>",
        encoding="utf-8",
    )
    with pytest.raises(ForestModelXMLError):
        parse_recipe(bad)
