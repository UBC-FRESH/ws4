"""Generate a useful default even-flow target with a final growing-stock guard.

A new model instance should open with a scenario that does something useful when the
user presses Solve. This module keeps the instance's own periodic and flow targets,
optionally raises its harvest-level aspirations, and adds a final-period floor at 90%
of the initial managed growing stock.

The generated file is written to a caller-provided cache path. The source target file is
never modified.
"""

from __future__ import annotations

import csv
import math
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

STOCK_FRACTION = 0.90
VOLUME_MULTIPLIER = 2.0


def _is_volume_account(account: str) -> bool:
    """Return whether an account is a managed harvest-yield account."""
    lower = account.lower()
    return lower.startswith("product.") and ("harvestedvolume" in lower or "yield" in lower)


def _is_stock_account(account: str) -> bool:
    """Return whether an account is a managed growing-stock total."""
    lower = account.lower()
    return (
        lower.startswith("feature.")
        and "yield" in lower
        and "managed" in lower
        and "total" in lower
    )


def initial_managed_stock(run_dir: Path) -> tuple[str, float] | None:
    """Return the exact account name and initial managed growing-stock value.

    Parameters
    ----------
    run_dir : Path
        A completed run directory containing ``account_values.csv``.

    Returns
    -------
    tuple of str and float or None
        The account label and its initial value, or None when the run has no managed
        growing-stock total at the initial offset.
    """
    path = Path(run_dir) / "account_values.csv"
    if not path.is_file():
        return None
    candidates: list[tuple[str, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("offset")) != "-1":
                continue
            account = str(row.get("account", ""))
            if not _is_stock_account(account):
                continue
            try:
                value = float(str(row.get("value")))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value > 0.0:
                candidates.append((account, value))
    if not candidates:
        return None
    # Prefer the shortest account name when a run carries both aggregate and species
    # totals; the aggregate is the managed growing stock.
    return min(candidates, key=lambda item: (len(item[0]), item[0]))


def find_initial_stock(runs_dir: Path) -> tuple[str, float] | None:
    """Find the newest run under a runs directory that carries managed growing stock.

    Parameters
    ----------
    runs_dir : Path
        A directory of run directories.

    Returns
    -------
    tuple of str and float or None
        The account label and initial value, or None when no run provides it.
    """
    root = Path(runs_dir)
    if not root.is_dir():
        return None
    candidates = sorted(
        (path for path in root.iterdir() if (path / "account_values.csv").is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for directory in candidates:
        found = initial_managed_stock(directory)
        if found is not None:
            return found
    return None


def _target_periods(entries: Sequence[Mapping[str, Any]]) -> int:
    """Return the final period represented by target entries."""
    periods = [
        int(float(str(entry["period"]))) for entry in entries if entry.get("period") is not None
    ]
    return max(periods, default=1)


def _has_stock_guard(
    entries: Sequence[Mapping[str, Any]],
    stock_account: str,
    final_period: int,
    floor: float,
) -> bool:
    """Return whether an entry already protects the requested final-period floor."""
    for entry in entries:
        if str(entry.get("account", "")).lower() != stock_account.lower():
            continue
        if int(float(str(entry.get("period", -1)))) != final_period:
            continue
        minimum = entry.get("minimum")
        if minimum is not None and float(minimum) >= floor * 0.98:
            return True
    return False


def _raise_volume_targets(entries: Sequence[dict[str, Any]], multiplier: float) -> None:
    """Raise managed harvest level targets in place, leaving flow and stock terms alone."""
    for entry in entries:
        account = str(entry.get("account", ""))
        if not _is_volume_account(account) or entry.get("flow"):
            continue
        minimum = entry.get("minimum")
        maximum = entry.get("maximum")
        if minimum is not None:
            entry["minimum"] = float(minimum) * multiplier
        if maximum is not None:
            entry["maximum"] = float(maximum) * multiplier


def build_default_stock90_targets(
    source: Path,
    destination: Path,
    *,
    initial_stock: float,
    stock_account: str,
    volume_multiplier: float = VOLUME_MULTIPLIER,
    stock_fraction: float = STOCK_FRACTION,
) -> Path:
    """Write a default target file with an even-flow structure and a 90% stock floor.

    Parameters
    ----------
    source : Path
        The instance's base targets YAML.
    destination : Path
        The cache path to write.
    initial_stock : float
        Initial managed growing stock.
    stock_account : str
        The exact growing-stock account label from the run.
    volume_multiplier : float, optional
        Factor applied to managed harvest level targets when the base file has no
        final-period stock guard. Defaults to 2.
    stock_fraction : float, optional
        Final-period stock floor as a fraction of initial stock. Defaults to 0.9.

    Returns
    -------
    Path
        The generated file path.
    """
    raw = yaml.safe_load(Path(source).read_text(encoding="utf-8")) or {}
    entries_raw = raw.get("targets", []) if isinstance(raw, dict) else []
    entries: list[dict[str, Any]] = [
        dict(entry) for entry in entries_raw if isinstance(entry, Mapping)
    ]
    final_period = _target_periods(entries)
    floor = float(initial_stock) * float(stock_fraction)
    existing = [
        entry
        for entry in entries
        if str(entry.get("account", "")).lower() == stock_account.lower()
        and entry.get("period") is not None
        and int(float(str(entry.get("period")))) == final_period
    ]
    if existing:
        weak = any(
            entry.get("minimum") is None or float(entry.get("minimum", 0.0)) < floor
            for entry in existing
        )
        for entry in existing:
            minimum = entry.get("minimum")
            if minimum is None or float(minimum) < floor:
                entry["minimum"] = floor
                entry["min_weight"] = max(10.0, float(entry.get("min_weight", 1.0)))
                entry["max_weight"] = max(1.0, float(entry.get("max_weight", 1.0)))
                entry["normalization"] = "auto"
                entry["notes"] = (
                    f"Default scenario: {stock_fraction:.0%} of initial managed "
                    f"growing stock {initial_stock:.2f} = {floor:.2f}."
                )
        if weak:
            _raise_volume_targets(entries, volume_multiplier)
    else:
        _raise_volume_targets(entries, volume_multiplier)
        priority = max(
            (int(entry.get("priority", 1)) for entry in entries if entry.get("priority")),
            default=1,
        )
        entries.append(
            {
                "account": stock_account,
                "period": final_period,
                "period_width": 10,
                "flow": "",
                "minimum": floor,
                "maximum": None,
                "min_weight": 10.0,
                "max_weight": 1.0,
                "shape": "linear",
                "normalization": "auto",
                "priority": priority,
                "active": True,
                "notes": (
                    f"Default scenario: {stock_fraction:.0%} of initial managed "
                    f"growing stock {initial_stock:.2f} = {floor:.2f}."
                ),
            }
        )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump({"targets": entries}, sort_keys=False), encoding="utf-8")
    return destination


def copy_default_targets(source: Path, destination: Path) -> Path:
    """Copy a base target file when no stock account can be detected.

    Parameters
    ----------
    source : Path
        The instance's base targets YAML.
    destination : Path
        The cache path to write.

    Returns
    -------
    Path
        The copied file path.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination
