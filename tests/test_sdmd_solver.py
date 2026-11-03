"""Tests for the SDMD option-space filter."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.sdmd.constraints import AuConstraint, load_constraints
from ws4.sdmd.diagram import load_diagram
from ws4.sdmd.regimes import Regime, load_regime_library
from ws4.sdmd.solver import (
    SdmdScheduleGuard,
    SdmdSolverError,
    SdmdSolverMap,
    filter_dataset,
    load_solver_map,
    trajectory_reaches_zone,
    trajectory_zones,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"


def _regimes() -> tuple[Regime, ...]:
    """Load the fixture regime library."""
    return load_regime_library(pd.read_csv(FIXTURE / "regimes.csv"))


def _constraints() -> tuple[AuConstraint, ...]:
    """Load the fixture constraint table."""
    return load_constraints(pd.read_csv(FIXTURE / "au_constraints.csv"))


def _dataset(tmp_path: Path) -> Path:
    """Build a small compiled dataset with one treatment table."""
    root = tmp_path / "dataset"
    root.mkdir()
    names = {
        1: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        2: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        3: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        4: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        5: "AU(AU-IDFdk3-PLI)+SILV_STATE(baseline)",
        6: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        7: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        8: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        9: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
        10: "AU(UNKNOWN)+SILV_STATE(baseline)",
        11: "AU(AU-IDFdk3-FDI)+SILV_STATE(baseline)",
    }
    pd.DataFrame({"track_id": list(names), "name": list(names.values())}).to_parquet(
        root / "tracks.parquet", index=False
    )
    rows = [
        (1, 70, "CT60", 40),
        (2, 70, "CC", 0),
        (3, 50, "CC", 0),
        (4, 100, "SEL80", 80),
        (5, 70, "CC", 0),
        (6, 90, "SW40", 60),
        (6, 110, "SW40", 60),
        (7, 90, "SW40", 60),
        (7, 100, "SW40", 60),
        (8, 70, "CT60", 90),
        (9, 70, "CT60", 20),
        (10, 70, "CT60", 40),
        (11, 70, "XYZ", 40),
    ]
    pd.DataFrame(
        {
            "track_id": [row[0] for row in rows],
            "begin": [row[1] for row in rows],
            "end": [1000 for _ in rows],
            "treatment": [row[2] for row in rows],
            "new_track": [100 + index for index in range(len(rows))],
            "offset": [0 for _ in rows],
            "retain": [row[3] for row in rows],
        }
    ).to_parquet(root / "treatments.parquet", index=False)
    pd.DataFrame(
        {
            "fragment_id": [1, 2],
            "block_id": [1, 2],
            "area_ha": [1.0, 2.0],
            "age": [40, 40],
            "track_id": [1, 2],
        }
    ).to_parquet(root / "fragments.parquet", index=False)
    (root / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    return root


def test_filter_keeps_allowed_treatments(tmp_path: Path) -> None:
    """Allowed tracks survive and forbidden ones are dropped with reasons."""
    dataset = _dataset(tmp_path)
    output = tmp_path / "filtered"
    report = filter_dataset(dataset, output, _regimes(), _constraints())
    assert report.tracks_before == 11
    assert report.tracks_after == 7
    assert report.treatments_before == 13
    assert report.treatments_after == 9
    assert report.unmapped_tracks == 1
    assert report.unmapped_treatments == 1
    filtered = pd.read_parquet(output / "treatments.parquet")
    assert set(filtered["track_id"]) == {1, 2, 6, 7, 8, 10, 11}
    assert (output / "manifest.json").is_file()


def test_filter_drops_each_forbidden_case(tmp_path: Path) -> None:
    """The report names the entry window, outside-SDMD, denied, interval, and removal cases."""
    output = tmp_path / "filtered"
    report = filter_dataset(_dataset(tmp_path), output, _regimes(), _constraints())
    dropped = {int(str(item["track_id"])): item for item in report.dropped}
    assert set(dropped) == {3, 4, 5, 9}
    for track, needle in ((3, "outside"), (4, "OUTSIDE-SDMD"), (5, "DENIED"), (9, "removes")):
        reasons = dropped[track]["reasons"]
        assert isinstance(reasons, list)
        assert any(needle in str(reason) for reason in reasons)


def test_filter_strict_drops_unmapped(tmp_path: Path) -> None:
    """Strict mode drops an unknown AU and an unknown treatment label."""
    output = tmp_path / "filtered"
    report = filter_dataset(_dataset(tmp_path), output, _regimes(), _constraints(), strict=True)
    assert report.tracks_after == 5
    assert report.treatments_after == 7
    filtered = pd.read_parquet(output / "treatments.parquet")
    assert set(filtered["track_id"]) == {1, 2, 6, 7, 8}


def test_filter_uses_a_sidecar_map(tmp_path: Path) -> None:
    """A map can assign a track to another AU and a label to another regime."""
    map_path = tmp_path / "map.yaml"
    map_path.write_text(
        "tracks:\n  5: AU-IDFdk3-FDI\ntreatments:\n  CC: REG-A-CLEARCUT\n",
        encoding="utf-8",
    )
    mapping = load_solver_map(map_path)
    output = tmp_path / "filtered"
    report = filter_dataset(_dataset(tmp_path), output, _regimes(), _constraints(), mapping=mapping)
    assert report.tracks_after == 8
    filtered = pd.read_parquet(output / "treatments.parquet")
    assert 5 in set(filtered["track_id"])


def test_filter_refuses_to_overwrite_the_input(tmp_path: Path) -> None:
    """An in-place filter would destroy the source table."""
    dataset = _dataset(tmp_path)
    with pytest.raises(SdmdSolverError, match="output_dir"):
        filter_dataset(dataset, dataset, _regimes(), _constraints())


def test_filter_requires_the_compiled_tables(tmp_path: Path) -> None:
    """A directory without tracks or treatments is refused."""
    with pytest.raises(SdmdSolverError, match=r"tracks\.parquet"):
        filter_dataset(tmp_path, tmp_path / "out", _regimes(), _constraints())


def test_map_loader_rejects_a_bad_shape(tmp_path: Path) -> None:
    """The sidecar is a mapping with optional track and treatment maps."""
    path = tmp_path / "map.yaml"
    path.write_text("- not a map\n", encoding="utf-8")
    with pytest.raises(SdmdSolverError, match="mapping"):
        load_solver_map(path)


def test_report_serializes(tmp_path: Path) -> None:
    """The report is JSON-serializable for a run record."""
    report = filter_dataset(_dataset(tmp_path), tmp_path / "filtered", _regimes(), _constraints())
    json.dumps(report.to_dict())
    assert report.to_dict()["tracks_after"] == 7


def test_empty_mapping_is_fine() -> None:
    """The default map keeps the built-in AU and treatment matching."""
    assert SdmdSolverMap().tracks == {}
    assert SdmdSolverMap().treatments == {}


def test_cli_filter_dataset(tmp_path: Path) -> None:
    """The CLI writes the filtered dataset and reports the counts."""
    from typer.testing import CliRunner
    from ws4.cli import app

    dataset = _dataset(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "sdmd",
            "filter-dataset",
            "--dataset",
            str(dataset),
            "--out",
            str(tmp_path / "cli-out"),
            "--regimes",
            str(FIXTURE / "regimes.csv"),
            "--constraints",
            str(FIXTURE / "au_constraints.csv"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "tracks_before" in result.output
    assert (tmp_path / "cli-out" / "treatments.parquet").is_file()


def test_trajectory_zone_check() -> None:
    """A stored path names the SDMD zones it passes through."""
    diagram = load_diagram(
        Path(__file__).resolve().parents[1]
        / "ws4"
        / "sdmd"
        / "data"
        / "sdmd"
        / "idf-dk3-fdi-natural.json"
    )
    points = ((500.0, 0.05), (1000.0, 0.2))
    zones = trajectory_zones(diagram, points)
    assert "density-management" in zones
    assert trajectory_reaches_zone(diagram, points, "density-management")
    assert not trajectory_reaches_zone(diagram, points, "outside")


def test_filter_enforces_the_required_zone(tmp_path: Path) -> None:
    """A track is kept only when its trajectory reaches the required zone."""
    root = _dataset(tmp_path)
    trajectory = tmp_path / "trajectories" / "AU-IDFdk3-FDI" / "REG-A-CT60.json"
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(json.dumps({"points": [[500.0, 0.05]]}) + "\n", encoding="utf-8")
    diagram = load_diagram(
        Path(__file__).resolve().parents[1]
        / "ws4"
        / "sdmd"
        / "data"
        / "sdmd"
        / "idf-dk3-fdi-natural.json"
    )
    filter_dataset(
        root,
        tmp_path / "out",
        _regimes(),
        _constraints(),
        diagram=diagram,
        trajectory_dir=tmp_path / "trajectories",
    )
    filtered = pd.read_parquet(tmp_path / "out" / "treatments.parquet")
    assert 1 in set(filtered["track_id"])
    trajectory.write_text(json.dumps({"points": [[1000.0, 0.5]]}) + "\n", encoding="utf-8")
    second = filter_dataset(
        root,
        tmp_path / "out2",
        _regimes(),
        _constraints(),
        diagram=diagram,
        trajectory_dir=tmp_path / "trajectories",
    )
    filtered = pd.read_parquet(tmp_path / "out2" / "treatments.parquet")
    assert 1 not in set(filtered["track_id"])
    reasons: list[str] = []
    for item in second.dropped:
        item_reasons = item["reasons"]
        if isinstance(item_reasons, list):
            reasons.extend(str(reason) for reason in item_reasons)
    assert any("never reaches" in reason for reason in reasons)


def test_schedule_guard_rejects_an_au_over_its_cap() -> None:
    """Two CT60 entries in one AU exceed the cap of one."""
    guard = SdmdScheduleGuard(
        pd.DataFrame({"block_id": [1, 2], "track_id": [1, 2], "area_ha": [1.0, 1.0]}),
        pd.DataFrame({"track_id": [1, 2], "name": ["AU(AU-IDFdk3-FDI)", "AU(AU-IDFdk3-FDI)"]}),
        pd.DataFrame(
            {
                "track_id": [1, 2],
                "treatment": ["CT60", "CT60"],
                "begin": [60, 60],
                "end": [100, 100],
                "new_track": [0, 0],
                "offset": [0, 0],
                "retain": [40, 40],
            }
        ),
        _regimes(),
        _constraints(),
    )
    schedule = {1: [("CT60", 60)], 2: [("CT60", 70)]}
    problems = guard.check(schedule)
    assert "SDMD-SCHEDULE-ENTRIES" in {item.code for item in problems}
    assert not guard.feasible(schedule)
    assert guard.feasible({1: [("CT60", 60)]})


def test_schedule_guard_rejects_an_interval() -> None:
    """Two shelterwood entries ten years apart break the 20-year interval."""
    guard = SdmdScheduleGuard(
        pd.DataFrame({"block_id": [1, 2], "track_id": [1, 2], "area_ha": [1.0, 1.0]}),
        pd.DataFrame({"track_id": [1, 2], "name": ["AU(AU-IDFdk3-FDI)", "AU(AU-IDFdk3-FDI)"]}),
        pd.DataFrame(
            {
                "track_id": [1, 2],
                "treatment": ["SW40", "SW40"],
                "begin": [90, 90],
                "end": [1000, 1000],
                "new_track": [0, 0],
                "offset": [0, 0],
                "retain": [60, 60],
            }
        ),
        _regimes(),
        _constraints(),
    )
    problems = guard.check({1: [("SW40", 90)], 2: [("SW40", 100)]})
    assert "SDMD-SCHEDULE-INTERVAL" in {item.code for item in problems}
