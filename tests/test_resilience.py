"""Resilience metric arithmetic, schedule comparison, and run integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.report import write_report
from ws4.resilience import (
    ResilienceError,
    ResilienceMetadata,
    age_class_diversity,
    compare_resilience_runs,
    compute_resilience,
    connectivity_metrics,
    fragmentation_metrics,
)

ESTATE = Path(__file__).resolve().parents[1] / "examples" / "estate"


def _area() -> dict[int, float]:
    """Return a small square block area map."""
    return {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}


def _edges() -> list[tuple[int, int, float]]:
    """Return a line topology 1-2-3 and an isolated block 4."""
    return [(1, 2, 0.0), (2, 3, 0.0)]


def test_connectivity_uses_untreated_components() -> None:
    """A removed middle block splits the line; isolated block 4 stays separate."""
    whole = connectivity_metrics({1, 2, 3, 4}, _edges(), _area())
    split = connectivity_metrics({1, 3, 4}, _edges(), _area())

    assert whole["resilience.connectivity.largest_component"] == pytest.approx(30.0)
    assert whole["resilience.connectivity.component_count"] == pytest.approx(2.0)
    assert split["resilience.connectivity.largest_component"] == pytest.approx(10.0)
    assert split["resilience.connectivity.component_count"] == pytest.approx(3.0)
    assert split["resilience.connectivity.untreated_area"] == pytest.approx(30.0)


def test_age_class_diversity_is_area_weighted() -> None:
    """Shannon rises with two equal age classes and is zero with one class."""
    one = age_class_diversity([(10.0, 10.0), (15.0, 10.0), (18.0, 10.0)])
    two = age_class_diversity([(10.0, 10.0), (30.0, 10.0)])
    uneven = age_class_diversity([(10.0, 30.0), (30.0, 10.0)])

    assert one["resilience.age_class.shannon"] == pytest.approx(0.0)
    assert one["resilience.age_class.count"] == pytest.approx(1.0)
    assert two["resilience.age_class.shannon"] == pytest.approx(0.6931471805599453)
    assert two["resilience.age_class.evenness"] == pytest.approx(1.0)
    assert uneven["resilience.age_class.evenness"] < 1.0


def test_fragmentation_counts_separate_openings() -> None:
    """Adjacent blocks make one patch; isolated blocks make separate patches."""
    compact = fragmentation_metrics({1, 2}, _edges(), _area())
    scattered = fragmentation_metrics({1, 3, 4}, _edges(), _area())

    assert compact["resilience.fragmentation.patch_count"] == pytest.approx(1.0)
    assert scattered["resilience.fragmentation.patch_count"] == pytest.approx(3.0)
    assert (
        scattered["resilience.fragmentation.mean_patch_area"]
        < compact["resilience.fragmentation.mean_patch_area"]
    )


def test_compute_returns_all_three_metric_families() -> None:
    """The combined result exposes connectivity, age, and fragmentation accounts."""
    result = compute_resilience(
        [(10.0, 10.0), (30.0, 10.0)],
        _edges(),
        _area(),
        untreated_blocks={1, 2, 3, 4},
        disturbed_blocks={1},
    )
    assert set(result) >= {
        "resilience.connectivity.largest_component",
        "resilience.age_class.shannon",
        "resilience.fragmentation.patch_count",
    }


def test_metadata_requires_topology_and_schema() -> None:
    """Dropping topology or using an unknown schema is an error."""
    metadata = ResilienceMetadata(topology="topology.csv")
    payload = metadata.to_dict()
    payload.pop("topology")
    with pytest.raises(ResilienceError, match="topology"):
        ResilienceMetadata.from_dict(payload)
    payload = metadata.to_dict()
    payload["schema_version"] = "unknown"
    with pytest.raises(ResilienceError, match="schema_version"):
        ResilienceMetadata.from_dict(payload)


def _run_schedule(tmp_path: Path, schedule: pd.DataFrame, name: str) -> Path:
    """Build the sample estate and run a schedule with resilience enabled."""
    from ws4.build.compiler import build_canonical_dataset
    from ws4.sim.engine import Simulator

    dataset = build_canonical_dataset(
        ESTATE / "recipe.xml", ESTATE / "fragments.csv", tmp_path / "compiled"
    )
    schedule_path = tmp_path / f"{name}.csv"
    schedule.to_csv(schedule_path, index=False)
    out = tmp_path / name
    Simulator.from_dataset(dataset).run(
        schedule_path,
        10,
        out,
        topology_csv=ESTATE / "topology.csv",
        resilience=True,
    )
    return out


def test_simulate_writes_resilience_metrics_and_report(tmp_path: Path) -> None:
    """A run writes per-year metrics, metadata, and a report block."""
    schedule = pd.DataFrame({"block_id": [1, 2, 9, 10], "treatment": ["CC"] * 4, "offset": [0] * 4})
    run = _run_schedule(tmp_path, schedule, "compact")
    metrics = pd.read_csv(run / "resilience_metrics.csv")
    metadata = json.loads((run / "resilience_metadata.json").read_text())

    assert set(metrics["account"]).issuperset(
        {
            "resilience.connectivity.largest_component",
            "resilience.age_class.shannon",
            "resilience.fragmentation.patch_count",
        }
    )
    assert metadata["schema_version"] == "ws4.resilience.v1"
    assert metrics["offset"].min() == -1

    values = pd.read_csv(run / "account_values.csv")
    write_report(values, [], run)
    report = pd.read_csv(run / "report_resilience.csv")
    assert "resilience.fragmentation.patch_count" in set(report["account"])
    flow = report.loc[report["account"] == "resilience.fragmentation.patch_count"].iloc[0]
    assert flow["semantics"] == "flow"
    assert flow["total"] == pytest.approx(1.0)
    assert "not a fire model" in report["caveat"].iloc[0]


def test_identical_schedules_produce_identical_metrics(tmp_path: Path) -> None:
    """The property test: replaying the same schedule gives the same table."""
    schedule = pd.DataFrame(
        {"block_id": [1, 12, 25, 41], "treatment": ["CC"] * 4, "offset": [0] * 4}
    )
    first = _run_schedule(tmp_path, schedule, "first")
    second = _run_schedule(tmp_path, schedule, "second")
    pd.testing.assert_frame_equal(
        pd.read_csv(first / "resilience_metrics.csv"),
        pd.read_csv(second / "resilience_metrics.csv"),
    )


def test_fragmented_schedule_changes_fragmentation_and_comparison(tmp_path: Path) -> None:
    """Same-year compact versus scattered openings differ, and compare writes both."""
    compact = _run_schedule(
        tmp_path,
        pd.DataFrame({"block_id": [1, 2, 9, 10], "treatment": ["CC"] * 4, "offset": [0] * 4}),
        "compact",
    )
    scattered = _run_schedule(
        tmp_path,
        pd.DataFrame({"block_id": [1, 12, 25, 41], "treatment": ["CC"] * 4, "offset": [0] * 4}),
        "scattered",
    )
    compact_metrics = pd.read_csv(compact / "resilience_metrics.csv")
    scattered_metrics = pd.read_csv(scattered / "resilience_metrics.csv")

    def at_zero(account: str, frame: pd.DataFrame) -> float:
        selected = frame[(frame["account"] == account) & (frame["offset"] == 0)]
        return float(selected["value"].iloc[0])

    assert at_zero("resilience.fragmentation.patch_count", compact_metrics) == pytest.approx(1.0)
    assert at_zero("resilience.fragmentation.patch_count", scattered_metrics) == pytest.approx(4.0)
    assert at_zero("resilience.fragmentation.mean_patch_area", scattered_metrics) < at_zero(
        "resilience.fragmentation.mean_patch_area", compact_metrics
    )
    # Non-redundancy: the age-class count is the same while fragmentation differs.
    assert at_zero("resilience.age_class.count", compact_metrics) == at_zero(
        "resilience.age_class.count", scattered_metrics
    )
    comparison = compare_resilience_runs(compact, scattered)
    row = comparison.loc[comparison["account"] == "resilience.fragmentation.patch_count"].iloc[0]
    assert row["unit"] == "count"
    assert row["semantics"] == "flow"
    assert row["run_a_total"] == pytest.approx(1.0)
    assert row["run_b_total"] == pytest.approx(4.0)
    assert row["run_a_mean"] != row["run_b_mean"]
