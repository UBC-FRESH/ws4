"""Load a compiled dataset into the stochastic process engine.

The compiled management dataset is the contract. This module turns its fragments, tracks,
features, curves, and treatments into the cohort state, volume bridge, block mapping, and
track transitions the process evaluator needs. It does not replace the dataset or silently
invent species and biomass: callers supply those provisional values where the dataset does
not carry them.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pandas as pd

from ..opt.objective import Target
from ..patch.accounts import load_patch_edges_detailed
from .bridge import BridgeError, VolumeBridgeConfig, track_age_volume_curves_from_frame
from .evaluation import ProcessScheduleEvaluation, evaluate_process_schedule
from .fire import FireConfig, FireEdge
from .landis import LandisSuccessionProcess
from .process import Process
from .regeneration import RegenerationConfig
from .state import CohortState, StateSchema
from .succession import SuccessionConfig

if TYPE_CHECKING:
    from ..opt.process_optimization import ProcessOptimizationResult
    from ..opt.process_search import ProcessSearchCandidate, ProcessSearchResult
    from ..opt.schedule_grammar import ScheduleMoveGrammar

DATASET_PROCESS_VERSION: Final[str] = "ws4.process-dataset.v1"


class ProcessDatasetError(ValueError):
    """Raised when a compiled dataset cannot be loaded into the process engine."""


def _read_table(directory: Path, name: str, required: tuple[str, ...]) -> pd.DataFrame:
    """Read one dataset table and require its columns."""
    path = directory / f"{name}.parquet"
    if not path.is_file():
        raise ProcessDatasetError(f"dataset has no {name}.parquet")
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError) as error:
        raise ProcessDatasetError(f"cannot read {name}.parquet: {error}") from error
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ProcessDatasetError(f"{name}.parquet is missing: {', '.join(missing)}")
    return frame


def _as_int(value: object, field: str) -> int:
    """Return an integer from a table value."""
    if isinstance(value, bool):
        raise ProcessDatasetError(f"{field} must be an integer")
    try:
        return int(str(value))
    except ValueError as error:
        raise ProcessDatasetError(f"{field} must be an integer") from error


def _as_float(value: object, field: str) -> float:
    """Return a finite non-negative float from a table value."""
    if isinstance(value, bool):
        raise ProcessDatasetError(f"{field} must be a number")
    try:
        number = float(str(value))
    except ValueError as error:
        raise ProcessDatasetError(f"{field} must be a number") from error
    if not math.isfinite(number) or number < 0.0:
        raise ProcessDatasetError(f"{field} must be finite and non-negative")
    return number


def _fragment_edges(
    topology: Path,
    block_fragments: Mapping[int, Sequence[int]],
) -> tuple[FireEdge, ...]:
    """Map a block topology onto the dataset's fragment graph."""
    edges: dict[frozenset[int], FireEdge] = {}
    for source_block, target_block, _length, distance in load_patch_edges_detailed(topology):
        if source_block == target_block:
            continue
        for source in block_fragments.get(source_block, ()):
            for target in block_fragments.get(target_block, ()):
                if source == target:
                    continue
                key = frozenset((source, target))
                edges.setdefault(key, FireEdge(source, target, distance))
    return tuple(sorted(edges.values(), key=lambda edge: (edge.source, edge.target)))


def _curve_ids(
    features: pd.DataFrame,
    tracks: pd.DataFrame,
    volume_label: str | None,
) -> tuple[dict[int, int], tuple[str, ...]]:
    """Return the compiled curve id for each track and the labels used."""
    available: dict[tuple[int, str], int] = {}
    for row in features.itertuples(index=False):
        available[(_as_int(row.track_id, "track_id"), str(row.label))] = _as_int(
            row.curve_id, "curve_id"
        )
    track_names = {
        _as_int(row.track_id, "track_id"): str(row.name) for row in tracks.itertuples(index=False)
    }
    chosen: dict[int, int] = {}
    labels: set[str] = set()
    for track, name in sorted(track_names.items()):
        if volume_label is not None:
            curve = available.get((track, volume_label))
            if curve is not None:
                chosen[track] = curve
                labels.add(volume_label)
            continue
        candidates: list[str] = []
        if (track, "feature.Volume") in available:
            candidates.append("feature.Volume")
        lower = name.lower()
        if "ifm(managed)" in lower:
            candidates.append("feature.Yield.managed.Total")
        if "ifm(unmanaged)" in lower:
            candidates.append("feature.Yield.unmanaged.Total")
        candidates.extend(
            sorted(
                label
                for _track, label in available
                if _track == track and "yield" in label.lower() and label.lower().endswith(".total")
            )
        )
        candidates.extend(
            sorted(
                label
                for _track, label in available
                if _track == track and ("volume" in label.lower() or "yield" in label.lower())
            )
        )
        for label in candidates:
            curve = available.get((track, label))
            if curve is not None:
                chosen[track] = curve
                labels.add(label)
                break
    if not chosen:
        raise ProcessDatasetError(
            "no track has a volume or yield curve; pass a volume label explicitly"
        )
    return chosen, tuple(sorted(labels))


@dataclass(frozen=True)
class ProcessDataset:
    """A compiled dataset prepared for the process evaluator.

    Parameters
    ----------
    dataset_dir : Path
        Compiled dataset directory.
    state : CohortState
        Initial cohort state, one cohort per fragment.
    block_fragments : mapping of int to tuple of int
        Block id to fragment ids.
    bridge : VolumeBridgeConfig
        Volume bridge with track age curves.
    track_transitions : mapping of (int, str) to int
        ``(source_track, treatment)`` to target track.
    volume_labels : tuple of str
        Feature labels used to build the track curves.
    species : str
        Provisional species label supplied where the dataset has no species column.
    topology : Path or None
        Block topology file, when one was supplied.
    edges : tuple of FireEdge
        Fragment fire edges mapped from the block topology.
    """

    dataset_dir: Path
    state: CohortState
    block_fragments: Mapping[int, tuple[int, ...]]
    bridge: VolumeBridgeConfig
    track_transitions: Mapping[tuple[int, str], int]
    volume_labels: tuple[str, ...]
    species: str
    topology: Path | None
    edges: tuple[FireEdge, ...]

    @classmethod
    def from_directory(
        cls,
        dataset_dir: Path,
        *,
        species: str = "PL",
        initial_biomass_t_ha: float = 100.0,
        initial_fuel_t_ha: float = 0.0,
        volume_label: str | None = None,
        topology: Path | None = None,
        max_blocks: int | None = None,
    ) -> ProcessDataset:
        """Build a process dataset from a compiled dataset directory.

        Parameters
        ----------
        dataset_dir : Path
            Compiled dataset directory.
        species : str, optional
            Species label for every initial cohort (default ``PL``). The compiled dataset
            does not carry a species column.
        initial_biomass_t_ha : float, optional
            Initial live biomass per hectare (default 100).
        initial_fuel_t_ha : float, optional
            Initial surface fuel per hectare (default zero; succession adds fuel).
        volume_label : str or None, optional
            Feature label to use for every track. None selects ``feature.Volume``, then the
            managed/unmanaged ``feature.Yield.*.Total`` label that matches the track name.
        topology : Path or None, optional
            Block topology CSV. When supplied, its block edges are mapped to fragment fire
            edges, so fire can spread between adjacent blocks.
        max_blocks : int or None, optional
            Keep only this many blocks, for a bounded trial run.

        Returns
        -------
        ProcessDataset
            The prepared state, bridge, and management mapping.

        Raises
        ------
        ProcessDatasetError
            If a table, column, id, area, age, or curve is invalid.
        """
        directory = Path(dataset_dir)
        if not directory.is_dir():
            raise ProcessDatasetError(f"dataset directory does not exist: {directory}")
        if isinstance(max_blocks, bool) or (max_blocks is not None and max_blocks <= 0):
            raise ProcessDatasetError("max_blocks must be a positive integer or None")
        if not isinstance(species, str) or not species.strip():
            raise ProcessDatasetError("species must be a non-empty string")
        biomass = _as_float(initial_biomass_t_ha, "initial_biomass_t_ha")
        fuel = _as_float(initial_fuel_t_ha, "initial_fuel_t_ha")

        fragments = _read_table(
            directory,
            "fragments",
            ("fragment_id", "block_id", "area_ha", "age", "track_id"),
        )
        if max_blocks is not None:
            blocks = sorted({_as_int(value, "block_id") for value in fragments["block_id"]})
            keep = set(blocks[:max_blocks])
            fragments = fragments[
                fragments["block_id"].map(lambda value: _as_int(value, "block_id")).isin(keep)
            ]
        if fragments.empty:
            raise ProcessDatasetError("the selected dataset has no fragments")
        tracks = _read_table(directory, "tracks", ("track_id", "name"))
        features = _read_table(directory, "features", ("track_id", "label", "curve_id"))
        curves = _read_table(directory, "curves", ("curve_id", "x", "y"))
        treatments = _read_table(
            directory,
            "treatments",
            ("track_id", "treatment", "new_track"),
        )
        curve_ids, labels = _curve_ids(features, tracks, volume_label)
        try:
            track_curves = track_age_volume_curves_from_frame(curves, curve_ids)
        except BridgeError as error:
            raise ProcessDatasetError(str(error)) from error

        areas: dict[int, float] = {}
        rows: list[dict[str, object]] = []
        for row in fragments.itertuples(index=False):
            fragment = _as_int(row.fragment_id, "fragment_id")
            block = _as_int(row.block_id, "block_id")
            area = _as_float(row.area_ha, "area_ha")
            age = _as_int(row.age, "age")
            track = _as_int(row.track_id, "track_id")
            if fragment <= 0 or block <= 0:
                raise ProcessDatasetError("fragment_id and block_id must be positive")
            if area <= 0.0:
                raise ProcessDatasetError("area_ha must be positive")
            if age < 0:
                raise ProcessDatasetError("age must be non-negative")
            if fragment in areas:
                raise ProcessDatasetError(f"duplicate fragment_id {fragment}")
            areas[fragment] = area
            rows.append(
                {
                    "fragment_id": fragment,
                    "cohort_id": 1,
                    "species": species.strip(),
                    "age": age,
                    "area_fraction": 1.0,
                    "biomass_t_ha": biomass,
                    "fuel_t_ha": fuel,
                    "snag_t_ha": 0.0,
                    "attributes_json": "{}",
                    "track_id": track,
                }
            )
        frame = pd.DataFrame(rows).astype(str)
        state = CohortState.from_tables(
            frame,
            StateSchema(variables={}, bridges=()),
            areas,
        )
        block_fragments: dict[int, list[int]] = {}
        for row in fragments.itertuples(index=False):
            block_fragments.setdefault(_as_int(row.block_id, "block_id"), []).append(
                _as_int(row.fragment_id, "fragment_id")
            )
        transitions: dict[tuple[int, str], int] = {}
        for row in treatments.itertuples(index=False):
            treatment = str(row.treatment).strip()
            if not treatment:
                raise ProcessDatasetError("treatment must be non-empty")
            transitions[(_as_int(row.track_id, "track_id"), treatment)] = _as_int(
                row.new_track, "new_track"
            )
        bridge = VolumeBridgeConfig(
            default_volume_m3_per_t=0.0,
            merchantable_fraction=1.0,
            track_age_volume_curves=track_curves,
        )
        ordered_blocks = {
            block: tuple(sorted(values)) for block, values in sorted(block_fragments.items())
        }
        edges: tuple[FireEdge, ...] = ()
        topology_path = None if topology is None else Path(topology)
        if topology_path is not None:
            if not topology_path.is_file():
                raise ProcessDatasetError(f"topology does not exist: {topology_path}")
            try:
                edges = _fragment_edges(topology_path, ordered_blocks)
            except (OSError, ValueError) as error:
                raise ProcessDatasetError(f"cannot read topology: {error}") from error
        return cls(
            dataset_dir=directory,
            state=state,
            block_fragments=ordered_blocks,
            bridge=bridge,
            track_transitions=transitions,
            volume_labels=labels,
            species=species.strip(),
            topology=topology_path,
            edges=edges,
        )

    def evaluate(
        self,
        schedule: Mapping[int, Sequence[tuple[str, int]]],
        *,
        horizon_years: int,
        fire: FireConfig | None = None,
        regeneration: RegenerationConfig | None = None,
        succession_process: Process | None = None,
        edges: Sequence[FireEdge] | None = None,
        harvest_fraction: float = 1.0,
        targets: Sequence[Target] = (),
        scenario_id: str = "process-dataset",
        seed: int = 0,
    ) -> ProcessScheduleEvaluation:
        """Run one block schedule through the process engine on this dataset.

        Parameters
        ----------
        schedule : mapping of int to sequence of (str, int)
            Block to ordered treatment/offset entries.
        horizon_years : int
            Process transitions.
        fire : FireConfig or None, optional
            Fire parameters; the default has no spatial edges but independent ignition.
        regeneration : RegenerationConfig or None, optional
            Regeneration parameters.
        succession_process : Process or None, optional
            Succession source; the default is the LANDIS process.
        edges : sequence of FireEdge or None, optional
            Spatial fire edges. None uses the edges loaded from ``topology``; an empty
            sequence disables inter-fragment spread.
        harvest_fraction : float, optional
            Fraction removed by a harvest.
        targets : sequence of Target, optional
            Targets priced against the final accounts.
        scenario_id : str, optional
            Scenario id.
        seed : int, optional
            Random-tape seed.

        Returns
        -------
        ProcessScheduleEvaluation
            Final state, accounts, values, and event log.
        """
        return evaluate_process_schedule(
            self.state,
            self.edges if edges is None else edges,
            schedule,
            self.block_fragments,
            horizon_years=horizon_years,
            fire=fire or FireConfig(),
            regeneration=regeneration or RegenerationConfig(),
            bridge=self.bridge,
            succession_process=succession_process or LandisSuccessionProcess(),
            targets=targets,
            harvest_fraction=harvest_fraction,
            track_transitions=self.track_transitions,
            scenario_id=scenario_id,
            seed=seed,
        )

    def search(
        self,
        candidates: Sequence[ProcessSearchCandidate],
        *,
        horizon_years: int,
        targets: Sequence[Target],
        fire: FireConfig | None = None,
        succession: SuccessionConfig | None = None,
        regeneration: RegenerationConfig | None = None,
        succession_process: Process | None = None,
        edges: Sequence[FireEdge] | None = None,
        harvest_fraction: float = 1.0,
        seed: int = 0,
    ) -> ProcessSearchResult:
        """Rank candidate schedules through the process engine on this dataset.

        Parameters
        ----------
        candidates : sequence of ProcessSearchCandidate
            Candidate schedules.
        horizon_years : int
            Process transitions.
        targets : sequence of Target
            Level targets used to price every candidate.
        fire : FireConfig or None, optional
            Fire parameters.
        succession : SuccessionConfig or None, optional
            Logistic succession parameters, used only when no process is supplied.
        regeneration : RegenerationConfig or None, optional
            Regeneration parameters.
        succession_process : Process or None, optional
            Succession source; the default is the LANDIS process.
        edges : sequence of FireEdge or None, optional
            Spatial fire edges; None uses the loaded topology.
        harvest_fraction : float, optional
            Fraction removed by a harvest.
        seed : int, optional
            Shared random-tape seed.

        Returns
        -------
        ProcessSearchResult
            Ranked candidate evaluations.
        """
        from ..opt.process_search import search_process_candidates

        return search_process_candidates(
            self.state,
            self.edges if edges is None else edges,
            candidates,
            self.block_fragments,
            horizon_years=horizon_years,
            fire=fire or FireConfig(),
            targets=targets,
            succession=succession,
            regeneration=regeneration,
            bridge=self.bridge,
            succession_process=succession_process or LandisSuccessionProcess(),
            harvest_fraction=harvest_fraction,
            track_transitions=self.track_transitions,
            seed=seed,
        )

    def optimize(
        self,
        grammar: ScheduleMoveGrammar,
        initial: ProcessSearchCandidate,
        *,
        horizon_years: int,
        targets: Sequence[Target],
        max_iterations: int,
        fire: FireConfig | None = None,
        succession: SuccessionConfig | None = None,
        regeneration: RegenerationConfig | None = None,
        succession_process: Process | None = None,
        edges: Sequence[FireEdge] | None = None,
        harvest_fraction: float = 1.0,
        seed: int = 0,
    ) -> ProcessOptimizationResult:
        """Optimize a schedule through the process engine on this dataset.

        Parameters
        ----------
        grammar : ScheduleMoveGrammar
            Add/remove/optional-move grammar.
        initial : ProcessSearchCandidate
            Starting candidate.
        horizon_years : int
            Process transitions; must match the grammar horizon.
        targets : sequence of Target
            Level targets used to price every candidate.
        max_iterations : int
            Maximum hill-climb rounds.
        fire : FireConfig or None, optional
            Fire parameters.
        succession : SuccessionConfig or None, optional
            Logistic succession parameters, used only when no process is supplied.
        regeneration : RegenerationConfig or None, optional
            Regeneration parameters.
        succession_process : Process or None, optional
            Succession source; the default is the LANDIS process.
        edges : sequence of FireEdge or None, optional
            Spatial fire edges; None uses the loaded topology.
        harvest_fraction : float, optional
            Fraction removed by a harvest.
        seed : int, optional
            Shared random-tape seed.

        Returns
        -------
        ProcessOptimizationResult
            Best evaluation, search trace, and block mapping.
        """
        from ..opt.process_optimization import optimize_process_schedule

        return optimize_process_schedule(
            self.state,
            self.edges if edges is None else edges,
            grammar,
            initial,
            self.block_fragments,
            horizon_years=horizon_years,
            fire=fire or FireConfig(),
            targets=targets,
            max_iterations=max_iterations,
            succession=succession,
            regeneration=regeneration,
            bridge=self.bridge,
            succession_process=succession_process or LandisSuccessionProcess(),
            harvest_fraction=harvest_fraction,
            track_transitions=self.track_transitions,
            seed=seed,
        )
