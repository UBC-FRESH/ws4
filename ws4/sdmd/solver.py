"""Filter a compiled dataset with AU regime constraints.

The optimizer reads the compiled matrix, so the smallest safe integration is to remove
the treatment rows a constraint forbids before the optimizer builds its candidate
chains. This module writes a filtered copy of a dataset: every other table is copied
unchanged and ``treatments.parquet`` keeps only the allowed rows.

The AU is read from the compiled track name (``AU(...)``) or a sidecar map. The
treatment label is matched to a regime by id, name, entry type, or a sidecar alias.
Unmapped tracks are kept by default so a dataset without SDMD metadata still runs;
``strict=True`` drops them.

This filter enforces the per-track entry window, entry cap, minimum interval, and
removal fraction. A cap across blocks in one AU needs AU state in the search and is
not enforced by this option-space filter; the report states that limit.
"""

from __future__ import annotations

import itertools
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .constraints import AuConstraint, check_regime
from .diagram import SdmdDiagram, SdmdDiagramError, place_point
from .regimes import Regime
from .schema import Problem

TRACK_AU_RE = re.compile(r"AU\(([^)]+)\)")
TREATMENT_ALIASES: dict[str, str] = {
    "cc": "clearcut",
    "clearcut": "clearcut",
    "ct": "ct60",
    "ct60": "ct60",
    "f50": "fuel50",
    "fuel50": "fuel50",
    "sel80": "selection80",
    "selection80": "selection80",
    "sw40": "shelterwood40",
    "shelterwood40": "shelterwood40",
    "vr": "vr20",
    "vr20": "vr20",
    "none": "untreated",
    "untreated": "untreated",
}


class SdmdSolverError(ValueError):
    """Raised when a dataset cannot be filtered."""


@dataclass(frozen=True)
class SdmdSolverMap:
    """Sidecar overrides for AU and treatment matching.

    Attributes
    ----------
    tracks : dict of int to str
        Track id to AU id. Overrides the ``AU(...)`` field in the track name.
    treatments : dict of str to str
        Treatment label to regime id, name, or entry type. Overrides the built-in
        aliases.
    """

    tracks: dict[int, str] = field(default_factory=dict)
    treatments: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SdmdFilterReport:
    """The option-space reduction from one filter run.

    Attributes
    ----------
    tracks_before : int
        Distinct source tracks with at least one treatment.
    tracks_after : int
        Distinct source tracks with at least one allowed treatment.
    treatments_before : int
        Treatment rows before filtering.
    treatments_after : int
        Treatment rows after filtering.
    unmapped_tracks : int
        Tracks with no AU or no matching regime.
    unmapped_treatments : int
        Treatment rows with no matching regime.
    dropped : tuple of dict
        One record per dropped track, with the AU, regime, and reasons.
    """

    tracks_before: int
    tracks_after: int
    treatments_before: int
    treatments_after: int
    unmapped_tracks: int
    unmapped_treatments: int
    dropped: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        """Return the report as a JSON-serializable mapping.

        Returns
        -------
        dict
            The counts and dropped records.
        """
        return {
            "tracks_before": self.tracks_before,
            "tracks_after": self.tracks_after,
            "treatments_before": self.treatments_before,
            "treatments_after": self.treatments_after,
            "unmapped_tracks": self.unmapped_tracks,
            "unmapped_treatments": self.unmapped_treatments,
            "dropped": list(self.dropped),
        }


def load_solver_map(path: str | Path) -> SdmdSolverMap:
    """Load a YAML or JSON sidecar map.

    Parameters
    ----------
    path : str or Path
        The file. It has optional ``tracks`` and ``treatments`` mappings.

    Returns
    -------
    SdmdSolverMap
        The parsed map.

    Raises
    ------
    SdmdSolverError
        If the file is missing or its shape is wrong.
    """
    source = Path(path)
    if not source.is_file():
        raise SdmdSolverError(f"map not found: {source}")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if raw is None:
        return SdmdSolverMap()
    if not isinstance(raw, Mapping):
        raise SdmdSolverError("map must be a mapping with tracks and treatments")
    tracks_raw = raw.get("tracks", {})
    treatments_raw = raw.get("treatments", {})
    if not isinstance(tracks_raw, Mapping) or not isinstance(treatments_raw, Mapping):
        raise SdmdSolverError("map tracks and treatments must be mappings")
    tracks = {int(str(key)): str(value) for key, value in tracks_raw.items()}
    treatments = {str(key): str(value) for key, value in treatments_raw.items()}
    return SdmdSolverMap(tracks=tracks, treatments=treatments)


def filter_dataset(
    dataset_dir: str | Path,
    output_dir: str | Path,
    regimes: Sequence[Regime],
    constraints: Sequence[AuConstraint],
    *,
    mapping: SdmdSolverMap | None = None,
    strict: bool = False,
    diagram: SdmdDiagram | None = None,
    trajectory_dir: str | Path | None = None,
) -> SdmdFilterReport:
    """Write a dataset copy whose treatments obey the AU constraints.

    Parameters
    ----------
    dataset_dir : str or Path
        The compiled dataset to read.
    output_dir : str or Path
        The directory to write. It must differ from ``dataset_dir``.
    regimes : sequence of Regime
        The regime library.
    constraints : sequence of AuConstraint
        The AU constraints.
    mapping : SdmdSolverMap, optional
        Track and treatment overrides.
    strict : bool
        Drop a track or treatment that cannot be mapped. Defaults to ``False``, which
        keeps unmapped rows so a dataset without SDMD metadata still runs.
    diagram : SdmdDiagram, optional
        The diagram for the required-zone check. The check runs only when a diagram
        and a trajectory directory are supplied.
    trajectory_dir : str or Path, optional
        The directory holding ``<au_id>/<regime_id>.json`` trajectories.

    Returns
    -------
    SdmdFilterReport
        The counts and dropped records.

    Raises
    ------
    SdmdSolverError
        If the dataset tables are missing, the output would overwrite the input, or
        the treatment table has no usable columns.
    """
    source = Path(dataset_dir)
    target = Path(output_dir)
    if source.resolve() == target.resolve():
        raise SdmdSolverError("output_dir must differ from dataset_dir")
    treatments_path = source / "treatments.parquet"
    tracks_path = source / "tracks.parquet"
    if not treatments_path.is_file() or not tracks_path.is_file():
        raise SdmdSolverError("dataset needs tracks.parquet and treatments.parquet")
    tracks = pd.read_parquet(tracks_path)
    treatments = pd.read_parquet(treatments_path)
    for column in ("track_id", "begin", "treatment", "retain"):
        if column not in treatments.columns:
            raise SdmdSolverError(f"treatments table has no {column} column")
    if "name" not in tracks.columns or "track_id" not in tracks.columns:
        raise SdmdSolverError("tracks table needs track_id and name")
    names = {int(str(row.track_id)): str(row.name) for row in tracks.itertuples(index=False)}
    constraint_by_key = {(item.au_id, item.regime_id): item for item in constraints}
    mapping = mapping or SdmdSolverMap()
    kept: list[int] = []
    dropped: list[dict[str, object]] = []
    unmapped_tracks = 0
    unmapped_treatments = 0
    for track_id, group in treatments.groupby("track_id", sort=True):
        track = int(str(track_id))
        au_id = _track_au(track, names.get(track, ""), mapping)
        if not au_id or not any(item.au_id == au_id for item in constraints):
            unmapped_tracks += 1
            if strict:
                dropped.append(_dropped(track, au_id, None, ["track has no AU constraint"]))
                continue
            kept.extend(group.index.tolist())
            continue
        entries: dict[str, tuple[Regime, AuConstraint, list[int]]] = {}
        reasons: list[str] = []
        for row in group.itertuples(index=False):
            label = str(row.treatment)
            regime = _match_regime(label, regimes, mapping, au_id)
            if regime is None:
                unmapped_treatments += 1
                if strict:
                    reasons.append(f"treatment {label} has no regime")
                continue
            constraint = constraint_by_key.get((au_id, regime.regime_id))
            if constraint is None:
                reasons.append(f"no constraint for {au_id}/{regime.regime_id}")
                continue
            findings = check_regime(constraint, regime)
            if findings:
                reasons.extend(f"{item.code}: {item.message}" for item in findings)
                continue
            if constraint.required_sdmd_zone is not None and (
                diagram is not None or trajectory_dir is not None
            ):
                if diagram is None or trajectory_dir is None:
                    reasons.append("zone rule needs a diagram and a trajectory directory")
                    continue
                path = Path(trajectory_dir) / au_id / f"{regime.regime_id}.json"
                if not path.is_file():
                    reasons.append(f"no trajectory for {regime.regime_id}")
                    continue
                try:
                    zones = trajectory_zones(diagram, load_trajectory_points(path))
                except (SdmdDiagramError, ValueError) as error:
                    reasons.append(f"trajectory {regime.regime_id}: {error}")
                    continue
                if constraint.required_sdmd_zone not in zones:
                    reasons.append(
                        f"trajectory {regime.regime_id} never reaches "
                        f"{constraint.required_sdmd_zone}"
                    )
                    continue
            begin = int(str(row.begin))
            if not constraint.min_entry_age <= begin <= constraint.max_entry_age:
                reasons.append(
                    f"{label} begins at {begin}, outside "
                    f"[{constraint.min_entry_age}, {constraint.max_entry_age}]"
                )
            retain = float(str(row.retain))
            removal = 0.0 if retain >= 100.0 else 1.0 - retain / 100.0
            if removal > constraint.max_removal_fraction + 1e-9:
                reasons.append(
                    f"{label} removes {removal:g}, above {constraint.max_removal_fraction:g}"
                )
            entries.setdefault(label, (regime, constraint, []))[2].append(begin)
        if reasons:
            dropped.append(_dropped(track, au_id, None, reasons))
            continue
        ordered = sorted(
            (min(begins), label, regime, constraint)
            for label, (regime, constraint, begins) in entries.items()
        )
        if ordered:
            maximum = min(constraint.max_entries for _, _, _, constraint in ordered)
            if len(ordered) > maximum:
                dropped.append(
                    _dropped(
                        track,
                        au_id,
                        ordered[0][2].regime_id,
                        [f"{len(ordered)} entries exceed {maximum}"],
                    )
                )
                continue
            interval = max(constraint.min_interval_years for _, _, _, constraint in ordered)
            if any(
                later[0] - earlier[0] < interval for earlier, later in itertools.pairwise(ordered)
            ):
                dropped.append(
                    _dropped(
                        track,
                        au_id,
                        ordered[0][2].regime_id,
                        [f"entry interval is below {interval} years"],
                    )
                )
                continue
        kept.extend(group.index.tolist())
    filtered = treatments.loc[sorted(set(kept))].reset_index(drop=True)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    filtered.to_parquet(target / "treatments.parquet", index=False)
    return SdmdFilterReport(
        tracks_before=int(treatments["track_id"].nunique()),
        tracks_after=int(filtered["track_id"].nunique()) if not filtered.empty else 0,
        treatments_before=len(treatments),
        treatments_after=len(filtered),
        unmapped_tracks=unmapped_tracks,
        unmapped_treatments=unmapped_treatments,
        dropped=tuple(dropped),
    )


class SdmdScheduleGuard:
    """Check a schedule's per-AU entry cap and interval.

    The guard reads the compiled fragments, tracks, and treatments, maps each block to
    its AU, and counts the selected entries per AU. It is a schedule guard: call
    :meth:`check` before accepting a move, or use :meth:`feasible` as a predicate.

    Parameters
    ----------
    fragments : pandas.DataFrame
        The compiled ``fragments`` table.
    tracks : pandas.DataFrame
        The compiled ``tracks`` table.
    treatments : pandas.DataFrame
        The compiled ``treatments`` table.
    regimes : sequence of Regime
        The regime library.
    constraints : sequence of AuConstraint
        The AU constraints.
    mapping : SdmdSolverMap, optional
        Track and treatment overrides.
    """

    def __init__(
        self,
        fragments: pd.DataFrame,
        tracks: pd.DataFrame,
        treatments: pd.DataFrame,
        regimes: Sequence[Regime],
        constraints: Sequence[AuConstraint],
        *,
        mapping: SdmdSolverMap | None = None,
    ) -> None:
        """Build the block-to-track and regime indexes."""
        if "area_ha" in fragments.columns:
            chosen = fragments.loc[fragments.groupby("block_id")["area_ha"].idxmax()]
        else:
            chosen = fragments.drop_duplicates("block_id")
        self._block_track = {
            int(str(row.block_id)): int(str(row.track_id)) for row in chosen.itertuples(index=False)
        }
        self._names = {
            int(str(row.track_id)): str(row.name) for row in tracks.itertuples(index=False)
        }
        self._regimes = tuple(regimes)
        self._constraints = {(item.au_id, item.regime_id): item for item in constraints}
        self._mapping = mapping or SdmdSolverMap()

    def check(self, schedule: Mapping[int, Sequence[tuple[str, int]]]) -> list[Problem]:
        """Check a schedule for AU entry caps and intervals.

        Parameters
        ----------
        schedule : mapping of int to sequence of (str, int)
            Block id to its ordered ``(treatment, year)`` entries.

        Returns
        -------
        list of Problem
            One finding per violated AU, or an empty list.
        """
        entries: dict[str, list[tuple[int, AuConstraint]]] = {}
        for block, chain in schedule.items():
            track = self._block_track.get(int(block))
            if track is None:
                continue
            au_id = _track_au(track, self._names.get(track, ""), self._mapping)
            if not au_id:
                continue
            for label, year in chain:
                regime = _match_regime(label, self._regimes, self._mapping, au_id)
                if regime is None:
                    continue
                constraint = self._constraints.get((au_id, regime.regime_id))
                if constraint is None:
                    continue
                entries.setdefault(au_id, []).append((int(year), constraint))
        problems: list[Problem] = []
        for au_id, selected in entries.items():
            cap = min(constraint.max_entries for _, constraint in selected)
            interval = max(constraint.min_interval_years for _, constraint in selected)
            years = sorted(year for year, _ in selected)
            if len(years) > cap:
                problems.append(
                    Problem(
                        "SDMD-SCHEDULE-ENTRIES",
                        au_id,
                        f"{len(years)} entries exceed the AU cap of {cap}",
                    )
                )
            if any(later - earlier < interval for earlier, later in itertools.pairwise(years)):
                problems.append(
                    Problem(
                        "SDMD-SCHEDULE-INTERVAL",
                        au_id,
                        f"entries are closer than {interval} years",
                    )
                )
        return problems

    def feasible(self, schedule: Mapping[int, Sequence[tuple[str, int]]]) -> bool:
        """Return whether a schedule satisfies the AU guard.

        Parameters
        ----------
        schedule : mapping of int to sequence of (str, int)
            Block id to its ordered entries.

        Returns
        -------
        bool
            ``True`` when :meth:`check` finds nothing.
        """
        return not self.check(schedule)


def load_trajectory_points(path: str | Path) -> tuple[tuple[float, float], ...]:
    """Load a trajectory's points from JSON.

    Parameters
    ----------
    path : str or Path
        A trajectory file with a ``points`` list.

    Returns
    -------
    tuple of tuple of float
        The ``(tph, mean_tree_volume_m3)`` points.

    Raises
    ------
    ValueError
        If the file has no usable points list.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("points"), list):
        raise ValueError(f"{path} needs a points list")
    points = tuple(
        (float(str(point[0])), float(str(point[1])))
        for point in raw["points"]
        if isinstance(point, list) and len(point) == 2
    )
    if not points:
        raise ValueError(f"{path} has no points")
    return points


def trajectory_zones(
    diagram: SdmdDiagram,
    points: Sequence[tuple[float, float]],
) -> set[str]:
    """Return the SDMD zones a trajectory passes through.

    Parameters
    ----------
    diagram : SdmdDiagram
        The diagram.
    points : sequence of tuple of float
        The trajectory points.

    Returns
    -------
    set of str
        The distinct zones.
    """
    return {place_point(diagram, tph, volume).zone for tph, volume in points}


def trajectory_reaches_zone(
    diagram: SdmdDiagram,
    points: Sequence[tuple[float, float]],
    zone: str,
) -> bool:
    """Return whether a trajectory reaches an SDMD zone.

    Parameters
    ----------
    diagram : SdmdDiagram
        The diagram.
    points : sequence of tuple of float
        The trajectory points.
    zone : str
        The required zone.

    Returns
    -------
    bool
        ``True`` when at least one point is in the zone.
    """
    return zone in trajectory_zones(diagram, points)


def _track_au(track: int, name: str, mapping: SdmdSolverMap) -> str | None:
    """Return a track's AU from the map or the track name."""
    if track in mapping.tracks:
        return mapping.tracks[track]
    match = TRACK_AU_RE.search(name)
    return match.group(1).strip() if match else None


def _match_regime(
    label: str,
    regimes: Sequence[Regime],
    mapping: SdmdSolverMap,
    au_id: str,
) -> Regime | None:
    """Match a treatment label to an AU's regime by id, name, entry type, or alias."""
    target = mapping.treatments.get(label, label)
    normalized = _normalize(target)
    matches = [
        regime
        for regime in regimes
        if normalized
        in {
            _normalize(regime.regime_id),
            _normalize(regime.name),
            _normalize(regime.entry_type),
        }
    ]
    if not matches:
        alias = TREATMENT_ALIASES.get(normalized)
        if alias:
            matches = [regime for regime in regimes if _normalize(regime.entry_type) == alias]
    for regime in matches:
        if regime.au_id == au_id:
            return regime
    return matches[0] if matches else None


def _normalize(value: str) -> str:
    """Normalize a label for matching."""
    return "".join(character for character in value.lower() if character.isalnum())


def _dropped(
    track: int,
    au_id: str | None,
    regime_id: str | None,
    reasons: Sequence[str],
) -> dict[str, object]:
    """Build one dropped-track record."""
    return {
        "track_id": track,
        "au_id": au_id,
        "regime_id": regime_id,
        "reasons": list(reasons),
    }
