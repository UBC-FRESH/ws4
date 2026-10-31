"""The resident-state watch logs one telemetry step per iteration, even when it paints nothing."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from ws4.opt.model2_trajectory import run_state_watch


class _FakeState:
    """A resident state just large enough to drive the SA loop without a compiled dataset."""

    def __init__(self, blocks: list[int], periods: int, period_width: int, years: int) -> None:
        """Build empty period pages for ``blocks``.

        Parameters
        ----------
        blocks : list of int
            Block identifiers the search may schedule.
        periods : int
            Number of displayed periods.
        period_width : int
            Years per displayed period.
        years : int
            Simulation horizon.
        """
        self.blocks = blocks
        self.periods = periods
        self.period_width = period_width
        self.years = years
        self.accounts: tuple[str, ...] = ()
        self.period_totals = np.zeros((periods, 0), dtype=float)
        self._seed_loaded = True

    def set_block(self, block: int, chain: Any) -> None:  # noqa: ANN401
        """Accept a move without pricing it; the accounts are empty.

        Parameters
        ----------
        block : int
            The block that moved.
        chain : object
            The block's new treatment chain.
        """

    def set_schedule(self, schedule: Any) -> None:  # noqa: ANN401
        """Accept a whole schedule without pricing it.

        Parameters
        ----------
        schedule : mapping
            The block-to-chain schedule.
        """


def _steps(path: Path) -> list[dict[str, object]]:
    """Return the telemetry step records, in file order.

    Parameters
    ----------
    path : pathlib.Path
        The telemetry JSONL file.

    Returns
    -------
    list of dict
        Every record whose ``type`` is ``step``.
    """
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [record for record in records if record["type"] == "step"]


def test_plain_state_watch_logs_every_iteration(tmp_path: Path) -> None:
    """A plain run (the web runner's mode) still writes one step per iteration."""
    state = _FakeState([1, 2], periods=1, period_width=10, years=10)
    candidates = {
        1: [(("CC", 10),), (("CT", 20),)],
        2: [(("CC", 10),), (("CT", 20),)],
    }
    cfg = SimpleNamespace(
        targets_path="targets.yaml",
        iterations=1,
        metaheuristic="state-sa",
        seed=1,
        warm_start=False,
    )
    telemetry = tmp_path / "telemetry.jsonl"

    summary = run_state_watch(
        state,  # type: ignore[arg-type]
        candidates,
        [],
        [],
        SimpleNamespace(cfg=cfg),
        iterations=5,
        plain=True,
        telemetry_path=telemetry,
    )

    steps = _steps(telemetry)
    assert summary["iterations"] == 5
    assert [step["iteration"] for step in steps] == [1, 2, 3, 4, 5]


def test_zero_iteration_plain_watch_still_writes_one_step(tmp_path: Path) -> None:
    """A search with no moves records its objective once rather than leaving no progress behind."""
    state = _FakeState([1], periods=1, period_width=10, years=10)
    cfg = SimpleNamespace(
        targets_path="targets.yaml",
        iterations=1,
        metaheuristic="state-sa",
        seed=1,
        warm_start=False,
    )
    telemetry = tmp_path / "telemetry.jsonl"

    run_state_watch(
        state,  # type: ignore[arg-type]
        {1: [(("CC", 10),)]},
        [],
        [],
        SimpleNamespace(cfg=cfg),
        iterations=0,
        plain=True,
        telemetry_path=telemetry,
    )

    assert [step["iteration"] for step in _steps(telemetry)] == [0]
