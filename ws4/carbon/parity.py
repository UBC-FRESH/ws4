"""Parity, mass-balance, and replay checks for carbon runs."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .libcbm import BIOMASS_POOLS, DOM_POOLS, CarbonRun

DEFAULT_REPLAY_FILES: tuple[str, ...] = (
    "carbon_accounts.csv",
    "carbon_pools.csv",
    "carbon_flux.csv",
    "carbon_manifest.json",
)


@dataclass(frozen=True)
class FrameComparison:
    """One table comparison.

    Attributes
    ----------
    left_rows : int
        Rows in the left table.
    right_rows : int
        Rows in the right table.
    matched_rows : int
        Rows that joined on the key.
    matched_columns : tuple of str
        Value columns compared.
    max_abs : float
        Maximum absolute difference.
    max_rel : float
        Maximum relative difference.
    ok : bool
        Whether the differences are inside the requested tolerance.
    """

    left_rows: int
    right_rows: int
    matched_rows: int
    matched_columns: tuple[str, ...]
    max_abs: float
    max_rel: float
    ok: bool


@dataclass(frozen=True)
class RunComparison:
    """A comparison of two carbon runs.

    Attributes
    ----------
    pools : FrameComparison
        Pool comparison.
    flux : FrameComparison
        Flux comparison.
    ok : bool
        Whether both comparisons pass.
    """

    pools: FrameComparison
    flux: FrameComparison

    @property
    def ok(self) -> bool:
        """Return whether both pool and flux comparisons pass.

        Returns
        -------
        bool
            True when both comparisons pass.
        """
        return self.pools.ok and self.flux.ok


def compare_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    key: Sequence[str] = ("timestep", "identifier"),
    columns: Sequence[str] | None = None,
    atol: float = 1e-6,
    rtol: float = 1e-6,
) -> FrameComparison:
    """Compare two carbon tables on a key.

    Parameters
    ----------
    left : pandas.DataFrame
        The left table.
    right : pandas.DataFrame
        The right table.
    key : sequence of str, optional
        Join columns. Defaults to ``("timestep", "identifier")``.
    columns : sequence of str or None, optional
        Value columns. Defaults to the numeric columns present in both tables.
    atol : float, optional
        Absolute tolerance. Defaults to 1e-6.
    rtol : float, optional
        Relative tolerance. Defaults to 1e-6.

    Returns
    -------
    FrameComparison
        The comparison.
    """
    keys = list(key)
    missing = [column for column in keys if column not in left or column not in right]
    if missing:
        return FrameComparison(
            left_rows=len(left),
            right_rows=len(right),
            matched_rows=0,
            matched_columns=(),
            max_abs=float("inf"),
            max_rel=float("inf"),
            ok=False,
        )
    left_keys = left.loc[:, keys].copy()
    right_keys = right.loc[:, keys].copy()
    if left_keys.duplicated().any() or right_keys.duplicated().any():
        return FrameComparison(
            left_rows=len(left),
            right_rows=len(right),
            matched_rows=0,
            matched_columns=(),
            max_abs=float("inf"),
            max_rel=float("inf"),
            ok=False,
        )
    merged = left.merge(right, on=keys, suffixes=("_left", "_right"), how="inner")
    if columns is None:
        value_columns = [
            column
            for column in left.columns
            if column not in keys
            and column in right.columns
            and pd.api.types.is_numeric_dtype(left[column])
            and pd.api.types.is_numeric_dtype(right[column])
        ]
    else:
        value_columns = [
            column for column in columns if column in left.columns and column in right.columns
        ]
    max_abs = 0.0
    max_rel = 0.0
    for column in value_columns:
        difference = (
            pd.to_numeric(merged[f"{column}_left"], errors="coerce")
            - pd.to_numeric(merged[f"{column}_right"], errors="coerce")
        ).abs()
        denominator = (
            pd.to_numeric(merged[f"{column}_right"], errors="coerce").abs().clip(lower=1e-12)
        )
        max_abs = max(max_abs, float(difference.max()) if not difference.empty else 0.0)
        relative = difference / denominator
        max_rel = max(max_rel, float(relative.max()) if not relative.empty else 0.0)
    matched = len(merged)
    ok = (
        matched == len(left) == len(right)
        and (max_abs <= atol or max_rel <= rtol)
        and bool(value_columns)
    )
    return FrameComparison(
        left_rows=len(left),
        right_rows=len(right),
        matched_rows=matched,
        matched_columns=tuple(value_columns),
        max_abs=max_abs,
        max_rel=max_rel,
        ok=ok,
    )


def compare_carbon_runs(
    left: CarbonRun,
    right: CarbonRun,
    *,
    atol: float = 1e-6,
    rtol: float = 1e-6,
) -> RunComparison:
    """Compare two carbon runs.

    Parameters
    ----------
    left : CarbonRun
        The left run.
    right : CarbonRun
        The right run.
    atol : float, optional
        Absolute tolerance.
    rtol : float, optional
        Relative tolerance.

    Returns
    -------
    RunComparison
        Pool and flux comparisons.
    """
    return RunComparison(
        pools=compare_frames(left.pools, right.pools, atol=atol, rtol=rtol),
        flux=compare_frames(left.flux, right.flux, atol=atol, rtol=rtol),
    )


def mass_balance(run: CarbonRun) -> pd.DataFrame:
    """Summarize the carbon totals and their period changes.

    This is an account-to-pool reconciliation, not a claim that every CBM flux
    closes a simplified ledger. It checks that the totals are finite and
    non-negative and that the period change matches the account difference.

    Parameters
    ----------
    run : CarbonRun
        The engine output.

    Returns
    -------
    pandas.DataFrame
        ``timestep``, biomass, DOM, products, ecosystem, total, delta, and
        ``non_negative`` columns.
    """
    pools = run.pools.groupby("timestep", sort=True).sum(numeric_only=True)
    biomass = _sum(pools, BIOMASS_POOLS)
    dom = _sum(pools, DOM_POOLS)
    products = (
        pools["Products"] if "Products" in pools.columns else pd.Series(0.0, index=pools.index)
    )
    ecosystem = biomass + dom
    total = ecosystem + products
    frame = pd.DataFrame(
        {
            "timestep": pools.index.astype(int),
            "biomass_tc": biomass.to_numpy(),
            "dom_tc": dom.to_numpy(),
            "products_tc": products.to_numpy(),
            "ecosystem_tc": ecosystem.to_numpy(),
            "total_tc": total.to_numpy(),
        }
    )
    frame["delta_total_tc"] = frame["total_tc"].diff().fillna(0.0)
    numeric = frame.loc[:, ["biomass_tc", "dom_tc", "products_tc", "ecosystem_tc", "total_tc"]]
    frame["non_negative"] = bool((numeric.to_numpy() >= 0.0).all())
    return frame


def replay_equal(
    left_dir: Path,
    right_dir: Path,
    *,
    files: Sequence[str] = DEFAULT_REPLAY_FILES,
) -> bool:
    """Return whether the selected run files are byte-identical.

    Parameters
    ----------
    left_dir : Path
        First run directory.
    right_dir : Path
        Second run directory.
    files : sequence of str, optional
        File names to compare.

    Returns
    -------
    bool
        True when every file exists in both directories and the digests match.
    """
    for name in files:
        left = Path(left_dir) / name
        right = Path(right_dir) / name
        if not left.is_file() or not right.is_file():
            return False
        if _sha256(left) != _sha256(right):
            return False
    return True


def _sum(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
    """Sum the columns that exist."""
    present = [column for column in columns if column in frame.columns]
    if not present:
        return pd.Series(0.0, index=frame.index)
    return frame.loc[:, present].sum(axis=1)


def _sha256(path: Path) -> str:
    """Return a file's hex SHA-256 digest."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
