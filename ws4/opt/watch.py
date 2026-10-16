"""A live target-window view of an optimization run.

The reference tool draws a *target chart* for each target account: time along one axis, the
account's units along the other, one bar per period, with the minimum and maximum target
levels shown as a band and the realized account value drawn over it. This module reproduces
that view in a terminal: :func:`target_window` aggregates the realized account values and
the target levels into periods, and :func:`render_frame` paints the band and the realized
value while a metaheuristic minimizes the summed penalty.

The objective the optimizer minimizes is the summed **per-year** penalty; the view groups
those years into periods for display. A period's window is the sum of its years' target
levels, so per-year targets that sum to a periodic target read as the periodic window.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING, Any

import pandas as pd
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .core import Problem
from .engine import Optimizer
from .objective import Target
from .operators import Schedule
from .solvers import solve_ils, solve_sa, solve_sa_delta, solve_tabu

if TYPE_CHECKING:
    from .incremental import IncrementalObjective

Cell = tuple[str, str]

_OK = "green"
_BELOW = "red"
_ABOVE = "blue"


def format_value(value: float) -> str:
    """Format an account value with an SI suffix.

    Parameters
    ----------
    value : float
        The value.

    Returns
    -------
    str
        A short human-readable string, for example ``1.3M`` for 1_300_000.
    """
    magnitude = abs(value)
    if magnitude >= 1.0e9:
        return f"{value / 1.0e9:.3g}G"
    if magnitude >= 1.0e6:
        return f"{value / 1.0e6:.3g}M"
    if magnitude >= 1.0e3:
        return f"{value / 1.0e3:.3g}k"
    return f"{value:.4g}"


def period_totals(
    values: pd.DataFrame, accounts: Sequence[str], period_width: int, years: int
) -> list[float]:
    """Sum the given accounts' values over each period.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values, with ``year``, ``account``, and ``value`` columns.
    accounts : sequence of str
        The account labels to sum (more than one sums them into a total).
    period_width : int
        The number of years per period.
    years : int
        The horizon, in years.

    Returns
    -------
    list of float
        One total per period; periods with no rows are zero.
    """
    n_periods = (years + period_width - 1) // period_width
    totals = [0.0] * max(0, n_periods)
    wanted = set(accounts)
    if values.empty or not wanted or period_width <= 0 or years <= 0:
        return totals
    for row in values.itertuples(index=False):
        account = str(row.account)
        if account not in wanted:
            continue
        year = int(float(str(row.year)))
        if year < 0 or year >= years:
            continue
        totals[year // period_width] += float(str(row.value))
    return totals


def _period_levels(
    targets: Sequence[Target], account: str, period_width: int, years: int
) -> tuple[list[float | None], list[float | None]]:
    """Return one account's minimum and maximum per period.

    A target's level is spread over its own period and apportioned to the watcher's periods
    by their overlap: a per-year target sums over the years of a watcher period, while a
    period-width target (the usual case) applies directly.
    """
    n_periods = (years + period_width - 1) // period_width
    minima: list[float | None] = [None] * max(0, n_periods)
    maxima: list[float | None] = [None] * max(0, n_periods)
    for target in targets:
        if target.account != account:
            continue
        width = max(1, target.period_width)
        start = target.year
        stop = target.year + width
        first = max(0, start // period_width)
        last = min((stop - 1) // period_width, n_periods - 1)
        for period in range(first, last + 1):
            window = period * period_width
            overlap = min(stop, window + period_width) - max(start, window)
            if overlap <= 0:
                continue
            if target.minimum is not None:
                minima[period] = (minima[period] or 0.0) + target.minimum * overlap / width
            if target.maximum is not None:
                maxima[period] = (maxima[period] or 0.0) + target.maximum * overlap / width
    return minima, maxima


@dataclass(frozen=True)
class TargetWindow:
    """The realized values and target window of an account over periods.

    Attributes
    ----------
    account : str
        The display label.
    period_width : int
        The number of years per period.
    realized : tuple of float
        The realized account value per period.
    minimum : tuple of float or None
        The minimum target level per period, or None where none is set.
    maximum : tuple of float or None
        The maximum target level per period, or None where none is set.
    """

    account: str
    period_width: int
    realized: tuple[float, ...]
    minimum: tuple[float | None, ...]
    maximum: tuple[float | None, ...]

    @property
    def n_periods(self) -> int:
        """Return the number of periods."""
        return len(self.realized)

    def shortfalls(self) -> tuple[float, ...]:
        """Return each period's shortfall below its minimum (zero when satisfied)."""
        return tuple(
            0.0 if low is None or value >= low else low - value
            for value, low in zip(self.realized, self.minimum, strict=True)
        )

    def excesses(self) -> tuple[float, ...]:
        """Return each period's excess above its maximum (zero when satisfied)."""
        return tuple(
            0.0 if high is None or value <= high else value - high
            for value, high in zip(self.realized, self.maximum, strict=True)
        )

    def penalties(self) -> tuple[float, ...]:
        """Return each period's total penalty."""
        return tuple(
            shortfall + excess
            for shortfall, excess in zip(self.shortfalls(), self.excesses(), strict=True)
        )

    def total_penalty(self) -> float:
        """Return the summed per-period penalty."""
        return sum(self.penalties())

    def statuses(self) -> tuple[str, ...]:
        """Return each period's status: ``ok``, ``below``, or ``above``."""
        result: list[str] = []
        for shortfall, excess in zip(self.shortfalls(), self.excesses(), strict=True):
            if shortfall > 0.0:
                result.append("below")
            elif excess > 0.0:
                result.append("above")
            else:
                result.append("ok")
        return tuple(result)


def target_window(
    values: pd.DataFrame,
    targets: Sequence[Target],
    accounts: Sequence[str],
    period_width: int,
    years: int,
    label: str | None = None,
) -> TargetWindow:
    """Build the realized-versus-target window for the given accounts.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values, with ``year``, ``account``, and ``value`` columns.
    targets : sequence of Target
        The goals; their levels are summed into periods.
    accounts : sequence of str
        The account labels to watch (summed for the realized value and the window).
    period_width : int
        The number of years per period.
    years : int
        The horizon, in years.
    label : str or None, optional
        A display label; defaults to the accounts joined with ``+``.

    Returns
    -------
    TargetWindow
        The realized values and the minimum/maximum window per period.
    """
    n_periods = (years + period_width - 1) // period_width
    minima: list[float | None] = [None] * max(0, n_periods)
    maxima: list[float | None] = [None] * max(0, n_periods)
    for account in accounts:
        account_minima, account_maxima = _period_levels(targets, account, period_width, years)
        for period in range(n_periods):
            low = account_minima[period]
            if low is not None:
                minima[period] = (minima[period] or 0.0) + low
            high = account_maxima[period]
            if high is not None:
                maxima[period] = (maxima[period] or 0.0) + high
    realized = period_totals(values, accounts, period_width, years)
    return TargetWindow(
        account=label if label is not None else "+".join(accounts),
        period_width=period_width,
        realized=tuple(realized),
        minimum=tuple(minima),
        maximum=tuple(maxima),
    )


def axis_maximum(window: TargetWindow) -> float:
    """Return a value-axis maximum that fits the realized values and the window."""
    candidates = [abs(value) for value in window.realized]
    candidates += [value for value in window.minimum if value is not None]
    candidates += [value for value in window.maximum if value is not None]
    if not candidates:
        return 1.0
    peak = max(candidates)
    return peak * 1.05 if peak > 0.0 else 1.0


def chart_cells(window: TargetWindow, height: int) -> list[list[Cell]]:
    """Return the chart as character cells, top row first.

    Each cell is ``(character, style)``. A realized bar is ``#`` coloured by the period's
    status (green when inside the window, red below the minimum, blue above the maximum);
    the target window band above the bar is a dim ``:``; an empty cell is a space.

    Parameters
    ----------
    window : TargetWindow
        The realized values and window.
    height : int
        The number of character rows.

    Returns
    -------
    list of list of (str, str)
        ``height`` rows, each with one cell per period.
    """
    peak = axis_maximum(window)
    statuses = window.statuses()
    styles = {"ok": _OK, "below": _BELOW, "above": _ABOVE}
    lows = [low if low is not None else 0.0 for low in window.minimum]
    highs = [high if high is not None else peak for high in window.maximum]
    rows: list[list[Cell]] = []
    for row in range(height):
        level = peak * (height - row) / height
        cells: list[Cell] = []
        for period in range(window.n_periods):
            in_band = lows[period] <= level <= highs[period]
            if 0.0 < level <= window.realized[period]:
                cells.append(("#", styles[statuses[period]]))
            elif in_band:
                cells.append((":", "grey50"))
            else:
                cells.append((" ", ""))
        rows.append(cells)
    return rows


def chart_renderable(
    window: TargetWindow, height: int = 12, column_width: int = 2
) -> RenderableType:
    """Render the target window as a vertical chart.

    Parameters
    ----------
    window : TargetWindow
        The realized values and window.
    height : int
        The number of character rows.
    column_width : int
        The number of characters per period column.

    Returns
    -------
    rich.console.RenderableType
        The chart, ready to print.
    """
    rows = chart_cells(window, height)
    peak = axis_maximum(window)
    label_width = 9
    lines: list[Text] = []
    for index, cells in enumerate(rows):
        line = Text(no_wrap=True)
        if index == 0:
            line.append(f"{format_value(peak):>{label_width}} ", style="grey50")
        elif index == height - 1:
            line.append(f"{'0':>{label_width}} ", style="grey50")
        else:
            line.append(" " * (label_width + 1))
        line.append("│", style="grey50")
        for character, style in cells:
            line.append(character * column_width, style=style or None)
        lines.append(line)
    axis = Text(" " * (label_width + 1) + "└", style="grey50")
    axis.append("─" * (window.n_periods * column_width), style="grey50")
    lines.append(axis)
    ticks = Text(" " * (label_width + 2))
    for period in range(window.n_periods):
        ticks.append(f"{period:<{column_width}}", style="grey50")
    lines.append(ticks)
    return Group(*lines)


def window_table(window: TargetWindow) -> Table:
    """Render the window's exact values as a table."""
    table = Table(title=f"{window.account} — per {window.period_width}-year period", box=None)
    for column in ("period", "min", "realized", "max", "shortfall", "excess", "status"):
        table.add_column(column, justify="right")
    for period in range(window.n_periods):
        low = window.minimum[period]
        high = window.maximum[period]
        status = window.statuses()[period]
        style = {"ok": _OK, "below": _BELOW, "above": _ABOVE}[status]
        table.add_row(
            str(period),
            "—" if low is None else format_value(low),
            format_value(window.realized[period]),
            "—" if high is None else format_value(high),
            format_value(window.shortfalls()[period]),
            format_value(window.excesses()[period]),
            f"[{style}]{status}[/]",
        )
    return table


@dataclass
class WatchState:
    """The live state the watcher paints.

    Attributes
    ----------
    label : str
        The display label for the watched account(s).
    accounts : tuple of str
        The account labels summed for display.
    period_width : int
        The number of years per period.
    years : int
        The horizon, in years.
    targets : tuple of Target
        The goals.
    best_objective : float
        The best objective seen.
    best_values : pandas.DataFrame or None
        The account values of the best objective seen.
    evaluations : int
        The number of evaluations.
    iteration : int
        The current iteration.
    window : TargetWindow or None
        The window of the incumbent.
    """

    label: str
    accounts: tuple[str, ...]
    period_width: int
    years: int
    targets: tuple[Target, ...]
    best_objective: float = math.inf
    best_values: pd.DataFrame | None = None
    evaluations: int = 0
    iteration: int = 0
    window: TargetWindow | None = None
    islands: int = 1
    blocks: int = 0

    def current_window(self) -> TargetWindow:
        """Return the window for the incumbent (an empty window before the first best)."""
        values = (
            self.best_values
            if self.best_values is not None
            else pd.DataFrame(columns=["year", "account", "value"])
        )
        return target_window(
            values, self.targets, self.accounts, self.period_width, self.years, self.label
        )


def render_frame(state: WatchState, optimizer: Optimizer, elapsed: float) -> RenderableType:
    """Render one frame: header, chart, and the exact period table."""
    window = state.window if state.window is not None else state.current_window()
    return Group(
        _header(state, optimizer, elapsed),
        Text(""),
        chart_renderable(window),
        Text(""),
        window_table(window),
    )


def _header(state: WatchState, optimizer: Optimizer, elapsed: float) -> Panel:
    """Render the run header panel."""
    rate = state.evaluations / elapsed if elapsed > 0.0 else 0.0
    objective = state.best_objective
    body = Text()
    body.append(state.label, style="bold")
    objective_text = "—" if math.isinf(objective) else format_value(objective)
    body.append(f"   objective (sum of penalties): {objective_text}")
    body.append(f"\niteration {state.iteration}/{optimizer.cfg.iterations}   {rate:.2f} eval/s")
    body.append(f"   elapsed {elapsed:.1f}s   seed {optimizer.cfg.seed}")
    body.append(f"   {optimizer.cfg.metaheuristic}")
    if state.islands > 1:
        body.append(f"   islands {state.islands} (showing the best)")
    if optimizer.cfg.warm_start:
        body.append(" (warm start)")
    return Panel(body, title="ws4 watch", border_style="cyan")


def _wrapped_evaluate(
    optimizer: Optimizer, targets: Sequence[Target], state: WatchState
) -> Callable[[Schedule], float]:
    """Return an evaluate function that keeps the incumbent's account values."""

    def evaluate(schedule: Schedule) -> float:
        objective = optimizer._evaluate(schedule, list(targets))
        state.evaluations += 1
        if objective < state.best_objective:
            state.best_objective = objective
            state.best_values = optimizer.last_account_values()
            state.window = state.current_window()
        return objective

    return evaluate


def _snapshot(evaluator: IncrementalObjective) -> tuple[tuple[int, str, float], ...]:
    """Return the evaluator's account values as picklable tuples."""
    return tuple(
        (int(float(str(row.year))), str(row.account), float(str(row.value)))
        for row in evaluator.values_frame().itertuples(index=False)
    )


def _island_worker(job: tuple[Any, ...]) -> None:
    """Run one island and stream its incumbent to the parent process.

    Module-level so ``multiprocessing`` can pickle it. The job carries the dataset path, the
    per-island configuration, the targets and watched accounts, the seed, the streaming
    interval, and the queue.
    """
    dataset_dir, cfg, targets, accounts, seed, interval, queue = job
    optimizer = Optimizer.from_dataset(Path(dataset_dir), cfg)
    evaluator = optimizer.delta_evaluator(targets, accounts)
    if evaluator is None:
        queue.put((seed, cfg.iterations, math.inf, (), 0))
        return
    candidates = optimizer.candidates()
    if cfg.warm_cache:
        evaluator.warm(candidates)
    initial = (
        {block: chains[0] for block, chains in candidates.items() if chains}
        if cfg.warm_start
        else None
    )
    seen = [math.inf]
    last = [0.0]

    def report(iteration: int, objective: float) -> None:
        if objective >= seen[0]:
            return
        seen[0] = objective
        now = time.monotonic()
        if now - last[0] < interval:
            return
        last[0] = now
        queue.put((seed, iteration, objective, _snapshot(evaluator), 0))

    best, objective = solve_sa_delta(
        evaluator,
        random.Random(seed),
        iterations=cfg.iterations,
        temperature=cfg.temperature,
        cooling=cfg.cooling,
        candidates=candidates,
        registry=optimizer.registry,
        initial=initial,
        on_step=report,
        adaptive=cfg.cooling_mode == "adaptive",
        cooling_window=cfg.cooling_window,
    )
    evaluator.reset(best)
    queue.put((seed, cfg.iterations, objective, _snapshot(evaluator), len(best)))


def _drain(queue: Any, state: WatchState) -> None:  # noqa: ANN401 - a multiprocessing queue
    """Apply every pending island report to the shared state, keeping the global best."""
    while True:
        try:
            _seed, iteration, objective, cells, blocks = queue.get_nowait()
        except Empty:
            return
        if iteration > state.iteration:
            state.iteration = iteration
        if objective < state.best_objective:
            state.best_objective = objective
            state.best_values = pd.DataFrame(list(cells), columns=["year", "account", "value"])
            state.window = state.current_window()
        if blocks:
            state.blocks = blocks


def _run_islands(
    optimizer: Optimizer,
    targets: Sequence[Target],
    accounts: tuple[str, ...],
    state: WatchState,
    refresh: float,
) -> None:
    """Run the islands in parallel, keeping the global best in ``state``."""
    from multiprocessing import Process, Queue

    cfg = optimizer.cfg
    queue: Any = Queue()
    jobs = [
        (
            str(optimizer.dataset_dir),
            replace(cfg, islands=1, workers=1),
            list(targets),
            accounts,
            cfg.seed + index,
            max(refresh, 0.1),
            queue,
        )
        for index in range(max(1, cfg.islands))
    ]
    processes = [Process(target=_island_worker, args=(job,)) for job in jobs]
    for process in processes:
        process.start()
    try:
        while any(process.is_alive() for process in processes):
            _drain(queue, state)
            time.sleep(0.05)
    finally:
        for process in processes:
            process.join()
    _drain(queue, state)


def run_watch(
    optimizer: Optimizer,
    targets: Sequence[Target],
    accounts: Sequence[str],
    *,
    period_width: int = 10,
    label: str | None = None,
    refresh: float = 2.0,
    plain: bool = False,
    console: Console | None = None,
) -> dict[str, Any]:
    """Run the search and paint the target window until it stops improving.

    Parameters
    ----------
    optimizer : Optimizer
        The configured optimizer (its ``cfg`` carries the solver settings).
    targets : sequence of Target
        The goals the objective uses.
    accounts : sequence of str
        The account labels to watch (summed).
    period_width : int, optional
        The number of years per period.
    label : str or None, optional
        A display label; defaults to the accounts joined with ``+``.
    refresh : float, optional
        The heartbeat interval, in seconds, between repaints.
    plain : bool, optional
        Print a single final frame instead of a live view.
    console : rich.console.Console or None, optional
        The console to draw on; a new one when omitted.

    Returns
    -------
    dict
        ``objective``, ``penalty``, ``evaluations``, ``blocks``, and ``elapsed``.
    """
    cfg = optimizer.cfg
    console = console if console is not None else Console()
    accounts_tuple = tuple(accounts)
    state = WatchState(
        label=label if label is not None else "+".join(accounts_tuple),
        accounts=accounts_tuple,
        period_width=period_width,
        years=cfg.years,
        targets=tuple(targets),
    )
    candidates = optimizer.candidates()
    evaluator = (
        optimizer.delta_evaluator(targets, accounts_tuple) if cfg.metaheuristic == "sa" else None
    )
    if evaluator is not None and cfg.warm_cache:
        console.print("[grey50]warming the contribution cache…[/]")
        evaluator.warm(candidates)
    state.islands = cfg.islands if (cfg.islands > 1 and evaluator is not None) else 1
    problem = Problem(
        evaluate=_wrapped_evaluate(optimizer, targets, state),
        candidates=candidates,
        registry=optimizer.registry,
    )
    rng = random.Random(cfg.seed)
    initial: Schedule | None = None
    if cfg.warm_start:
        initial = {block: options[0] for block, options in candidates.items() if options}

    started = time.monotonic()
    heartbeat = max(refresh, 0.1)
    live: Live | None = (
        None
        if plain
        else Live(
            console=console,
            auto_refresh=True,
            refresh_per_second=1.0 / heartbeat,
            get_renderable=lambda: render_frame(state, optimizer, time.monotonic() - started),
        )
    )

    if state.islands > 1:
        if live is not None:
            with live:
                _run_islands(optimizer, targets, accounts_tuple, state, refresh)
                live.update(
                    render_frame(state, optimizer, time.monotonic() - started), refresh=True
                )
            console.print()
        else:
            _run_islands(optimizer, targets, accounts_tuple, state, refresh)
            state.window = state.current_window()
            console.print(render_frame(state, optimizer, time.monotonic() - started))
        elapsed_islands = time.monotonic() - started
        state.iteration = cfg.iterations
        state.window = state.current_window()
        return {
            "objective": state.best_objective,
            "penalty": state.window.total_penalty(),
            "evaluations": state.evaluations,
            "blocks": state.blocks,
            "elapsed": elapsed_islands,
        }

    def on_step(iteration: int, objective: float) -> None:
        state.iteration = iteration
        state.evaluations = iteration + 1
        if evaluator is not None and objective < state.best_objective:
            state.best_objective = objective
            state.best_values = evaluator.values_frame()
            state.window = state.current_window()

    def solve() -> Schedule:
        if evaluator is not None:
            best, _ = solve_sa_delta(
                evaluator,
                rng,
                iterations=cfg.iterations,
                temperature=cfg.temperature,
                cooling=cfg.cooling,
                candidates=candidates,
                registry=optimizer.registry,
                initial=initial,
                on_step=on_step,
                adaptive=cfg.cooling_mode == "adaptive",
                cooling_window=cfg.cooling_window,
            )
        elif cfg.metaheuristic == "tabu":
            best, _ = solve_tabu(
                problem,
                rng,
                iterations=cfg.iterations,
                tenure=cfg.tenure,
                on_step=on_step,
                initial=initial,
            )
        elif cfg.metaheuristic == "ils":
            best, _ = solve_ils(
                problem,
                rng,
                iterations=cfg.iterations,
                perturbation=cfg.perturbation,
                on_step=on_step,
                initial=initial,
            )
        else:
            best, _ = solve_sa(
                problem,
                rng,
                iterations=cfg.iterations,
                temperature=cfg.temperature,
                cooling=cfg.cooling,
                on_step=on_step,
                initial=initial,
                adaptive=cfg.cooling_mode == "adaptive",
                cooling_window=cfg.cooling_window,
            )
        return best

    if live is not None:
        with live:
            best = solve()
            elapsed = time.monotonic() - started
            state.iteration = cfg.iterations
            state.window = state.current_window()
            live.update(render_frame(state, optimizer, elapsed), refresh=True)
        console.print()
    else:
        best = solve()
        elapsed = time.monotonic() - started
        state.iteration = cfg.iterations
        state.window = state.current_window()
        console.print(render_frame(state, optimizer, elapsed))
    return {
        "objective": state.best_objective,
        "penalty": state.window.total_penalty(),
        "evaluations": state.evaluations,
        "blocks": len(best),
        "elapsed": elapsed,
    }


__all__ = [
    "TargetWindow",
    "WatchState",
    "axis_maximum",
    "chart_cells",
    "chart_renderable",
    "format_value",
    "period_totals",
    "render_frame",
    "run_watch",
    "target_window",
    "window_table",
]
