"""One-page scenario storyboard from an existing WS4 run."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from .forest_condition import build_report_from_accounts


def build_storyboard(
    values: pd.DataFrame,
    *,
    scenario_id: str,
    generated_utc: str,
    source_version: str = "unversioned",
    provenance: Mapping[str, str] | None = None,
) -> str:
    """Build a Markdown scenario storyboard from account values.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value`` columns.
    scenario_id : str
        Run or scenario identifier.
    generated_utc : str
        ISO-8601 generation timestamp.
    source_version : str, optional
        Run or dataset version.
    provenance : mapping of str to str, optional
        Additional provenance.

    Returns
    -------
    str
        Markdown storyboard. Derived indicators are review-required.

    Raises
    ------
    ValueError
        If the account table is invalid or has no feature accounts.
    """
    card = build_report_from_accounts(
        values,
        report_id=f"{scenario_id}-storyboard",
        scenario_id=scenario_id,
        generated_utc=generated_utc,
        period="run",
        source_version=source_version,
        provenance=provenance,
    )
    return "\n".join(
        [
            f"# Scenario storyboard: {scenario_id}",
            "",
            "This is a report-only view of an existing run. It does not change the",
            "objective, constraints, growth, schedule, or solver.",
            "",
            card.to_markdown().replace("# Forest condition report: ", "## Condition card: ", 1),
            "",
            "## Storyboard limits",
            "",
            "- Derived indicators are `review_required`.",
            "- Alerts are advisory, not operational decisions.",
            "- No new condition source or uncertainty model is included.",
            "",
        ]
    )
