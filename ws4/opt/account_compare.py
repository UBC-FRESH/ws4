"""Compare mapped process and estate account values.

The process and estate layers do not share account names by default. This module requires an
explicit mapping and compares final-period values. It is a measurement bridge, not a claim that
the two account systems are equivalent.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

ACCOUNT_COMPARISON_VERSION: Final[str] = "ws4.account-comparison.v1"


class AccountComparisonError(ValueError):
    """Raised when account comparison inputs are invalid."""


def _number(value: object, field: str) -> float:
    """Return a finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AccountComparisonError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise AccountComparisonError(f"{field} must be finite")
    return number


def _final_values(
    frame: pd.DataFrame, *, scenario: str | None, label: str
) -> tuple[int, dict[str, float]]:
    """Return final-offset account values after scenario selection."""
    for column in ("offset", "account", "value"):
        if column not in frame.columns:
            raise AccountComparisonError(f"{label} values need a {column!r} column")
    selected = frame
    if "scenario" in frame.columns:
        scenarios = sorted({str(value) for value in frame["scenario"]})
        if scenario is not None:
            selected = frame[frame["scenario"].astype(str) == scenario]
            if selected.empty:
                raise AccountComparisonError(f"unknown {label} scenario: {scenario!r}")
        elif len(scenarios) > 1:
            raise AccountComparisonError(f"{label} values contain multiple scenarios; choose one")
    if selected.empty:
        raise AccountComparisonError(f"{label} values are empty")
    final_offset = int(selected["offset"].max())
    final = selected[selected["offset"] == final_offset]
    if final["account"].duplicated().any():
        raise AccountComparisonError(f"{label} has duplicate final accounts")
    return final_offset, {
        str(row.account): _number(row.value, f"{label} {row.account}")
        for row in final.itertuples(index=False)
    }


@dataclass(frozen=True)
class AccountComparison:
    """Mapped process-versus-estate account comparison.

    Attributes
    ----------
    process_offset : int
        Final process offset.
    estate_offset : int
        Final estate offset.
    rows : pandas.DataFrame
        One row per mapped account.
    """

    process_offset: int
    estate_offset: int
    rows: pd.DataFrame

    def summary(self) -> dict[str, object]:
        """Return a stable JSON-ready summary.

        Returns
        -------
        dict
            Schema version, final offsets, and one row per mapped account.
        """
        return {
            "schema_version": ACCOUNT_COMPARISON_VERSION,
            "process_offset": self.process_offset,
            "estate_offset": self.estate_offset,
            "accounts": [
                {
                    "process_account": str(row.process_account),
                    "estate_account": str(row.estate_account),
                    "process_value": float(str(row.process_value)),
                    "estate_value": float(str(row.estate_value)),
                    "absolute_difference": float(str(row.absolute_difference)),
                    "relative_difference": (
                        None
                        if pd.isna(row.relative_difference)
                        else float(str(row.relative_difference))
                    ),
                }
                for row in self.rows.itertuples(index=False)
            ],
        }

    def write(self, out_dir: Path) -> None:
        """Write the comparison CSV and JSON.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        self.rows.to_csv(target / "account_comparison.csv", index=False)
        (target / "account_comparison.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def compare_accounts(
    process_values: pd.DataFrame,
    estate_values: pd.DataFrame,
    mapping: Mapping[str, str],
    *,
    process_scenario: str | None = None,
    estate_scenario: str | None = None,
) -> AccountComparison:
    """Compare final-period mapped accounts.

    Parameters
    ----------
    process_values : pandas.DataFrame
        Process accounts with ``offset``, ``account``, and ``value``.
    estate_values : pandas.DataFrame
        Estate accounts with the same columns and optional ``scenario``.
    mapping : mapping of str to str
        Process account to estate account.
    process_scenario : str or None, optional
        Process scenario when the frame has one.
    estate_scenario : str or None, optional
        Estate scenario when the frame has more than one.

    Returns
    -------
    AccountComparison
        Final offsets and mapped differences.

    Raises
    ------
    AccountComparisonError
        If the mapping is empty, an account is missing, or scenario selection is ambiguous.
    """
    if not isinstance(mapping, Mapping) or not mapping:
        raise AccountComparisonError("mapping must be a non-empty mapping")
    process_offset, process = _final_values(
        process_values, scenario=process_scenario, label="process"
    )
    estate_offset, estate = _final_values(estate_values, scenario=estate_scenario, label="estate")
    rows: list[dict[str, object]] = []
    for raw_process, raw_estate in sorted(mapping.items()):
        if not isinstance(raw_process, str) or not raw_process.strip():
            raise AccountComparisonError("process account names must be non-empty strings")
        if not isinstance(raw_estate, str) or not raw_estate.strip():
            raise AccountComparisonError("estate account names must be non-empty strings")
        if raw_process not in process:
            raise AccountComparisonError(f"missing process account: {raw_process!r}")
        if raw_estate not in estate:
            raise AccountComparisonError(f"missing estate account: {raw_estate!r}")
        difference = process[raw_process] - estate[raw_estate]
        relative = None if estate[raw_estate] == 0.0 else difference / estate[raw_estate]
        rows.append(
            {
                "process_account": raw_process,
                "estate_account": raw_estate,
                "process_value": process[raw_process],
                "estate_value": estate[raw_estate],
                "absolute_difference": difference,
                "relative_difference": relative,
            }
        )
    frame = pd.DataFrame(
        rows,
        columns=[
            "process_account",
            "estate_account",
            "process_value",
            "estate_value",
            "absolute_difference",
            "relative_difference",
        ],
    )
    return AccountComparison(process_offset=process_offset, estate_offset=estate_offset, rows=frame)
