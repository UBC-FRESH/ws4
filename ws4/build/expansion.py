"""Model II stratum-and-track expansion for the matrix builder.

A stratum is a unique combination of state-variable values. A track is a trajectory
over time; a treatment resets state variables, which moves a block to the stratum of
the new values and therefore onto that stratum's track. This module enumerates the
reachable strata from the inventory and the treatment transitions, and assigns each
stratum to the select that governs it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..io.forest_model_xml import Recipe, Select, Term, Treatment


@dataclass(frozen=True)
class Stratum:
    """One stratum: a state-variable combination and its track.

    Attributes
    ----------
    key : tuple of str
        The state-variable values, in the order of the recipe's state variables.
    track_id : int
        The one-based track id.
    select_indices : tuple of int
        The one-based indices of every select that governs this stratum.
    """

    key: tuple[str, ...]
    track_id: int
    select_indices: tuple[int, ...]


def state_variables(recipe: Recipe) -> tuple[str, ...]:
    """Return the state variables: the recipe's non-constant define fields.

    A define bound to a fragment column takes its value from that column; a bare
    define (such as ``treatment``) starts empty and is set by treatments.

    Parameters
    ----------
    recipe : Recipe
        The parsed recipe.

    Returns
    -------
    tuple of str
        The state-variable names, in define order.
    """
    return tuple(recipe.defines)


def state_of(
    row: Mapping[str, object], variables: Sequence[str], recipe: Recipe
) -> tuple[str, ...]:
    """Return a row's state-variable values.

    Parameters
    ----------
    row : mapping
        A fragment row, keyed by column name.
    variables : sequence of str
        The state variables, from :func:`state_variables`.
    recipe : Recipe
        The parsed recipe, whose defines bind variables to columns.

    Returns
    -------
    tuple of str
        The state values, in the order of ``variables``.
    """
    values: list[str] = []
    for name in variables:
        column = recipe.defines.get(name)
        values.append(str(row[column]) if column is not None and column in row else "")
    return tuple(values)


def _matches(terms: tuple[Term, ...], row: Mapping[str, object], constants: dict[str, str]) -> bool:
    """Return whether a select statement's terms match a row.

    A term the parser could not evaluate (``op == '?'``) is skipped, so matching is
    best-effort for statements that use the full expression language.
    """
    for term in terms:
        if term.op == "?":
            continue
        if term.field not in row:
            return False
        actual = str(row[term.field])
        expected = constants.get(term.value, term.value) if term.op == "in" else term.value
        if term.op in ("eq", "in"):
            if actual != expected:
                return False
        elif term.op == "ne":
            if actual == expected:
                return False
        else:
            try:
                left, right = float(actual), float(expected)
            except ValueError:
                return False
            if (term.op == "lt" and not left < right) or (term.op == "le" and not left <= right):
                return False
            if (term.op == "gt" and not left > right) or (term.op == "ge" and not left >= right):
                return False
    return True


def matching_selects(
    key: tuple[str, ...],
    variables: Sequence[str],
    selects: Sequence[Select],
    constants: dict[str, str],
) -> tuple[int, ...]:
    """Return the one-based indices of every select that governs a stratum.

    A stratum is governed by every select whose statement matches it, not only the
    first; features, products, and treatments accumulate across the matching selects.
    """
    row = dict(zip(variables, key, strict=True))
    return tuple(
        index
        for index, select in enumerate(selects, start=1)
        if _matches(select.terms, row, constants)
    )


def transition_key(
    key: tuple[str, ...], variables: Sequence[str], treatment: Treatment, constants: dict[str, str]
) -> tuple[str, ...]:
    """Return the state key after a treatment resets its state variables."""
    state = dict(zip(variables, key, strict=True))
    for name, value in treatment.transition.items():
        state[name] = constants.get(value, value)
    return tuple(state.get(name, "") for name in variables)


def expand_strata(fragment_keys: Sequence[tuple[str, ...]], recipe: Recipe) -> list[Stratum]:
    """Enumerate the reachable strata and assign each a track and a select.

    Starts from the inventory strata and follows treatment transitions to a fixed
    point, so strata that exist only after a treatment are included.

    Parameters
    ----------
    fragment_keys : sequence of tuple of str
        The inventory strata, in first-seen order.
    recipe : Recipe
        The parsed recipe.

    Returns
    -------
    list of Stratum
        Every reachable stratum, in discovery order, with its track and select.
    """
    variables = state_variables(recipe)
    keys: list[tuple[str, ...]] = list(dict.fromkeys(fragment_keys))
    known = set(keys)
    frontier = list(keys)
    while frontier:
        key = frontier.pop(0)
        for select_index in matching_selects(key, variables, recipe.selects, recipe.constants):
            for treatment in recipe.selects[select_index - 1].treatments:
                target = transition_key(key, variables, treatment, recipe.constants)
                if target not in known:
                    known.add(target)
                    keys.append(target)
                    frontier.append(target)
    return [
        Stratum(
            key=key,
            track_id=index,
            select_indices=matching_selects(key, variables, recipe.selects, recipe.constants),
        )
        for index, key in enumerate(keys, start=1)
    ]
