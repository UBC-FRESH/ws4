"""Tests for the target-weight portfolio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from ws4.opt.engine import OptimizeConfig
from ws4.opt.objective import load_targets
from ws4.opt.portfolio import (
    PortfolioMember,
    metrics_from_accounts,
    parse_directions,
    parse_vary,
    run_portfolio,
    scale_targets,
    summarize_members,
    weight_vectors,
)

import portfolio as portfolio_script


def _targets(path: Path) -> Path:
    """Write two periodic targets."""
    path.write_text(
        "targets:\n"
        "  - account: product.volume\n    period: 1\n    minimum: 100\n    min_weight: 1\n"
        "  - account: feature.old\n    period: 1\n    minimum: 10\n    min_weight: 1\n",
        encoding="utf-8",
    )
    return path


class _FakeRunner:
    """Write a deterministic run from the volume target's factor."""

    def __init__(self, config: OptimizeConfig) -> None:
        self.config = config

    def run(self, out_dir: Path) -> dict[str, Any]:
        """Write account values, a schedule, and a summary."""
        out_dir.mkdir(parents=True, exist_ok=True)
        targets = load_targets(Path(self.config.targets_path))
        factor = targets[0].min_weight
        volume = 100.0 * factor
        habitat = 100.0 / factor
        pd.DataFrame(
            [
                {"offset": offset, "account": "product.volume", "value": volume}
                for offset in range(self.config.years)
            ]
            + [
                {"offset": offset, "account": "feature.old", "value": habitat}
                for offset in range(self.config.years)
            ]
        ).to_csv(out_dir / "account_values.csv", index=False)
        pd.DataFrame([{"block_id": 1, "treatment": "CC", "offset": 0}]).to_csv(
            out_dir / "schedule.csv", index=False
        )
        summary = {
            "incumbent_objective": -volume - habitat,
            "status": "ok",
            "seed": self.config.seed,
        }
        (out_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return summary


def test_parse_vary_accepts_semicolon_groups() -> None:
    """Accounts are separated by semicolons and factors by commas."""
    assert parse_vary("product.volume=0.5,1;feature.old=2") == {
        "product.volume": (0.5, 1.0),
        "feature.old": (2.0,),
    }
    with pytest.raises(ValueError, match="positive"):
        parse_vary("a=0")


def test_weight_vectors_cross_the_groups_and_cap_the_product() -> None:
    """The grid is the Cartesian product and refuses an oversized one."""
    vectors = weight_vectors({"a": (1.0, 2.0), "b": (3.0,)}, max_members=4)
    assert vectors == [{"a": 1.0, "b": 3.0}, {"a": 2.0, "b": 3.0}]
    with pytest.raises(ValueError, match="over"):
        weight_vectors({"a": (1.0, 2.0), "b": (3.0, 4.0)}, max_members=3)


def test_scale_targets_multiplies_only_the_matching_weights(tmp_path: Path) -> None:
    """A factor scales the minimum and maximum weights and leaves the bounds alone."""
    base = load_targets(_targets(tmp_path / "targets.yaml"))
    scaled = scale_targets(base, {"product.volume": 2.0})
    assert scaled[0].min_weight == 2.0
    assert scaled[0].minimum == 100
    assert scaled[1].min_weight == 1.0
    with pytest.raises(ValueError, match="names no target"):
        scale_targets(base, {"feature.missing": 2.0})


def test_scale_targets_can_select_one_period(tmp_path: Path) -> None:
    """An account@period key leaves the other periods alone."""
    path = tmp_path / "targets.yaml"
    path.write_text(
        "targets:\n"
        "  - account: product.volume\n    period: 1\n    minimum: 1\n"
        "  - account: product.volume\n    period: 2\n    minimum: 1\n",
        encoding="utf-8",
    )
    scaled = scale_targets(load_targets(path), {"product.volume@2": 3.0})
    assert [target.min_weight for target in scaled] == [1.0, 3.0]


def test_metric_names_select_end_sum_and_offset() -> None:
    """Bare, sum, and explicit-offset selectors read the account frame."""
    frame = pd.DataFrame(
        [
            {"offset": 0, "account": "product.volume", "value": 10.0},
            {"offset": 1, "account": "product.volume", "value": 20.0},
        ]
    )
    assert metrics_from_accounts(frame, ["product.volume"]) == {"product.volume": 20.0}
    assert metrics_from_accounts(frame, ["product.volume@sum"]) == {"product.volume@sum": 30.0}
    assert metrics_from_accounts(frame, ["product.volume@0"]) == {"product.volume@0": 10.0}
    with pytest.raises(ValueError, match="no value"):
        metrics_from_accounts(frame, ["product.volume@5"])


def test_parse_directions_defaults_to_max_and_adds_objective() -> None:
    """Unnamed metrics maximize; objective always minimizes."""
    assert parse_directions(None, ["a", "b"]) == {
        "objective": "min",
        "a": "max",
        "b": "max",
    }
    assert parse_directions("a=min", ["a"])["a"] == "min"
    with pytest.raises(ValueError, match="unknown metric"):
        parse_directions("missing=min", ["a"])


def test_portfolio_writes_members_front_and_archive(tmp_path: Path) -> None:
    """The report contains every member, a nonempty front, and exported schedules."""
    targets = _targets(tmp_path / "targets.yaml")
    report = run_portfolio(
        dataset=tmp_path / "dataset",
        targets=targets,
        out_dir=tmp_path / "portfolio",
        vary={"product.volume": (1.0, 2.0)},
        metrics=["product.volume", "feature.old"],
        seeds=(1, 2),
        iterations=2,
        years=2,
        directions={"product.volume": "max", "feature.old": "max"},
        runner_factory=lambda _dataset, config: _FakeRunner(config),
    )
    assert len(report["members"]) == 4
    assert report["front"]
    assert report["failures"] == 0
    assert (tmp_path / "portfolio" / "portfolio.json").is_file()
    assert (tmp_path / "portfolio" / "portfolio.md").is_file()
    assert (tmp_path / "portfolio" / "front.csv").is_file()
    assert (tmp_path / "portfolio" / "archive" / "archive.json").is_file()
    members = [
        PortfolioMember(
            label=f"m{index}",
            factors={},
            seed=1,
            targets_path=targets,
            run_dir=tmp_path,
            objective=value,
            metrics={},
            schedule_path=None,
            status="ok",
        )
        for index, value in enumerate((3.0, 1.0))
    ]
    assert summarize_members(members)["best"] == 1.0


def test_portfolio_records_a_failed_member(tmp_path: Path) -> None:
    """A failed run is named in the report instead of aborting the portfolio."""
    targets = _targets(tmp_path / "targets.yaml")

    class _Broken:
        def __init__(self, config: OptimizeConfig) -> None:
            self.config = config

        def run(self, out_dir: Path) -> dict[str, Any]:
            raise RuntimeError("boom")

    report = run_portfolio(
        dataset=tmp_path / "dataset",
        targets=targets,
        out_dir=tmp_path / "portfolio",
        vary={"product.volume": (1.0,)},
        metrics=["product.volume"],
        seeds=(1,),
        iterations=1,
        years=1,
        runner_factory=lambda _dataset, config: _Broken(config),
    )
    assert report["failures"] == 1
    assert "boom" in str(report["markdown"])


def test_portfolio_main_wires_the_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI parses the grid, defaults the metrics, and reports success."""
    captured: dict[str, Any] = {}

    def fake(**kwargs: object) -> dict[str, Any]:
        captured.update(kwargs)
        return {"markdown": "# portfolio", "front": [], "failures": 0}

    monkeypatch.setattr(portfolio_script, "run_portfolio", fake)
    code = portfolio_script.main(
        [
            "--dataset",
            str(tmp_path / "dataset"),
            "--targets",
            str(tmp_path / "targets.yaml"),
            "--out",
            str(tmp_path / "out"),
            "--vary",
            "product.volume=1,2",
            "--seeds",
            "1,2",
            "--iterations",
            "3",
        ]
    )
    assert code == 0
    assert captured["vary"] == {"product.volume": (1.0, 2.0)}
    assert captured["metrics"] == ["product.volume"]
    assert captured["seeds"] == [1, 2]


def test_portfolio_main_returns_one_on_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A member failure is a non-zero exit."""
    monkeypatch.setattr(
        portfolio_script,
        "run_portfolio",
        lambda **kwargs: {"markdown": "# portfolio", "front": [], "failures": 1},
    )
    assert (
        portfolio_script.main(
            [
                "--dataset",
                str(tmp_path / "dataset"),
                "--targets",
                str(tmp_path / "targets.yaml"),
                "--out",
                str(tmp_path / "out"),
                "--vary",
                "a=1",
            ]
        )
        == 1
    )
