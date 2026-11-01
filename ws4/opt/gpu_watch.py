"""Live target-window rendering for a resident GPU population session.

The CPU watcher calls :func:`ws4.opt.watch.run_watch`; this module provides the GPU
equivalent.  It advances one population generation at a time, reads the incumbent's effect
totals directly from the sparse table, and feeds the same :class:`WatchState` and
:func:`render_frame` used by the CPU watcher.

The GPU watcher shows generations rather than CPU iterations.  It requires a persisted
effect table, simulator cache, and candidate cache; building those full-model artifacts is
a separate one-time step.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from rich.console import Console
from rich.live import Live

from .watch import WatchState, render_frame

if TYPE_CHECKING:
    from .gpu_ga import GenomePopulation
    from .objective import Target


def _incumbent_values(population: GenomePopulation) -> pd.DataFrame:
    """Return the incumbent's table-cell values as offset/account/value rows."""
    assert population.scores is not None
    assert population.totals is not None
    import torch

    index = int(torch.argmin(population.scores))
    totals = population.totals[index].detach().cpu().tolist()
    return pd.DataFrame(
        [
            {"offset": int(offset), "account": str(account), "value": float(value)}
            for (offset, account), value in zip(population.table.cells, totals, strict=True)
        ]
    )


def run_gpu_watch(
    population: GenomePopulation,
    targets: list[Target],
    accounts: tuple[str, ...],
    *,
    generations: int,
    period_width: int = 10,
    label: str | None = None,
    refresh: float = 2.0,
    plain: bool = False,
    console: Console | None = None,
    schedule_out: Path | None = None,
    targets_path: Path | None = None,
) -> dict[str, Any]:
    """Run a resident GPU population and paint its target windows per generation.

    Parameters
    ----------
    population : GenomePopulation
        The resident population with its loaded table and option map.
    targets : list of Target
        The exact target set used by the population evaluator.
    accounts : tuple of str
        Account labels to watch.
    generations : int
        Number of evolved generations after the initial evaluation.
    period_width : int, optional
        Years per period. Defaults to 10.
    label : str or None, optional
        Header label; defaults to the accounts joined with ``+``.
    refresh : float, optional
        Minimum seconds between live repaints. Defaults to 2.
    plain : bool, optional
        Print one final frame instead of a live view. Defaults to False.
    console : rich.console.Console or None, optional
        Console to draw on.
    schedule_out : pathlib.Path or None, optional
        Write the final schedule CSV here.
    targets_path : pathlib.Path or None, optional
        Watch this YAML file for target edits. When its mtime changes, the existing
        population is re-priced without recreating the effect table or option map.

    Returns
    -------
    dict
        ``objective``, ``penalty``, ``evaluations``, ``generations``, ``blocks``, and
        ``elapsed``.
    """
    if generations < 0:
        raise ValueError("generations must not be negative")
    console = console if console is not None else Console()
    cfg = population.optimizer.cfg
    cfg.iterations = generations
    cfg.metaheuristic = "gpu-ga"
    accounts_tuple = tuple(accounts)
    from .objective import load_targets

    target_mtime = targets_path.stat().st_mtime_ns if targets_path is not None else None
    last_target_check = 0.0
    last_paint = 0.0
    state = WatchState(
        label=label if label is not None else "+".join(accounts_tuple),
        accounts=accounts_tuple,
        period_width=period_width,
        years=cfg.years,
        targets=tuple(targets),
        point_in_time=tuple(account.name for account in population.optimizer.patch_accounts()),
    )
    state.blocks = len(population.blocks)
    state.islands = population.islands
    started = time.monotonic()

    def update() -> None:
        if population.best_objective >= state.best_objective - 1e-9:
            return
        state.best_objective = population.best_objective
        state.best_values = _incumbent_values(population)
        state.windows = state.current_windows()

    def reload_targets() -> None:
        """Apply a changed target YAML to the resident population."""
        nonlocal targets, target_mtime, last_target_check
        if targets_path is None:
            return
        # Do not touch the shared filesystem on every generation; stat polling belongs
        # outside the hot solver loop.
        now = time.monotonic()
        if now - last_target_check < 1.0:
            return
        last_target_check = now
        try:
            mtime = targets_path.stat().st_mtime_ns
        except OSError:
            return
        if target_mtime == mtime:
            return
        target_mtime = mtime
        try:
            changed = load_targets(targets_path)
            population.update_targets(changed)
        except Exception as error:  # pragma: no cover - live file/UI failure path
            console.print(f"[red]target reload failed:[/] {error}")
            return
        targets = changed
        state.targets = tuple(changed)
        state.accounts = tuple(
            dict.fromkeys([*state.accounts, *(target.account for target in changed)])
        )
        state.best_objective = population.best_objective
        state.best_values = _incumbent_values(population)
        state.windows = state.current_windows()

    population.advance()
    update()
    state.iteration = population.generation
    state.evaluations = population.population
    heartbeat = max(refresh, 0.1)
    live: Live | None = (
        None
        if plain
        else Live(
            console=console,
            auto_refresh=True,
            refresh_per_second=1.0 / heartbeat,
            get_renderable=lambda: render_frame(
                state, population.optimizer, time.monotonic() - started
            ),
        )
    )
    if live is not None:
        with live:
            for _ in range(generations):
                reload_targets()
                population.advance()
                state.iteration = population.generation
                state.evaluations += population.population
                update()
                now = time.monotonic()
                if now - last_paint >= max(refresh, 0.1):
                    last_paint = now
                    live.update(
                        render_frame(state, population.optimizer, now - started),
                        refresh=True,
                    )
            live.update(render_frame(state, population.optimizer, time.monotonic() - started))
        console.print()
    else:
        for _ in range(generations):
            reload_targets()
            population.advance()
        state.iteration = population.generation
        state.evaluations = population.population * (generations + 1)
        update()
        state.windows = state.current_windows()
        console.print(render_frame(state, population.optimizer, time.monotonic() - started))

    if schedule_out is not None:
        from .archive import write_schedule

        write_schedule(schedule_out, population.schedule(population.best_genome))
    elapsed = time.monotonic() - started
    state.windows = state.current_windows()
    return {
        "objective": state.best_objective,
        "penalty": sum(window.total_penalty() for window in state.windows),
        "evaluations": state.evaluations,
        "generations": population.generation,
        "blocks": len(population.blocks),
        "elapsed": elapsed,
    }
