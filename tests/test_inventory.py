"""Tests for target kinds and the ending-inventory report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target
from ws4.report import ending_inventory, target_kind, target_status, write_report

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _values() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"offset": 0, "account": "feature.Volume", "value": 10.0},
            {"offset": 1, "account": "feature.Volume", "value": 20.0},
            {"offset": 1, "account": "product.Yield", "value": 5.0},
        ]
    )


def test_ending_inventory_reads_the_final_feature_value() -> None:
    """Only feature accounts at the last offset are closing inventory."""
    frame = ending_inventory(_values())
    assert frame.to_dict(orient="records") == [
        {"offset": 1, "account": "feature.Volume", "value": 20.0}
    ]


def test_target_kind_labels_level_and_flow_targets() -> None:
    """A level target and the two flow forms have distinct kinds."""
    assert target_kind(Target("a", period=1)) == "level"
    assert target_kind(Target("a", period=1, flow="even")) == "flow.even"
    assert target_kind(Target("a", period=1, flow="ndy")) == "flow.ndy"
    rows = target_status(_values(), [Target("feature.Volume", period=1, minimum=15.0)])
    assert rows.iloc[0]["kind"] == "level"


def test_write_report_writes_the_ending_inventory(tmp_path: Path) -> None:
    """The report directory carries the ending-inventory table."""
    write_report(
        _values(),
        [Target("feature.Volume", period=1, minimum=15.0)],
        tmp_path / "report",
    )
    frame = pd.read_csv(tmp_path / "report" / "ending_inventory.csv")
    assert frame.to_dict(orient="records") == [
        {"offset": 1, "account": "feature.Volume", "value": 20.0}
    ]


def test_optimizer_summary_carries_the_ending_inventory(tmp_path: Path) -> None:
    """A completed run records and writes the final feature inventory."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    period: 1\n    maximum: 500\n",
        encoding="utf-8",
    )
    cfg = OptimizeConfig(targets_path=str(targets), years=1, iterations=2, seed=1, threads=1)
    summary = Optimizer.from_dataset(dataset, cfg).run(tmp_path / "run")
    ending = summary["ending_inventory"]
    assert isinstance(ending, dict)
    assert ending["offset"] == 0
    assert "feature.Volume" in ending["accounts"]
    assert (tmp_path / "run" / "ending_inventory.csv").is_file()
