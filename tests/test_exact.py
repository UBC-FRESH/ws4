"""Tests for the exact option-selection lane."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner
from ws4.build.compiler import build_canonical_dataset
from ws4.cli import app
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.exact import solve_option_model, write_exact_result
from ws4.opt.objective import load_targets

from exact_vs_heuristic import main, run_comparison

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    period: 1\n    maximum: 500\n",
        encoding="utf-8",
    )
    return dataset, targets


def test_exact_lane_writes_a_replayed_schedule(tmp_path: Path) -> None:
    """The option model solves and the replay writes the normal run artefacts."""
    dataset, targets = _setup(tmp_path)
    goal_list = load_targets(targets)
    result = solve_option_model(dataset, goal_list, 1)
    report = write_exact_result(tmp_path / "exact", dataset, goal_list, 1, result)
    assert result.status == "optimal"
    assert report["model"] == "option-selection"
    assert (tmp_path / "exact" / "mip.json").is_file()
    assert (tmp_path / "exact" / "schedule.csv").is_file()
    assert (tmp_path / "exact" / "account_values.csv").is_file()
    assert (tmp_path / "exact" / "report_targets.csv").is_file()
    assert float(report["actual_target_penalty"]) >= 0.0


def test_exact_vs_heuristic_reports_a_gap(tmp_path: Path) -> None:
    """The comparison writes both schedules and a numeric gap."""
    dataset, targets = _setup(tmp_path)
    report = run_comparison(
        dataset=dataset,
        targets=targets,
        out_dir=tmp_path / "compare",
        years=1,
        iterations=2,
    )
    assert report["exact"]["status"] == "optimal"
    assert isinstance(report["gap"], float)
    assert (tmp_path / "compare" / "exact_vs_heuristic.json").is_file()
    assert (tmp_path / "compare" / "exact_vs_heuristic.md").is_file()
    assert "Exact versus heuristic" in str(report["markdown"])


def test_exact_cli_writes_the_report(tmp_path: Path) -> None:
    """The script exposes the comparison as a command."""
    dataset, targets = _setup(tmp_path)
    assert (
        main(
            [
                "--dataset",
                str(dataset),
                "--targets",
                str(targets),
                "--out",
                str(tmp_path / "cli"),
                "--years",
                "1",
                "--iterations",
                "2",
            ]
        )
        == 0
    )
    payload = json.loads((tmp_path / "cli" / "exact_vs_heuristic.json").read_text(encoding="utf-8"))
    assert payload["exact"]["status"] == "optimal"


def test_optimizer_records_the_lp_bound(tmp_path: Path) -> None:
    """--lp-bound adds the LP bound, gap, and status to the summary."""
    dataset, targets = _setup(tmp_path)
    cfg = OptimizeConfig(targets_path=str(targets), years=1, iterations=2, seed=1, lp_bound=True)
    summary = Optimizer.from_dataset(dataset, cfg).run(tmp_path / "run")
    assert summary["lp_status"] == "optimal"
    assert "lp_bound" in summary
    assert "lp_gap" in summary


def test_solve_mip_command_writes_the_lane(tmp_path: Path) -> None:
    """The ws4 solve-mip command wires the exact lane."""
    dataset, targets = _setup(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "solve-mip",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets),
            "--out",
            str(tmp_path / "mip"),
            "--years",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "mip" / "mip.json").is_file()
