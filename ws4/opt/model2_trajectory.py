"""Precompiled Model II track trajectories and block splicing.

A track stores feature curves as a function of age.  A block schedule is a path through
tracks: feature cells are slices of track trajectories, and products are event values at
the track/age where a treatment is applied.  This module is the P84 prototype; it does not
yet replace the simulator, but it establishes the exact cell representation the scheduler
will use.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from ..sim.engine import Simulator


@dataclass
class TrackTrajectory:
    """Precomputed feature state for every track and age.

    Parameters
    ----------
    simulator : Simulator
        The compiled Model II simulator; its tables and curve evaluator are the source of
        truth for the prototype.
    years : int
        Horizon in years.
    feature_values : dict of int to dict of str to list of float
        ``track -> label -> value by age``.
    """

    simulator: Simulator
    years: int
    feature_values: dict[int, dict[str, list[float]]]

    @classmethod
    def build(
        cls, simulator: Simulator, years: int, accounts: Collection[str] | None = None
    ) -> TrackTrajectory:
        """Precompute track feature trajectories for the full horizon.

        Parameters
        ----------
        simulator : Simulator
            Compiled Model II simulator.
        years : int
            Horizon in years.
        accounts : collection of str or None, optional
            Feature labels to precompute; None precomputes every feature label.

        Returns
        -------
        TrackTrajectory
            The precomputed feature trajectories.
        """
        wanted = None if accounts is None else set(accounts)
        values: dict[int, dict[str, list[float]]] = {}
        for track, features in simulator._track_features.items():
            labels = {
                label: curve for curve, label in features if wanted is None or label in wanted
            }
            track_values = {
                label: [simulator._curve_value(curve, age) for age in range(years)]
                for label, curve in labels.items()
            }
            values[int(track)] = track_values
        return cls(simulator=simulator, years=years, feature_values=values)

    def _feature(self, track: int, age: int, label: str) -> float:
        """Return one cached feature value, falling back to the curve evaluator."""
        track_values = self.feature_values.get(track, {}).get(label)
        if track_values is not None and 0 <= age < len(track_values):
            return track_values[age]
        for curve, curve_label in self.simulator._track_features.get(track, ()):
            if curve_label == label:
                return self.simulator._curve_value(curve, age)
        return 0.0

    def block_cells(
        self,
        block_id: int,
        events: Sequence[tuple[str, int]],
        *,
        feature_offsets: Collection[int] | None = None,
        accounts: Collection[str] | None = None,
    ) -> dict[tuple[int, str], float]:
        """Splice a block's track segments into account cells.

        This mirrors :meth:`Simulator.block_chain` but features are read from the
        precomputed track trajectories.  Products remain event lookups.

        Parameters
        ----------
        block_id : int
            The block.
        events : sequence of (str, int)
            Treatment events and their simulation offsets.
        feature_offsets : collection of int or None, optional
            Offsets at which feature cells are returned.
        accounts : collection of str or None, optional
            Restrict cells to these account labels.

        Returns
        -------
        dict of (int, str) to float
            Absolute account cells for the block.
        """
        simulator = self.simulator
        positions = simulator._block_index().get(int(block_id), [])
        if not positions:
            return {}
        by_offset = {int(offset): str(treatment) for treatment, offset in events}
        arrays_track, arrays_offset, arrays_area = simulator._fragment_arrays()
        tracks = [int(value) for value in arrays_track[positions]]
        offsets = [int(value) for value in arrays_offset[positions]]
        areas = [float(value) for value in arrays_area[positions]]
        wanted = None if feature_offsets is None else {int(value) for value in feature_offsets}
        wanted_accounts = None if accounts is None else set(accounts)
        totals: dict[tuple[int, str], float] = {}
        checkpoints = sorted((set() if wanted is None else wanted) | set(by_offset) | {-1})
        current_year = 0
        for step in checkpoints:
            if step >= self.years:
                break
            if step > current_year:
                delta = step - current_year
                offsets = [value + delta for value in offsets]
                current_year = step
            # Pre-simulation snapshot at -1: advance by one from year zero is not applied.
            treatment = by_offset.get(step)
            if treatment is not None:
                for index, track in enumerate(tracks):
                    transition = simulator._treatment_by_key.get((track, treatment))
                    if transition is None:
                        continue
                    age = offsets[index]
                    for curve, label in simulator._products_by_key.get((track, treatment), ()):
                        if wanted_accounts is not None and label not in wanted_accounts:
                            continue
                        key = (step, label)
                        totals[key] = totals.get(key, 0.0) + areas[index] * simulator._curve_value(
                            curve, age
                        )
                    tracks[index] = int(transition[0])
                    offsets[index] = int(transition[1])
            if wanted is None or step in wanted:
                for index, track in enumerate(tracks):
                    age = offsets[index]
                    for _curve, label in simulator._track_features.get(track, ()):
                        if wanted_accounts is not None and label not in wanted_accounts:
                            continue
                        key = (step, label)
                        totals[key] = totals.get(key, 0.0) + areas[index] * self._feature(
                            track, age, label
                        )
        return totals


@dataclass(frozen=True)
class SpliceSegment:
    """One track segment in a block's Model II timeline.

    Parameters
    ----------
    start : int
        Horizon offset where the segment begins.
    track : int
        Track id for the segment.
    age : int
        Track-relative age at the segment start.
    """

    start: int
    track: int
    age: int


class SplicedTimeline:
    """A block timeline of track segments with constant-time state lookup.

    The timeline stores only splice offsets and track/age anchors.  Reading a horizon offset
    is a binary search plus one track/age vector lookup; no splice combination is
    materialized.

    Parameters
    ----------
    trajectory : TrackTrajectory
        Precomputed track trajectories.
    tracks : sequence of int
        Initial track ids per fragment.
    ages : sequence of int
        Initial track-relative ages per fragment.
    events : sequence of (str, int)
        Treatment events and their horizon offsets.
    """

    def __init__(
        self,
        trajectory: TrackTrajectory,
        tracks: Sequence[int],
        ages: Sequence[int],
        events: Sequence[tuple[str, int]],
    ) -> None:
        """Build the segment timeline and treatment-event cells for one block fragment."""
        from bisect import bisect_right

        simulator = trajectory.simulator
        ordered = sorted(events, key=lambda event: int(event[1]))
        segments: list[SpliceSegment] = [
            SpliceSegment(start=0, track=int(tracks[0]), age=int(ages[0]))
        ]
        event_cells: dict[tuple[int, str], float] = {}
        current_track = int(tracks[0])
        current_age = int(ages[0])
        current_start = 0
        for treatment, raw_offset in ordered:
            offset = int(raw_offset)
            if offset < current_start:
                continue
            age = current_age + offset - current_start
            transition = simulator._treatment_by_key.get((current_track, str(treatment)))
            if transition is None:
                continue
            for curve, label in simulator._products_by_key.get((current_track, str(treatment)), ()):
                value = simulator._curve_value(curve, age)
                event_cells[(offset, label)] = value
            current_track = int(transition[0])
            current_age = int(transition[1])
            current_start = offset
            segments.append(SpliceSegment(start=offset, track=current_track, age=current_age))
        self.trajectory = trajectory
        self.segments = tuple(segments)
        self._starts = tuple(segment.start for segment in segments)
        self.event_cells = event_cells
        self._bisect = bisect_right

    def state_at(self, offset: int) -> dict[str, float]:
        """Return every cached track feature at one horizon offset.

        Parameters
        ----------
        offset : int
            Horizon offset.

        Returns
        -------
        dict of str to float
            Feature values keyed by label.
        """
        index = self._bisect(self._starts, offset) - 1
        segment = self.segments[max(0, index)]
        age = segment.age + offset - segment.start
        values = self.trajectory.feature_values.get(segment.track, {})
        return {
            label: series[age] if 0 <= age < len(series) else 0.0
            for label, series in values.items()
        }


class BlockAccountState:
    """Resident block x account x period pages and the chart projection.

    The state is indexed ``[period, block, account]``.  Updating a block writes only that
    block's row for each period and adjusts the running ``period_totals`` projection used by
    the watcher charts.

    Parameters
    ----------
    trajectory : TrackTrajectory
        Precomputed track trajectories.
    blocks : sequence of int
        Block ids in the state.
    accounts : sequence of str
        Account labels in the state.
    years : int
        Simulation horizon.
    period_width : int
        Years per period.
    """

    def __init__(
        self,
        trajectory: TrackTrajectory,
        blocks: Sequence[int],
        accounts: Sequence[str],
        *,
        years: int,
        period_width: int,
        skip_empty: bool = False,
    ) -> None:
        import numpy as np

        self.trajectory = trajectory
        self.blocks = tuple(sorted(int(block) for block in blocks))
        self.accounts = tuple(accounts)
        self.account_index = {account: index for index, account in enumerate(self.accounts)}
        self.block_index = {block: index for index, block in enumerate(self.blocks)}
        self.years = years
        self.period_width = period_width
        self.periods = (years + period_width - 1) // period_width
        # A feature is a level: its period value is read at the period end.  Only these
        # checkpoints are needed; products still read their actual event offsets.
        self.feature_offsets = tuple(
            min(years - 1, (period + 1) * period_width - 1) for period in range(self.periods)
        )
        shape = (self.periods, len(self.blocks), len(self.accounts))
        # Feature/state accounts are resident track-derived pages.  Product accounts are
        # event rows attached to treatments; their values are kept separately and added to
        # the chart projection only when the event occurs.
        self.state = np.zeros(shape, dtype=np.float64)
        self.event_state = np.zeros(shape, dtype=np.float64)
        self.state_totals = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        self.event_totals = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        self.period_totals = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        # Per-block/option absolute rows; the SA applies these cached rows to the pages.
        from collections import OrderedDict

        self._row_cache: OrderedDict[tuple[int, tuple[tuple[str, int], ...]], tuple[Any, Any]] = (
            OrderedDict()
        )
        self._row_cache_limit = 250_000
        self._seed_loaded = False
        self._fragment_cache: dict[int, tuple[list[int], list[int], list[float]]] = {}
        # Filter treatment products down to the watched product accounts once.
        self._product_curves: dict[tuple[int, str], tuple[tuple[Any, int], ...]] = {}
        for (track, treatment), products in self.trajectory.simulator._products_by_key.items():
            wanted = tuple(
                (curve, self.account_index[label])
                for curve, label in products
                if label in self.account_index and not label.startswith("feature.")
            )
            if wanted:
                self._product_curves[(int(track), str(treatment))] = wanted
        if not skip_empty:
            for block in self.blocks:
                state_row, event_row = self._row_for(block, ())
                index = self.block_index[block]
                self.state[:, index, :] = state_row
                self.event_state[:, index, :] = event_row
                self.state_totals += state_row
                self.event_totals += event_row
        self._project()

    def _row_for(self, block: int, events: Sequence[tuple[str, int]]) -> tuple[Any, Any]:
        """Return cached state/event period rows for one block option."""
        key = (int(block), tuple((str(treatment), int(year)) for treatment, year in events))
        cached = self._row_cache.get(key)
        if cached is None:
            cached = self._period_rows(int(block), key[1])
            if len(self._row_cache) >= self._row_cache_limit:
                self._row_cache.popitem(last=False)
            self._row_cache[key] = cached
        else:
            self._row_cache.move_to_end(key)
        return cached

    def _fragments(self, block: int) -> tuple[list[int], list[int], list[float]]:
        """Return cached fragment tracks, initial ages, and areas for one block."""
        cached = self._fragment_cache.get(int(block))
        if cached is None:
            simulator = self.trajectory.simulator
            positions = simulator._block_index().get(int(block), [])
            arrays_track, arrays_offset, arrays_area = simulator._fragment_arrays()
            cached = (
                [int(value) for value in arrays_track[positions]],
                [int(value) for value in arrays_offset[positions]],
                [float(value) for value in arrays_area[positions]],
            )
            self._fragment_cache[int(block)] = cached
        return cached

    def _period_rows(self, block: int, events: Sequence[tuple[str, int]]) -> tuple[Any, Any]:
        """Return feature/state and treatment-event period rows.

        The implementation walks each fragment's splice segments directly.  It avoids
        materializing a checkpoint dictionary for every candidate option, which is the hot
        path for SA and LNS moves.
        """
        import numpy as np

        simulator = self.trajectory.simulator
        tracks, offsets, areas = self._fragments(int(block))
        if not tracks:
            return (
                np.zeros((self.periods, len(self.accounts)), dtype=np.float64),
                np.zeros((self.periods, len(self.accounts)), dtype=np.float64),
            )
        feature_columns = [
            (column, account)
            for column, account in enumerate(self.accounts)
            if account.startswith("feature.")
        ]
        ordered = sorted((int(offset), str(treatment)) for treatment, offset in events)
        state_row = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        event_row = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        # Per-fragment segment arrays.  Segment i is active from starts[i] through the next
        # segment start; its track/age are the anchors used by SplicedTimeline.state_at.
        segments: list[tuple[list[int], list[int], list[int], float]] = []
        for fragment_track, fragment_offset, area in zip(tracks, offsets, areas, strict=True):
            starts = [0]
            segment_tracks = [fragment_track]
            segment_ages = [fragment_offset]
            current_track = fragment_track
            current_offset = fragment_offset
            current_start = 0
            for offset, treatment in ordered:
                if offset < current_start or offset >= self.years:
                    continue
                age = current_offset + offset - current_start
                transition = simulator._treatment_by_key.get((current_track, treatment))
                if transition is None:
                    continue
                for curve, column in self._product_curves.get((current_track, treatment), ()):
                    event_row[offset // self.period_width, column] += area * simulator._curve_value(
                        curve, age
                    )
                current_track = int(transition[0])
                current_offset = int(transition[1])
                current_start = offset
                starts.append(offset)
                segment_tracks.append(current_track)
                segment_ages.append(current_offset)
            segments.append((starts, segment_tracks, segment_ages, area))
        from bisect import bisect_right

        feature_values = self.trajectory.feature_values
        for period, offset in enumerate(self.feature_offsets):
            for starts, segment_tracks, segment_ages, area in segments:
                active = bisect_right(starts, offset) - 1
                track = segment_tracks[active]
                age = segment_ages[active] + offset - starts[active]
                feature_track = feature_values.get(track, {})
                for column, label in feature_columns:
                    series = feature_track.get(label)
                    if series is not None and 0 <= age < len(series):
                        state_row[period, column] += area * series[age]
                    else:
                        state_row[period, column] += area * self.trajectory._feature(
                            track, age, label
                        )
        return state_row, event_row

    def _project(self) -> None:
        """Rebuild the per-account chart projection from the correct source."""
        for column, account in enumerate(self.accounts):
            if account.startswith("feature."):
                self.period_totals[:, column] = self.state_totals[:, column]
            else:
                self.period_totals[:, column] = self.event_totals[:, column]

    def save_seed(self, path: str | Path) -> Path:
        """Persist the current resident pages as a seed-state cache.

        Parameters
        ----------
        path : str or pathlib.Path
            Destination archive.

        Returns
        -------
        pathlib.Path
            The written path.
        """
        import numpy as np

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            destination,
            state=self.state,
            event_state=self.event_state,
            state_totals=self.state_totals,
            event_totals=self.event_totals,
            accounts=np.asarray(self.accounts),
            blocks=np.asarray(self.blocks, dtype=np.int64),
            periods=np.asarray([self.periods], dtype=np.int64),
            years=np.asarray([self.years], dtype=np.int64),
            period_width=np.asarray([self.period_width], dtype=np.int64),
        )
        return destination

    def load_seed(self, path: str | Path) -> None:
        """Load a seed-state cache into these pages.

        Parameters
        ----------
        path : str or pathlib.Path
            Archive written by :meth:`save_seed`.

        Raises
        ------
        ValueError
            When the cache does not match the resident page shape or identity.
        """
        import numpy as np

        with np.load(Path(path), allow_pickle=False) as payload:
            state = payload["state"]
            event_state = payload["event_state"]
            if state.shape != self.state.shape or event_state.shape != self.event_state.shape:
                raise ValueError("seed-state cache does not match the resident page shape")
            if tuple(str(value) for value in payload["accounts"].tolist()) != self.accounts:
                raise ValueError("seed-state cache does not match the account list")
            if tuple(int(value) for value in payload["blocks"].tolist()) != self.blocks:
                raise ValueError("seed-state cache does not match the block list")
            if int(payload["periods"][0]) != self.periods:
                raise ValueError("seed-state cache does not match the period count")
            if int(payload["years"][0]) != self.years:
                raise ValueError("seed-state cache does not match the horizon")
            if int(payload["period_width"][0]) != self.period_width:
                raise ValueError("seed-state cache does not match the period width")
            self.state = state.copy()
            self.event_state = event_state.copy()
            self.state_totals = payload["state_totals"].copy()
            self.event_totals = payload["event_totals"].copy()
        self._project()
        self._seed_loaded = True

    def set_block(self, block: int, events: Sequence[tuple[str, int]]) -> None:
        """Replace one block's rows and update the chart projection.

        Parameters
        ----------
        block : int
            The block.
        events : sequence of (str, int)
            Treatment events and offsets.
        """
        index = self.block_index[int(block)]
        previous_state = self.state[:, index, :]
        previous_event = self.event_state[:, index, :]
        current_state, current_event = self._row_for(int(block), events)
        self.state_totals += current_state - previous_state
        self.event_totals += current_event - previous_event
        self.period_totals += (current_state + current_event) - (previous_state + previous_event)
        self.state[:, index, :] = current_state
        self.event_state[:, index, :] = current_event

    def set_schedule(self, schedule: dict[int, tuple[tuple[str, int], ...]]) -> None:
        """Apply a complete schedule to the resident state.

        Parameters
        ----------
        schedule : dict of int to tuple of (str, int)
            The block schedule.
        """
        for block, events in schedule.items():
            if int(block) in self.block_index:
                self.set_block(int(block), events)


def state_objective(state: BlockAccountState, targets: Sequence[Any]) -> float:
    """Return the target objective from the resident period pages.

    Parameters
    ----------
    state : BlockAccountState
        Resident period pages.
    targets : sequence of Target
        Goal-programming targets.

    Returns
    -------
    float
        Scalar weighted objective.
    """
    return StateObjective(state, targets).value()


def run_state_sa(
    state: BlockAccountState,
    candidates: Any,  # noqa: ANN401
    targets: Sequence[Any],
    *,
    iterations: int,
    seed: int = 1,
    temperature: float = 1000.0,
    cooling: float = 0.99,
    lns_weight: float = 0.2,
    lns_destroy: float = 0.1,
    lns_max_destroy: int = 64,
    toggle_weight: float = 1.0,
    shift_weight: float = 1.0,
    swap_weight: float = 0.5,
    warmup_iterations: int = 1000,
    initial: dict[int, tuple[tuple[str, int], ...]] | None = None,
    on_step: Callable[[int, BlockAccountState, float], None] | None = None,
) -> tuple[dict[int, tuple[tuple[str, int], ...]], float]:
    """Run a small SA loop over compact block option indices using resident pages.

    Parameters
    ----------
    state : BlockAccountState
        Resident period pages.
    candidates : CandidateIndex or mapping
        Compact candidate index or candidate mapping.
    targets : sequence of Target
        Goal-programming targets.
    iterations : int
        Number of SA moves.
    seed : int, optional
        Random seed.
    temperature : float, optional
        Initial SA temperature.
    cooling : float, optional
        Geometric cooling factor.
    on_step : callable or None, optional
        Callback ``(iteration, state, best_objective)``.

    Returns
    -------
    tuple of (dict, float)
        Best schedule and objective.
    """
    import math
    import random

    from .model2_index import CandidateIndex

    rng = random.Random(seed)
    index = candidates if isinstance(candidates, CandidateIndex) else None
    blocks = (
        [int(block) for block in index.blocks.tolist() if index.option_count(int(block)) > 0]
        if index is not None
        else [block for block in state.blocks if candidates.get(block)]
    )
    if not blocks:
        raise ValueError("state search has no blocks with candidate options")
    schedule: dict[int, tuple[tuple[str, int], ...]] = dict(initial or {})
    if schedule and not state._seed_loaded:
        state.set_schedule(schedule)
    calculator = StateObjective(state, targets)
    current = calculator.value()
    best = current
    best_schedule = dict(schedule)
    temp = temperature
    operator_names = ("toggle", "shift", "swap", "lns")
    operator_weights = (
        max(0.0, toggle_weight),
        max(0.0, shift_weight),
        max(0.0, swap_weight),
        max(0.0, lns_weight) if schedule else 0.0,
    )

    def option(block: int) -> tuple[tuple[str, int], ...]:
        if index is not None:
            count = index.option_count(block)
            if count <= 0:
                block = rng.choice(blocks)
                count = index.option_count(block)
            return index.chain(block, rng.randrange(max(1, count)))
        return rng.choice(candidates[block])

    def random_move() -> dict[int, tuple[tuple[str, int], ...] | None]:
        """Diversify with single-block assignments or a bounded LNS move."""
        use_lns = bool(schedule) and lns_weight > 0.0 and rng.random() < lns_weight
        if use_lns:
            count = max(1, int(len(schedule) * lns_destroy))
            count = min(count, lns_max_destroy, len(schedule))
            changed = rng.sample(list(schedule), count)
            previous: dict[int, tuple[tuple[str, int], ...] | None] = {
                block: schedule[block] for block in changed
            }
            for block in changed:
                chain = option(block)
                schedule[block] = chain
                state.set_block(block, chain)
            return previous
        block = rng.choice(blocks)
        previous = {block: schedule.get(block)}
        chain = option(block)
        schedule[block] = chain
        state.set_block(block, chain)
        return previous

    def mixed_move() -> dict[int, tuple[tuple[str, int], ...] | None]:
        """Apply one weighted toggle/shift/swap/LNS move."""
        operator = (
            rng.choices(operator_names, weights=operator_weights, k=1)[0]
            if sum(operator_weights) > 0.0
            else "toggle"
        )
        if operator == "lns" and schedule:
            count = max(1, int(len(schedule) * lns_destroy))
            count = min(count, lns_max_destroy, len(schedule))
            changed = rng.sample(list(schedule), count)
            previous: dict[int, tuple[tuple[str, int], ...] | None] = {
                block: schedule[block] for block in changed
            }
            for block in changed:
                chain = option(block)
                schedule[block] = chain
                state.set_block(block, chain)
            return previous
        if operator == "swap" and len(schedule) >= 2:
            first, second = rng.sample(list(schedule), 2)
            previous = {
                first: schedule[first],
                second: schedule[second],
            }
            schedule[first], schedule[second] = schedule[second], schedule[first]
            state.set_block(first, schedule[first])
            state.set_block(second, schedule[second])
            return previous
        if operator == "shift" and schedule:
            shifted: int | None = None
            if index is not None:
                for _ in range(12):
                    probe = rng.choice(blocks)
                    if probe in schedule and index.option_count(probe) > 1:
                        shifted = probe
                        break
            if shifted is None:
                assigned = [
                    candidate_block
                    for candidate_block in schedule
                    if index is None or index.option_count(candidate_block) > 1
                ]
                shifted = rng.choice(assigned) if assigned else rng.choice(list(schedule))
            previous = {shifted: schedule[shifted]}
            chain = option(shifted)
            schedule[shifted] = chain
            state.set_block(shifted, chain)
            return previous
        toggled = rng.choice(blocks)
        old = schedule.get(toggled)
        previous = {toggled: old}
        if old is not None and rng.random() < 0.5:
            schedule.pop(toggled, None)
            state.set_block(toggled, ())
        else:
            chain = option(toggled)
            schedule[toggled] = chain
            state.set_block(toggled, chain)
        return previous

    warmup = max(0, min(warmup_iterations, iterations))
    for iteration in range(1, iterations + 1):
        previous = random_move() if iteration <= warmup else mixed_move()
        candidate = calculator.value()
        delta = candidate - current
        if delta <= 0.0 or rng.random() < math.exp(-delta / max(temp, 1e-12)):
            current = candidate
            if candidate < best:
                best = candidate
                best_schedule = dict(schedule)
        else:
            for block, old in previous.items():
                if old is None:
                    schedule.pop(block, None)
                else:
                    schedule[block] = old
                state.set_block(block, old or ())
        if on_step is not None:
            on_step(iteration, state, best)
        temp *= cooling
    if best < current:
        state.set_schedule(best_schedule)
    return best_schedule, best


def state_values(state: BlockAccountState) -> Any:  # noqa: ANN401
    """Return the resident period totals as an offset/account/value frame.

    Parameters
    ----------
    state : BlockAccountState
        Resident period pages.

    Returns
    -------
    pandas.DataFrame
        One row per period and account.
    """
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for period in range(state.periods):
        year = min(state.years - 1, (period + 1) * state.period_width - 1)
        for column, account in enumerate(state.accounts):
            rows.append(
                {
                    "offset": year,
                    "account": account,
                    "value": float(state.period_totals[period, column]),
                }
            )
    return pd.DataFrame(rows)


def run_state_watch(
    state: BlockAccountState,
    candidates: Any,  # noqa: ANN401
    targets: Sequence[Any],
    accounts: Sequence[str],
    optimizer: Any,  # noqa: ANN401
    *,
    iterations: int,
    period_width: int = 10,
    label: str | None = None,
    refresh: float = 2.0,
    plain: bool = False,
    console: Any | None = None,  # noqa: ANN401
    schedule_out: Path | None = None,
    telemetry_path: Path | None = None,
    initial: dict[int, tuple[tuple[str, int], ...]] | None = None,
    lns_weight: float = 0.2,
    lns_destroy: float = 0.1,
    lns_max_destroy: int = 64,
) -> dict[str, Any]:
    """Run the resident-state SA and paint target windows from the period pages.

    Parameters
    ----------
    state : BlockAccountState
        Resident period pages.
    candidates : CandidateIndex or mapping
        Compact candidate index or candidate mapping.
    targets : sequence of Target
        Goal-programming targets.
    accounts : sequence of str
        Accounts to display.
    optimizer : Optimizer
        The optimizer whose configuration labels the frame.
    iterations : int
        Number of SA moves.
    period_width : int, optional
        Years per displayed period.
    label : str or None, optional
        Display label.
    refresh : float, optional
        Seconds between live repaints.
    plain : bool, optional
        Print one final frame.
    console : rich.console.Console or None, optional
        Console to draw on.
    schedule_out : pathlib.Path or None, optional
        Write the final schedule CSV here.
    initial : dict or None, optional
        Initial schedule to apply before the SA moves.
    lns_weight : float, optional
        Probability of a bounded LNS move.
    lns_destroy : float, optional
        Fraction of assigned blocks destroyed.
    lns_max_destroy : int, optional
        Maximum blocks destroyed.

    Returns
    -------
    dict
        Objective, penalty, evaluations, iterations, blocks, elapsed, and schedule.
    """
    import time

    from rich.console import Console
    from rich.live import Live

    from .watch import WatchState, render_frame

    console = console if console is not None else Console()
    logger = None
    if telemetry_path is not None:
        from .telemetry import RunLogger

        logger = RunLogger(
            telemetry_path,
            run_id=label if label is not None else "state-watch",
            config={
                "dataset": "",
                "targets": str(optimizer.cfg.targets_path or ""),
                "iterations": iterations,
                "period_width": period_width,
                "years": state.years,
            },
        )
    view = WatchState(
        label=label if label is not None else "+".join(accounts),
        accounts=tuple(accounts),
        period_width=period_width,
        years=state.years,
        targets=tuple(targets),
    )
    view.blocks = len(state.blocks)
    cfg = optimizer.cfg
    cfg.iterations = iterations
    cfg.metaheuristic = "state-sa"
    started = time.monotonic()
    live: Any = (
        None
        if plain
        else Live(
            console=console,
            auto_refresh=True,
            refresh_per_second=1.0 / max(refresh, 0.1),
        )
    )
    last_update = [0.0]

    def paint(iteration: int, current: BlockAccountState, best: float) -> None:
        if logger is not None:
            logger.step(iteration, best)
        if plain:
            return
        now = time.monotonic()
        if now - last_update[0] < refresh and iteration != iterations:
            return
        last_update[0] = now
        view.best_objective = best
        view.best_values = state_values(current)
        view.windows = view.current_windows()
        view.iteration = iteration
        view.evaluations = iteration + 1
        if live is not None:
            live.update(
                render_frame(view, optimizer, now - started),
                refresh=True,
            )

    if live is not None:
        live.start(refresh=True)
    try:
        schedule, objective = run_state_sa(
            state,
            candidates,
            targets,
            iterations=iterations,
            initial=initial,
            on_step=paint,
            lns_weight=lns_weight,
            lns_destroy=lns_destroy,
            lns_max_destroy=lns_max_destroy,
        )
        view.best_objective = objective
        view.best_values = state_values(state)
        view.windows = view.current_windows()
        view.iteration = iterations
        view.evaluations = iterations + 1
        if live is not None:
            live.update(
                render_frame(view, optimizer, time.monotonic() - started),
                refresh=True,
            )
    finally:
        if live is not None:
            live.stop()
    if live is None:
        console.print(render_frame(view, optimizer, time.monotonic() - started))
    if logger is not None:
        if iterations == 0:
            logger.step(0, objective)
        logger.close()
    if schedule_out is not None:
        from .archive import write_schedule

        write_schedule(schedule_out, schedule)
    return {
        "objective": objective,
        "penalty": sum(window.total_penalty() for window in view.windows),
        "evaluations": iterations + 1,
        "iterations": iterations,
        "blocks": len(state.blocks),
        "elapsed": time.monotonic() - started,
        "schedule": schedule,
    }


class StateObjective:
    """Direct target pricing from the resident period pages.

    The target set is prepared once; evaluating a move reads only the relevant
    `period_totals` cells.  Feature and product pages come from ``state.period_totals``;
    flow terms read the page sequence, not a rebuilt DataFrame.
    """

    def __init__(self, state: BlockAccountState, targets: Sequence[Any]) -> None:
        """Precompute target account/period locations."""
        from .objective import PRIORITY_SCALE

        self.state = state
        self.targets = tuple(targets)
        self.account_index = {account: index for index, account in enumerate(state.accounts)}
        self.width = state.period_width
        self.years = state.years
        self.periods = state.periods
        self._prepared: list[tuple[Any, int | None, int | None]] = []
        for target in self.targets:
            if not target.active:
                continue
            column = self.account_index.get(target.account)
            if column is None:
                continue
            if target.flow:
                self._prepared.append((target, column, None))
                continue
            period = (target.end_offset() + 1) // self.width
            if 0 < period <= self.periods:
                self._prepared.append((target, column, period - 1))
        priorities = {target.priority for target, _column, _period in self._prepared}
        highest = max(priorities) if priorities else 0
        self._factors = [
            PRIORITY_SCALE ** (highest - target.priority)
            for target, _column, _period in self._prepared
        ]

    def _index_for_flow(self, account: str) -> dict[tuple[int, str], float]:
        """Return the period-end index expected by the flow target evaluator."""
        column = self.account_index[account]
        return {
            (min(self.years - 1, (period + 1) * self.width - 1), account): float(
                self.state.period_totals[period, column]
            )
            for period in range(self.periods)
        }

    def value(self) -> float:
        """Return the scalar objective from current period totals."""
        from .objective import flow_penalty, penalty

        total = 0.0
        for (target, column, period), factor in zip(self._prepared, self._factors, strict=True):
            if period is None:
                assert column is not None
                term = flow_penalty(self._index_for_flow(target.account), target, self.years)
            else:
                assert column is not None
                term = penalty(float(self.state.period_totals[period, column]), target)
            total += factor * term
        return total
