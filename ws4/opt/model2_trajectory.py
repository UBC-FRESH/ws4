"""Precompiled Model II track trajectories and block splicing.

A track stores feature curves as a function of age.  A block schedule is a path through
tracks: feature cells are slices of track trajectories, and products are event values at
the track/age where a treatment is applied.  This module is the P84 prototype; it does not
yet replace the simulator, but it establishes the exact cell representation the scheduler
will use.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    def build(cls, simulator: Simulator, years: int) -> TrackTrajectory:
        """Precompute track feature trajectories for the full horizon."""
        values: dict[int, dict[str, list[float]]] = {}
        for track, features in simulator._track_features.items():
            labels = {label: curve for curve, label in features}
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
    """One track segment in a block's Model II timeline."""

    start: int
    track: int
    age: int


class SplicedTimeline:
    """A block timeline of track segments with constant-time state lookup.

    The timeline stores only splice offsets and track/age anchors.  Reading a horizon offset
    is a binary search plus one track/age vector lookup; no splice combination is
    materialized.
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
        """Return every cached track feature at one horizon offset."""
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
    """

    def __init__(
        self,
        trajectory: TrackTrajectory,
        blocks: Sequence[int],
        accounts: Sequence[str],
        *,
        years: int,
        period_width: int,
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
        shape = (self.periods, len(self.blocks), len(self.accounts))
        # Feature/state accounts are resident track-derived pages.  Product accounts are
        # event rows attached to treatments; their values are kept separately and added to
        # the chart projection only when the event occurs.
        self.state = np.zeros(shape, dtype=np.float64)
        self.event_state = np.zeros(shape, dtype=np.float64)
        self.state_totals = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        self.event_totals = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        self.period_totals = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        for block in self.blocks:
            state_row, event_row = self._period_rows(block, ())
            index = self.block_index[block]
            self.state[:, index, :] = state_row
            self.event_state[:, index, :] = event_row
            self.state_totals += state_row
            self.event_totals += event_row
        self._project()

    def _period_rows(self, block: int, events: Sequence[tuple[str, int]]) -> tuple[Any, Any]:
        """Return feature/state and treatment-event period rows."""
        import numpy as np

        cells = self.trajectory.block_cells(
            block, events, feature_offsets=range(self.years), accounts=self.accounts
        )
        state_row = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        event_row = np.zeros((self.periods, len(self.accounts)), dtype=np.float64)
        latest: dict[tuple[int, int], tuple[int, float]] = {}
        for (offset, account), value in cells.items():
            if offset < 0 or offset >= self.years or account not in self.account_index:
                continue
            period = offset // self.period_width
            column = self.account_index[account]
            if account.startswith("feature."):
                previous = latest.get((period, column))
                if previous is None or offset >= previous[0]:
                    latest[(period, column)] = (offset, float(value))
            else:
                # Product/treatment event rows.
                event_row[period, column] += float(value)
        for (period, column), (_offset, value) in latest.items():
            state_row[period, column] += value
        return state_row, event_row

    def _project(self) -> None:
        """Rebuild the per-account chart projection from the correct source."""
        for column, account in enumerate(self.accounts):
            if account.startswith("feature."):
                self.period_totals[:, column] = self.state_totals[:, column]
            else:
                self.period_totals[:, column] = self.event_totals[:, column]

    def set_block(self, block: int, events: Sequence[tuple[str, int]]) -> None:
        """Replace one block's rows and update the chart projection."""
        index = self.block_index[int(block)]
        previous_state = self.state[:, index, :]
        previous_event = self.event_state[:, index, :]
        current_state, current_event = self._period_rows(int(block), events)
        self.state_totals += current_state - previous_state
        self.event_totals += current_event - previous_event
        self.period_totals += (current_state + current_event) - (previous_state + previous_event)
        self.state[:, index, :] = current_state
        self.event_state[:, index, :] = current_event

    def set_schedule(self, schedule: dict[int, tuple[tuple[str, int], ...]]) -> None:
        """Apply a complete schedule to the resident state."""
        for block, events in schedule.items():
            if int(block) in self.block_index:
                self.set_block(int(block), events)
