"""A bounded evaluator for the model's select expression language.

Select statements use a SQL-like language: comparison operators (``eq``, ``ne``,
``lt``, ``le``, ``gt``, ``ge``, ``in``), boolean operators (``and``, ``or``,
``not``), parentheses, and a small set of functions (``startswith``,
``endswith``, ``substring``, ``int``, ``Number``, ``length``, ``if``).

This evaluator covers that subset. It is deliberately bounded: an expression it
cannot parse raises :class:`ExpressionError`, and the caller decides how to treat
it (for example, an unresolved term).
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<string>'[^']*')"
    r"|(?P<word>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<arith>[+\-*/])"
    r"|(?P<lparen>\()"
    r"|(?P<rparen>\))"
    r"|(?P<comma>,)"
    r"|(?P<other>\S)"
    r")"
)

_COMPARISONS = {"eq", "ne", "lt", "le", "gt", "ge", "in"}
_FUNCTIONS = {
    "startswith",
    "endswith",
    "substring",
    "int",
    "number",
    "length",
    "if",
    "lastindexof",
    "curveid",
    "attribute",
    "operable",
    "lookuptable",
}


class ExpressionError(ValueError):
    """Raised when an expression cannot be parsed or evaluated."""


class CurveRef(str):
    """A curve reference: a name produced by ``curveId`` or ``attribute``.

    It behaves as a string, so it still concatenates in a label expression, but
    arithmetic can tell it apart from a data value: a curve scaled or offset by a
    constant stays that curve.
    """


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


def tokenize(expression: str) -> list[_Token]:
    """Split an expression into tokens.

    Parameters
    ----------
    expression : str
        The expression text.

    Returns
    -------
    list of _Token
        The tokens, in order.

    Raises
    ------
    ExpressionError
        When the expression contains an unexpected character.
    """
    tokens: list[_Token] = []
    position = 0
    while position < len(expression):
        match = _TOKEN_RE.match(expression, position)
        if match is None or match.end() == position:
            raise ExpressionError(f"unexpected character at {position}: {expression[position:]!r}")
        position = match.end()
        for kind in ("number", "string", "word", "arith", "lparen", "rparen", "comma"):
            value = match.group(kind)
            if value is not None:
                tokens.append(_Token(kind, value))
                break
        else:
            raise ExpressionError(f"unexpected token: {match.group('other')!r}")
    return tokens


class _Parser:
    """A recursive-descent parser for the boolean/comparison subset."""

    def __init__(self, tokens: Sequence[_Token]) -> None:
        self._tokens = tokens
        self._index = 0

    def _peek(self) -> _Token | None:
        return self._tokens[self._index] if self._index < len(self._tokens) else None

    def _next(self) -> _Token:
        token = self._peek()
        if token is None:
            raise ExpressionError("unexpected end of expression")
        self._index += 1
        return token

    def _accept_word(self, word: str) -> bool:
        token = self._peek()
        if token is not None and token.kind == "word" and token.value.lower() == word:
            self._index += 1
            return True
        return False

    def parse(self) -> Any:
        """Parse the whole expression into an AST."""
        node = self._parse_or()
        if self._peek() is not None:
            raise ExpressionError(f"trailing tokens: {self._peek()}")
        return node

    def _parse_or(self) -> Any:
        node = self._parse_and()
        while self._accept_word("or"):
            node = ("bool", "or", node, self._parse_and())
        return node

    def _parse_and(self) -> Any:
        node = self._parse_not()
        while self._accept_word("and"):
            node = ("bool", "and", node, self._parse_not())
        return node

    def _parse_not(self) -> Any:
        if self._accept_word("not"):
            return ("not", self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> Any:
        left = self._parse_additive()
        token = self._peek()
        if token is not None and token.kind == "word" and token.value.lower() in _COMPARISONS:
            self._index += 1
            return ("cmp", token.value.lower(), left, self._parse_additive())
        return left

    def _parse_additive(self) -> Any:
        node = self._parse_multiplicative()
        token = self._peek()
        while token is not None and token.kind == "arith" and token.value in ("+", "-"):
            self._index += 1
            node = ("arith", token.value, node, self._parse_multiplicative())
            token = self._peek()
        return node

    def _parse_multiplicative(self) -> Any:
        node = self._parse_primary()
        token = self._peek()
        while token is not None and token.kind == "arith" and token.value in ("*", "/"):
            self._index += 1
            node = ("arith", token.value, node, self._parse_primary())
            token = self._peek()
        return node

    def _parse_primary(self) -> Any:
        token = self._next()
        if token.kind == "lparen":
            node = self._parse_or()
            if self._next().kind != "rparen":
                raise ExpressionError("missing closing parenthesis")
            return node
        if token.kind == "number":
            return ("num", float(token.value))
        if token.kind == "string":
            return ("str", token.value[1:-1])
        if token.kind == "word":
            if token.value.lower() in _FUNCTIONS and self._peek() is not None:
                nxt = self._peek()
                if nxt is not None and nxt.kind == "lparen":
                    self._index += 1
                    args = self._parse_args()
                    return ("call", token.value.lower(), args)
            return ("field", token.value)
        raise ExpressionError(f"unexpected token: {token}")

    def _parse_args(self) -> list[Any]:
        args: list[Any] = []
        token = self._peek()
        if token is not None and token.kind == "rparen":
            self._index += 1
            return args
        args.append(self._parse_or())
        token = self._peek()
        while token is not None and token.kind == "comma":
            self._index += 1
            args.append(self._parse_or())
            token = self._peek()
        if self._next().kind != "rparen":
            raise ExpressionError("missing closing parenthesis in call")
        return args


def _as_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ExpressionError(f"not a number: {value!r}") from exc


def _field(row: Mapping[str, object], name: str, constants: dict[str, str]) -> str:
    if name in constants:
        return constants[name]
    if name in row:
        value = row[name]
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    raise ExpressionError(f"unknown field: {name}")


def _call(
    name: str,
    args: list[Any],
    row: Mapping[str, object],
    constants: dict[str, str],
    attributes: Mapping[str, str] | None,
) -> Any:
    values = [_evaluate(arg, row, constants, attributes) for arg in args]
    if name == "startswith":
        return str(values[0]).startswith(str(values[1]))
    if name == "endswith":
        return str(values[0]).endswith(str(values[1]))
    if name == "substring":
        text = str(values[0])
        start = int(_as_number(values[1]))
        end = int(_as_number(values[2])) if len(values) > 2 else len(text)
        return text[start:end]
    if name == "length":
        return float(len(str(values[0])))
    if name == "int":
        try:
            return float(int(_as_number(values[0])))
        except ExpressionError:
            return 0.0
    if name == "number":
        try:
            return _as_number(values[0])
        except ExpressionError:
            return 0.0
    if name == "if":
        return values[1] if values[0] else values[2]
    if name == "lastindexof":
        return float(str(values[0]).rfind(str(values[1])))
    if name == "lookuptable":
        return _lookup_table(values[0], str(values[1]), str(values[2]))
    if name == "curveid":
        # A curve reference; the value is its name.
        return CurveRef(str(values[0]))
    if name == "attribute":
        key = str(values[0])
        if attributes is not None and key in attributes:
            return CurveRef(attributes[key])
        return CurveRef(key)
    if name == "operable":
        # ``operable(X)`` marks a curve as restricted to operable area. The curve
        # identity is unchanged here; masking is a runtime concern.
        return values[0]
    raise ExpressionError(f"unknown function: {name}")


_TABLE_CACHE: dict[int, tuple[str, dict[str, str], dict[float, str]]] = {}


def _parse_table(keys_text: str, values_text: str) -> tuple[dict[str, str], dict[float, str]]:
    """Parse a comma-separated lookup table into a string map and a numeric map."""
    string_table: dict[str, str] = {}
    numeric_table: dict[float, str] = {}
    keys = keys_text.split(",")
    entries = values_text.split(",")
    for position, candidate in enumerate(keys):
        key = candidate.strip()
        value = entries[position].strip() if position < len(entries) else ""
        string_table[key] = value
        with contextlib.suppress(ValueError):
            numeric_table[float(key)] = value
    return string_table, numeric_table


def _lookup_table(key: Any, keys_text: str, values_text: str) -> str:
    """Return the value whose position matches ``key`` in a comma-separated table.

    ``lookupTable(k, '1,2,3', 'a,b,c')`` returns ``'b'`` for ``k == 2``. A numeric key
    compares numerically; any other key compares as text. A key that is absent returns an
    empty string.

    The table literals in a recipe are large and constant, so the parsed form is cached by
    the identity of the keys string (the evaluator reuses the same parse tree, so the same
    string object is passed on every call). The cached tuple keeps the string alive and the
    identity is checked, so ``id`` reuse cannot serve a stale table.

    Parameters
    ----------
    key : Any
        The lookup key.
    keys_text : str
        The comma-separated table keys.
    values_text : str
        The comma-separated table values, positionally aligned with ``keys_text``.

    Returns
    -------
    str
        The matching value, or an empty string when the key is absent.
    """
    cached = _TABLE_CACHE.get(id(keys_text))
    if cached is None or cached[0] is not keys_text:
        string_table, numeric_table = _parse_table(keys_text, values_text)
        cached = (keys_text, string_table, numeric_table)
        _TABLE_CACHE[id(keys_text)] = cached
    _, string_table, numeric_table = cached
    try:
        number = float(key)
    except (TypeError, ValueError):
        number = None
    if number is not None:
        match = numeric_table.get(number)
        if match is not None:
            return match
    return string_table.get(str(key), "")


def _evaluate(
    node: Any,
    row: Mapping[str, object],
    constants: dict[str, str],
    attributes: Mapping[str, str] | None = None,
) -> Any:
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "str":
        return node[1]
    if kind == "field":
        return _field(row, node[1], constants)
    if kind == "not":
        return not bool(_evaluate(node[1], row, constants, attributes))
    if kind == "bool":
        # Short-circuit, so an unparsable right operand is not evaluated when the left
        # decides the result (for example ``startswith(au,'t') or int(au) gt 2200``).
        left = bool(_evaluate(node[2], row, constants, attributes))
        if node[1] == "and":
            return left and bool(_evaluate(node[3], row, constants, attributes))
        return left or bool(_evaluate(node[3], row, constants, attributes))
    if kind == "cmp":
        return _compare(
            node[1],
            _evaluate(node[2], row, constants, attributes),
            _evaluate(node[3], row, constants, attributes),
        )
    if kind == "arith":
        return _arith(
            node[1],
            _evaluate(node[2], row, constants, attributes),
            _evaluate(node[3], row, constants, attributes),
        )
    if kind == "call":
        return _call(node[1], node[2], row, constants, attributes)
    raise ExpressionError(f"unknown node: {kind}")


def _arith(op: str, left: Any, right: Any) -> Any:
    """Evaluate an arithmetic or string-concatenation operator.

    ``+`` concatenates two strings (``'a' + 'b'``). When exactly one operand is a
    :class:`CurveRef` — a curve reference such as the result of ``curveId('Yield')`` —
    the curve is kept through arithmetic: a curve scaled or offset by a constant is
    still that curve for matrix purposes, so ``curveId('Yield') * 55 + 2963`` resolves
    to the ``Yield`` curve.
    """
    if op == "+":
        if isinstance(left, CurveRef) and not isinstance(right, CurveRef):
            return left
        if isinstance(right, CurveRef) and not isinstance(left, CurveRef):
            return right
        if isinstance(left, str) or isinstance(right, str):
            return _canonical(left) + _canonical(right)
        return _as_number(left) + _as_number(right)
    if isinstance(left, CurveRef):
        return left
    if isinstance(right, CurveRef):
        return right
    if op == "-":
        return _as_number(left) - _as_number(right)
    if op == "*":
        return _as_number(left) * _as_number(right)
    return _as_number(left) / _as_number(right)


def _compare(op: str, left: Any, right: Any) -> bool:
    if op in ("eq", "in"):
        return _equal(left, right)
    if op == "ne":
        return not _equal(left, right)
    try:
        a, b = _as_number(left), _as_number(right)
    except ExpressionError:
        a, b = str(left), str(right)  # type: ignore[assignment]
    if op == "lt":
        return a < b
    if op == "le":
        return a <= b
    if op == "gt":
        return a > b
    if op == "ge":
        return a >= b
    raise ExpressionError(f"unknown operator: {op}")


def _canonical(value: Any) -> str:
    """Render a value canonically so a number matches a numeric string."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        return left == right
    return _canonical(left) == _canonical(right)


def evaluate_value(
    expression: str,
    row: Mapping[str, object],
    constants: dict[str, str],
    attributes: Mapping[str, str] | None = None,
) -> Any:
    """Evaluate an expression and return its raw value.

    Parameters
    ----------
    expression : str
        The expression text.
    row : mapping
        The row's field values.
    constants : dict of str to str
        The recipe's scalar constants.
    attributes : mapping of str to str, optional
        A label-to-curve-name map for ``attribute('label')`` lookups. When omitted,
        ``attribute('label')`` evaluates to the label itself.

    Returns
    -------
    Any
        The expression's value (a string, number, or boolean).

    Raises
    ------
    ExpressionError
        When the expression cannot be parsed or evaluated.
    """
    return _evaluate(_parse(expression), row, constants, attributes)


@lru_cache(maxsize=2048)
def _parse(expression: str) -> Any:
    """Parse an expression into a tree, caching the tree by the expression text.

    A select statement is re-evaluated for every fragment, so parsing once per distinct
    statement (rather than per fragment) is a large saving on a big inventory. The tree is
    built from immutable tuples and is never mutated, so sharing it is safe.
    """
    return _Parser(tokenize(expression)).parse()


def evaluate(
    expression: str,
    row: Mapping[str, object],
    constants: dict[str, str],
    attributes: Mapping[str, str] | None = None,
) -> bool:
    """Evaluate a select statement against a row.

    Parameters
    ----------
    expression : str
        The select statement.
    row : mapping
        The row's field values.
    constants : dict of str to str
        The recipe's scalar constants.
    attributes : mapping of str to str, optional
        A label-to-curve-name map for ``attribute('label')`` lookups.

    Returns
    -------
    bool
        Whether the statement holds for the row.

    Raises
    ------
    ExpressionError
        When the expression cannot be parsed or evaluated.
    """
    return bool(_evaluate(_parse(expression), row, constants, attributes))
