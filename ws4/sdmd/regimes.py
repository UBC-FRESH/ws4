"""Even-aged regime library and state-machine validation.

A regime is a repeated entry, not a one-off schedule. The stored columns give the first
entry age, the entry type, the residual basal area and removal fraction, a cycle length,
and a repeat count. This module expands that into ordered entry ages, validates the
sequence, and marks selection regimes as outside the even-aged SDMD.

The module does not choose a regime and does not run FVS. Solver filtering is P87.7.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from .schema import (
    REGIME_ENTRY_TYPES,
    REGIMES,
    REVIEW_STATUSES,
    Problem,
    coerce_to_schema,
    validate_dataset,
)

SELECTION_ENTRY_TYPES: tuple[str, ...] = ("selection80",)


class SdmdRegimeError(ValueError):
    """Raised when a regime or a regime library is unusable."""


class _RegimeRow(Protocol):
    """The fields of one table row."""

    @property
    def regime_id(self) -> object: ...

    @property
    def au_id(self) -> object: ...

    @property
    def name(self) -> object: ...

    @property
    def entry_age(self) -> object: ...

    @property
    def entry_type(self) -> object: ...

    @property
    def residual_ba_m2_ha(self) -> object: ...

    @property
    def removal_fraction(self) -> object: ...

    @property
    def cycle_length(self) -> object: ...

    @property
    def repeat_count(self) -> object: ...

    @property
    def post_treatment_track(self) -> object: ...

    @property
    def eligibility_expr(self) -> object: ...

    @property
    def operability_expr(self) -> object: ...

    @property
    def constraint_ids(self) -> object: ...

    @property
    def review_status(self) -> object: ...


@dataclass(frozen=True)
class Regime:
    """One silviculture regime as an ordered sequence of entries.

    Attributes
    ----------
    regime_id : str
        Stable regime identifier.
    au_id : str
        The analysis unit the regime belongs to.
    name : str
        Human-readable name.
    entry_age : int
        Age of the first entry.
    entry_type : str
        One of the declared entry types.
    residual_ba_m2_ha : float
        Basal area retained after an entry.
    removal_fraction : float
        Fraction of basal area removed at an entry.
    cycle_length : int
        Years between entries. Zero for a single entry.
    repeat_count : int
        Additional entries after the first.
    post_treatment_track : str or None
        The track the stand follows after the sequence.
    eligibility_expr : str or None
        Eligibility expression, when the regime declares one.
    operability_expr : str or None
        Operability expression, when the regime declares one.
    constraint_ids : tuple of str
        Constraint records that apply to the regime.
    review_status : str
        Review state.
    """

    regime_id: str
    au_id: str
    name: str
    entry_age: int
    entry_type: str
    residual_ba_m2_ha: float
    removal_fraction: float
    cycle_length: int
    repeat_count: int
    post_treatment_track: str | None
    eligibility_expr: str | None
    operability_expr: str | None
    constraint_ids: tuple[str, ...]
    review_status: str

    @property
    def is_untreated(self) -> bool:
        """Return whether the regime is the no-treatment baseline.

        Returns
        -------
        bool
            ``True`` for the ``untreated`` entry type.
        """
        return self.entry_type == "untreated"

    @property
    def is_sdmd_valid(self) -> bool:
        """Return whether the regime can be read on an even-aged SDMD.

        Returns
        -------
        bool
            ``False`` for a selection regime, which the even-aged diagram does not
            describe.
        """
        return self.entry_type not in SELECTION_ENTRY_TYPES

    def entry_ages(self) -> tuple[int, ...]:
        """Return the ordered entry ages.

        Returns
        -------
        tuple of int
            One age per entry, or an empty tuple for the untreated baseline.
        """
        if self.is_untreated:
            return ()
        return tuple(
            self.entry_age + offset * self.cycle_length for offset in range(self.repeat_count + 1)
        )

    def entry_count(self) -> int:
        """Return the number of entries in the sequence.

        Returns
        -------
        int
            Zero for the untreated baseline, otherwise one plus the repeat count.
        """
        return 0 if self.is_untreated else self.repeat_count + 1

    def to_dict(self) -> dict[str, object]:
        """Return the regime as a JSON-serializable mapping.

        Returns
        -------
        dict
            The regime fields, with the entry ages expanded.
        """
        return {
            "regime_id": self.regime_id,
            "au_id": self.au_id,
            "name": self.name,
            "entry_age": self.entry_age,
            "entry_type": self.entry_type,
            "residual_ba_m2_ha": self.residual_ba_m2_ha,
            "removal_fraction": self.removal_fraction,
            "cycle_length": self.cycle_length,
            "repeat_count": self.repeat_count,
            "entry_ages": list(self.entry_ages()),
            "entry_count": self.entry_count(),
            "sdmd_valid": self.is_sdmd_valid,
            "review_status": self.review_status,
        }


def load_regime_library(frame: pd.DataFrame) -> tuple[Regime, ...]:
    """Load and validate a regime table.

    Parameters
    ----------
    frame : pandas.DataFrame
        A table with the ``regimes`` columns.

    Returns
    -------
    tuple of Regime
        The regimes in table order.

    Raises
    ------
    SdmdRegimeError
        If the table fails the schema or a regime fails its sequence checks.
    """
    result = coerce_to_schema(frame, REGIMES)
    problems = validate_dataset({"regimes": result})
    if problems:
        raise SdmdRegimeError(_format(problems))
    regimes = tuple(_regime(row) for row in result.itertuples(index=False))
    sequence = validate_regime_library(regimes)
    if sequence:
        raise SdmdRegimeError(_format(sequence))
    return regimes


def validate_regime(regime: Regime) -> list[Problem]:
    """Validate one regime's fields and entry sequence.

    Parameters
    ----------
    regime : Regime
        The regime.

    Returns
    -------
    list of Problem
        The findings. The list is empty when the regime is valid.
    """
    problems: list[Problem] = []
    for field, value in (
        ("regime_id", regime.regime_id),
        ("au_id", regime.au_id),
        ("name", regime.name),
    ):
        if not value.strip():
            problems.append(
                Problem("SDMD-REGIME-FIELD", f"regimes.{field}", "value must not be empty")
            )
    if regime.entry_type not in REGIME_ENTRY_TYPES:
        problems.append(
            Problem(
                "SDMD-REGIME-ENTRY-TYPE",
                "regimes.entry_type",
                f"unknown entry type {regime.entry_type!r}",
            )
        )
    if regime.review_status not in REVIEW_STATUSES:
        problems.append(
            Problem(
                "SDMD-REGIME-REVIEW",
                "regimes.review_status",
                f"unknown review status {regime.review_status!r}",
            )
        )
    if regime.entry_age < 0:
        problems.append(Problem("SDMD-REGIME-AGE", "regimes.entry_age", "must not be negative"))
    if regime.residual_ba_m2_ha < 0:
        problems.append(
            Problem(
                "SDMD-REGIME-RESIDUAL",
                "regimes.residual_ba_m2_ha",
                "must not be negative",
            )
        )
    if not 0.0 <= regime.removal_fraction <= 1.0:
        problems.append(
            Problem(
                "SDMD-REGIME-REMOVAL",
                "regimes.removal_fraction",
                "must be between zero and one",
            )
        )
    if regime.repeat_count < 0:
        problems.append(
            Problem("SDMD-REGIME-REPEAT", "regimes.repeat_count", "must not be negative")
        )
    if regime.cycle_length < 0:
        problems.append(
            Problem("SDMD-REGIME-CYCLE", "regimes.cycle_length", "must not be negative")
        )
    if regime.repeat_count > 0 and regime.cycle_length <= 0:
        problems.append(
            Problem(
                "SDMD-REGIME-CYCLE",
                "regimes.cycle_length",
                "a repeated entry needs a positive cycle length",
            )
        )
    if regime.is_untreated:
        if regime.entry_age != 0 or regime.repeat_count != 0 or regime.cycle_length != 0:
            problems.append(
                Problem(
                    "SDMD-REGIME-UNTREATED",
                    "regimes.entry_type",
                    "the untreated baseline has no entry, cycle, or repeat",
                )
            )
        if regime.removal_fraction != 0 or regime.residual_ba_m2_ha != 0:
            problems.append(
                Problem(
                    "SDMD-REGIME-UNTREATED",
                    "regimes.entry_type",
                    "the untreated baseline removes no basal area",
                )
            )
    for constraint_id in regime.constraint_ids:
        if not constraint_id.strip():
            problems.append(
                Problem(
                    "SDMD-REGIME-CONSTRAINT-ID",
                    "regimes.constraint_ids",
                    "constraint ids must not be blank",
                )
            )
    return problems


def validate_regime_library(regimes: Sequence[Regime]) -> list[Problem]:
    """Validate a regime library for duplicate ids and sequence errors.

    Parameters
    ----------
    regimes : sequence of Regime
        The regimes.

    Returns
    -------
    list of Problem
        The findings. The list is empty when the library is valid.
    """
    problems: list[Problem] = []
    seen: set[str] = set()
    names: set[tuple[str, str]] = set()
    for regime in regimes:
        problems.extend(validate_regime(regime))
        if regime.regime_id in seen:
            problems.append(
                Problem(
                    "SDMD-REGIME-DUPLICATE",
                    "regimes.regime_id",
                    f"duplicate regime id {regime.regime_id!r}",
                )
            )
        seen.add(regime.regime_id)
        name_key = (regime.au_id, regime.name)
        if name_key in names:
            problems.append(
                Problem(
                    "SDMD-REGIME-DUPLICATE",
                    "regimes.name",
                    f"duplicate regime name {regime.name!r} for {regime.au_id}",
                )
            )
        names.add(name_key)
    return problems


def available_regimes(
    regimes: Sequence[Regime],
    au_id: str,
    *,
    sdmd_only: bool = False,
) -> tuple[Regime, ...]:
    """Return the regimes that belong to an AU.

    Parameters
    ----------
    regimes : sequence of Regime
        The library.
    au_id : str
        The analysis unit.
    sdmd_only : bool
        Exclude regimes that the even-aged diagram cannot describe. Defaults to
        ``False``.

    Returns
    -------
    tuple of Regime
        The matching regimes, in library order.
    """
    return tuple(
        regime
        for regime in regimes
        if regime.au_id == au_id and (regime.is_sdmd_valid or not sdmd_only)
    )


def get_regime(regimes: Sequence[Regime], regime_id: str) -> Regime:
    """Return one regime by id.

    Parameters
    ----------
    regimes : sequence of Regime
        The library.
    regime_id : str
        The regime identifier.

    Returns
    -------
    Regime
        The regime.

    Raises
    ------
    SdmdRegimeError
        If the id is not in the library.
    """
    for regime in regimes:
        if regime.regime_id == regime_id:
            return regime
    raise SdmdRegimeError(f"unknown regime {regime_id!r}")


def _regime(row: _RegimeRow) -> Regime:
    """Build a regime from one table row.

    Parameters
    ----------
    row : object
        An ``itertuples`` row with the ``regimes`` columns.

    Returns
    -------
    Regime
        The parsed regime.
    """
    return Regime(
        regime_id=_text(row.regime_id),
        au_id=_text(row.au_id),
        name=_text(row.name),
        entry_age=int(str(row.entry_age)),
        entry_type=_text(row.entry_type),
        residual_ba_m2_ha=float(str(row.residual_ba_m2_ha)),
        removal_fraction=float(str(row.removal_fraction)),
        cycle_length=int(str(row.cycle_length)),
        repeat_count=int(str(row.repeat_count)),
        post_treatment_track=_optional_text(row.post_treatment_track),
        eligibility_expr=_optional_text(row.eligibility_expr),
        operability_expr=_optional_text(row.operability_expr),
        constraint_ids=_constraint_ids(row.constraint_ids),
        review_status=_text(row.review_status),
    )


def _constraint_ids(value: object) -> tuple[str, ...]:
    """Parse a constraint-id cell.

    Parameters
    ----------
    value : object
        A comma- or semicolon-separated cell.

    Returns
    -------
    tuple of str
        The non-empty ids.
    """
    text = _text(value).replace(";", ",")
    return tuple(part.strip() for part in text.split(",") if part.strip())


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
