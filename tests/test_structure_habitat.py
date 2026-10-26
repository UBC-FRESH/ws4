"""Structure habitat index arithmetic, coverage, account, report, and DHI tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from ws4.report import write_report
from ws4.structure_habitat import (
    STRUCTURE_HABITAT_INDEX_VERSION,
    StructureHabitatAccount,
    StructureHabitatError,
    StructureHabitatSource,
    compare_to_dhi,
    compute_structure_habitat,
    diagnose_femic_canopy_structure,
    diagnose_metrics,
    make_source,
    read_structure_habitat,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "structure_habitat_pilot"
DHI_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "dhi_pilot"


def _metrics() -> pd.DataFrame:
    """Read the committed synthetic exact-metric fixture."""
    return pd.read_csv(EXAMPLE / "structure_metrics.csv")


def _account() -> StructureHabitatAccount:
    """Read the committed stand table and provenance."""
    return read_structure_habitat(
        EXAMPLE / "structure_habitat_stand.csv",
        EXAMPLE / "structure_habitat_metadata.json",
    )


def test_compute_structure_habitat_uses_published_classes_and_boundaries() -> None:
    """Threshold values fall into the lower class; class codes are stable."""
    metrics = pd.DataFrame(
        {
            "block_id": [1, 2, 3, 4],
            "height_p95_m": [10.0, 20.0, 20.1, 9.9],
            "cover_gt_1_37_pct": [33.0, 66.0, 66.1, 32.9],
            "complexity_sd_gt_1_37_m": [3.0, 5.0, 5.1, 2.9],
        }
    )
    result = compute_structure_habitat(metrics)

    assert result["height_class"].tolist() == [0, 1, 2, 0]
    assert result["cover_class"].tolist() == [0, 1, 2, 0]
    assert result["complexity_class"].tolist() == [0, 1, 2, 0]
    assert result["class_code"].tolist() == [0, 13, 26, 0]
    assert result["class_label"].tolist() == ["H0-C0-K0", "H1-C1-K1", "H2-C2-K2", "H0-C0-K0"]


def test_missing_metrics_fail_and_are_not_imputed() -> None:
    """A missing required metric is an error, not a zero fill."""
    with pytest.raises(StructureHabitatError, match="missing"):
        compute_structure_habitat(_metrics().drop(columns=["complexity_sd_gt_1_37_m"]))
    bad = _metrics()
    bad.loc[0, "height_p95_m"] = None
    with pytest.raises(StructureHabitatError, match="non-finite"):
        compute_structure_habitat(bad)


def test_diagnose_metrics_names_the_proxies_and_the_gap() -> None:
    """CHM fields are reported as proxies and never make the index computable."""
    report = cast(
        dict[str, Any],
        diagnose_metrics(["block_id", "chm_p95", "chm_cover_ge_2", "chm_mean"]),
    )
    assert report["index_computable"] is False
    assert report["missing"] == [
        "height_p95_m",
        "cover_gt_1_37_pct",
        "complexity_sd_gt_1_37_m",
    ]
    assert "chm_p95" in report["proxies"]["height_p95_m"]
    assert "1.37" in report["proxies"]["cover_gt_1_37_pct"]
    assert "no first-return" in report["proxies"]["complexity_sd_gt_1_37_m"]
    assert "not computable" in report["message"]


def test_diagnose_femic_canopy_structure_reports_the_real_gap() -> None:
    """The FEMIC canopy summary has only CHM proxies, so the index is unavailable."""
    payload = {
        "height_metrics": {"p95_m": 21.78},
        "cover_fractions": {"ge_2m": 70.94},
    }
    report = cast(dict[str, Any], diagnose_femic_canopy_structure(payload))
    assert report["index_computable"] is False
    assert report["present"] == []
    assert "chm_p95" in report["proxies"]["height_p95_m"]


def test_source_requires_version_and_supported_index() -> None:
    """Dropping provenance or using an unknown index version fails."""
    source = _account().source
    payload = source.to_dict()
    payload.pop("source_version")
    with pytest.raises(StructureHabitatError, match="source_version"):
        StructureHabitatSource.from_dict(payload)
    payload = source.to_dict()
    payload["index_version"] = "unknown"
    with pytest.raises(StructureHabitatError, match="index_version"):
        StructureHabitatSource.from_dict(payload)


def test_account_values_and_landscape_class_areas() -> None:
    """The account is a level: means and class areas over surviving blocks."""
    account = _account()
    areas = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}
    baseline = account.account_values(areas)
    harvested = account.account_values(areas, excluded_blocks={1, 3})

    assert baseline["feature.SHI.area"] == pytest.approx(40.0)
    assert baseline["feature.SHI.height"] == pytest.approx(20.75)
    assert baseline["feature.SHI.cover"] == pytest.approx(56.25)
    assert baseline["feature.SHI.complexity"] == pytest.approx(5.0)
    assert baseline["feature.SHI.height.low_area"] == pytest.approx(10.0)
    assert baseline["feature.SHI.height.medium_area"] == pytest.approx(10.0)
    assert baseline["feature.SHI.height.high_area"] == pytest.approx(20.0)
    assert harvested["feature.SHI.area"] == pytest.approx(20.0)
    assert harvested["feature.SHI.height"] == pytest.approx(25.0)
    assert harvested["feature.SHI.cover"] == pytest.approx(67.5)


def test_simulation_records_structure_trajectory_for_two_schedules(tmp_path: Path) -> None:
    """The baseline stays flat; the harvest schedule removes low/high blocks."""
    from ws4.build.compiler import build_canonical_dataset
    from ws4.sim.engine import Simulator

    dataset = build_canonical_dataset(
        DHI_EXAMPLE / "recipe.xml", DHI_EXAMPLE / "fragments.csv", tmp_path / "compiled"
    )
    account = _account()

    baseline_dir = tmp_path / "baseline"
    Simulator.from_dataset(dataset).run(
        DHI_EXAMPLE / "schedule_baseline.csv",
        10,
        baseline_dir,
        structure_habitat_account=account,
    )
    harvest_dir = tmp_path / "harvest"
    Simulator.from_dataset(dataset).run(
        DHI_EXAMPLE / "schedule_harvest.csv",
        10,
        harvest_dir,
        structure_habitat_account=account,
    )

    baseline = pd.read_csv(baseline_dir / "account_values.csv")
    harvest = pd.read_csv(harvest_dir / "account_values.csv")
    base_height = baseline.loc[baseline["account"] == "feature.SHI.height", "value"].to_numpy()
    harvest_height = harvest.loc[harvest["account"] == "feature.SHI.height", "value"].to_numpy()

    assert base_height.min() == pytest.approx(20.75)
    assert base_height.max() == pytest.approx(20.75)
    assert harvest_height[0] == pytest.approx(20.75)
    assert harvest_height[-1] == pytest.approx(25.0)
    assert (baseline_dir / "structure_habitat_values.csv").is_file()
    assert (baseline_dir / "structure_habitat_landscape.csv").is_file()
    metadata = json.loads((baseline_dir / "structure_habitat_metadata.json").read_text())
    assert metadata["index_version"] == STRUCTURE_HABITAT_INDEX_VERSION


def test_report_writes_structure_block_with_caveat(tmp_path: Path) -> None:
    """The standard report gains a structure table with source and caveat."""
    account = _account()
    areas = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}
    values = pd.DataFrame(
        [
            {"offset": -1, "account": key, "value": value}
            for key, value in account.account_values(areas).items()
        ]
        + [
            {"offset": 0, "account": key, "value": value}
            for key, value in account.account_values(areas, excluded_blocks={1, 3}).items()
        ]
    )
    (tmp_path / "structure_habitat_metadata.json").write_text(
        json.dumps(account.source.to_dict()), encoding="utf-8"
    )

    write_report(values, [], tmp_path)

    report = pd.read_csv(tmp_path / "report_structure_habitat.csv")
    row = report.loc[report["account"] == "feature.SHI.height"].iloc[0]
    assert row["unit"] == "m"
    assert row["final"] == pytest.approx(25.0)
    assert row["index_version"] == STRUCTURE_HABITAT_INDEX_VERSION
    assert "not a species observation" in row["caveat"]


def test_compare_to_dhi_reports_direction_and_sample_size() -> None:
    """The comparison records positive and negative rank agreement explicitly."""
    structure = pd.DataFrame(
        {
            "block_id": [1, 2, 3, 4, 5],
            "height_p95_m": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cover_gt_1_37_pct": [5.0, 4.0, 3.0, 2.0, 1.0],
            "complexity_sd_gt_1_37_m": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    dhi = pd.DataFrame(
        {
            "block_id": [1, 2, 3, 4, 5],
            "cum": [10.0, 20.0, 30.0, 40.0, 50.0],
            "min": [1.0, 1.0, 1.0, 1.0, 1.0],
            "var": [5.0, 4.0, 3.0, 2.0, 1.0],
        }
    )
    result = compare_to_dhi(structure, dhi)
    height_cum = result[
        (result["structure_metric"] == "height_p95_m") & (result["dhi_band"] == "cum")
    ].iloc[0]
    cover_cum = result[
        (result["structure_metric"] == "cover_gt_1_37_pct") & (result["dhi_band"] == "cum")
    ].iloc[0]
    min_row = result[
        (result["structure_metric"] == "height_p95_m") & (result["dhi_band"] == "min")
    ].iloc[0]

    assert height_cum["n"] == 5
    assert height_cum["direction"] == "positive"
    assert height_cum["spearman_r"] == pytest.approx(1.0)
    assert cover_cum["direction"] == "negative"
    assert cover_cum["spearman_r"] == pytest.approx(-1.0)
    assert min_row["direction"] == "unavailable"


def test_compute_is_reproducible() -> None:
    """The same metric table produces byte-equivalent stand values."""
    first = compute_structure_habitat(_metrics())
    second = compute_structure_habitat(_metrics())
    pd.testing.assert_frame_equal(first, second)


def test_source_requires_a_nonempty_version() -> None:
    """The convenience constructor rejects an empty source version."""
    with pytest.raises(StructureHabitatError, match="source_version"):
        make_source(source_id="fixture", source_version=" ")
