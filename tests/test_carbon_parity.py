"""Tests for carbon parity, mass balance, and replay checks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.carbon.libcbm import CarbonRun, CbmDefaultsReference
from ws4.carbon.parity import compare_carbon_runs, compare_frames, mass_balance, replay_equal


def _run() -> CarbonRun:
    """Return a tiny synthetic run."""
    pools = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "SoftwoodMerch": [10.0, 11.0],
            "AboveGroundSlowSoil": [2.0, 2.0],
            "Products": [0.0, 1.0],
        }
    )
    flux = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "DeltaBiomass_AG": [1.0, 1.0],
            "DecaySlowAGToAir": [0.2, 0.2],
        }
    )
    return CarbonRun(
        pools=pools,
        flux=flux,
        classifiers=pd.DataFrame(),
        state=pd.DataFrame(),
        libcbm_version="2.10.2",
        defaults=CbmDefaultsReference(
            path=Path("cbm_defaults.db"), version="1.2.9300.391", sha256="b" * 64
        ),
    )


def test_compare_frames_detects_identical_and_changed_values() -> None:
    """The comparator passes identical tables and fails a changed cell."""
    left = _run().pools
    right = _run().pools
    assert compare_frames(left, right).ok

    changed = right.copy()
    changed.loc[1, "SoftwoodMerch"] = 12.0
    result = compare_frames(left, changed)
    assert not result.ok
    assert result.max_abs == 1.0


def test_compare_carbon_runs_checks_pools_and_flux() -> None:
    """The run comparison covers both tables."""
    result = compare_carbon_runs(_run(), _run())
    assert result.ok
    assert result.pools.ok
    assert result.flux.ok


def test_mass_balance_reports_totals_and_non_negative() -> None:
    """The mass-balance table reports totals and a period change."""
    frame = mass_balance(_run())
    assert frame.loc[0, "ecosystem_tc"] == 12.0
    assert frame.loc[1, "total_tc"] == 14.0
    assert frame.loc[1, "delta_total_tc"] == 2.0
    assert bool(frame["non_negative"].all())


def test_replay_equal_compares_files(tmp_path: Path) -> None:
    """Replay equality is a byte comparison of the selected run files."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for root in (left, right):
        (root / "carbon_accounts.csv").write_text("offset,account,value\n0,a,1\n", encoding="utf-8")
    assert replay_equal(left, right, files=("carbon_accounts.csv",))
    (right / "carbon_accounts.csv").write_text("offset,account,value\n0,a,2\n", encoding="utf-8")
    assert not replay_equal(left, right, files=("carbon_accounts.csv",))
