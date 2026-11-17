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

import numpy as np
import pandas as pd

from ..opt.objective import Target
from ..patch.accounts import load_patch_edges_detailed
from .bridge import BridgeError, VolumeBridgeConfig, track_age_volume_curves_from_frame
from .evaluation import ProcessScheduleEvaluation, evaluate_process_schedule
from .fire import FireConfig, FireEdge
from .landis import (
    LANDIS_REFERENCE_TRAITS,
    LandisBatchSuccessionProcess,
    LandisSpeciesTraits,
    LandisSuccessionConfig,
    LandisSuccessionProcess,
)
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
    text = str(value).strip()
    try:
        return int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError as error:
            raise ProcessDatasetError(f"{field} must be an integer") from error
        if not number.is_integer():
            raise ProcessDatasetError(f"{field} must be an integer") from None
        return int(number)


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


_BIOMASS_SOURCES: Final[frozenset[str]] = frozenset({"auto", "feature", "fixed", "volume"})

_SPECIES_ALIASES: Final[Mapping[str, str]] = {
    "ACT": "poputrem",
    "AT": "poputrem",
    "BL": "abiebals",
    "CW": "thujocci",
    "HW": "tsugcana",
    "PB": "betupapy",
    "PL": "pinubank",
    "PLI": "pinubank",
    "SE": "piceglau",
    "SW": "piceglau",
    "SX": "piceglau",
    "WB": "betualle",
}


def _landis_config(
    species_traits: Mapping[str, LandisSpeciesTraits] | None,
) -> LandisSuccessionConfig:
    """Return the LANDIS traits used by the dataset process."""
    traits = {
        code: LANDIS_REFERENCE_TRAITS[target]
        for code, target in _SPECIES_ALIASES.items()
        if target in LANDIS_REFERENCE_TRAITS
    }
    if species_traits is not None:
        traits.update(species_traits)
    return LandisSuccessionConfig(species=traits)


def _species_fractions(
    fragments: pd.DataFrame,
    features: pd.DataFrame,
    curves: pd.DataFrame,
    *,
    default: str,
) -> dict[int, dict[str, float]]:
    """Return compiled species area fractions for each fragment."""
    by_track: dict[int, dict[str, int]] = {}
    for row in features.itertuples(index=False):
        label = str(row.label)
        if not label.startswith("feature.SpeciesProp."):
            continue
        species = label.rsplit(".", 1)[-1].strip()
        if species:
            by_track.setdefault(_as_int(row.track_id, "track_id"), {})[species] = _as_int(
                row.curve_id, "curve_id"
            )
    if not by_track:
        return {
            int(str(row.fragment_id)): {default: 1.0} for row in fragments.itertuples(index=False)
        }
    needed = {curve for values in by_track.values() for curve in values.values()}
    points: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for curve_id in needed:
        subset = curves.loc[curves["curve_id"] == curve_id]
        if subset.empty:
            raise ProcessDatasetError(f"species curve {curve_id} is missing")
        x = subset["x"].to_numpy(dtype=float)
        y = subset["y"].to_numpy(dtype=float)
        order = np.argsort(x)
        points[curve_id] = (x[order], y[order])
    fractions: dict[int, dict[str, float]] = {}
    for track, group in fragments.groupby("track_id", sort=False):
        track_id = _as_int(track, "track_id")
        species_curves = by_track.get(track_id)
        ids = [int(str(value)) for value in group["fragment_id"]]
        if not species_curves:
            for fragment in ids:
                fractions[fragment] = {default: 1.0}
            continue
        ages = group["age"].to_numpy(dtype=float)
        names = sorted(species_curves)
        values = np.column_stack([np.interp(ages, *points[species_curves[name]]) for name in names])
        values = np.maximum(values, 0.0)
        for fragment, row in zip(ids, values, strict=True):
            total = float(row.sum())
            if total <= 0.0:
                fractions[fragment] = {default: 1.0}
                continue
            parts = {
                name: float(value) / total
                for name, value in zip(names, row, strict=True)
                if float(value) > 0.0
            }
            fractions[fragment] = parts
    return fractions


def _biomass_feature_curves(
    features: pd.DataFrame,
    curves: pd.DataFrame,
    label: str | None,
) -> dict[int, dict[int, float]]:
    """Return per-track biomass curves from a compiled feature label."""
    chosen: dict[int, int] = {}
    for row in features.itertuples(index=False):
        feature = str(row.label)
        matches = feature == label if label is not None else "biomass" in feature.lower()
        if not matches:
            continue
        track = _as_int(row.track_id, "track_id")
        chosen.setdefault(track, _as_int(row.curve_id, "curve_id"))
    if not chosen:
        return {}
    try:
        return track_age_volume_curves_from_frame(curves, chosen)
    except BridgeError as error:
        raise ProcessDatasetError(str(error)) from error


def _biomass_values(
    fragments: pd.DataFrame,
    track_curves: Mapping[int, Mapping[int, float]],
    feature_curves: Mapping[int, Mapping[int, float]],
    *,
    source: str,
    fixed: float,
    wood_density: float,
    expansion: float,
) -> np.ndarray:
    """Return initial biomass density for each fragment."""
    selected = source
    if source == "auto":
        if feature_curves:
            selected = "feature"
        elif track_curves:
            selected = "volume"
        else:
            selected = "fixed"
    if selected == "feature" and not feature_curves:
        raise ProcessDatasetError("no compiled biomass curve is available")
    if selected == "volume" and not track_curves:
        raise ProcessDatasetError("no compiled volume curve is available")
    values = np.full(len(fragments), fixed, dtype=float)
    curves = feature_curves if selected == "feature" else track_curves
    if selected == "fixed":
        return values
    for track, group in fragments.groupby("track_id", sort=False):
        track_id = _as_int(track, "track_id")
        curve = curves.get(track_id)
        if not curve:
            raise ProcessDatasetError(f"track {track_id} has no {selected} curve")
        points = sorted(curve)
        ages = group["age"].to_numpy(dtype=float)
        evaluated = np.interp(
            ages,
            np.array(points, dtype=float),
            np.array([curve[point] for point in points], dtype=float),
        )
        if selected == "volume":
            evaluated = evaluated * wood_density * expansion
        values[group.index.to_numpy()] = evaluated
    return values


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
    treatment_windows : mapping of (int, str) to (int, int)
        Compiled inclusive age window for each ``(source_track, treatment)``.
    volume_labels : tuple of str
        Feature labels used to build the track curves.
    species : str
        Fallback species label where the dataset has no species-proportion curves.
    landis_config : LandisSuccessionConfig
        Species traits used by the LANDIS process, with provisional compiled-code aliases.
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
    treatment_windows: Mapping[tuple[int, str], tuple[int, int]]
    volume_labels: tuple[str, ...]
    species: str
    landis_config: LandisSuccessionConfig
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
        biomass_source: str = "auto",
        biomass_label: str | None = None,
        wood_density_t_m3: float = 0.5,
        biomass_expansion: float = 1.5,
        species_composition: bool = True,
        species_traits: Mapping[str, LandisSpeciesTraits] | None = None,
        topology: Path | None = None,
        max_blocks: int | None = None,
    ) -> ProcessDataset:
        """Build a process dataset from a compiled dataset directory.

        Parameters
        ----------
        dataset_dir : Path
            Compiled dataset directory.
        species : str, optional
            Fallback species label when a track has no species-proportion curve (default
            ``PL``).
        initial_biomass_t_ha : float, optional
            Fixed initial live biomass per hectare, used when ``biomass_source`` is
            ``fixed`` or as the fallback (default 100).
        initial_fuel_t_ha : float, optional
            Initial surface fuel per hectare (default zero; succession adds fuel).
        volume_label : str or None, optional
            Feature label to use for every track. None selects ``feature.Volume``, then the
            managed/unmanaged ``feature.Yield.*.Total`` label that matches the track name.
        biomass_source : str, optional
            ``auto`` (compiled biomass curve, then volume conversion, then fixed), ``feature``
            (compiled biomass curve), ``volume`` (track volume x wood density x expansion), or
            ``fixed``.
        biomass_label : str or None, optional
            Exact compiled biomass feature label. None selects the first label containing
            ``biomass``.
        wood_density_t_m3 : float, optional
            Wood density used by the volume conversion (default 0.5 t/m3).
        biomass_expansion : float, optional
            Biomass expansion factor used by the volume conversion (default 1.5).
        species_composition : bool, optional
            Read ``feature.SpeciesProp.*`` curves and split each fragment into species
            cohorts by area fraction (default True). False uses the fallback species
            everywhere.
        species_traits : mapping of str to LandisSpeciesTraits or None, optional
            Explicit trait overrides by compiled species code. The default aliases map the
            common BC codes to the published reference traits.
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
        if not isinstance(species_composition, bool):
            raise ProcessDatasetError("species_composition must be a boolean")
        if species_traits is not None and not isinstance(species_traits, Mapping):
            raise ProcessDatasetError("species_traits must be a mapping or None")
        biomass = _as_float(initial_biomass_t_ha, "initial_biomass_t_ha")
        fuel = _as_float(initial_fuel_t_ha, "initial_fuel_t_ha")
        if biomass_source not in _BIOMASS_SOURCES:
            raise ProcessDatasetError(
                f"biomass_source must be one of: {', '.join(sorted(_BIOMASS_SOURCES))}"
            )
        wood_density = _as_float(wood_density_t_m3, "wood_density_t_m3")
        expansion = _as_float(biomass_expansion, "biomass_expansion")
        if wood_density <= 0.0 or expansion <= 0.0:
            raise ProcessDatasetError("wood density and biomass expansion must be positive")
        if biomass_label is not None and (
            not isinstance(biomass_label, str) or not biomass_label.strip()
        ):
            raise ProcessDatasetError("biomass_label must be a non-empty string or None")

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
            ("track_id", "begin", "end", "treatment", "new_track"),
        )
        curve_ids, labels = _curve_ids(features, tracks, volume_label)
        try:
            track_curves = track_age_volume_curves_from_frame(curves, curve_ids)
        except BridgeError as error:
            raise ProcessDatasetError(str(error)) from error

        areas: dict[int, float] = {}
        valid: list[dict[str, int | float]] = []
        block_fragments: dict[int, list[int]] = {}
        for row in fragments.itertuples(index=False):
            fragment = _as_int(row.fragment_id, "fragment_id")
            block = _as_int(row.block_id, "block_id")
            area = _as_float(row.area_ha, "area_ha")
            if area <= 0.0:
                continue
            age = _as_int(row.age, "age")
            track = _as_int(row.track_id, "track_id")
            if fragment <= 0 or block <= 0:
                raise ProcessDatasetError("fragment_id and block_id must be positive")
            if age < 0:
                raise ProcessDatasetError("age must be non-negative")
            if fragment in areas:
                raise ProcessDatasetError(f"duplicate fragment_id {fragment}")
            areas[fragment] = area
            block_fragments.setdefault(block, []).append(fragment)
            valid.append(
                {
                    "fragment_id": fragment,
                    "block_id": block,
                    "area_ha": area,
                    "age": age,
                    "track_id": track,
                }
            )
        if not valid:
            raise ProcessDatasetError("the selected dataset has no positive-area fragments")
        fragment_frame = pd.DataFrame(valid)
        feature_curves = _biomass_feature_curves(features, curves, biomass_label)
        biomass_values = _biomass_values(
            fragment_frame,
            track_curves,
            feature_curves,
            source=biomass_source,
            fixed=biomass,
            wood_density=wood_density,
            expansion=expansion,
        )
        fallback = species.strip()
        fractions = (
            _species_fractions(fragment_frame, features, curves, default=fallback)
            if species_composition
            else {int(str(value)): {fallback: 1.0} for value in fragment_frame["fragment_id"]}
        )
        rows: list[dict[str, object]] = []
        for position, row in enumerate(fragment_frame.itertuples(index=False)):
            fragment = int(str(row.fragment_id))
            for cohort_id, (name, fraction) in enumerate(
                sorted(fractions[fragment].items()), start=1
            ):
                rows.append(
                    {
                        "fragment_id": fragment,
                        "cohort_id": cohort_id,
                        "species": name,
                        "age": int(str(row.age)),
                        "area_fraction": fraction,
                        "biomass_t_ha": float(biomass_values[position]),
                        "fuel_t_ha": fuel,
                        "snag_t_ha": 0.0,
                        "attributes_json": "{}",
                        "track_id": int(str(row.track_id)),
                    }
                )
        frame = pd.DataFrame(rows).astype(str)
        state = CohortState.from_tables(
            frame,
            StateSchema(variables={}, bridges=()),
            areas,
        )
        transitions: dict[tuple[int, str], int] = {}
        treatment_windows: dict[tuple[int, str], tuple[int, int]] = {}
        for row in treatments.itertuples(index=False):
            treatment = str(row.treatment).strip()
            if not treatment:
                raise ProcessDatasetError("treatment must be non-empty")
            track = _as_int(row.track_id, "track_id")
            transitions[(track, treatment)] = _as_int(row.new_track, "new_track")
            begin = _as_int(row.begin, "begin")
            end = _as_int(row.end, "end")
            if begin < 0 or end < begin:
                raise ProcessDatasetError("treatment age windows must satisfy 0 <= begin <= end")
            treatment_windows.setdefault((track, treatment), (begin, end))
        bridge = VolumeBridgeConfig(
            default_volume_m3_per_t=0.0,
            merchantable_fraction=1.0,
            track_age_volume_curves=track_curves,
        )
        landis_config = _landis_config(species_traits)
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
            treatment_windows=treatment_windows,
            volume_labels=labels,
            species=species.strip(),
            landis_config=landis_config,
            topology=topology_path,
            edges=edges,
        )

    def grammar(
        self,
        horizon_years: int,
        *,
        treatments: Sequence[str] | None = None,
        max_events_per_block: int = 1,
        allow_offset_moves: bool = False,
    ) -> ScheduleMoveGrammar:
        """Build a schedule grammar from the compiled treatment windows.

        Parameters
        ----------
        horizon_years : int
            Number of schedule offsets.
        treatments : sequence of str or None, optional
            Treatments to expose. None uses every compiled treatment.
        max_events_per_block : int, optional
            Maximum events per block (default one).
        allow_offset_moves : bool, optional
            Whether to move existing event offsets (default False).

        Returns
        -------
        ScheduleMoveGrammar
            Grammar restricted to blocks and offsets where every fragment in the block
            is inside its compiled treatment age window.

        Raises
        ------
        ProcessDatasetError
            If no block has an eligible treatment.
        """
        from ..opt.schedule_grammar import ScheduleMoveGrammar

        available = (
            sorted({treatment for _track, treatment in self.track_transitions})
            if treatments is None
            else sorted({str(treatment).strip() for treatment in treatments})
        )
        first = self.state.cohorts.groupby("fragment_id", sort=False).first()
        per_block: dict[int, dict[str, tuple[int, int]]] = {}
        for block, fragments in self.block_fragments.items():
            allowed: dict[str, tuple[int, int]] = {}
            for treatment in available:
                starts: list[int] = []
                ends: list[int] = []
                for fragment in fragments:
                    row = first.loc[fragment]
                    track = int(str(row["track_id"]))
                    age = int(str(row["age"]))
                    window = self.treatment_windows.get((track, treatment))
                    if window is None:
                        break
                    begin, end = window
                    start = max(0, begin - age)
                    stop = min(horizon_years, end - age + 1)
                    if start >= stop:
                        break
                    starts.append(start)
                    ends.append(stop)
                else:
                    start = max(starts)
                    stop = min(ends)
                    if start < stop:
                        allowed[treatment] = (start, stop)
            if allowed:
                per_block[block] = allowed
        if not per_block:
            raise ProcessDatasetError("no block has an eligible treatment in the horizon")
        grammar_treatments = sorted(
            {treatment for values in per_block.values() for treatment in values}
        )
        return ScheduleMoveGrammar(
            blocks=tuple(sorted(per_block)),
            treatments=grammar_treatments,
            horizon_years=horizon_years,
            max_events_per_block=max_events_per_block,
            allow_offset_moves=allow_offset_moves,
            treatment_windows=per_block,
        )

    def evaluate(
        self,
        schedule: Mapping[int, Sequence[tuple[str, int]]],
        *,
        horizon_years: int,
        fire: FireConfig | None = None,
        regeneration: RegenerationConfig | None = None,
        succession_process: Process | None = None,
        batch_succession: bool = True,
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
        batch_succession : bool, optional
            Use the vectorized landscape LANDIS process when no source is supplied
            (default True). Set False for one succession event per fragment.
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
            fire=fire or FireConfig(batch_fire=True),
            regeneration=regeneration or RegenerationConfig(batch=True),
            bridge=self.bridge,
            succession_process=succession_process
            or (
                LandisBatchSuccessionProcess(self.landis_config)
                if batch_succession
                else LandisSuccessionProcess(self.landis_config)
            ),
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
        batch_succession: bool = True,
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
        batch_succession : bool, optional
            Use the vectorized landscape LANDIS process when no source is supplied
            (default True).
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
            fire=fire or FireConfig(batch_fire=True),
            targets=targets,
            succession=succession,
            regeneration=regeneration or RegenerationConfig(batch=True),
            bridge=self.bridge,
            succession_process=succession_process
            or (
                LandisBatchSuccessionProcess(self.landis_config)
                if batch_succession
                else LandisSuccessionProcess(self.landis_config)
            ),
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
        batch_succession: bool = True,
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
        batch_succession : bool, optional
            Use the vectorized landscape LANDIS process when no source is supplied
            (default True).
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
            fire=fire or FireConfig(batch_fire=True),
            targets=targets,
            max_iterations=max_iterations,
            succession=succession,
            regeneration=regeneration or RegenerationConfig(batch=True),
            bridge=self.bridge,
            succession_process=succession_process
            or (
                LandisBatchSuccessionProcess(self.landis_config)
                if batch_succession
                else LandisSuccessionProcess(self.landis_config)
            ),
            harvest_fraction=harvest_fraction,
            track_transitions=self.track_transitions,
            seed=seed,
        )
