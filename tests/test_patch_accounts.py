"""Tests for patch accounts."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.patch.accounts import (
    PatchAccount,
    PatchLedger,
    load_patch_edges,
    patch_account_values,
    size_class_labels,
)


def test_size_class_labels() -> None:
    """Size classes are labelled by their bounds, the last open-ended."""
    assert size_class_labels((50.0, 150.0, 250.0, 2500.0, float("inf"))) == (
        "0_50",
        "50_150",
        "150_250",
        "250_2500",
        "2500_9999999",
    )


def test_patch_accounts_area_size_and_frequency() -> None:
    """A connected patch is classified by area, and the sub-accounts add up."""
    # Two adjacent blocks of 30 ha each -> one 60 ha patch in the 50_150 class.
    values = {1: 1.0, 2: 1.0, 3: 0.0}
    edges = [(1, 2, 100.0), (2, 3, 100.0)]
    block_area = {1: 30.0, 2: 30.0, 3: 10.0}
    account = PatchAccount(name="patch.d", criteria="feature.d", threshold=0.5)
    result = patch_account_values(account, values, edges, block_area)
    assert result["50_150.area"] == 60.0
    assert result["50_150.frequency"] == 1.0
    assert result["50_150.size"] == pytest.approx(100.0)
    assert result["TOTAL.area"] == 60.0
    assert result["TOTAL.frequency"] == 1.0


def test_a_half_disturbed_block_contributes_half_its_area() -> None:
    """The patch area scales with the criterion value."""
    values = {1: 0.5}
    block_area = {1: 40.0}
    account = PatchAccount(name="patch.d", criteria="feature.d", threshold=0.0)
    result = patch_account_values(account, values, [], block_area)
    assert result["0_50.area"] == 20.0


def test_below_threshold_is_not_a_member() -> None:
    """A block at or below the threshold does not join a patch."""
    values = {1: 0.5}
    account = PatchAccount(name="patch.d", criteria="feature.d", threshold=0.5)
    result = patch_account_values(account, values, [], {1: 40.0})
    assert result["TOTAL.frequency"] == 0.0


def test_patch_ledger_writes_a_frame() -> None:
    """The ledger records one row per period."""
    account = PatchAccount(name="patch.d", criteria="feature.d")
    ledger = PatchLedger([account], [], {1: 10.0})
    ledger.record(0, {"feature.d": {1: 1.0}})
    ledger.record(1, {"feature.d": {}})
    frame = ledger.frame()
    assert list(frame["period"]) == [0.0, 1.0]
    assert "patch.d.TOTAL.area" in frame.columns


def test_load_patch_edges_accepts_the_legacy_columns(tmp_path: Path) -> None:
    """The legacy topology columns are accepted and the sentinel rows dropped."""
    path = tmp_path / "topology.csv"
    path.write_text(
        "BLOCK1,BLOCK2,DISTANCE,LENGTH\n-9999,1,0.0,1070.0\n1,2,0.0,460.0\n",
        encoding="utf-8",
    )
    assert load_patch_edges(path) == [(1, 2, 460.0)]


def test_load_patch_edges_accepts_the_ws4_columns(tmp_path: Path) -> None:
    """The WS4 topology columns are accepted."""
    path = tmp_path / "topology.csv"
    path.write_text("src_block,dst_block,distance_m\n1,2,10.0\n", encoding="utf-8")
    assert load_patch_edges(path) == [(1, 2, 10.0)]


def test_load_patch_edges_rejects_a_missing_block_column(tmp_path: Path) -> None:
    """A topology without block columns is rejected."""
    path = tmp_path / "topology.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no block columns"):
        load_patch_edges(path)
