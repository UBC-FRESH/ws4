"""Factorized block/option effects for account switching on the GPU path.

A full effects matrix would be ``options x accounts x offsets``.  For a full model that is
hundreds of billions of cells.  This module keeps the structural facts instead:

- one descriptor per option, containing its fragment segments and treatment events;
- feature values at ``(track, age)`` read from the simulator's curve tables;
- product values at treatment events read from the same curve tables.

A target account is evaluated by selecting a label and gathering from those tables. No
account-by-option matrix is materialized.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .engine import Optimizer
    from .operators import Candidates, Chain


@dataclass(frozen=True)
class Segment:
    """One fragment segment in an option's splice timeline.

    Parameters
    ----------
    start : int
        Horizon offset where this segment starts.
    track : int
        Track id.
    age : int
        Track-relative age at ``start``.
    area : float
        Fragment area in hectares.
    """

    start: int
    track: int
    age: int
    area: float


@dataclass(frozen=True)
class Event:
    """One treatment event in an option.

    Parameters
    ----------
    offset : int
        Horizon offset where the treatment occurs.
    track : int
        Track id before the treatment.
    treatment : str
        Treatment label.
    age : int
        Track-relative age at the treatment.
    area : float
        Fragment area in hectares.
    """

    offset: int
    track: int
    treatment: str
    age: int
    area: float


@dataclass(frozen=True)
class OptionDescriptor:
    """Structural effects for one block/option pair.

    Parameters
    ----------
    segments : tuple of tuple of Segment
        Segments grouped by fragment. Each fragment's segments are ordered by start offset.
    events : tuple of Event
        Treatment events in horizon order.
    """

    segments: tuple[tuple[Segment, ...], ...]
    events: tuple[Event, ...]


class FactorizedEffectBasis:
    """Account-independent option descriptors with on-demand pricing.

    Parameters
    ----------
    optimizer : Optimizer
        The compiled-model optimizer.
    descriptors : mapping of int to tuple of OptionDescriptor
        Structural descriptors per block and candidate option.
    chain_index : mapping of int to mapping of tuple to int
        Candidate-chain position per block.
    years : int
        Simulation horizon.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        descriptors: Mapping[int, tuple[OptionDescriptor, ...]],
        chain_index: Mapping[int, Mapping[Chain, int]],
        years: int,
    ) -> None:
        self.optimizer = optimizer
        self.descriptors = descriptors
        self.chain_index = chain_index
        self.years = years
        self.simulator = optimizer.simulator()

    @classmethod
    def build(
        cls,
        optimizer: Optimizer,
        candidates: Candidates,
        *,
        years: int,
    ) -> FactorizedEffectBasis:
        """Build structural descriptors for every candidate option.

        This is deliberately structural: it stores segment/event coordinates, not
        per-account values.

        Parameters
        ----------
        optimizer : Optimizer
            The compiled-model optimizer.
        candidates : mapping of int to sequence of tuple
            Candidate chains per block.
        years : int
            Simulation horizon.

        Returns
        -------
        FactorizedEffectBasis
            The factorized basis.
        """
        simulator = optimizer.simulator()
        block_index = simulator._block_index()
        arrays_track, arrays_offset, arrays_area = simulator._fragment_arrays()
        descriptors: dict[int, tuple[OptionDescriptor, ...]] = {}
        chain_index: dict[int, dict[Chain, int]] = {}
        for block in sorted(int(value) for value in candidates):
            positions = block_index.get(block, [])
            tracks = [int(value) for value in arrays_track[positions]]
            offsets = [int(value) for value in arrays_offset[positions]]
            areas = [float(value) for value in arrays_area[positions]]
            options: list[OptionDescriptor] = []
            positions_by_chain: dict[Chain, int] = {}
            for index, chain in enumerate(candidates[block]):
                options.append(_describe_option(simulator, tracks, offsets, areas, chain, years))
                positions_by_chain[tuple(chain)] = index
            descriptors[block] = tuple(options)
            chain_index[block] = positions_by_chain
        return cls(optimizer, descriptors, chain_index, years)

    def feature_period_values(
        self,
        account: str,
        schedule: Mapping[int, Chain],
        *,
        period_width: int,
    ) -> dict[int, float]:
        """Return feature account totals by accounting period.

        Parameters
        ----------
        account : str
            Feature account label.
        schedule : mapping of int to tuple of (str, int)
            One chain per block.
        period_width : int
            Years per accounting period.

        Returns
        -------
        dict of int to float
            Period index to feature value.
        """
        periods = (self.years + period_width - 1) // period_width
        totals = dict.fromkeys(range(1, periods + 1), 0.0)
        for block, chain in schedule.items():
            option = self._option(block, chain)
            for end in range(period_width - 1, self.years, period_width):
                period = end // period_width + 1
                for segments in option.segments:
                    active = _active_segment(segments, end)
                    if active is None:
                        continue
                    age = active.age + end - active.start
                    totals[period] += active.area * self._feature(active.track, age, account)
        return totals

    def product_period_values(
        self,
        account: str,
        schedule: Mapping[int, Chain],
        *,
        period_width: int,
    ) -> dict[int, float]:
        """Return product account totals by accounting period.

        Parameters
        ----------
        account : str
            Product account label.
        schedule : mapping of int to tuple of (str, int)
            One chain per block.
        period_width : int
            Years per accounting period.

        Returns
        -------
        dict of int to float
            Period index to product value.
        """
        periods = (self.years + period_width - 1) // period_width
        totals = dict.fromkeys(range(1, periods + 1), 0.0)
        for block, chain in schedule.items():
            option = self._option(block, chain)
            for event in option.events:
                if event.offset >= self.years:
                    continue
                period = event.offset // period_width + 1
                for curve, label in self.simulator._products_by_key.get(
                    (event.track, event.treatment), ()
                ):
                    if str(label) != account:
                        continue
                    totals[period] += event.area * self.simulator._curve_value(curve, event.age)
        return totals

    def _option(self, block: int, chain: Chain) -> OptionDescriptor:
        """Return the descriptor for one block/chain pair."""
        index = self.chain_index[block].get(tuple(chain))
        if index is None:
            raise KeyError((block, chain))
        return self.descriptors[block][index]

    def _feature(self, track: int, age: int, account: str) -> float:
        """Return one track/age feature value."""
        for curve, label in self.simulator._track_features.get(track, ()):
            if str(label) == account:
                return self.simulator._curve_value(curve, age)
        return 0.0


def _active_segment(segments: Sequence[Segment], offset: int) -> Segment | None:
    """Return the segment active at one offset, or None for an empty list."""
    from bisect import bisect_right

    if not segments:
        return None
    starts = [segment.start for segment in segments]
    index = bisect_right(starts, offset) - 1
    return segments[max(0, index)]


def _describe_option(
    simulator: object,
    tracks: Sequence[int],
    offsets: Sequence[int],
    areas: Sequence[float],
    chain: Sequence[tuple[str, int]],
    years: int,
) -> OptionDescriptor:
    """Describe one block/chain pair without materializing account values."""
    ordered = sorted((int(offset), str(treatment)) for treatment, offset in chain)
    events: list[Event] = []
    grouped_segments: list[tuple[Segment, ...]] = []
    for track, offset, area in zip(tracks, offsets, areas, strict=True):
        current_track = int(track)
        current_age = int(offset)
        current_start = 0
        segments = [Segment(0, current_track, current_age, float(area))]
        for event_offset, treatment in ordered:
            if event_offset < current_start or event_offset >= years:
                continue
            age = current_age + event_offset - current_start
            transition = simulator._treatment_by_key.get((current_track, treatment))  # type: ignore[attr-defined]
            if transition is None:
                continue
            events.append(Event(event_offset, current_track, treatment, age, float(area)))
            current_track = int(transition[0])
            current_age = int(transition[1])
            current_start = event_offset
            segments.append(Segment(event_offset, current_track, current_age, float(area)))
        grouped_segments.append(tuple(segments))
    return OptionDescriptor(tuple(grouped_segments), tuple(events))


class FactorizedEffectArrays:
    """Flat numeric storage for all option segment/event descriptors.

    This is the scalable representation behind :class:`FactorizedEffectBasis`. It avoids
    one Python object per option, segment, or event and can be converted to device tensors
    or consumed by a bounded column builder.

    Parameters
    ----------
    blocks : numpy.ndarray
        Sorted block ids.
    chain_offsets : numpy.ndarray
        Offset of each block's first option, plus a sentinel.
    segment_offsets : numpy.ndarray
        Offset of each option's first segment, plus a sentinel.
    option_fragment_offsets : numpy.ndarray
        Offset of each option's first fragment, plus a sentinel.
    fragment_offsets : numpy.ndarray
        Offset of each fragment's first segment, plus a sentinel.
    segment_start, segment_track, segment_age : numpy.ndarray
        Segment anchors.
    segment_area : numpy.ndarray
        Segment area in hectares.
    event_offsets : numpy.ndarray
        Offset of each option's first event, plus a sentinel.
    event_offset, event_track, event_age : numpy.ndarray
        Event anchors.
    event_label : numpy.ndarray
        Integer treatment label per event.
    event_area : numpy.ndarray
        Event fragment area in hectares.
    labels : tuple of str
        Treatment-label dictionary.
    """

    def __init__(
        self,
        blocks: Any,  # noqa: ANN401
        chain_offsets: Any,  # noqa: ANN401
        segment_offsets: Any,  # noqa: ANN401
        option_fragment_offsets: Any,  # noqa: ANN401
        fragment_offsets: Any,  # noqa: ANN401
        segment_start: Any,  # noqa: ANN401
        segment_track: Any,  # noqa: ANN401
        segment_age: Any,  # noqa: ANN401
        segment_area: Any,  # noqa: ANN401
        event_offsets: Any,  # noqa: ANN401
        event_offset: Any,  # noqa: ANN401
        event_track: Any,  # noqa: ANN401
        event_age: Any,  # noqa: ANN401
        event_label: Any,  # noqa: ANN401
        event_area: Any,  # noqa: ANN401
        labels: tuple[str, ...],
    ) -> None:
        self.blocks = blocks
        self.chain_offsets = chain_offsets
        self.segment_offsets = segment_offsets
        self.option_fragment_offsets = option_fragment_offsets
        self.fragment_offsets = fragment_offsets
        self.segment_start = segment_start
        self.segment_track = segment_track
        self.segment_age = segment_age
        self.segment_area = segment_area
        self.event_offsets = event_offsets
        self.event_offset = event_offset
        self.event_track = event_track
        self.event_age = event_age
        self.event_label = event_label
        self.event_area = event_area
        self.labels = labels

    @classmethod
    def build(
        cls,
        optimizer: Optimizer,
        candidates: Candidates,
        *,
        years: int,
    ) -> FactorizedEffectArrays:
        """Build flat option descriptors from the compiled simulator.

        Parameters
        ----------
        optimizer : Optimizer
            The compiled-model optimizer.
        candidates : mapping of int to sequence of tuple
            Candidate chains per block.
        years : int
            Simulation horizon.

        Returns
        -------
        FactorizedEffectArrays
            Flat descriptor arrays.
        """
        from array import array

        import numpy as np

        simulator = optimizer.simulator()
        block_index = simulator._block_index()
        arrays_track, arrays_offset, arrays_area = simulator._fragment_arrays()
        blocks: list[int] = []
        chain_offsets = array("i", [0])
        segment_offsets = array("i", [0])
        option_fragment_offsets = array("i", [0])
        fragment_offsets = array("i")
        segment_start = array("h")
        segment_track = array("h")
        segment_age = array("h")
        segment_area = array("f")
        event_offsets = array("i", [0])
        event_offset = array("h")
        event_track = array("h")
        event_age = array("h")
        event_label = array("h")
        event_area = array("f")
        labels = {
            treatment: index
            for index, treatment in enumerate(
                sorted({str(treatment) for _track, treatment in simulator._treatment_by_key})
            )
        }
        for block in sorted(int(value) for value in candidates):
            blocks.append(block)
            positions = block_index.get(block, [])
            tracks = [int(value) for value in arrays_track[positions]]
            offsets = [int(value) for value in arrays_offset[positions]]
            areas = [float(value) for value in arrays_area[positions]]
            for chain in candidates[block]:
                _append_option_arrays(
                    simulator,
                    tracks,
                    offsets,
                    areas,
                    chain,
                    years,
                    fragment_offsets,
                    segment_start,
                    segment_track,
                    segment_age,
                    segment_area,
                    event_offset,
                    event_track,
                    event_age,
                    event_label,
                    event_area,
                    labels,
                )
                fragment_offsets.append(len(segment_start))
                option_fragment_offsets.append(len(fragment_offsets))
                segment_offsets.append(len(segment_start))
                event_offsets.append(len(event_offset))
            chain_offsets.append(len(segment_offsets) - 1)
        inverse = {value: key for key, value in labels.items()}
        return cls(
            blocks=np.asarray(blocks, dtype=np.int64),
            chain_offsets=np.asarray(chain_offsets, dtype=np.int32),
            segment_offsets=np.asarray(segment_offsets, dtype=np.int32),
            option_fragment_offsets=np.asarray(option_fragment_offsets, dtype=np.int32),
            fragment_offsets=np.asarray(fragment_offsets, dtype=np.int32),
            segment_start=np.asarray(segment_start, dtype=np.int16),
            segment_track=np.asarray(segment_track, dtype=np.int16),
            segment_age=np.asarray(segment_age, dtype=np.int16),
            segment_area=np.asarray(segment_area, dtype=np.float32),
            event_offsets=np.asarray(event_offsets, dtype=np.int32),
            event_offset=np.asarray(event_offset, dtype=np.int16),
            event_track=np.asarray(event_track, dtype=np.int16),
            event_age=np.asarray(event_age, dtype=np.int16),
            event_label=np.asarray(event_label, dtype=np.int16),
            event_area=np.asarray(event_area, dtype=np.float32),
            labels=tuple(inverse[index] for index in range(len(inverse))),
        )

    @classmethod
    def build_parallel(
        cls,
        optimizer: Optimizer,
        candidates: Candidates,
        *,
        years: int,
        workers: int,
        chunk_blocks: int = 512,
        worker_memory_bytes: int = 16_000_000_000,
    ) -> FactorizedEffectArrays:
        """Build flat descriptors across bounded forked workers.

        Parameters
        ----------
        optimizer : Optimizer
            The compiled-model optimizer.
        candidates : mapping of int to sequence of tuple
            Candidate chains per block.
        years : int
            Simulation horizon.
        workers : int
            Worker process count.
        chunk_blocks : int, optional
            Blocks per worker task.
        worker_memory_bytes : int, optional
            Per-worker ``RLIMIT_AS`` in bytes.

        Returns
        -------
        FactorizedEffectArrays
            The merged descriptor arrays.
        """
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor

        simulator = optimizer.simulator()
        labels = {
            treatment: index
            for index, treatment in enumerate(
                sorted({str(treatment) for _track, treatment in simulator._treatment_by_key})
            )
        }
        blocks = sorted(int(value) for value in candidates)
        chunk = max(32, int(chunk_blocks))
        tasks = [tuple(blocks[index : index + chunk]) for index in range(0, len(blocks), chunk)]
        if workers <= 1 or len(tasks) <= 1:
            return _build_arrays_for_blocks(optimizer, candidates, blocks, years, labels)
        global _array_optimizer, _array_candidates, _array_years, _array_labels
        _array_optimizer = optimizer
        _array_candidates = candidates
        _array_years = years
        _array_labels = labels
        multiprocessing.set_start_method("fork", force=True)
        worker_limit = max(1_000_000_000, int(worker_memory_bytes))
        with ProcessPoolExecutor(
            max_workers=max(1, workers),
            mp_context=multiprocessing.get_context("fork"),
            initializer=_init_array_worker,
            initargs=(worker_limit,),
        ) as executor:
            results = list(executor.map(_build_array_chunk, tasks))
        return _merge_arrays(results, labels)

    @property
    def option_count(self) -> int:
        """Return the number of option rows.

        Returns
        -------
        int
            Number of options.
        """
        return int(self.chain_offsets[-1])

    def feature_period_values(
        self,
        account: str,
        options: Mapping[int, int],
        *,
        period_width: int,
        years: int,
        simulator: object,
    ) -> dict[int, float]:
        """Evaluate a feature account from the flat descriptors.

        Parameters
        ----------
        account : str
            Feature account label.
        options : mapping of int to int
            Block id to candidate option position.
        period_width : int
            Years per accounting period.
        years : int
            Simulation horizon.
        simulator : object
            Simulator providing track/age curve lookup.

        Returns
        -------
        dict of int to float
            Period index to feature value.
        """
        period_count = (int(years) + period_width - 1) // max(1, period_width)
        totals = dict.fromkeys(range(1, period_count + 1), 0.0)
        block_position = {int(block): index for index, block in enumerate(self.blocks)}
        for block, option in options.items():
            position = block_position.get(int(block))
            if position is None:
                continue
            row = int(self.chain_offsets[position]) + int(option)
            frag_start = int(self.option_fragment_offsets[row])
            frag_stop = int(self.option_fragment_offsets[row + 1])
            for fragment in range(frag_start, frag_stop - 1):
                segment_start = int(self.fragment_offsets[fragment])
                segment_stop = int(self.fragment_offsets[fragment + 1])
                for end in range(period_width - 1, years, period_width):
                    active = _active_array_segment(
                        self.segment_start,
                        self.segment_track,
                        self.segment_age,
                        self.segment_area,
                        segment_start,
                        segment_stop,
                        end,
                    )
                    if active is None:
                        continue
                    track, age, area = active
                    period = end // period_width + 1
                    totals[period] += area * _simulator_feature(simulator, track, age, account)
        return totals

    def product_period_values(
        self,
        account: str,
        options: Mapping[int, int],
        *,
        period_width: int,
        years: int,
        simulator: object,
    ) -> dict[int, float]:
        """Evaluate a product account from the flat event rows.

        Parameters
        ----------
        account : str
            Product account label.
        options : mapping of int to int
            Block id to candidate option position.
        period_width : int
            Years per accounting period.
        years : int
            Simulation horizon.
        simulator : object
            Simulator providing product curve lookup.

        Returns
        -------
        dict of int to float
            Period index to product value.
        """
        period_count = (int(years) + period_width - 1) // max(1, period_width)
        totals = dict.fromkeys(range(1, period_count + 1), 0.0)
        block_position = {int(block): index for index, block in enumerate(self.blocks)}
        for block, option in options.items():
            position = block_position.get(int(block))
            if position is None:
                continue
            row = int(self.chain_offsets[position]) + int(option)
            start = int(self.event_offsets[row])
            stop = int(self.event_offsets[row + 1])
            for index in range(start, stop):
                label = self.labels[int(self.event_label[index])]
                offset = int(self.event_offset[index])
                period = offset // period_width + 1
                track = int(self.event_track[index])
                treatment = label
                age = int(self.event_age[index])
                area = float(self.event_area[index])
                for curve, product in simulator._products_by_key.get(  # type: ignore[attr-defined]
                    (track, treatment), ()
                ):
                    if str(product) == account:
                        totals[period] += area * simulator._curve_value(  # type: ignore[attr-defined]
                            curve, age
                        )
        return totals

    def to_tensors(self, device: str = "cpu") -> dict[str, Any]:
        """Return the flat descriptor arrays as device tensors.

        Parameters
        ----------
        device : str, optional
            Torch device string. Defaults to ``cpu``.

        Returns
        -------
        dict of str to torch.Tensor
            Device tensors for the segment, event, and offset arrays.
        """
        import torch

        names = (
            "blocks",
            "chain_offsets",
            "segment_offsets",
            "option_fragment_offsets",
            "fragment_offsets",
            "segment_start",
            "segment_track",
            "segment_age",
            "segment_area",
            "event_offsets",
            "event_offset",
            "event_track",
            "event_age",
            "event_label",
            "event_area",
        )
        return {name: torch.as_tensor(getattr(self, name), device=device) for name in names}

    def save(self, path: str | Path) -> Path:
        """Persist the flat descriptor arrays to one NumPy archive.

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
        np.savez(
            destination,
            blocks=self.blocks,
            chain_offsets=self.chain_offsets,
            segment_offsets=self.segment_offsets,
            option_fragment_offsets=self.option_fragment_offsets,
            fragment_offsets=self.fragment_offsets,
            segment_start=self.segment_start,
            segment_track=self.segment_track,
            segment_age=self.segment_age,
            segment_area=self.segment_area,
            event_offsets=self.event_offsets,
            event_offset=self.event_offset,
            event_track=self.event_track,
            event_age=self.event_age,
            event_label=self.event_label,
            event_area=self.event_area,
            labels=np.asarray(self.labels),
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> FactorizedEffectArrays:
        """Load a persisted flat descriptor archive.

        Parameters
        ----------
        path : str or pathlib.Path
            Archive written by :meth:`save`.

        Returns
        -------
        FactorizedEffectArrays
            The loaded arrays.
        """
        import numpy as np

        with np.load(Path(path), allow_pickle=False) as payload:
            return cls(
                blocks=payload["blocks"],
                chain_offsets=payload["chain_offsets"],
                segment_offsets=payload["segment_offsets"],
                option_fragment_offsets=payload["option_fragment_offsets"],
                fragment_offsets=payload["fragment_offsets"],
                segment_start=payload["segment_start"],
                segment_track=payload["segment_track"],
                segment_age=payload["segment_age"],
                segment_area=payload["segment_area"],
                event_offsets=payload["event_offsets"],
                event_offset=payload["event_offset"],
                event_track=payload["event_track"],
                event_age=payload["event_age"],
                event_label=payload["event_label"],
                event_area=payload["event_area"],
                labels=tuple(str(value) for value in payload["labels"].tolist()),
            )

    def nbytes(self) -> int:
        """Return the bytes held by the flat descriptor arrays.

        Returns
        -------
        int
            Total array bytes.
        """
        arrays = (
            self.blocks,
            self.chain_offsets,
            self.segment_offsets,
            self.option_fragment_offsets,
            self.fragment_offsets,
            self.segment_start,
            self.segment_track,
            self.segment_age,
            self.segment_area,
            self.event_offsets,
            self.event_offset,
            self.event_track,
            self.event_age,
            self.event_label,
            self.event_area,
        )
        return sum(int(value.nbytes) for value in arrays)


class PaddedFactorizedEvents:
    """Padded device event tensors for batched product-account evaluation.

    Events are point contributions. TSA24 has at most three events per option, so a
    ``[options, events]`` layout is small enough to keep on the device without an
    all-account matrix.

    Parameters
    ----------
    offset, track, age, label, area : torch.Tensor
        ``[options, events]`` event tensors.
    valid : torch.Tensor
        Boolean validity mask with the same shape.
    chain_offsets : torch.Tensor
        Block-to-option offset tensor.
    blocks : torch.Tensor
        Sorted block ids.
    """

    def __init__(
        self,
        offset: Any,  # noqa: ANN401
        track: Any,  # noqa: ANN401
        age: Any,  # noqa: ANN401
        label: Any,  # noqa: ANN401
        area: Any,  # noqa: ANN401
        valid: Any,  # noqa: ANN401
        chain_offsets: Any,  # noqa: ANN401
        blocks: Any,  # noqa: ANN401
    ) -> None:
        self.offset = offset
        self.track = track
        self.age = age
        self.label = label
        self.area = area
        self.valid = valid
        self.chain_offsets = chain_offsets
        self.blocks = blocks
        self.device = offset.device

    @classmethod
    def estimated_bytes(cls, arrays: FactorizedEffectArrays) -> int:
        """Return the padded CPU event array bytes before torch conversion.

        Parameters
        ----------
        arrays : FactorizedEffectArrays
            Flat descriptor arrays.

        Returns
        -------
        int
            Estimated padded bytes.
        """
        import numpy as np

        options = arrays.option_count
        max_events = int(np.diff(arrays.event_offsets).max(initial=0))
        slots = options * max_events
        return slots * (2 + 2 + 2 + 2 + 4 + 1)

    @classmethod
    def from_arrays(
        cls,
        arrays: FactorizedEffectArrays,
        *,
        device: str = "cpu",
    ) -> PaddedFactorizedEvents:
        """Pad flat event descriptors into ``[options, events]`` tensors.

        Parameters
        ----------
        arrays : FactorizedEffectArrays
            Flat descriptor arrays.
        device : str, optional
            Torch device. Defaults to ``cpu``.

        Returns
        -------
        PaddedFactorizedEvents
            Padded event tensors.
        """
        import numpy as np
        import torch

        options = arrays.option_count
        max_events = int(np.diff(arrays.event_offsets).max(initial=0))
        offset = np.full((options, max_events), 32767, dtype=np.int16)
        track = np.zeros_like(offset)
        age = np.zeros_like(offset)
        label = np.zeros_like(offset)
        area = np.zeros((options, max_events), dtype=np.float32)
        valid = np.zeros((options, max_events), dtype=np.bool_)
        for row in range(options):
            event_start = int(arrays.event_offsets[row])
            event_stop = int(arrays.event_offsets[row + 1])
            for event in range(event_start, event_stop):
                slot = event - event_start
                offset[row, slot] = arrays.event_offset[event]
                track[row, slot] = arrays.event_track[event]
                age[row, slot] = arrays.event_age[event]
                label[row, slot] = arrays.event_label[event]
                area[row, slot] = arrays.event_area[event]
                valid[row, slot] = True
        return cls(
            offset=torch.as_tensor(offset, device=device),
            track=torch.as_tensor(track, device=device),
            age=torch.as_tensor(age, device=device),
            label=torch.as_tensor(label, device=device),
            area=torch.as_tensor(area, device=device),
            valid=torch.as_tensor(valid, device=device),
            chain_offsets=torch.as_tensor(arrays.chain_offsets, device=device),
            blocks=torch.as_tensor(arrays.blocks, device=device),
        )

    def product_offsets(
        self,
        genomes: Any,  # noqa: ANN401
        product_values: Any,  # noqa: ANN401
        offsets: Sequence[int],
        *,
        years: int,
    ) -> Any:  # noqa: ANN401
        """Return product values at requested year offsets for a genome batch.

        Parameters
        ----------
        genomes : torch.Tensor
            ``[genomes, blocks]`` option indices.
        product_values : torch.Tensor
            ``[tracks, labels, ages]`` product lookup for one account.
        offsets : sequence of int
            Year offsets to read.
        years : int
            Horizon; events outside it are ignored.

        Returns
        -------
        torch.Tensor
            ``[genomes, offsets]`` product totals.
        """
        import torch

        genomes = genomes.to(self.device)
        product_values = product_values.to(self.device)
        block_positions = torch.arange(len(self.blocks), device=self.device)
        rows = self.chain_offsets[block_positions].unsqueeze(0) + genomes
        event_offsets = self.offset[rows]
        valid = self.valid[rows] & (event_offsets < years)
        selected_track = self.track[rows].clamp(0, product_values.shape[0] - 1).long()
        selected_label = self.label[rows].clamp(0, product_values.shape[1] - 1).long()
        selected_age = self.age[rows].clamp(0, product_values.shape[2] - 1).long()
        values = product_values[selected_track, selected_label, selected_age]
        values = torch.where(valid, values, torch.zeros_like(values))
        contributions = values * self.area[rows]
        event_year = event_offsets.clamp(0, years - 1).long()
        genomes_count = genomes.shape[0]
        batch_index = (
            torch.arange(genomes_count, device=self.device)
            .view(genomes_count, 1, 1)
            .expand_as(event_year)
        )
        flat_index = batch_index.reshape(-1) * years + event_year.reshape(-1)
        output = torch.zeros(genomes_count * years, dtype=torch.float64, device=self.device)
        output.scatter_add_(0, flat_index, contributions.double().reshape(-1))
        output = output.view(genomes_count, years)
        selected = torch.as_tensor(offsets, dtype=torch.int64, device=self.device)
        if bool((selected < 0).any()) or bool((selected >= years).any()):
            raise ValueError("factorized product offsets must be inside the horizon")
        return output[:, selected]

    def state_dict(self) -> dict[str, Any]:
        """Return CPU tensors for a persisted padded cache.

        Returns
        -------
        dict of str to torch.Tensor
            Detached CPU tensors for the padded layout.
        """
        return {
            "offset": self.offset.detach().cpu(),
            "track": self.track.detach().cpu(),
            "age": self.age.detach().cpu(),
            "label": self.label.detach().cpu(),
            "area": self.area.detach().cpu(),
            "valid": self.valid.detach().cpu(),
            "chain_offsets": self.chain_offsets.detach().cpu(),
            "blocks": self.blocks.detach().cpu(),
        }

    @classmethod
    def from_state_dict(
        cls,
        payload: dict[str, Any],
        *,
        device: str = "cpu",
    ) -> PaddedFactorizedEvents:
        """Restore padded event tensors from a cache payload.

        Parameters
        ----------
        payload : dict
            Cache payload from :meth:`state_dict`.
        device : str
            Torch device string.

        Returns
        -------
        PaddedFactorizedEvents
            The restored event layout.
        """
        import torch

        return cls(
            offset=torch.as_tensor(payload["offset"], device=device),
            track=torch.as_tensor(payload["track"], device=device),
            age=torch.as_tensor(payload["age"], device=device),
            label=torch.as_tensor(payload["label"], device=device),
            area=torch.as_tensor(payload["area"], device=device),
            valid=torch.as_tensor(payload["valid"], device=device),
            chain_offsets=torch.as_tensor(payload["chain_offsets"], device=device),
            blocks=torch.as_tensor(payload["blocks"], device=device),
        )

    def to(self, device: str) -> PaddedFactorizedEvents:
        """Move the padded event tensors to another device.

        Parameters
        ----------
        device : str
            Torch device string.

        Returns
        -------
        PaddedFactorizedEvents
            The same layout on the requested device.
        """
        return PaddedFactorizedEvents(
            offset=self.offset.to(device),
            track=self.track.to(device),
            age=self.age.to(device),
            label=self.label.to(device),
            area=self.area.to(device),
            valid=self.valid.to(device),
            chain_offsets=self.chain_offsets.to(device),
            blocks=self.blocks.to(device),
        )

    def product_batch(
        self,
        genomes: Any,  # noqa: ANN401
        product_values: Any,  # noqa: ANN401
        *,
        years: int,
        period_width: int,
    ) -> Any:  # noqa: ANN401
        """Return product totals for a batch of genomes.

        Parameters
        ----------
        genomes : torch.Tensor
            ``[genomes, blocks]`` option indices.
        product_values : torch.Tensor
            ``[tracks, labels, ages]`` product lookup for one account.
        years : int
            Horizon.
        period_width : int
            Years per accounting period.

        Returns
        -------
        torch.Tensor
            ``[genomes, periods]`` product totals.
        """
        import torch

        genomes = genomes.to(self.device)
        product_values = product_values.to(self.device)
        periods = (years + period_width - 1) // period_width
        block_positions = torch.arange(len(self.blocks), device=self.device)
        rows = self.chain_offsets[block_positions].unsqueeze(0) + genomes
        offsets = self.offset[rows]
        valid = self.valid[rows] & (offsets < years)
        period_index = (offsets // period_width).clamp(0, periods - 1)
        selected_track = self.track[rows].clamp(0, product_values.shape[0] - 1).long()
        selected_label = self.label[rows].clamp(0, product_values.shape[1] - 1).long()
        selected_age = self.age[rows].clamp(0, product_values.shape[2] - 1).long()
        values = product_values[selected_track, selected_label, selected_age]
        values = torch.where(valid, values, torch.zeros_like(values))
        contributions = values * self.area[rows]
        genomes_count = genomes.shape[0]
        batch_index = (
            torch.arange(genomes_count, device=self.device)
            .view(genomes_count, 1, 1)
            .expand_as(period_index)
        )
        flat_index = batch_index.reshape(-1) * periods + period_index.reshape(-1)
        output = torch.zeros(genomes_count * periods, dtype=torch.float64, device=self.device)
        output.scatter_add_(0, flat_index, contributions.double().reshape(-1))
        return output.view(genomes_count, periods)


def _feature_table_from_limits(
    max_track: int,
    max_age: int,
    simulator: object,
    account: str,
) -> Any:  # noqa: ANN401
    """Build a feature lookup table from explicit track/age limits."""
    import numpy as np

    table = np.zeros((max(0, max_track) + 1, max(1, max_age)), dtype=np.float64)
    features = getattr(simulator, "_track_features", {})
    curve_value = simulator._curve_value  # type: ignore[attr-defined]
    for track, labels in features.items():
        track_index = int(track)
        if track_index > max_track:
            continue
        for curve, label in labels:
            if str(label) == account:
                table[track_index] = [
                    float(curve_value(curve, age)) for age in range(table.shape[1])
                ]
                break
    return table


def build_feature_value_table(
    arrays: FactorizedEffectArrays,
    simulator: object,
    account: str,
    *,
    years: int,
) -> Any:  # noqa: ANN401
    """Build one track/age feature lookup table from flat descriptors.

    Parameters
    ----------
    arrays : FactorizedEffectArrays
        Flat descriptor arrays.
    simulator : object
        Simulator with track feature curves.
    account : str
        Feature account label.
    years : int
        Simulation horizon; the table includes ages after segment start.

    Returns
    -------
    numpy.ndarray
        ``[tracks, ages]`` float64 values for one account.
    """
    max_track = max(0, int(arrays.segment_track.max(initial=0)))
    max_age = max(1, int(arrays.segment_age.max(initial=0)) + int(years))
    return _feature_table_from_limits(max_track, max_age, simulator, account)


def _product_table_from_limits(
    max_track: int,
    max_age: int,
    labels: Sequence[str],
    simulator: object,
    account: str,
) -> Any:  # noqa: ANN401
    """Build a product lookup table from explicit track/age limits."""
    import numpy as np

    table = np.zeros((max(0, max_track) + 1, len(labels), max(1, max_age)), dtype=np.float64)
    label_index = {str(label): index for index, label in enumerate(labels)}
    products = getattr(simulator, "_products_by_key", {})
    curve_value = simulator._curve_value  # type: ignore[attr-defined]
    for (track, treatment), curves in products.items():
        index = label_index.get(str(treatment))
        track_index = int(track)
        if index is None or track_index > max_track:
            continue
        for curve, label in curves:
            if str(label) == account:
                table[track_index, index] = [
                    float(curve_value(curve, age)) for age in range(table.shape[2])
                ]
                break
    return table


def build_product_value_table(
    arrays: FactorizedEffectArrays,
    simulator: object,
    account: str,
) -> Any:  # noqa: ANN401
    """Build one track/treatment/age product lookup table.

    Parameters
    ----------
    arrays : FactorizedEffectArrays
        Flat descriptor arrays.
    simulator : object
        Simulator with product curves.
    account : str
        Product account label.

    Returns
    -------
    numpy.ndarray
        ``[tracks, labels, ages]`` float64 values for one account.
    """
    max_track = max(0, int(arrays.event_track.max(initial=0)))
    max_age = max(1, int(arrays.event_age.max(initial=0)) + 1)
    return _product_table_from_limits(
        max_track, max_age, tuple(str(label) for label in arrays.labels), simulator, account
    )


class FactorizedAccountSet:
    """One-account factorized lookups for target-cell pricing.

    This is the account-switching surface: the segment and event layouts are
    account-independent, while each requested feature or product account gets a small
    cache entry built from the simulator curves.

    Parameters
    ----------
    segments : PaddedFactorizedTensors
        Padded segment tensors.
    events : PaddedFactorizedEvents
        Padded event tensors.
    simulator : object
        Simulator providing curve lookup.
    blocks : numpy.ndarray
        Artifact block order.
    years : int
        Simulation horizon.
    device : str
        Torch device.
    feature_max_track, feature_max_age : int
        Feature lookup limits.
    product_max_track, product_max_age : int
        Product lookup limits.
    labels : sequence of str
        Event treatment labels in artifact index order.
    """

    def __init__(
        self,
        segments: PaddedFactorizedTensors,
        events: PaddedFactorizedEvents,
        simulator: object,
        blocks: Any,  # noqa: ANN401
        *,
        years: int,
        device: str = "cpu",
        feature_max_track: int,
        feature_max_age: int,
        product_max_track: int,
        product_max_age: int,
        labels: Sequence[str],
    ) -> None:
        self.segments = segments
        self.events = events
        self.simulator = simulator
        self.blocks = blocks
        self.years = int(years)
        self.device = device
        self.feature_max_track = int(feature_max_track)
        self.feature_max_age = int(feature_max_age)
        self.product_max_track = int(product_max_track)
        self.product_max_age = int(product_max_age)
        self.labels = tuple(str(label) for label in labels)
        self._feature_tables: dict[str, Any] = {}
        self._product_tables: dict[str, Any] = {}
        self._feature_accounts: set[str] | None = None
        self._product_accounts: set[str] | None = None

    def supports(self, account: str) -> bool:
        """Return whether the simulator exposes the account label.

        Parameters
        ----------
        account : str
            Feature or product account label.

        Returns
        -------
        bool
            ``True`` when the simulator has that account.
        """
        if account.startswith("product."):
            if self._product_accounts is None:
                self._product_accounts = {
                    str(label)
                    for curves in getattr(self.simulator, "_products_by_key", {}).values()
                    for _curve, label in curves
                }
            return account in self._product_accounts
        if self._feature_accounts is None:
            self._feature_accounts = {
                str(label)
                for labels in getattr(self.simulator, "_track_features", {}).values()
                for _curve, label in labels
            }
        return account in self._feature_accounts

    @classmethod
    def from_arrays(
        cls,
        arrays: FactorizedEffectArrays,
        simulator: object,
        *,
        years: int,
        device: str = "cpu",
    ) -> FactorizedAccountSet:
        """Build the account set from flat descriptor arrays.

        Parameters
        ----------
        arrays : FactorizedEffectArrays
            Flat descriptor arrays.
        simulator : object
            Simulator providing curve lookup.
        years : int
            Simulation horizon.
        device : str
            Torch device string.

        Returns
        -------
        FactorizedAccountSet
            The account set on ``device``.
        """
        feature_max_track = max(0, int(arrays.segment_track.max(initial=0)))
        feature_max_age = max(1, int(arrays.segment_age.max(initial=0)) + int(years))
        product_max_track = max(0, int(arrays.event_track.max(initial=0)))
        product_max_age = max(1, int(arrays.event_age.max(initial=0)) + 1)
        segments = PaddedFactorizedTensors.from_arrays(arrays).to(device)
        events = PaddedFactorizedEvents.from_arrays(arrays).to(device)
        return cls(
            segments,
            events,
            simulator,
            arrays.blocks.copy(),
            years=years,
            device=device,
            feature_max_track=feature_max_track,
            feature_max_age=feature_max_age,
            product_max_track=product_max_track,
            product_max_age=product_max_age,
            labels=tuple(str(label) for label in arrays.labels),
        )

    @classmethod
    def from_artifact(
        cls,
        path: str | Path,
        simulator: object,
        *,
        years: int,
        device: str = "cpu",
        arrays: FactorizedEffectArrays | None = None,
        cache: str | Path | None = None,
    ) -> FactorizedAccountSet:
        """Build the account set from a persisted descriptor archive.

        Parameters
        ----------
        path : str or pathlib.Path
            Persisted archive path.
        simulator : object
            Simulator providing curve lookup.
        years : int
            Simulation horizon.
        device : str
            Torch device string.
        arrays : FactorizedEffectArrays or None, optional
            Already-loaded arrays; None loads ``path``.
        cache : str or pathlib.Path or None, optional
            Padded cache to load, or to create when it is absent.

        Returns
        -------
        FactorizedAccountSet
            The account set on ``device``.
        """
        if cache is not None and Path(cache).is_file():
            return cls.load_cache(cache, simulator, device=device)
        payload = arrays if arrays is not None else FactorizedEffectArrays.load(path)
        accounts = cls.from_arrays(payload, simulator, years=years, device=device)
        if cache is not None:
            accounts.save_cache(cache)
        return accounts

    def save_cache(self, path: str | Path) -> Path:
        """Persist the padded tensors and lookup metadata to one torch file.

        Parameters
        ----------
        path : str or pathlib.Path
            Destination cache file.

        Returns
        -------
        pathlib.Path
            The written path.
        """
        import torch

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "version": 1,
                "years": self.years,
                "feature_max_track": self.feature_max_track,
                "feature_max_age": self.feature_max_age,
                "product_max_track": self.product_max_track,
                "product_max_age": self.product_max_age,
                "labels": list(self.labels),
                "segments": self.segments.state_dict(),
                "events": self.events.state_dict(),
            },
            destination,
        )
        return destination

    @classmethod
    def load_cache(
        cls,
        path: str | Path,
        simulator: object,
        *,
        device: str = "cpu",
    ) -> FactorizedAccountSet:
        """Load a persisted padded cache without rebuilding the layout.

        Parameters
        ----------
        path : str or pathlib.Path
            Cache written by :meth:`save_cache`.
        simulator : object
            Simulator providing curve lookup.
        device : str
            Torch device string.

        Returns
        -------
        FactorizedAccountSet
            The account set on ``device``.
        """
        import torch

        payload = torch.load(Path(path), map_location="cpu", weights_only=True)
        segments = PaddedFactorizedTensors.from_state_dict(payload["segments"], device=device)
        events = PaddedFactorizedEvents.from_state_dict(payload["events"], device=device)
        return cls(
            segments,
            events,
            simulator,
            segments.blocks.cpu().numpy(),
            years=int(payload["years"]),
            device=device,
            feature_max_track=int(payload["feature_max_track"]),
            feature_max_age=int(payload["feature_max_age"]),
            product_max_track=int(payload["product_max_track"]),
            product_max_age=int(payload["product_max_age"]),
            labels=tuple(str(label) for label in payload["labels"]),
        )

    def _feature_table(self, account: str) -> Any:  # noqa: ANN401
        import torch

        table = self._feature_tables.get(account)
        if table is None:
            table = torch.as_tensor(
                _feature_table_from_limits(
                    self.feature_max_track,
                    self.feature_max_age,
                    self.simulator,
                    account,
                ),
                device=self.device,
            )
            self._feature_tables[account] = table
        return table

    def _product_table(self, account: str) -> Any:  # noqa: ANN401
        import torch

        table = self._product_tables.get(account)
        if table is None:
            table = torch.as_tensor(
                _product_table_from_limits(
                    self.product_max_track,
                    self.product_max_age,
                    self.labels,
                    self.simulator,
                    account,
                ),
                device=self.device,
            )
            self._product_tables[account] = table
        return table

    def totals(
        self,
        genomes: Any,  # noqa: ANN401
        cells: Sequence[tuple[int, str]],
    ) -> Any:  # noqa: ANN401
        """Return absolute factorized totals for requested target cells.

        Parameters
        ----------
        genomes : torch.Tensor
            ``[genomes, blocks]`` option indices.
        cells : sequence of (int, str)
            Year/account target cells.

        Returns
        -------
        torch.Tensor
            ``[genomes, cells]`` float64 totals.
        """
        import torch

        output = torch.zeros(
            (genomes.shape[0], len(cells)), dtype=torch.float64, device=self.device
        )
        grouped: dict[str, list[tuple[int, int]]] = {}
        for column, (offset, account) in enumerate(cells):
            grouped.setdefault(str(account), []).append((column, int(offset)))
        for account, entries in grouped.items():
            if not self.supports(account):
                raise ValueError(f"factorized account is not available: {account}")
            offsets = sorted({offset for _column, offset in entries})
            if account.startswith("product."):
                values = self.events.product_offsets(
                    genomes,
                    self._product_table(account),
                    offsets,
                    years=self.years,
                )
            else:
                values = self.segments.feature_offsets(
                    genomes,
                    self._feature_table(account),
                    offsets,
                )
            positions = {offset: position for position, offset in enumerate(offsets)}
            for column, offset in entries:
                output[:, column] = values[:, positions[offset]]
        return output


def _active_array_segment(
    starts: Any,  # noqa: ANN401
    tracks: Any,  # noqa: ANN401
    ages: Any,  # noqa: ANN401
    areas: Any,  # noqa: ANN401
    start: int,
    stop: int,
    offset: int,
) -> tuple[int, int, float] | None:
    """Return the active segment's track, age, and area from flat arrays."""
    active = None
    for index in range(start, stop):
        if int(starts[index]) <= offset:
            active = index
        else:
            break
    if active is None:
        return None
    return (
        int(tracks[active]),
        int(ages[active]) + offset - int(starts[active]),
        float(areas[active]),
    )


def _simulator_feature(simulator: object, track: int, age: int, account: str) -> float:
    """Return a feature value from the simulator's track curves."""
    for curve, label in simulator._track_features.get(track, ()):  # type: ignore[attr-defined]
        if str(label) == account:
            return float(simulator._curve_value(curve, age))  # type: ignore[attr-defined]
    return 0.0


def _append_option_arrays(
    simulator: object,
    tracks: Sequence[int],
    offsets: Sequence[int],
    areas: Sequence[float],
    chain: Sequence[tuple[str, int]],
    years: int,
    fragment_offsets: Any,  # noqa: ANN401
    segment_start: Any,  # noqa: ANN401
    segment_track: Any,  # noqa: ANN401
    segment_age: Any,  # noqa: ANN401
    segment_area: Any,  # noqa: ANN401
    event_offset: Any,  # noqa: ANN401
    event_track: Any,  # noqa: ANN401
    event_age: Any,  # noqa: ANN401
    event_label: Any,  # noqa: ANN401
    event_area: Any,  # noqa: ANN401
    labels: dict[str, int],
) -> None:
    """Append one option's segment and event coordinates to flat arrays."""
    ordered = sorted((int(offset), str(treatment)) for treatment, offset in chain)
    for track, offset, area in zip(tracks, offsets, areas, strict=True):
        fragment_offsets.append(len(segment_start))
        current_track = int(track)
        current_age = int(offset)
        current_start = 0
        segment_start.append(0)
        segment_track.append(current_track)
        segment_age.append(current_age)
        segment_area.append(float(area))
        for event_at, treatment in ordered:
            if event_at < current_start or event_at >= years:
                continue
            age = current_age + event_at - current_start
            transition = simulator._treatment_by_key.get((current_track, treatment))  # type: ignore[attr-defined]
            if transition is None:
                continue
            event_offset.append(event_at)
            event_track.append(current_track)
            event_age.append(age)
            event_label.append(labels.setdefault(treatment, len(labels)))
            event_area.append(float(area))
            current_track = int(transition[0])
            current_age = int(transition[1])
            current_start = event_at
            segment_start.append(event_at)
            segment_track.append(current_track)
            segment_age.append(current_age)
            segment_area.append(float(area))


_array_optimizer: Any = None
_array_candidates: Any = None
_array_years: int = 0
_array_labels: dict[str, int] = {}
_ARRAY_WORKER_LIMIT: int = 0


def _init_array_worker(limit: int) -> None:
    """Apply a hard address-space limit in one forked worker."""
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def _build_array_chunk(blocks: tuple[int, ...]) -> FactorizedEffectArrays:
    """Build descriptors for one block chunk."""
    return _build_arrays_for_blocks(
        _array_optimizer,
        _array_candidates,
        blocks,
        _array_years,
        _array_labels,
    )


def _build_arrays_for_blocks(
    optimizer: Optimizer,
    candidates: Candidates,
    blocks: Sequence[int],
    years: int,
    labels: dict[str, int],
) -> FactorizedEffectArrays:
    """Build descriptors for a block sequence without multiprocessing."""
    from array import array

    import numpy as np

    simulator = optimizer.simulator()
    block_index = simulator._block_index()
    arrays_track, arrays_offset, arrays_area = simulator._fragment_arrays()
    chosen_blocks: list[int] = []
    chain_offsets = array("i", [0])
    segment_offsets = array("i", [0])
    option_fragment_offsets = array("i", [0])
    fragment_offsets = array("i")
    segment_start = array("h")
    segment_track = array("h")
    segment_age = array("h")
    segment_area = array("f")
    event_offsets = array("i", [0])
    event_offset = array("h")
    event_track = array("h")
    event_age = array("h")
    event_label = array("h")
    event_area = array("f")
    for block in blocks:
        positions = block_index.get(int(block), [])
        tracks = [int(value) for value in arrays_track[positions]]
        offsets = [int(value) for value in arrays_offset[positions]]
        areas = [float(value) for value in arrays_area[positions]]
        chosen_blocks.append(int(block))
        for chain in candidates[int(block)]:
            _append_option_arrays(
                simulator,
                tracks,
                offsets,
                areas,
                chain,
                years,
                fragment_offsets,
                segment_start,
                segment_track,
                segment_age,
                segment_area,
                event_offset,
                event_track,
                event_age,
                event_label,
                event_area,
                labels,
            )
            fragment_offsets.append(len(segment_start))
            option_fragment_offsets.append(len(fragment_offsets))
            segment_offsets.append(len(segment_start))
            event_offsets.append(len(event_offset))
        chain_offsets.append(len(segment_offsets) - 1)
    return FactorizedEffectArrays(
        blocks=np.asarray(chosen_blocks, dtype=np.int64),
        chain_offsets=np.asarray(chain_offsets, dtype=np.int32),
        segment_offsets=np.asarray(segment_offsets, dtype=np.int32),
        option_fragment_offsets=np.asarray(option_fragment_offsets, dtype=np.int32),
        fragment_offsets=np.asarray(fragment_offsets, dtype=np.int32),
        segment_start=np.asarray(segment_start, dtype=np.int16),
        segment_track=np.asarray(segment_track, dtype=np.int16),
        segment_age=np.asarray(segment_age, dtype=np.int16),
        segment_area=np.asarray(segment_area, dtype=np.float32),
        event_offsets=np.asarray(event_offsets, dtype=np.int32),
        event_offset=np.asarray(event_offset, dtype=np.int16),
        event_track=np.asarray(event_track, dtype=np.int16),
        event_age=np.asarray(event_age, dtype=np.int16),
        event_label=np.asarray(event_label, dtype=np.int16),
        event_area=np.asarray(event_area, dtype=np.float32),
        labels=tuple(value for value, _index in sorted(labels.items(), key=lambda item: item[1])),
    )


def _merge_arrays(
    results: Sequence[FactorizedEffectArrays],
    labels: dict[str, int],
) -> FactorizedEffectArrays:
    """Merge block-chunk arrays with global offsets."""
    import numpy as np

    blocks = [result.blocks for result in results]
    chain_offsets: list[int] = [0]
    segment_offsets: list[int] = [0]
    option_fragment_offsets: list[int] = [0]
    fragment_offsets: list[int] = []
    event_offsets: list[int] = [0]
    segment_start = []
    segment_track = []
    segment_age = []
    segment_area = []
    event_offset = []
    event_track = []
    event_age = []
    event_label = []
    event_area = []
    row_offset = 0
    segment_offset = 0
    event_offset_value = 0
    fragment_index_offset = 0
    for result in results:
        chain_offsets.extend((result.chain_offsets[1:] + row_offset).tolist())
        segment_offsets.extend((result.segment_offsets[1:] + segment_offset).tolist())
        option_fragment_offsets.extend(
            (result.option_fragment_offsets[1:] + fragment_index_offset).tolist()
        )
        fragment_offsets.extend((result.fragment_offsets + segment_offset).tolist())
        event_offsets.extend((result.event_offsets[1:] + event_offset_value).tolist())
        segment_start.append(result.segment_start)
        segment_track.append(result.segment_track)
        segment_age.append(result.segment_age)
        segment_area.append(result.segment_area)
        event_offset.append(result.event_offset)
        event_track.append(result.event_track)
        event_age.append(result.event_age)
        event_label.append(result.event_label)
        event_area.append(result.event_area)
        row_offset += result.option_count
        segment_offset += len(result.segment_start)
        event_offset_value += len(result.event_offset)
        fragment_index_offset += len(result.fragment_offsets)
    return FactorizedEffectArrays(
        blocks=np.concatenate(blocks) if blocks else np.empty(0, dtype=np.int64),
        chain_offsets=np.asarray(chain_offsets, dtype=np.int32),
        segment_offsets=np.asarray(segment_offsets, dtype=np.int32),
        option_fragment_offsets=np.asarray(option_fragment_offsets, dtype=np.int32),
        fragment_offsets=np.asarray(fragment_offsets, dtype=np.int32),
        segment_start=np.concatenate(segment_start)
        if segment_start
        else np.empty(0, dtype=np.int16),
        segment_track=np.concatenate(segment_track)
        if segment_track
        else np.empty(0, dtype=np.int16),
        segment_age=np.concatenate(segment_age) if segment_age else np.empty(0, dtype=np.int16),
        segment_area=np.concatenate(segment_area)
        if segment_area
        else np.empty(0, dtype=np.float32),
        event_offsets=np.asarray(event_offsets, dtype=np.int32),
        event_offset=np.concatenate(event_offset) if event_offset else np.empty(0, dtype=np.int16),
        event_track=np.concatenate(event_track) if event_track else np.empty(0, dtype=np.int16),
        event_age=np.concatenate(event_age) if event_age else np.empty(0, dtype=np.int16),
        event_label=np.concatenate(event_label) if event_label else np.empty(0, dtype=np.int16),
        event_area=np.concatenate(event_area) if event_area else np.empty(0, dtype=np.float32),
        labels=tuple(value for value, _index in sorted(labels.items(), key=lambda item: item[1])),
    )


class PaddedFactorizedTensors:
    """Padded device tensors for batched feature-account evaluation.

    TSA24 currently has two fragments per option and at most four segments per
    fragment. Padding those small dimensions lets one batch evaluate many genomes with
    tensor gathers rather than per-option Python loops.

    Parameters
    ----------
    start, track, age, area : torch.Tensor
        ``[options, fragments, segments]`` segment tensors.
    valid : torch.Tensor
        Boolean validity mask with the same shape.
    chain_offsets : torch.Tensor
        Block-to-option offset tensor.
    blocks : torch.Tensor
        Sorted block ids.
    """

    def __init__(
        self,
        start: Any,  # noqa: ANN401
        track: Any,  # noqa: ANN401
        age: Any,  # noqa: ANN401
        area: Any,  # noqa: ANN401
        valid: Any,  # noqa: ANN401
        chain_offsets: Any,  # noqa: ANN401
        blocks: Any,  # noqa: ANN401
    ) -> None:
        self.start = start
        self.track = track
        self.age = age
        self.area = area
        self.valid = valid
        self.chain_offsets = chain_offsets
        self.blocks = blocks
        self.device = start.device

    @classmethod
    def estimated_bytes(cls, arrays: FactorizedEffectArrays) -> int:
        """Return the padded CPU array bytes before torch conversion.

        Parameters
        ----------
        arrays : FactorizedEffectArrays
            Flat descriptor arrays.

        Returns
        -------
        int
            Estimated padded bytes.
        """
        import numpy as np

        options = arrays.option_count
        max_fragments = int(np.diff(arrays.option_fragment_offsets).max(initial=0))
        max_segments = int(np.diff(arrays.fragment_offsets).max(initial=0))
        slots = options * max_fragments * max_segments
        return slots * (2 + 2 + 2 + 4 + 1)

    def feature_offsets(
        self,
        genomes: Any,  # noqa: ANN401
        feature_values: Any,  # noqa: ANN401
        offsets: Sequence[int],
    ) -> Any:  # noqa: ANN401
        """Return feature values at requested year offsets for a genome batch.

        Parameters
        ----------
        genomes : torch.Tensor
            ``[genomes, blocks]`` option indices.
        feature_values : torch.Tensor
            ``[tracks, ages]`` feature lookup for one account.
        offsets : sequence of int
            Year offsets to read. Negative watched-only offsets are not accepted.

        Returns
        -------
        torch.Tensor
            ``[genomes, offsets]`` feature totals.
        """
        import torch

        genomes = genomes.to(self.device)
        feature_values = feature_values.to(self.device)
        block_positions = torch.arange(len(self.blocks), device=self.device)
        rows = self.chain_offsets[block_positions].unsqueeze(0) + genomes
        segment_slots = torch.arange(self.start.shape[-1], device=self.device)
        output = torch.zeros(
            (genomes.shape[0], len(offsets)), dtype=torch.float64, device=self.device
        )
        for column, raw_offset in enumerate(offsets):
            offset = int(raw_offset)
            if offset < 0:
                raise ValueError("factorized feature offsets must be non-negative")
            starts = self.start[rows]
            active = self.valid[rows] & (starts <= offset)
            choices = torch.where(active, segment_slots, -1).max(dim=-1).values
            safe_choices = choices.clamp_min(0)
            selected_track = torch.gather(self.track[rows], 3, safe_choices.unsqueeze(-1)).squeeze(
                -1
            )
            selected_age = torch.gather(self.age[rows], 3, safe_choices.unsqueeze(-1)).squeeze(-1)
            selected_area = torch.gather(self.area[rows], 3, safe_choices.unsqueeze(-1)).squeeze(-1)
            ages = (
                selected_age
                + offset
                - torch.gather(starts, 3, safe_choices.unsqueeze(-1)).squeeze(-1)
            )
            ages = ages.clamp(0, feature_values.shape[1] - 1)
            values = feature_values[
                selected_track.clamp(0, feature_values.shape[0] - 1).long(), ages.long()
            ]
            values = torch.where(choices >= 0, values, torch.zeros_like(values))
            output[:, column] = (values * selected_area).sum(dim=(1, 2))
        return output

    def state_dict(self) -> dict[str, Any]:
        """Return CPU tensors for a persisted padded cache.

        Returns
        -------
        dict of str to torch.Tensor
            Detached CPU tensors for the padded layout.
        """
        return {
            "start": self.start.detach().cpu(),
            "track": self.track.detach().cpu(),
            "age": self.age.detach().cpu(),
            "area": self.area.detach().cpu(),
            "valid": self.valid.detach().cpu(),
            "chain_offsets": self.chain_offsets.detach().cpu(),
            "blocks": self.blocks.detach().cpu(),
        }

    @classmethod
    def from_state_dict(
        cls,
        payload: dict[str, Any],
        *,
        device: str = "cpu",
    ) -> PaddedFactorizedTensors:
        """Restore padded segment tensors from a cache payload.

        Parameters
        ----------
        payload : dict
            Cache payload from :meth:`state_dict`.
        device : str
            Torch device string.

        Returns
        -------
        PaddedFactorizedTensors
            The restored segment layout.
        """
        import torch

        return cls(
            start=torch.as_tensor(payload["start"], device=device),
            track=torch.as_tensor(payload["track"], device=device),
            age=torch.as_tensor(payload["age"], device=device),
            area=torch.as_tensor(payload["area"], device=device),
            valid=torch.as_tensor(payload["valid"], device=device),
            chain_offsets=torch.as_tensor(payload["chain_offsets"], device=device),
            blocks=torch.as_tensor(payload["blocks"], device=device),
        )

    def to(self, device: str) -> PaddedFactorizedTensors:
        """Move the padded tensors to another device.

        Parameters
        ----------
        device : str
            Torch device string.

        Returns
        -------
        PaddedFactorizedTensors
            The same layout on the requested device.
        """
        return PaddedFactorizedTensors(
            start=self.start.to(device),
            track=self.track.to(device),
            age=self.age.to(device),
            area=self.area.to(device),
            valid=self.valid.to(device),
            chain_offsets=self.chain_offsets.to(device),
            blocks=self.blocks.to(device),
        )

    @classmethod
    def from_arrays(
        cls,
        arrays: FactorizedEffectArrays,
        *,
        device: str = "cpu",
    ) -> PaddedFactorizedTensors:
        """Pad flat descriptors into ``[options, fragments, segments]`` tensors.

        Parameters
        ----------
        arrays : FactorizedEffectArrays
            Flat descriptor arrays.
        device : str, optional
            Torch device. Defaults to ``cpu``.

        Returns
        -------
        PaddedFactorizedTensors
            Padded device tensors.
        """
        import numpy as np
        import torch

        option_fragment_counts = np.diff(arrays.option_fragment_offsets)
        fragment_segment_counts = np.diff(arrays.fragment_offsets)
        max_fragments = int(option_fragment_counts.max(initial=0))
        max_segments = int(fragment_segment_counts.max(initial=0))
        options = arrays.option_count
        start = np.full((options, max_fragments, max_segments), 32767, dtype=np.int16)
        track = np.zeros_like(start)
        age = np.zeros_like(start)
        area = np.zeros((options, max_fragments, max_segments), dtype=np.float32)
        valid = np.zeros((options, max_fragments, max_segments), dtype=np.bool_)
        for row in range(options):
            frag_start = int(arrays.option_fragment_offsets[row])
            frag_stop = int(arrays.option_fragment_offsets[row + 1])
            for fragment in range(frag_start, frag_stop - 1):
                segment_start = int(arrays.fragment_offsets[fragment])
                segment_stop = int(arrays.fragment_offsets[fragment + 1])
                fragment_slot = fragment - frag_start
                for segment in range(segment_start, segment_stop):
                    slot = segment - segment_start
                    start[row, fragment_slot, slot] = arrays.segment_start[segment]
                    track[row, fragment_slot, slot] = arrays.segment_track[segment]
                    age[row, fragment_slot, slot] = arrays.segment_age[segment]
                    area[row, fragment_slot, slot] = arrays.segment_area[segment]
                    valid[row, fragment_slot, slot] = True
        return cls(
            start=torch.as_tensor(start, device=device),
            track=torch.as_tensor(track, device=device),
            age=torch.as_tensor(age, device=device),
            area=torch.as_tensor(area, device=device),
            valid=torch.as_tensor(valid, device=device),
            chain_offsets=torch.as_tensor(arrays.chain_offsets, device=device),
            blocks=torch.as_tensor(arrays.blocks, device=device),
        )

    def feature_batch(
        self,
        genomes: Any,  # noqa: ANN401
        feature_values: Any,  # noqa: ANN401
        *,
        years: int,
        period_width: int,
    ) -> Any:  # noqa: ANN401
        """Return feature totals for a batch of genomes.

        Parameters
        ----------
        genomes : torch.Tensor
            ``[genomes, blocks]`` option indices.
        feature_values : torch.Tensor
            ``[tracks, years]`` feature lookup for one account.
        years : int
            Horizon.
        period_width : int
            Years per accounting period.

        Returns
        -------
        torch.Tensor
            ``[genomes, periods]`` feature totals.
        """
        import torch

        genomes = genomes.to(self.device)
        feature_values = feature_values.to(self.device)
        block_positions = torch.arange(len(self.blocks), device=self.device)
        rows = self.chain_offsets[block_positions].unsqueeze(0) + genomes
        starts = self.start[rows]
        valid = self.valid[rows]
        segment_slots = torch.arange(starts.shape[-1], device=self.device)
        periods = (years + period_width - 1) // period_width
        output = torch.zeros((genomes.shape[0], periods), dtype=torch.float64, device=self.device)
        for period in range(periods):
            end = min(years - 1, (period + 1) * period_width - 1)
            active = valid & (starts <= end)
            choices = torch.where(active, segment_slots, -1).max(dim=-1).values
            safe_choices = choices.clamp_min(0)
            selected_track = torch.gather(self.track[rows], 3, safe_choices.unsqueeze(-1)).squeeze(
                -1
            )
            selected_age = torch.gather(self.age[rows], 3, safe_choices.unsqueeze(-1)).squeeze(-1)
            selected_area = torch.gather(self.area[rows], 3, safe_choices.unsqueeze(-1)).squeeze(-1)
            ages = (
                selected_age
                + end
                - torch.gather(self.start[rows], 3, safe_choices.unsqueeze(-1)).squeeze(-1)
            )
            ages = ages.clamp(0, feature_values.shape[1] - 1)
            values = feature_values[
                selected_track.clamp(0, feature_values.shape[0] - 1).long(), ages.long()
            ]
            values = torch.where(choices >= 0, values, torch.zeros_like(values))
            output[:, period] = (values * selected_area).sum(dim=(1, 2))
        return output
