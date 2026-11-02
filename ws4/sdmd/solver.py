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
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .constraints import AuConstraint, check_regime
from .regimes import Regime

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
