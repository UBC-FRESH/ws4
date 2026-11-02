"""AU constraint validation and regime filtering.

A constraint declares which regimes an AU may use and the limits on each: the entry-age
window, the maximum number of entries, the minimum interval, and the maximum removal
fraction. ``check_regime`` returns findings, so a caller can fail closed. This module
does not run the optimizer; it supplies the checks that P87.7 will call before model
construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from .regimes import Regime
from .schema import (
    AU_CONSTRAINTS,
    REVIEW_STATUSES,
    SDMD_ZONES,
    Problem,
    coerce_to_schema,
    validate_dataset,
)


class SdmdConstraintError(ValueError):
    """Raised when an AU constraint table is unusable."""


class _ConstraintRow(Protocol):
    """The fields of one table row."""

    @property
    def au_id(self) -> object: ...

    @property
    def regime_id(self) -> object: ...

    @property
    def allowed(self) -> object: ...

    @property
    def min_entry_age(self) -> object: ...

    @property
    def max_entry_age(self) -> object: ...

    @property
    def max_entries(self) -> object: ...

    @property
    def min_interval_years(self) -> object: ...

    @property
    def max_removal_fraction(self) -> object: ...

    @property
    def required_sdmd_zone(self) -> object: ...

    @property
    def source(self) -> object: ...

    @property
    def review_status(self) -> object: ...


@dataclass(frozen=True)
class AuConstraint:
    """One allowed or denied regime for one analysis unit.

    Attributes
    ----------
    au_id : str
        The analysis unit.
    regime_id : str
        The regime the constraint applies to.
    allowed : bool
        Whether the AU may use the regime.
    min_entry_age : int
        Earliest permitted first entry.
    max_entry_age : int
        Latest permitted first entry.
    max_entries : int
        Maximum number of entries.
    min_interval_years : int
        Minimum years between entries.
    max_removal_fraction : float
        Maximum fraction of basal area removed at an entry.
    required_sdmd_zone : str or None
        The SDMD zone the regime must reach, when one is required.
    source : str
        Constraint provenance.
    review_status : str
        Review state.
    """

    au_id: str
    regime_id: str
    allowed: bool
    min_entry_age: int
    max_entry_age: int
    max_entries: int
    min_interval_years: int
    max_removal_fraction: float
    required_sdmd_zone: str | None
    source: str
    review_status: str


def load_constraints(frame: pd.DataFrame) -> tuple[AuConstraint, ...]:
    """Load and validate an AU constraint table.

    Parameters
    ----------
    frame : pandas.DataFrame
        A table with the ``au_constraints`` columns.

    Returns
    -------
    tuple of AuConstraint
        The constraints in table order.

    Raises
    ------
    SdmdConstraintError
        If the schema fails, a window is inverted, or a primary key repeats.
    """
    result = coerce_to_schema(frame, AU_CONSTRAINTS)
    problems = validate_dataset({"au_constraints": result})
    if problems:
        raise SdmdConstraintError(_format(problems))
    constraints = tuple(_constraint(row) for row in result.itertuples(index=False))
    problems = validate_constraints(constraints)
    if problems:
        raise SdmdConstraintError(_format(problems))
    return constraints


def validate_constraint(constraint: AuConstraint) -> list[Problem]:
    """Validate one constraint's fields and limits.

    Parameters
    ----------
    constraint : AuConstraint
        The constraint.

    Returns
    -------
    list of Problem
        The findings. The list is empty when the constraint is valid.
    """
    problems: list[Problem] = []
    if not constraint.au_id.strip():
        problems.append(
            Problem("SDMD-CONSTRAINT-FIELD", "au_constraints.au_id", "must not be empty")
        )
    if not constraint.regime_id.strip():
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-FIELD",
                "au_constraints.regime_id",
                "must not be empty",
            )
        )
    if not constraint.source.strip():
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-FIELD",
                "au_constraints.source",
                "must not be empty",
            )
        )
    if constraint.review_status not in REVIEW_STATUSES:
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-REVIEW",
                "au_constraints.review_status",
                f"unknown review status {constraint.review_status!r}",
            )
        )
    for field, value in (
        ("min_entry_age", constraint.min_entry_age),
        ("max_entry_age", constraint.max_entry_age),
        ("max_entries", constraint.max_entries),
        ("min_interval_years", constraint.min_interval_years),
    ):
        if value < 0:
            problems.append(
                Problem(
                    "SDMD-CONSTRAINT-RANGE",
                    f"au_constraints.{field}",
                    "must not be negative",
                )
            )
    if constraint.min_entry_age > constraint.max_entry_age:
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-WINDOW",
                "au_constraints.min_entry_age",
                "must not exceed max_entry_age",
            )
        )
    if not 0.0 <= constraint.max_removal_fraction <= 1.0:
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-REMOVAL",
                "au_constraints.max_removal_fraction",
                "must be between zero and one",
            )
        )
    if (
        constraint.required_sdmd_zone is not None
        and constraint.required_sdmd_zone not in SDMD_ZONES
    ):
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-ZONE",
                "au_constraints.required_sdmd_zone",
                f"unknown zone {constraint.required_sdmd_zone!r}",
            )
        )
    return problems


def validate_constraints(constraints: Sequence[AuConstraint]) -> list[Problem]:
    """Validate a constraint table for field errors and duplicate keys.

    Parameters
    ----------
    constraints : sequence of AuConstraint
        The constraints.

    Returns
    -------
    list of Problem
        The findings. The list is empty when the table is valid.
    """
    problems: list[Problem] = []
    seen: set[tuple[str, str]] = set()
    for constraint in constraints:
        problems.extend(validate_constraint(constraint))
        key = (constraint.au_id, constraint.regime_id)
        if key in seen:
            problems.append(
                Problem(
                    "SDMD-CONSTRAINT-DUPLICATE",
                    "au_constraints",
                    f"duplicate constraint for {constraint.au_id} / {constraint.regime_id}",
                )
            )
        seen.add(key)
    return problems


def check_regime(constraint: AuConstraint, regime: Regime) -> list[Problem]:
    """Check one regime against one AU constraint.

    Parameters
    ----------
    constraint : AuConstraint
        The AU constraint.
    regime : Regime
        The regime to check.

    Returns
    -------
    list of Problem
        The findings. The list is empty when the regime satisfies the constraint.
    """
    if constraint.au_id != regime.au_id or constraint.regime_id != regime.regime_id:
        return [
            Problem(
                "SDMD-CONSTRAINT-REGIME",
                "au_constraints",
                f"constraint {constraint.au_id}/{constraint.regime_id} does not "
                f"describe regime {regime.au_id}/{regime.regime_id}",
            )
        ]
    if not constraint.allowed:
        return [
            Problem(
                "SDMD-CONSTRAINT-DENIED",
                "au_constraints.allowed",
                f"regime {regime.regime_id!r} is not allowed for {regime.au_id}",
            )
        ]
    if regime.is_untreated:
        return []
    problems: list[Problem] = []
    if not constraint.min_entry_age <= regime.entry_age <= constraint.max_entry_age:
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-ENTRY",
                "regimes.entry_age",
                f"{regime.entry_age} is outside "
                f"[{constraint.min_entry_age}, {constraint.max_entry_age}]",
            )
        )
    if regime.entry_count() > constraint.max_entries:
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-ENTRIES",
                "regimes.repeat_count",
                f"{regime.entry_count()} entries exceed {constraint.max_entries}",
            )
        )
    if regime.entry_count() > 1 and regime.cycle_length < constraint.min_interval_years:
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-INTERVAL",
                "regimes.cycle_length",
                f"{regime.cycle_length} years is below {constraint.min_interval_years}",
            )
        )
    if regime.removal_fraction > constraint.max_removal_fraction + 1e-9:
        problems.append(
            Problem(
                "SDMD-CONSTRAINT-REMOVAL",
                "regimes.removal_fraction",
                f"{regime.removal_fraction:g} exceeds {constraint.max_removal_fraction:g}",
            )
        )
    if constraint.required_sdmd_zone is not None and not regime.is_sdmd_valid:
        problems.append(
            Problem(
                "SDMD-REGIME-OUTSIDE-SDMD",
                "regimes.entry_type",
                f"{regime.entry_type} is outside the even-aged SDMD",
            )
        )
    return problems


def allowed_regimes(
    regimes: Sequence[Regime],
    constraints: Sequence[AuConstraint],
    au_id: str,
) -> tuple[Regime, ...]:
    """Return the regimes an AU may use.

    Parameters
    ----------
    regimes : sequence of Regime
        The regime library.
    constraints : sequence of AuConstraint
        The AU constraints.
    au_id : str
        The analysis unit.

    Returns
    -------
    tuple of Regime
        The allowed regimes that pass every limit, in library order.
    """
    by_id = {
        constraint.regime_id: constraint for constraint in constraints if constraint.au_id == au_id
    }
    result: list[Regime] = []
    for regime in regimes:
        constraint = by_id.get(regime.regime_id)
        if constraint is None:
            continue
        if not check_regime(constraint, regime):
            result.append(regime)
    return tuple(result)


def option_counts(
    before: Sequence[Regime],
    after: Sequence[Regime],
) -> dict[str, int]:
    """Report the option-space size before and after filtering.

    Parameters
    ----------
    before : sequence of Regime
        The unfiltered regimes.
    after : sequence of Regime
        The filtered regimes.

    Returns
    -------
    dict
        Regime and entry counts before and after.
    """
    return {
        "regimes_before": len(before),
        "regimes_after": len(after),
        "entries_before": sum(item.entry_count() for item in before),
        "entries_after": sum(item.entry_count() for item in after),
    }


def _constraint(row: _ConstraintRow) -> AuConstraint:
    """Build a constraint from one table row.

    Parameters
    ----------
    row : object
        An ``itertuples`` row with the ``au_constraints`` columns.

    Returns
    -------
    AuConstraint
        The parsed constraint.
    """
    return AuConstraint(
        au_id=_text(row.au_id),
        regime_id=_text(row.regime_id),
        allowed=bool(row.allowed),
        min_entry_age=int(str(row.min_entry_age)),
        max_entry_age=int(str(row.max_entry_age)),
        max_entries=int(str(row.max_entries)),
        min_interval_years=int(str(row.min_interval_years)),
        max_removal_fraction=float(str(row.max_removal_fraction)),
        required_sdmd_zone=_optional_text(row.required_sdmd_zone),
        source=_text(row.source),
        review_status=_text(row.review_status),
    )


def _text(value: object) -> str:
    """Return trimmed text, or an empty string for a missing value.

    Parameters
    ----------
    value : object
        A cell value.

    Returns
    -------
    str
        The trimmed text.
    """
    if value is None or value is pd.NA:
        return ""
    return str(value).strip()


def _optional_text(value: object) -> str | None:
    """Return trimmed text or ``None``.

    Parameters
    ----------
    value : object
        A cell value.

    Returns
    -------
    str or None
        The trimmed text, or ``None`` when it is missing or blank.
    """
    text = _text(value)
    return text or None


def _format(problems: Sequence[Problem]) -> str:
    """Format findings for an exception message.

    Parameters
    ----------
    problems : sequence of Problem
        The findings.

    Returns
    -------
    str
        One line per finding.
    """
    return "; ".join(f"{item.code} {item.where}: {item.message}" for item in problems)
