"""Tests for the live target-window watcher."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
from rich.console import Console
from typer.testing import CliRunner
from ws4.build.compiler import build_canonical_dataset
from ws4.cli import app
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target, load_targets
from ws4.opt.watch import (
    TargetWindow,
    WatchState,
    chart_cells,
    format_value,
    period_label,
    period_totals,
    run_watch,
    target_window,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path) -> Path:
    """Compile the synthetic fixture."""
    return build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "c"
    )


def _values() -> pd.DataFrame:
    """Two accounts over four simulation offsets."""
    return pd.DataFrame(
        {
            "offset": [0, 1, 2, 3, 0],
            "account": ["a", "a", "a", "a", "b"],
            "value": [1.0, 2.0, 3.0, 4.0, 10.0],
        }
    )


def test_format_value_uses_si_suffixes() -> None:
    """Values render with k, M, and G suffixes."""
    assert format_value(950.0) == "950"
    assert format_value(12_500.0) == "12.5k"
    assert format_value(1_300_000.0) == "1.3M"
    assert format_value(2_500_000_000.0) == "2.5G"


def test_period_totals_sums_the_named_accounts_per_period() -> None:
    """Values are summed by year into periods; other accounts are ignored."""
    assert period_totals(_values(), ["a"], 2, 4) == [3.0, 7.0]
    assert period_totals(_values(), ["a", "b"], 4, 4) == [20.0]
    assert period_totals(_values(), ["missing"], 2, 4) == [0.0, 0.0]


def test_target_window_bands_penalties_and_statuses() -> None:
    """The window sums per-year levels and scores each period."""
    targets = [
        Target("a", 1, minimum=1.0, maximum=2.0),
        Target("a", 2, minimum=1.0, maximum=2.0),
        Target("a", 3, minimum=1.0, maximum=2.0),
        Target("a", 4, minimum=1.0, maximum=2.0),
    ]
    window = target_window(_values(), targets, ["a"], 2, 4, label="account a")
    assert window.account == "account a"
    assert window.realized == (3.0, 7.0)
    assert window.minimum == (2.0, 2.0)
    assert window.maximum == (4.0, 4.0)
    assert window.shortfalls() == (0.0, 0.0)
    assert window.excesses() == (0.0, 3.0)
    assert window.penalties() == (0.0, 3.0)
    assert window.total_penalty() == 3.0
    assert window.statuses() == ("ok", "above")


def test_target_window_without_levels_has_an_open_window() -> None:
    """A period with no target has no minimum or maximum and no penalty."""
    window = target_window(_values(), [], ["a"], 2, 4)
    assert window.minimum == (None, None)
    assert window.maximum == (None, None)
    assert window.statuses() == ("ok", "ok")
    assert window.total_penalty() == 0.0


def test_chart_cells_colour_the_realized_bar_by_status() -> None:
    """A period below, inside, and above its window is drawn red, green, and blue."""
    window = TargetWindow(
        account="a",
        period_width=1,
        realized=(5.0, 15.0, 25.0),
        minimum=(10.0, 10.0, 10.0),
        maximum=(20.0, 20.0, 20.0),
    )
    assert window.statuses() == ("below", "ok", "above")
    cells = chart_cells(window, height=10)
    styles = [
        {cells[row][period][1] for row in range(len(cells)) if cells[row][period][0] == "#"}
        for period in range(3)
    ]
    assert styles == [{"red"}, {"green"}, {"blue"}]


def test_run_watch_returns_a_summary_and_paints_the_frame(tmp_path: Path) -> None:
    """A plain run evaluates the schedule and prints the watched account."""
    dataset = _dataset(tmp_path)
    optimizer = Optimizer.from_dataset(
        dataset, OptimizeConfig(years=2, iterations=4, seed=1, warm_start=True)
    )
    targets = [Target("product.Volume", 0, minimum=300.0, maximum=400.0)]
    stream = StringIO()
    summary = run_watch(
        optimizer,
        targets,
        ["product.Volume"],
        period_width=1,
        plain=True,
        console=Console(file=stream, width=100),
    )
    assert summary["evaluations"] >= 4
    assert isinstance(summary["blocks"], int)
    assert "product.Volume" in stream.getvalue()


def test_last_account_values_exposes_the_evaluation(tmp_path: Path) -> None:
    """The optimizer keeps the account values of its most recent evaluation."""
    dataset = _dataset(tmp_path)
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=2, iterations=1, seed=1))
    empty = optimizer.last_account_values()
    assert list(empty.columns) == ["offset", "account", "value"]
    assert empty.empty
    optimizer._evaluate({1: (("CC", 0),)}, [Target("product.Volume", period=1, minimum=0.0)])
    values = optimizer.last_account_values()
    assert not values.empty
    assert "product.Volume" in {str(a) for a in values["account"]}


def test_a_flow_target_does_not_change_the_account_window() -> None:
    """A flow target is a percent term, not an account level, so the window ignores it."""
    values = pd.DataFrame([{"offset": 0, "account": "a", "value": 5.0}])
    level = Target("a", period=1, minimum=1.0)
    flow = Target("a", 0, flow="even", minimum=-1.0, maximum=1.0, min_weight=10.0)
    window = target_window(values, [level, flow], ("a",), 1, 1)
    assert window.minimum == (1.0,)
    assert window.maximum == (None,)


def test_period_labels_start_at_one() -> None:
    """Period 0 is the pre-simulation state, so simulated periods are numbered from 1."""
    assert period_label(0) == "1"
    assert period_label(4) == "5"


def test_a_percentage_account_is_averaged_over_a_period() -> None:
    """A patch size-class share is a mean over the period, not a sum."""
    account = "patch.h.10_50.size"
    values = pd.DataFrame(
        [
            {"offset": 0, "account": account, "value": 40.0},
            {"offset": 1, "account": account, "value": 60.0},
        ]
    )
    assert period_totals(values, (account,), 2, 2) == [100.0]
    assert period_totals(values, (account,), 2, 2, mean=True) == [50.0]
    window = target_window(values, [Target(account, period=1, minimum=100.0)], (account,), 2, 2)
    assert window.realized == (50.0,)
    assert window.minimum == (100.0,)
    assert window.total_penalty() == 50.0


def test_a_watch_state_builds_one_window_per_account() -> None:
    """Each watched account gets its own target window, not a summed one."""
    state = WatchState(
        label="a+b",
        accounts=("a", "b"),
        period_width=1,
        years=2,
        targets=(Target("a", 1, minimum=1.0), Target("b", 2, minimum=2.0)),
    )
    state.best_values = pd.DataFrame(
        [
            {"offset": 0, "account": "a", "value": 1.0},
            {"offset": 1, "account": "b", "value": 3.0},
        ]
    )
    windows = state.current_windows()
    assert [window.account for window in windows] == ["a", "b"]
    assert windows[0].realized == (1.0, 0.0)
    assert windows[1].realized == (0.0, 3.0)
    assert windows[0].total_penalty() == 0.0
    assert windows[1].total_penalty() == 0.0


def test_watch_command_shows_two_windows(tmp_path: Path) -> None:
    """Repeating --account paints one window per account."""
    dataset = _dataset(tmp_path)
    targets = tmp_path / "two.yaml"
    targets.write_text(
        "targets:\n  - account: product.Volume\n    period: 1\n    minimum: 300\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        [
            "watch",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets),
            "--account",
            "product.Volume",
            "--account",
            "feature.Volume",
            "--years",
            "2",
            "--period-width",
            "1",
            "--iterations",
            "3",
            "--plain",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "product.Volume" in result.output
    assert "feature.Volume" in result.output


def test_watch_command_prints_a_frame(tmp_path: Path) -> None:
    """The command runs a short search and prints the watched account."""
    dataset = _dataset(tmp_path)
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: product.Volume\n    period: 1\n"
        "    minimum: 300\n    maximum: 400\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        [
            "watch",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets),
            "--account",
            "product.Volume",
            "--years",
            "2",
            "--period-width",
            "1",
            "--iterations",
            "3",
            "--warm-start",
            "--plain",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "product.Volume" in result.output


def test_watch_command_accepts_the_adaptive_schedule(tmp_path: Path) -> None:
    """The watch command runs with the adaptive temperature schedule."""
    dataset = _dataset(tmp_path)
    targets = tmp_path / "adaptive.yaml"
    targets.write_text(
        "targets:\n  - account: product.Volume\n    period: 1\n"
        "    minimum: 300\n    maximum: 400\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        [
            "watch",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets),
            "--account",
            "product.Volume",
            "--years",
            "2",
            "--period-width",
            "1",
            "--iterations",
            "12",
            "--cooling-mode",
            "adaptive",
            "--cooling-window",
            "4",
            "--plain",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "product.Volume" in result.output


def test_watch_runs_islands(tmp_path: Path) -> None:
    """The watcher can run parallel islands and still finish with a summary."""
    dataset = _dataset(tmp_path)
    targets_path = tmp_path / "islands.yaml"
    targets_path.write_text(
        "targets:\n  - account: product.Volume\n    period: 1\n"
        "    minimum: 300\n    maximum: 400\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=2,
            iterations=5,
            seed=1,
            warm_start=True,
            islands=2,
            workers=2,
            targets_path=str(targets_path),
        ),
    )
    stream = StringIO()
    summary = run_watch(
        optimizer,
        load_targets(targets_path),
        ["product.Volume"],
        period_width=1,
        plain=True,
        console=Console(file=stream, width=100),
    )
    assert summary["objective"] < float("inf")
    assert summary["blocks"] > 0


def test_watch_command_needs_an_account(tmp_path: Path) -> None:
    """With no account and no targets there is nothing to watch."""
    dataset = _dataset(tmp_path)
    targets = tmp_path / "empty.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")
    result = CliRunner().invoke(
        app, ["watch", "--dataset", str(dataset), "--targets", str(targets)]
    )
    assert result.exit_code == 1


@pytest.mark.parametrize("period_width", [1, 5])
def test_period_width_matches_the_requested_bucket(period_width: int) -> None:
    """The number of periods follows the requested width."""
    window = target_window(_values(), [], ["b"], period_width, 4)
    assert window.n_periods == (4 + period_width - 1) // period_width
