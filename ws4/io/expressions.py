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

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<string>'[^']*')"
    r"|(?P<word>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<lparen>\()"
    r"|(?P<rparen>\))"
    r"|(?P<comma>,)"
    r"|(?P<other>\S)"
    r")"
)

_COMPARISONS = {"eq", "ne", "lt", "le", "gt", "ge", "in"}
_FUNCTIONS = {"startswith", "endswith", "substring", "int", "number", "length", "if"}


class ExpressionError(ValueError):
    """Raised when an expression cannot be parsed or evaluated."""


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
        for kind in ("number", "string", "word", "lparen", "rparen", "comma"):
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
        left = self._parse_primary()
        token = self._peek()
        if token is not None and token.kind == "word" and token.value.lower() in _COMPARISONS:
            self._index += 1
            return ("cmp", token.value.lower(), left, self._parse_primary())
        return left

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


def _call(name: str, args: list[Any], row: Mapping[str, object], constants: dict[str, str]) -> Any:
    values = [_evaluate(arg, row, constants) for arg in args]
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
        return float(int(_as_number(values[0])))
    if name == "number":
        return _as_number(values[0])
    if name == "if":
        return values[1] if values[0] else values[2]
    raise ExpressionError(f"unknown function: {name}")


def _evaluate(node: Any, row: Mapping[str, object], constants: dict[str, str]) -> Any:
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "str":
        return node[1]
    if kind == "field":
        return _field(row, node[1], constants)
    if kind == "not":
        return not bool(_evaluate(node[1], row, constants))
    if kind == "bool":
        left = bool(_evaluate(node[2], row, constants))
        right = bool(_evaluate(node[3], row, constants))
        return (left and right) if node[1] == "and" else (left or right)
    if kind == "cmp":
        return _compare(
            node[1], _evaluate(node[2], row, constants), _evaluate(node[3], row, constants)
        )
    if kind == "call":
        return _call(node[1], node[2], row, constants)
    raise ExpressionError(f"unknown node: {kind}")


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


def evaluate(expression: str, row: Mapping[str, object], constants: dict[str, str]) -> bool:
    """Evaluate a select statement against a row.

    Parameters
    ----------
    expression : str
        The select statement.
    row : mapping
        The row's field values.
    constants : dict of str to str
        The recipe's scalar constants.

    Returns
    -------
    bool
        Whether the statement holds for the row.

    Raises
    ------
    ExpressionError
        When the expression cannot be parsed or evaluated.
    """
    tree = _Parser(tokenize(expression)).parse()
    return bool(_evaluate(tree, row, constants))
