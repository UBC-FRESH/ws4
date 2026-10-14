"""Parse a ForestModelXML recipe into structured parts.

The recipe is the established model format: a root ``ForestModel`` with a horizon and
base year, curves, field defines, an input block/area/age definition, an output
definition, and a set of ``select`` blocks that partition the inventory by a statement
and carry features, a track with treatments, and products.

Only the structural subset WS4 needs is parsed here; the full expression language is a
later task. A select statement is read as a conjunction of ``field eq 'value'`` terms.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

Point = tuple[float, float]


class ForestModelXMLError(ValueError):
    """Raised when a recipe violates the ForestModelXML structure."""


@dataclass(frozen=True)
class Attribute:
    """A feature or product attribute.

    The source is either a curve reference or an expression. ``factor`` is the
    optional area or yield modifier expression.
    """

    label: str
    curve: str | None
    expression: str | None
    factor: str | None


@dataclass(frozen=True)
class Treatment:
    """A treatment inside a track."""

    label: str
    min_age: int
    max_age: int
    transition: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Term:
    """One term of a select statement.

    ``op`` is one of ``eq``, ``ne``, ``lt``, ``le``, ``gt``, ``ge``, ``in``, or
    ``?`` for a term the parser cannot evaluate (a function call or a ``not``
    expression).
    """

    field: str
    op: str
    value: str


@dataclass(frozen=True)
class Retention:
    """A retention rule: move a fraction of the area to another state.

    ``factor`` is the retained fraction (a column name or a constant), and
    ``assigns`` are the state-variable values the retained area moves to.
    """

    factor: str
    assigns: dict[str, str]


@dataclass(frozen=True)
class Select:
    """One ``select`` block."""

    statement: str
    terms: tuple[Term, ...]
    features: tuple[Attribute, ...]
    products: tuple[Attribute, ...]
    treatments: tuple[Treatment, ...]
    retention: Retention | None = None
    treatment_context: str = ""
    """The ``treatment eq 'X'`` value, if the select has one.

    A select with a treatment context applies to the stratum that matches its other
    terms, and its products are tagged with ``X``. It is not a stratum dimension.
    """


@dataclass(frozen=True)
class Recipe:
    """A parsed ForestModelXML recipe."""

    horizon: int
    year: int
    match: str
    curves: dict[str, tuple[Point, ...]]
    defines: dict[str, str | None]
    constants: dict[str, str]
    input_block: str
    input_area: str
    input_age: str
    output: dict[str, str]
    selects: tuple[Select, ...]


_OPERATORS: tuple[str, ...] = ("eq", "ne", "lt", "le", "gt", "ge", "in")


def parse_statement(statement: str) -> tuple[Term, ...]:
    """Parse a select statement into a tuple of terms.

    A term is ``field op value`` for a comparison operator, or an opaque term
    (``op='?'``) when the statement uses a function call or a ``not`` expression
    that the parser cannot evaluate.

    Parameters
    ----------
    statement : str
        A statement such as ``"status in managed and oper in operable"``.

    Returns
    -------
    tuple of Term
        The parsed terms.
    """
    terms: list[Term] = []
    for part in statement.split(" and "):
        part = part.strip()
        for op in _OPERATORS:
            needle = f" {op} "
            if needle in part:
                field, value = part.split(needle, 1)
                terms.append(Term(field.strip(), op, value.strip().strip("'")))
                break
        else:
            terms.append(Term(part, "?", ""))
    return tuple(terms)


def _retention(element: ET.Element) -> Retention | None:
    """Return the parsed retention rule for a select, or None."""
    retention = element.find("./retention")
    if retention is None:
        return None
    assigns = {
        assign.get("field", ""): assign.get("value", "") for assign in retention.findall("./assign")
    }
    return Retention(factor=retention.get("factor", ""), assigns=assigns)


def _attribute(element: ET.Element) -> Attribute:
    """Return the parsed attribute element.

    An attribute carries a curve reference or an expression as its source; an
    attribute with neither is rejected.
    """
    label = element.get("label")
    if label is None:
        raise ForestModelXMLError("an attribute needs a label")
    curve = element.find("./curve")
    expression = element.find("./expression")
    curve_id = curve.get("idref") if curve is not None else None
    statement = expression.get("statement") if expression is not None else None
    if curve_id is None and statement is None:
        raise ForestModelXMLError(f"attribute {label!r} needs a curve or an expression")
    return Attribute(
        label=label,
        curve=curve_id,
        expression=statement,
        factor=element.get("factor"),
    )


def _int_or_zero(value: str | None) -> int:
    """Parse an integer, or return 0 for an expression or missing value."""
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _treatment(element: ET.Element) -> Treatment:
    """Return the parsed treatment for a treatment element."""
    label = element.get("label")
    if label is None:
        raise ForestModelXMLError("a treatment needs a label")
    transition: dict[str, str] = {}
    for assign in element.findall("./transition/assign"):
        name = assign.get("field")
        value = assign.get("value")
        if name is not None and value is not None:
            # Keep the raw expression: it may be a constant, a field reference, or
            # a string concatenation such as ``'thn_'+au``.
            transition[name] = value
    return Treatment(
        label=label,
        min_age=_int_or_zero(element.get("minage")),
        max_age=_int_or_zero(element.get("maxage")),
        transition=transition,
    )


def parse_recipe(path: Path) -> Recipe:
    """Parse and validate a ForestModelXML recipe.

    Parameters
    ----------
    path : Path
        Path to the recipe.

    Returns
    -------
    Recipe
        The parsed recipe.

    Raises
    ------
    ForestModelXMLError
        When the recipe violates the required structure.
    """
    root = ET.parse(path).getroot()
    if root.tag != "ForestModel":
        raise ForestModelXMLError(f"root tag must be ForestModel, not {root.tag!r}")
    for name in ("horizon", "year", "match"):
        if root.get(name) is None:
            raise ForestModelXMLError(f"ForestModel needs a {name} attribute")

    curves: dict[str, tuple[Point, ...]] = {}
    for curve in root.findall("./curve"):
        curve_id = curve.get("id")
        if curve_id is None:
            raise ForestModelXMLError("a curve needs an id")
        curves[curve_id] = tuple(
            (float(point.get("x", 0.0)), float(point.get("y", 0.0)))
            for point in curve.findall("./point")
        )
    if not curves:
        raise ForestModelXMLError("the recipe needs at least one curve")

    defines: dict[str, str | None] = {}
    constants: dict[str, str] = {}
    for element in root.findall("./define"):
        name = element.get("field", "")
        constant = element.get("constant")
        if constant is not None:
            constants[name] = constant.strip("'")
        else:
            defines[name] = element.get("column")

    input_element = root.find("./input")
    if input_element is None:
        raise ForestModelXMLError("the recipe needs an <input> element")
    for name in ("block", "area", "age"):
        if input_element.get(name) is None:
            raise ForestModelXMLError(f"<input> needs a {name} attribute")

    output_element = root.find("./output")
    if output_element is None:
        raise ForestModelXMLError("the recipe needs an <output> element")

    selects: list[Select] = []
    for element in root.findall("./select"):
        statement = element.get("statement", "")
        features = tuple(_attribute(a) for a in element.findall("./features/attribute"))
        products = tuple(_attribute(a) for a in element.findall("./products/attribute"))
        treatments = tuple(_treatment(t) for t in element.findall("./track/treatment"))
        for attribute in (*features, *products):
            if attribute.curve is not None and attribute.curve not in curves:
                raise ForestModelXMLError(
                    f"attribute {attribute.label!r} references unknown curve {attribute.curve!r}"
                )
        terms = parse_statement(statement)
        context = next(
            (term.value for term in terms if term.field == "treatment" and term.op == "eq"), ""
        )
        selects.append(
            Select(
                statement=statement,
                terms=terms,
                features=features,
                products=products,
                treatments=treatments,
                retention=_retention(element),
                treatment_context=context,
            )
        )

    if not any(select.treatments for select in selects):
        raise ForestModelXMLError("the recipe needs at least one treatment")

    return Recipe(
        horizon=int(root.get("horizon", 0)),
        year=int(root.get("year", 0)),
        match=root.get("match", "single"),
        curves=curves,
        defines=defines,
        constants=constants,
        input_block=input_element.get("block", "BLOCK"),
        input_area=input_element.get("area", "AREA_HA"),
        input_age=input_element.get("age", "F_AGE"),
        output=dict(output_element.attrib.items()),
        selects=tuple(selects),
    )
