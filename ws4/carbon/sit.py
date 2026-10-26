"""Compile CBM Standard Import Tool tables from a WS4 dataset and schedule.

The compiler reads the compiled dataset and a FEMIC carbon package. It does not run a
carbon engine. Its output is the SIT input that P51.3 will hand to libcbm, plus enough
metadata to audit the conversion.

The first version is intentionally narrow:

- events are annual and take their area from the dataset's fragments;
- retention splits are rejected rather than approximated;
- a treatment must be declared in the package's disturbance map;
- the package's yield table is authoritative, so the dataset's curves are not resampled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..model.schema import Problem
from ..schedule import schedule_offset_frame
from .package import CarbonPackage, TrackResolution, resolve_tracks

# SIT disturbance-event fields after the classifier columns. The CBM parser interprets
# these positionally; the labels match the CBM-CFS3 documentation.
_EVENT_FIELDS: tuple[str, ...] = (
    "using_age_class",
    "min_softwood_age",
    "max_softwood_age",
    "min_hardwood_age",
    "max_hardwood_age",
    "MinYearsSinceDist",
    "MaxYearsSinceDist",
    "LastDistTypeID",
    "MinTotBiomassC",
    "MaxTotBiomassC",
    "MinSWMerchBiomassC",
    "MaxSWMerchBiomassC",
    "MinHWMerchBiomassC",
    "MaxHWMerchBiomassC",
    "MinTotalStemSnagC",
    "MaxTotalStemSnagC",
    "MinSWStemSnagC",
    "MaxSWStemSnagC",
    "MinHWStemSnagC",
    "MaxHWStemSnagC",
    "MinTotalStemSnagMerchC",
    "MaxTotalStemSnagMerchC",
    "MinSWMerchStemSnagC",
    "MaxSWMerchStemSnagC",
    "MinHWMerchStemSnagC",
    "MaxHWMerchStemSnagC",
    "efficiency",
    "sort_type",
    "target_type",
    "target",
    "disturbance_type",
    "time_step",
)

_INVENTORY_FIELDS: tuple[str, ...] = (
    "using_age_class",
    "age",
    "area",
    "delay",
    "landclass",
    "historic_disturbance",
    "last_pass_disturbance",
)

_YIELD_FIELDS: tuple[str, ...] = ("leading_species",)


@dataclass(frozen=True)
class DisturbanceRule:
    """One validated disturbance mapping from the package.

    Attributes
    ----------
    user_dist_type : str
        The WS4-facing disturbance type.
    default_dist_type : str
        The CBM default disturbance type.
    removes_biomass : bool
        Whether the disturbance removes biomass.
    transition_reset_age : int
        Reset age applied by the transition rule.
    regen_delay : int
        Regeneration delay applied by the transition rule.
    """

    user_dist_type: str
    default_dist_type: str
    removes_biomass: bool
    transition_reset_age: int
    regen_delay: int


@dataclass(frozen=True)
class SitTables:
    """The SIT tables compiled from a package, dataset, and schedule.

    Attributes
    ----------
    classifiers : pandas.DataFrame
        SIT classifier table.
    disturbance_types : pandas.DataFrame
        SIT disturbance-type table.
    age_classes : pandas.DataFrame
        SIT age-class table.
    inventory : pandas.DataFrame
        SIT inventory table.
    yield_table : pandas.DataFrame
        SIT yield table.
    events : pandas.DataFrame
        SIT disturbance events.
    transitions : pandas.DataFrame
        SIT transition rules.
    track_resolution : TrackResolution
        The package-to-dataset track join.
    inventory_area_ha : float
        Total area in the SIT inventory.
    event_area_ha : float
        Total area targeted by events.
    """

    classifiers: pd.DataFrame
    disturbance_types: pd.DataFrame
    age_classes: pd.DataFrame
    inventory: pd.DataFrame
    yield_table: pd.DataFrame
    events: pd.DataFrame
    transitions: pd.DataFrame
    track_resolution: TrackResolution
    inventory_area_ha: float
    event_area_ha: float


class CarbonSitError(ValueError):
    """Raised when the package, dataset, and schedule cannot be compiled.

    Parameters
    ----------
    findings : sequence of Problem
        The conversion findings.
    """

    def __init__(self, findings: Sequence[Problem]) -> None:
        """Store the findings and build a readable message."""
        self.findings: tuple[Problem, ...] = tuple(findings)
        super().__init__(
            "; ".join(f"{item.code}: {item.message}" for item in self.findings)
            or "cannot compile carbon SIT tables"
        )


def write_sit_tables(tables: SitTables, output_dir: Path) -> dict[str, Path]:
    """Write the audit copy of the generated SIT tables.

    Parameters
    ----------
    tables : SitTables
        The compiled tables.
    output_dir : Path
        Directory to write into.

    Returns
    -------
    dict of str to Path
        File label to written path.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    frames = {
        "sit_classifiers": tables.classifiers,
        "sit_disturbance_types": tables.disturbance_types,
        "sit_age_classes": tables.age_classes,
        "sit_inventory": tables.inventory,
        "sit_yield": tables.yield_table,
        "sit_events": tables.events,
        "sit_transitions": tables.transitions,
    }
    paths: dict[str, Path] = {}
    for label, frame in frames.items():
        path = root / f"{label}.csv"
        frame.to_csv(path, index=False)
        paths[label] = path
    return paths


def read_schedule(path: Path) -> pd.DataFrame:
    """Read a schedule CSV and validate its ``offset`` clock.

    Parameters
    ----------
    path : Path
        A schedule CSV.

    Returns
    -------
    pandas.DataFrame
        The schedule with ``block_id``, ``treatment``, and ``offset``.

    Raises
    ------
    CarbonSitError
        When required columns are missing or the offset column is invalid.
    """
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError) as exc:
        raise CarbonSitError(
            [Problem("CARBON-SCHEDULE", str(path), f"cannot read schedule: {exc}")]
        ) from exc
    return _validate_schedule(frame)


def _validate_schedule(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the schedule columns and the offset clock."""
    missing = [column for column in ("block_id", "treatment", "offset") if column not in frame]
    if missing:
        raise CarbonSitError(
            [
                Problem(
                    "CARBON-SCHEDULE-COLUMN",
                    "schedule",
                    f"missing required columns: {missing}",
                )
            ]
        )
    try:
        result = schedule_offset_frame(frame)
    except ValueError as exc:
        raise CarbonSitError([Problem("CARBON-SCHEDULE-OFFSET", "schedule", str(exc))]) from exc
    result["block_id"] = pd.to_numeric(result["block_id"], errors="raise").astype(int)
    result["treatment"] = result["treatment"].astype(str)
    optional = [column for column in ("target_track", "target_area_ha") if column in result.columns]
    return result.loc[:, ["block_id", "treatment", "offset", *optional]].sort_values(
        ["offset", "block_id"], kind="stable"
    )


def build_sit_tables(
    package: CarbonPackage,
    dataset_dir: Path,
    schedule: pd.DataFrame,
    *,
    allow_unmatched: bool = False,
) -> SitTables:
    """Compile SIT tables from a package, a compiled dataset, and a schedule.

    Parameters
    ----------
    package : CarbonPackage
        The loaded and validated FEMIC package.
    dataset_dir : Path
        The compiled dataset directory.
    schedule : pandas.DataFrame
        The schedule with ``block_id``, ``treatment``, and ``offset``.
    allow_unmatched : bool, optional
        Pass through to :func:`resolve_tracks`. Defaults to False.

    Returns
    -------
    SitTables
        The compiled SIT tables and audit totals.

    Raises
    ------
    CarbonSitError
        When the package, dataset, or schedule cannot be compiled.
    """
    fragments, tracks, treatments = read_dataset_tables(dataset_dir)
    return build_sit_tables_from_tables(
        package,
        fragments,
        tracks,
        treatments,
        schedule,
        allow_unmatched=allow_unmatched,
    )


def read_dataset_tables(
    dataset_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the three dataset tables used by the SIT compiler.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset directory.

    Returns
    -------
    tuple of pandas.DataFrame
        The ``fragments``, ``tracks``, and ``treatments`` tables.

    Raises
    ------
    CarbonSitError
        When a required dataset table is missing.
    """
    root = Path(dataset_dir)
    findings: list[Problem] = []
    fragments = _read_table(root, "fragments", findings)
    tracks = _read_table(root, "tracks", findings)
    treatments = _read_table(root, "treatments", findings)
    if findings:
        raise CarbonSitError(findings)
    return fragments, tracks, treatments


def build_sit_tables_from_tables(
    package: CarbonPackage,
    fragments: pd.DataFrame,
    tracks: pd.DataFrame,
    treatments: pd.DataFrame,
    schedule: pd.DataFrame,
    *,
    allow_unmatched: bool = False,
) -> SitTables:
    """Compile SIT tables from in-memory dataset tables.

    This is the block-level entry point used by the carbon ledger. It takes the
    same package and schedule as :func:`build_sit_tables`, but the dataset tables
    are supplied directly so one block can be compiled without writing a dataset
    directory.

    Parameters
    ----------
    package : CarbonPackage
        The loaded and validated FEMIC package.
    fragments : pandas.DataFrame
        The ``fragments`` table.
    tracks : pandas.DataFrame
        The ``tracks`` table.
    treatments : pandas.DataFrame
        The ``treatments`` table.
    schedule : pandas.DataFrame
        The schedule with ``block_id``, ``treatment``, and ``offset``.
    allow_unmatched : bool, optional
        Pass through to :func:`resolve_tracks`. Defaults to False.

    Returns
    -------
    SitTables
        The compiled SIT tables and audit totals.

    Raises
    ------
    CarbonSitError
        When the package, tables, or schedule cannot be compiled.
    """
    findings: list[Problem] = []

    try:
        resolution = resolve_tracks(package, tracks, allow_unmatched=allow_unmatched)
    except Exception as exc:
        if hasattr(exc, "findings"):
            raise CarbonSitError(list(exc.findings)) from exc
        raise

    try:
        schedule_frame = _validate_schedule(schedule)
    except CarbonSitError as exc:
        raise exc

    classifier_names, classifier_rows = _build_classifiers(package, findings)
    if findings:
        raise CarbonSitError(findings)

    track_map = package.table("track_carbon_map").set_index("track_name", drop=False)
    disturbance_map = _disturbance_map(package)
    age_classes = package.table("age_classes").loc[:, ["name", "class_size"]].copy()
    age_width = _age_width(age_classes, findings)
    if age_width is None or findings:
        raise CarbonSitError(findings)

    classifier_by_track = _classifier_values_by_track(track_map, classifier_names, findings)
    inventory = _build_inventory(
        fragments=fragments,
        tracks=tracks,
        resolution=resolution,
        track_map=track_map,
        classifier_names=classifier_names,
        classifier_by_track=classifier_by_track,
        disturbance_map=disturbance_map,
        findings=findings,
    )
    yield_table = _build_yield(
        package=package,
        track_map=track_map,
        classifier_names=classifier_names,
        classifier_by_track=classifier_by_track,
        age_width=age_width,
        age_count=len(age_classes),
        findings=findings,
    )
    events = _build_events(
        schedule_frame=schedule_frame,
        fragments=fragments,
        tracks=tracks,
        resolution=resolution,
        classifier_names=classifier_names,
        classifier_by_track=classifier_by_track,
        disturbance_map=disturbance_map,
        findings=findings,
    )
    transitions = _build_transitions(
        treatments=treatments,
        tracks=tracks,
        track_map=track_map,
        classifier_names=classifier_names,
        classifier_by_track=classifier_by_track,
        disturbance_map=disturbance_map,
        findings=findings,
    )
    if findings:
        raise CarbonSitError(findings)

    classifiers = pd.DataFrame(classifier_rows, columns=["classifier_id", "name", "description"])
    disturbance_types = pd.DataFrame(
        {
            "id": [row.user_dist_type for row in disturbance_map.values()],
            "name": [row.user_dist_type for row in disturbance_map.values()],
        }
    )
    inventory_area = float(pd.to_numeric(inventory["area"], errors="coerce").sum())
    event_area = float(pd.to_numeric(events["target"], errors="coerce").sum())
    return SitTables(
        classifiers=classifiers,
        disturbance_types=disturbance_types,
        age_classes=age_classes,
        inventory=inventory,
        yield_table=yield_table,
        events=events,
        transitions=transitions,
        track_resolution=resolution,
        inventory_area_ha=inventory_area,
        event_area_ha=event_area,
    )


def _read_table(root: Path, name: str, findings: list[Problem]) -> pd.DataFrame:
    """Read one required dataset table, recording a finding on failure."""
    path = Path(root) / f"{name}.parquet"
    if not path.is_file():
        findings.append(
            Problem("CARBON-DATASET-TABLE", str(path), f"missing dataset table {name!r}")
        )
        return pd.DataFrame()
    return pd.read_parquet(path)


def _build_classifiers(
    package: CarbonPackage,
    findings: list[Problem],
) -> tuple[list[str], list[list[object]]]:
    """Build the SIT classifier table and the classifier order."""
    frame = package.table("classifiers")
    if not {"classifier_id", "classifier", "value"}.issubset(frame.columns):
        findings.append(
            Problem(
                "CARBON-CLASSIFIER",
                "classifiers",
                "classifier table is missing required columns",
            )
        )
        return [], []
    ids = sorted({int(value) for value in frame["classifier_id"].tolist()})
    names: list[str] = []
    rows: list[list[object]] = []
    for classifier_id in ids:
        block = frame.loc[frame["classifier_id"].astype(int) == classifier_id]
        classifier_names = sorted(set(block["classifier"].astype(str)))
        if len(classifier_names) != 1:
            findings.append(
                Problem(
                    "CARBON-CLASSIFIER",
                    "classifiers",
                    f"classifier_id {classifier_id} has multiple names",
                )
            )
            continue
        name = classifier_names[0]
        if name in names:
            findings.append(
                Problem(
                    "CARBON-CLASSIFIER",
                    "classifiers",
                    f"duplicate classifier name {name!r}",
                )
            )
            continue
        names.append(name)
        values = sorted(set(block["value"].astype(str)))
        rows.append([classifier_id, "_CLASSIFIER", name])
        for value in values:
            rows.append([classifier_id, value, value])
    return names, rows


def _age_width(age_classes: pd.DataFrame, findings: list[Problem]) -> int | None:
    """Return the constant age-class width."""
    sizes = pd.to_numeric(age_classes["class_size"], errors="coerce")
    if sizes.isna().any() or len(sizes) < 2:
        findings.append(Problem("CARBON-AGE-CLASS", "age_classes", "invalid age classes"))
        return None
    positive = sizes.iloc[1:].unique()
    if len(positive) != 1:
        findings.append(
            Problem(
                "CARBON-AGE-CLASS",
                "age_classes",
                "age-class width must be constant",
            )
        )
        return None
    return int(positive[0])


def _disturbance_map(package: CarbonPackage) -> dict[str, DisturbanceRule]:
    """Return the disturbance map keyed by normalized user type."""
    frame = package.table("disturbance_types")
    result: dict[str, DisturbanceRule] = {}
    for row in frame.itertuples(index=False):
        user_type = str(row.user_dist_type).strip()
        result[user_type.lower()] = DisturbanceRule(
            user_dist_type=user_type,
            default_dist_type=str(row.default_dist_type).strip(),
            removes_biomass=str(row.removes_biomass).strip().lower() in {"true", "1", "yes", "y"},
            transition_reset_age=int(float(str(row.transition_reset_age))),
            regen_delay=int(float(str(row.regen_delay))),
        )
    return result


def _classifier_values_by_track(
    track_map: pd.DataFrame,
    classifier_names: Sequence[str],
    findings: list[Problem],
) -> dict[str, list[str]]:
    """Return the classifier values for every package track."""
    result: dict[str, list[str]] = {}
    for row in track_map.itertuples(index=False):
        track_name = str(row.track_name)
        values = [part.strip() for part in str(row.classifier_set).split(";")]
        if len(values) != len(classifier_names):
            findings.append(
                Problem(
                    "CARBON-CLASSIFIER-SET",
                    "track_carbon_map.classifier_set",
                    f"{track_name!r} has {len(values)} values for "
                    f"{len(classifier_names)} classifiers",
                )
            )
        result[track_name] = values
    return result


def _build_inventory(
    *,
    fragments: pd.DataFrame,
    tracks: pd.DataFrame,
    resolution: TrackResolution,
    track_map: pd.DataFrame,
    classifier_names: Sequence[str],
    classifier_by_track: Mapping[str, Sequence[str]],
    disturbance_map: Mapping[str, DisturbanceRule],
    findings: list[Problem],
) -> pd.DataFrame:
    """Build the SIT inventory from the dataset fragments."""
    track_names = {int(str(row.track_id)): str(row.name) for row in tracks.itertuples(index=False)}
    rows: list[dict[str, object]] = []
    for fragment in fragments.itertuples(index=False):
        track_id = int(str(fragment.track_id))
        track_name = track_names.get(track_id)
        if track_name is None:
            findings.append(
                Problem(
                    "CARBON-UNKNOWN-TRACK",
                    "fragments.track_id",
                    f"fragment {int(str(fragment.fragment_id))} uses unknown track {track_id}",
                )
            )
            continue
        if track_name not in resolution.mapping:
            findings.append(
                Problem(
                    "CARBON-UNMATCHED-TRACK",
                    "fragments.track_id",
                    f"{track_name!r} is not in the carbon package",
                )
            )
            continue
        values = list(classifier_by_track.get(track_name, []))
        track_row = track_map.loc[track_name]
        landclass = int(str(track_row.loc["landclass"]))
        last_disturbance = _user_disturbance(
            str(track_row.loc["last_disturbance"]), disturbance_map
        )
        historic = _user_disturbance("fire", disturbance_map)
        row: dict[str, object] = dict(zip(classifier_names, values, strict=True))
        row.update(
            {
                "using_age_class": "FALSE",
                "age": int(str(fragment.age)),
                "area": float(str(fragment.area_ha)),
                "delay": 0,
                "landclass": landclass,
                "historic_disturbance": historic,
                "last_pass_disturbance": last_disturbance,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=[*classifier_names, *_INVENTORY_FIELDS])


def _build_yield(
    *,
    package: CarbonPackage,
    track_map: pd.DataFrame,
    classifier_names: Sequence[str],
    classifier_by_track: Mapping[str, Sequence[str]],
    age_width: int,
    age_count: int,
    findings: list[Problem],
) -> pd.DataFrame:
    """Pivot the package's long yield table into the SIT wide table."""
    frame = package.table("yield")
    rows: list[dict[str, object]] = []
    for (track_name, _species), block in frame.groupby(["track_name", "species"], sort=True):
        track_name = str(track_name)
        if track_name not in classifier_by_track:
            findings.append(
                Problem(
                    "CARBON-UNKNOWN-TRACK",
                    "yield.track_name",
                    f"{track_name!r} is not in the track map",
                )
            )
            continue
        values = list(classifier_by_track[track_name])
        row: dict[str, object] = dict(zip(classifier_names, values, strict=True))
        row["leading_species"] = str(block["leading_species"].iloc[0])
        for index in range(age_count):
            row[f"v{index}"] = 0.0
        for point in block.itertuples(index=False):
            age = int(str(point.age))
            if age % age_width != 0:
                findings.append(
                    Problem(
                        "CARBON-YIELD-GRID",
                        "yield.age",
                        f"{track_name!r} has age {age}, not on the {age_width}-year grid",
                    )
                )
                continue
            index = age // age_width
            if index >= age_count:
                findings.append(
                    Problem(
                        "CARBON-YIELD-GRID",
                        "yield.age",
                        f"{track_name!r} has age {age} beyond the age classes",
                    )
                )
                continue
            row[f"v{index}"] = float(str(point.volume_m3_ha))
        rows.append(row)
    return pd.DataFrame(
        rows, columns=[*classifier_names, *_YIELD_FIELDS, *[f"v{i}" for i in range(age_count)]]
    )


def _build_events(
    *,
    schedule_frame: pd.DataFrame,
    fragments: pd.DataFrame,
    tracks: pd.DataFrame,
    resolution: TrackResolution,
    classifier_names: Sequence[str],
    classifier_by_track: Mapping[str, Sequence[str]],
    disturbance_map: Mapping[str, DisturbanceRule],
    findings: list[Problem],
) -> pd.DataFrame:
    """Build SIT disturbance events from the schedule."""
    track_names = {int(str(row.track_id)): str(row.name) for row in tracks.itertuples(index=False)}
    block_fragments = {
        int(str(block)): block_frame
        for block, block_frame in fragments.groupby("block_id", sort=False)
    }
    rows: list[dict[str, object]] = []
    for event in schedule_frame.itertuples(index=False):
        block_id = int(str(event.block_id))
        treatment = str(event.treatment)
        offset = int(str(event.offset))
        block_frame = block_fragments.get(block_id)
        if block_frame is None:
            findings.append(
                Problem(
                    "CARBON-UNKNOWN-BLOCK",
                    "schedule.block_id",
                    f"block {block_id} is not in the dataset",
                )
            )
            continue
        disturbance = disturbance_map.get(treatment.strip().lower())
        if disturbance is None:
            findings.append(
                Problem(
                    "CARBON-UNKNOWN-DISTURBANCE",
                    "schedule.treatment",
                    f"treatment {treatment!r} is not in the package disturbance map",
                )
            )
            continue
        grouped: dict[tuple[str, ...], float] = {}
        target_track = getattr(event, "target_track", None)
        if isinstance(target_track, str) and target_track.strip():
            target_name = target_track.strip()
            if target_name not in classifier_by_track:
                findings.append(
                    Problem(
                        "CARBON-UNMATCHED-TRACK",
                        "schedule.target_track",
                        f"recovery event targets {target_name!r}, which is not in the package",
                    )
                )
                continue
            target_area = getattr(event, "target_area_ha", None)
            if target_area is None or pd.isna(target_area):
                area = float(pd.to_numeric(block_frame["area_ha"], errors="coerce").sum())
            else:
                area = float(str(target_area))
            grouped[tuple(classifier_by_track[target_name])] = area
        else:
            for fragment in block_frame.itertuples(index=False):
                track_name = track_names.get(int(str(fragment.track_id)))
                if track_name is None or track_name not in resolution.mapping:
                    findings.append(
                        Problem(
                            "CARBON-UNMATCHED-TRACK",
                            "fragments.track_id",
                            f"block {block_id} has a track absent from the package",
                        )
                    )
                    continue
                values = tuple(classifier_by_track.get(track_name, []))
                grouped[values] = grouped.get(values, 0.0) + float(str(fragment.area_ha))
        for values, area in grouped.items():
            row: dict[str, object] = dict(zip(classifier_names, values, strict=True))
            row.update(dict.fromkeys(_EVENT_FIELDS, -1))
            row.update(
                {
                    "using_age_class": "FALSE",
                    "efficiency": 1.0,
                    "sort_type": 3,
                    "target_type": "A",
                    "target": area,
                    "disturbance_type": str(disturbance.user_dist_type),
                    "time_step": offset + 1,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows, columns=[*classifier_names, *_EVENT_FIELDS])


def _build_transitions(
    *,
    treatments: pd.DataFrame,
    tracks: pd.DataFrame,
    track_map: pd.DataFrame,
    classifier_names: Sequence[str],
    classifier_by_track: Mapping[str, Sequence[str]],
    disturbance_map: Mapping[str, DisturbanceRule],
    findings: list[Problem],
) -> pd.DataFrame:
    """Build SIT transition rules from the dataset's treatments."""
    track_names = {int(str(row.track_id)): str(row.name) for row in tracks.itertuples(index=False)}
    key_columns = ["track_id", "treatment", "new_track", "retain"]
    unique = treatments.loc[:, [column for column in key_columns if column in treatments]]
    unique = unique.drop_duplicates()
    rows: list[dict[str, object]] = []
    for treatment in unique.itertuples(index=False):
        source_name = track_names.get(int(str(treatment.track_id)))
        if source_name is None or source_name not in track_map.index:
            findings.append(
                Problem(
                    "CARBON-UNKNOWN-TRACK",
                    "treatments.track_id",
                    f"treatment {treatment.treatment!r} has an unknown source track",
                )
            )
            continue
        new_track = int(str(getattr(treatment, "new_track", 0) or 0))
        destination_name = track_names.get(new_track, source_name)
        if destination_name not in track_map.index:
            findings.append(
                Problem(
                    "CARBON-UNKNOWN-TRACK",
                    "treatments.new_track",
                    f"treatment {treatment.treatment!r} targets {destination_name!r}, "
                    "which is not in the package",
                )
            )
            continue
        if int(str(getattr(treatment, "retain", 0) or 0)) != 0:
            findings.append(
                Problem(
                    "CARBON-RETENTION-UNSUPPORTED",
                    "treatments.retain",
                    f"treatment {treatment.treatment!r} uses retention; the first SIT "
                    "compiler does not approximate it",
                )
            )
            continue
        disturbance = disturbance_map.get(str(treatment.treatment).strip().lower())
        if disturbance is None:
            findings.append(
                Problem(
                    "CARBON-UNKNOWN-DISTURBANCE",
                    "treatments.treatment",
                    f"treatment {treatment.treatment!r} is not in the disturbance map",
                )
            )
            continue
        source_values = list(classifier_by_track[source_name])
        destination_values = list(classifier_by_track[destination_name])
        row: dict[str, object] = dict(zip(classifier_names, source_values, strict=True))
        row.update(dict.fromkeys(_EVENT_FIELDS[:5], -1))
        row.update(
            {
                "using_age_class": "FALSE",
                "disturbance_type": str(disturbance.user_dist_type),
            }
        )
        for name, value in zip(classifier_names, destination_values, strict=True):
            row[f"{name}_tr"] = value
        row["regeneration_delay"] = int(str(disturbance.regen_delay))
        row["reset_age"] = int(str(disturbance.transition_reset_age))
        row["percent"] = 100.0
        rows.append(row)
    columns = [
        *classifier_names,
        "using_age_class",
        "min_softwood_age",
        "max_softwood_age",
        "min_hardwood_age",
        "max_hardwood_age",
        "disturbance_type",
        *[f"{name}_tr" for name in classifier_names],
        "regeneration_delay",
        "reset_age",
        "percent",
    ]
    return pd.DataFrame(rows, columns=columns)


def _user_disturbance(
    value: str,
    disturbance_map: Mapping[str, DisturbanceRule],
) -> str:
    """Return a user disturbance type for an inventory disturbance value."""
    normalized = value.strip().lower()
    direct = disturbance_map.get(normalized)
    if direct is not None:
        return str(direct.user_dist_type)
    for row in disturbance_map.values():
        if str(row.default_dist_type).strip().lower() == normalized:
            return str(row.user_dist_type)
    return value
