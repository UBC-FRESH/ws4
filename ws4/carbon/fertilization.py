"""Fertilization growth response and emissions for carbon runs.

The growth response is applied as a temporary CBM growth multiplier after an
``f1``, ``f2``, or ``f3`` schedule event. The multiplier and the response window
come from the public TIPSY materialization in FEMIC; the emissions factors are
the public thesis factors already used by the FEMIC audit.

This module does not alter the carbon package on disk. It returns a package copy
with the three fertilizer disturbance types added to the in-memory table, so a
normal package can be used with a fertilization schedule without a rebuild.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ..model.schema import Problem
from .package import CarbonPackage

FERTILIZATION_TREATMENTS: tuple[str, ...] = ("f1", "f2", "f3")
_N2O_KEYS: dict[str, str] = {
    "f1": "n2o_once",
    "f2": "n2o_twice",
    "f3": "n2o_thrice",
}


@dataclass(frozen=True)
class FertilizationApplication:
    """One materialized fertilized-curve transition.

    Attributes
    ----------
    treatment : str
        The schedule treatment (``f1``, ``f2``, or ``f3``).
    source_track : str
        The package/dataset track the transition starts from.
    curve : Path
        The materialized curve CSV from ``femic carbon fertilization-curve``.
    target_track : str
        The new track that receives the fertilized curve.
    """

    treatment: str
    source_track: str
    curve: Path
    target_track: str


class FertilizationConfigError(ValueError):
    """Raised when a fertilization configuration is invalid."""

    def __init__(self, findings: Sequence[Problem]) -> None:
        """Store the findings and build a readable message."""
        self.findings: tuple[Problem, ...] = tuple(findings)
        super().__init__(
            "; ".join(f"{item.code}: {item.message}" for item in self.findings)
            or "invalid fertilization configuration"
        )


@dataclass(frozen=True)
class FertilizationConfig:
    """Fertilization growth and emissions assumptions.

    Attributes
    ----------
    dose_kg_n_ha : float
        Nitrogen dose applied per hectare.
    response_years : int
        Number of years the growth multiplier remains active.
    growth_multiplier : float
        Multiplier applied to CBM's annual growth while the response is active.
    co2_kg_ha : float
        Embodied CO2 emissions per hectare.
    ch4_kg_ha : float
        Embodied CH4 emissions per hectare.
    n2o_kg_ha : mapping of str to float
        N2O emissions per hectare for ``f1``, ``f2``, and ``f3``.
    gwp_ch4 : float
        CH4 GWP100.
    gwp_n2o : float
        N2O GWP100.
    source : mapping of str to object
        Optional provenance copied into the run manifest.
    path : Path or None
        The configuration file, when loaded from disk.
    applications : tuple of FertilizationApplication
        Materialized curve applications. When non-empty, they take precedence
        over the temporary growth multiplier.
    """

    dose_kg_n_ha: float
    response_years: int
    growth_multiplier: float
    co2_kg_ha: float
    ch4_kg_ha: float
    n2o_kg_ha: Mapping[str, float]
    gwp_ch4: float
    gwp_n2o: float
    source: Mapping[str, Any]
    path: Path | None = None
    applications: tuple[FertilizationApplication, ...] = ()

    @property
    def uses_curves(self) -> bool:
        """Return whether the configuration has materialized curve applications."""
        return bool(self.applications)

    def disturbance_rows(self, *, transition_reset_age: int = 0) -> list[dict[str, object]]:
        """Return SIT disturbance rows for the three fertilizer treatments.

        Parameters
        ----------
        transition_reset_age : int, optional
            The reset age for a fertilizer transition. The curve path uses ``-1``
            so the stand age is preserved; the multiplier path uses ``0`` because
            it has no transition rule.

        Returns
        -------
        list of dict
            Rows with the package disturbance-type columns.
        """
        return [
            {
                "user_dist_type": treatment,
                "default_dist_type": "Natural succession",
                "removes_biomass": "false",
                "transition_reset_age": transition_reset_age,
                "regen_delay": 0,
            }
            for treatment in FERTILIZATION_TREATMENTS
        ]

    def manifest(self) -> dict[str, object]:
        """Return the configuration record written into a carbon manifest."""
        return {
            "schema_version": "0.1",
            "config": str(self.path) if self.path is not None else None,
            "dose_kg_n_ha": self.dose_kg_n_ha,
            "response_years": self.response_years,
            "growth_multiplier": self.growth_multiplier,
            "mode": "curve" if self.uses_curves else "multiplier",
            "factors_kg_ha": {
                "co2": self.co2_kg_ha,
                "ch4": self.ch4_kg_ha,
                **{key: self.n2o_kg_ha[treatment] for treatment, key in _N2O_KEYS.items()},
            },
            "gwp100": {"ch4": self.gwp_ch4, "n2o": self.gwp_n2o},
            "applications": [
                {
                    "treatment": application.treatment,
                    "source_track": application.source_track,
                    "target_track": application.target_track,
                    "curve": str(application.curve),
                }
                for application in self.applications
            ],
            "source": dict(self.source),
        }


def load_fertilization_config(path: Path) -> FertilizationConfig:
    """Load a fertilization configuration from YAML.

    The loader accepts the FEMIC ``fertilization.bc.yaml`` file directly. If the
    file has no ``growth_multiplier``, the public default of ``1.10`` is used;
    the materialized TIPSY curve can be used to justify a different value.

    Parameters
    ----------
    path : Path
        YAML configuration.

    Returns
    -------
    FertilizationConfig
        The validated configuration.

    Raises
    ------
    FertilizationConfigError
        When the file is missing or a required value is invalid.
    """
    config_path = Path(path)
    findings: list[Problem] = []
    if not config_path.is_file():
        raise FertilizationConfigError(
            [Problem("FERTILIZATION-CONFIG", str(config_path), "configuration not found")]
        )
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise FertilizationConfigError(
            [Problem("FERTILIZATION-CONFIG", str(config_path), f"cannot read YAML: {exc}")]
        ) from exc
    if not isinstance(raw, Mapping):
        raise FertilizationConfigError(
            [Problem("FERTILIZATION-CONFIG", str(config_path), "configuration must be a mapping")]
        )
    factors = _mapping(raw.get("factors_kg_ha"), "factors_kg_ha", findings)
    gwp = _mapping(raw.get("gwp100"), "gwp100", findings)
    growth = _mapping(raw.get("growth_response"), "growth_response", findings)
    dose = _number(raw.get("dose_kg_n_ha"), "dose_kg_n_ha", findings)
    response_years = _integer(
        growth.get("response_years", raw.get("response_years")),
        "response_years",
        findings,
    )
    multiplier_value = growth.get("growth_multiplier", raw.get("growth_multiplier", 1.10))
    growth_multiplier = _number(multiplier_value, "growth_multiplier", findings)
    co2 = _number(factors.get("co2"), "factors_kg_ha.co2", findings)
    ch4 = _number(factors.get("ch4"), "factors_kg_ha.ch4", findings)
    n2o = {
        treatment: _number(
            factors.get(key),
            f"factors_kg_ha.{key}",
            findings,
        )
        for treatment, key in _N2O_KEYS.items()
    }
    gwp_ch4 = _number(gwp.get("ch4"), "gwp100.ch4", findings)
    gwp_n2o = _number(gwp.get("n2o"), "gwp100.n2o", findings)
    if dose is not None and dose < 0:
        findings.append(
            Problem("FERTILIZATION-CONFIG", "dose_kg_n_ha", "dose must be non-negative")
        )
    if response_years is not None and response_years <= 0:
        findings.append(
            Problem("FERTILIZATION-CONFIG", "response_years", "response window must be positive")
        )
    if growth_multiplier is not None and growth_multiplier < 1.0:
        findings.append(
            Problem(
                "FERTILIZATION-CONFIG",
                "growth_multiplier",
                "growth multiplier must be at least 1.0",
            )
        )
    for name, value in {
        "co2": co2,
        "ch4": ch4,
        **{f"n2o_{treatment}": value for treatment, value in n2o.items()},
        "gwp_ch4": gwp_ch4,
        "gwp_n2o": gwp_n2o,
    }.items():
        if value is not None and value < 0:
            findings.append(
                Problem("FERTILIZATION-CONFIG", name, "emission factor must be non-negative")
            )
    source = raw.get("source")
    if source is not None and not isinstance(source, Mapping):
        findings.append(Problem("FERTILIZATION-CONFIG", "source", "source must be a mapping"))
    applications = _applications(raw.get("applications"), config_path.parent, findings)
    if findings:
        raise FertilizationConfigError(findings)
    assert dose is not None
    assert response_years is not None
    assert growth_multiplier is not None
    assert co2 is not None
    assert ch4 is not None
    assert gwp_ch4 is not None
    assert gwp_n2o is not None
    assert all(value is not None for value in n2o.values())
    return FertilizationConfig(
        dose_kg_n_ha=dose,
        response_years=response_years,
        growth_multiplier=growth_multiplier,
        co2_kg_ha=co2,
        ch4_kg_ha=ch4,
        n2o_kg_ha={
            treatment: float(value) for treatment, value in n2o.items() if value is not None
        },
        gwp_ch4=gwp_ch4,
        gwp_n2o=gwp_n2o,
        source=dict(source) if isinstance(source, Mapping) else {},
        path=config_path,
        applications=applications,
    )


def with_fertilization_disturbances(
    package: CarbonPackage,
    config: FertilizationConfig,
) -> CarbonPackage:
    """Return a package copy with ``f1``, ``f2``, and ``f3`` disturbances.

    Parameters
    ----------
    package : CarbonPackage
        The loaded package.
    config : FertilizationConfig
        Fertilization assumptions.

    Returns
    -------
    CarbonPackage
        A copy whose in-memory disturbance table includes the fertilizer
        treatments. The on-disk package is unchanged.
    """
    frame = package.table("disturbance_types").copy()
    present = {str(value).strip().lower() for value in frame.get("user_dist_type", [])}
    rows = [
        row
        for row in config.disturbance_rows()
        if str(row["user_dist_type"]).lower() not in present
    ]
    if rows:
        frame = pd.concat([frame, pd.DataFrame(rows)], ignore_index=True)
    tables = dict(package.tables)
    tables["disturbance_types"] = frame
    return replace(package, tables=tables)


def with_fertilization_curves(
    package: CarbonPackage,
    tracks: pd.DataFrame,
    treatments: pd.DataFrame,
    config: FertilizationConfig,
) -> tuple[CarbonPackage, pd.DataFrame, pd.DataFrame]:
    """Add materialized fertilized tracks and transitions to in-memory tables.

    Each application copies its source track's classifier, map, yield, and curve
    rows to a new target track. The target yield uses the materialized curve for
    the leading species and preserves the source species shares for any other
    species. The dataset treatment table gains a source-to-target transition, and
    the disturbance reset age is ``-1`` so the stand age is preserved.

    Parameters
    ----------
    package : CarbonPackage
        The loaded package.
    tracks : pandas.DataFrame
        The dataset ``tracks`` table.
    treatments : pandas.DataFrame
        The dataset ``treatments`` table.
    config : FertilizationConfig
        Fertilization assumptions and curve applications.

    Returns
    -------
    tuple of (CarbonPackage, pandas.DataFrame, pandas.DataFrame)
        The augmented package, tracks, and treatments.

    Raises
    ------
    ValueError
        When an application names an unknown track, a duplicate target, a
        missing curve, or a malformed curve file.
    """
    if not config.applications:
        return package, tracks, treatments
    tables = {name: frame.copy() for name, frame in package.tables.items()}
    track_frame = tracks.copy()
    treatment_frame = treatments.copy()
    track_map = tables["track_carbon_map"].copy()
    classifiers = tables["classifiers"].copy()
    yields = tables["yield"].copy()
    curves = tables["curve_carbon_map"].copy()
    disturbances = tables["disturbance_types"].copy()
    if not {"track_id", "name"}.issubset(track_frame.columns):
        raise ValueError("tracks table needs track_id and name")
    track_ids = pd.to_numeric(track_frame["track_id"], errors="coerce").dropna().astype(int)
    next_track_id = int(track_ids.max()) + 1 if not track_ids.empty else 1
    new_tracks: list[dict[str, object]] = []
    new_treatments: list[dict[str, object]] = []
    for application in config.applications:
        source_rows = track_frame.loc[track_frame["name"].astype(str) == application.source_track]
        if source_rows.empty:
            raise ValueError(
                f"fertilization source track {application.source_track!r} is not in the dataset"
            )
        if len(source_rows) > 1:
            raise ValueError(
                f"fertilization source track {application.source_track!r} is duplicated"
            )
        source_id = int(str(source_rows.iloc[0]["track_id"]))
        if application.target_track in set(track_frame["name"].astype(str)):
            raise ValueError(
                f"fertilization target track {application.target_track!r} already exists"
            )
        source_map = track_map.loc[track_map["track_name"] == application.source_track]
        if source_map.empty:
            raise ValueError(
                f"fertilization source track {application.source_track!r} is not in the "
                "package track map"
            )
        source_row = source_map.iloc[0].copy()
        classifier_set = [value.strip() for value in str(source_row["classifier_set"]).split(";")]
        replaced = False
        for index, value in enumerate(classifier_set):
            if value == application.source_track:
                classifier_set[index] = application.target_track
                replaced = True
        if not replaced:
            raise ValueError(
                f"fertilization source track {application.source_track!r} is not in its "
                "classifier set"
            )
        source_yield = yields.loc[yields["track_name"] == application.source_track]
        if source_yield.empty:
            raise ValueError(
                f"fertilization source track {application.source_track!r} has no yield rows"
            )
        curve = _read_fertilized_curve(application.curve, application.treatment)
        leading_species = str(source_row["leading_species"])
        target_yield = _fertilized_yield_rows(
            source_yield,
            curve,
            application.target_track,
            leading_species,
        )
        target_map = source_row.copy()
        target_map["track_name"] = application.target_track
        target_map["classifier_set"] = ";".join(classifier_set)
        track_map = pd.concat([track_map, pd.DataFrame([target_map])], ignore_index=True)
        track_classifier = classifiers.loc[classifiers["classifier"].astype(str) == "track"]
        classifier_id = (
            track_classifier["classifier_id"].iloc[0] if not track_classifier.empty else 1
        )
        classifiers = pd.concat(
            [
                classifiers,
                pd.DataFrame(
                    [
                        {
                            "classifier_id": classifier_id,
                            "classifier": "track",
                            "value": application.target_track,
                            "description": f"fertilized {application.source_track}",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        yields = pd.concat([yields, target_yield], ignore_index=True)
        source_curves = curves.loc[curves["track_name"] == application.source_track]
        if source_curves.empty:
            raise ValueError(
                f"fertilization source track {application.source_track!r} has no curve rows"
            )
        target_curves = source_curves.copy()
        target_curves["track_name"] = application.target_track
        curves = pd.concat([curves, target_curves], ignore_index=True)
        new_tracks.append({"track_id": next_track_id, "name": application.target_track})
        new_treatments.append(
            {
                "track_id": source_id,
                "begin": 0,
                "end": 9999,
                "treatment": application.treatment,
                "new_track": next_track_id,
                "offset": 0,
                "retain": 0,
            }
        )
        next_track_id += 1
    if new_tracks:
        track_frame = pd.concat([track_frame, pd.DataFrame(new_tracks)], ignore_index=True)
    if new_treatments:
        treatment_frame = pd.concat(
            [treatment_frame, pd.DataFrame(new_treatments)],
            ignore_index=True,
        )
    disturbance_frame = disturbances.copy()
    present = {str(value).strip().lower() for value in disturbance_frame.get("user_dist_type", [])}
    rows = [
        row
        for row in config.disturbance_rows(transition_reset_age=-1)
        if str(row["user_dist_type"]).lower() not in present
    ]
    if rows:
        disturbance_frame = pd.concat(
            [disturbance_frame, pd.DataFrame(rows)],
            ignore_index=True,
        )
    tables["track_carbon_map"] = track_map
    tables["classifiers"] = classifiers
    tables["yield"] = yields
    tables["curve_carbon_map"] = curves
    tables["disturbance_types"] = disturbance_frame
    return replace(package, tables=tables), track_frame, treatment_frame


def _read_fertilized_curve(path: Path, treatment: str) -> pd.DataFrame:
    """Read and validate a materialized fertilized curve."""
    curve_path = Path(path)
    if not curve_path.is_file():
        raise ValueError(f"fertilization curve for {treatment!r} not found: {curve_path}")
    frame = pd.read_csv(curve_path)
    if not {"age", "volume_m3_ha"}.issubset(frame.columns):
        raise ValueError(f"fertilization curve {curve_path} needs age and volume_m3_ha columns")
    frame = frame.loc[:, ["age", "volume_m3_ha"]].copy()
    frame["age"] = pd.to_numeric(frame["age"], errors="raise").astype(float)
    frame["volume_m3_ha"] = pd.to_numeric(frame["volume_m3_ha"], errors="raise").astype(float)
    if frame.empty:
        raise ValueError(f"fertilization curve {curve_path} is empty")
    if (frame["volume_m3_ha"] < 0).any():
        raise ValueError(f"fertilization curve {curve_path} has a negative volume")
    return (
        frame.sort_values("age", kind="stable")
        .drop_duplicates("age", keep="last")
        .reset_index(drop=True)
    )


def _fertilized_yield_rows(
    source_yield: pd.DataFrame,
    curve: pd.DataFrame,
    target_track: str,
    leading_species: str,
) -> pd.DataFrame:
    """Build target yield rows from a materialized leading-species curve."""
    source = source_yield.copy()
    source["age"] = pd.to_numeric(source["age"], errors="raise").astype(float)
    source["volume_m3_ha"] = pd.to_numeric(source["volume_m3_ha"], errors="raise").astype(float)
    curve_age = curve["age"].to_numpy(dtype=float)
    curve_volume = curve["volume_m3_ha"].to_numpy(dtype=float)
    leading = source.loc[source["species"].astype(str) == leading_species]
    leading_age = pd.to_numeric(leading["age"], errors="raise").to_numpy(dtype=float)
    leading_volume = pd.to_numeric(leading["volume_m3_ha"], errors="raise").to_numpy(dtype=float)
    rows: list[dict[str, object]] = []
    for row in source.itertuples(index=False):
        values = dict(zip(source.columns, row, strict=True))
        age = float(values["age"])
        fertilized = float(
            np.interp(age, curve_age, curve_volume, left=curve_volume[0], right=curve_volume[-1])
        )
        if str(values["species"]) == leading_species or len(leading_age) == 0:
            volume = fertilized
        else:
            base = float(
                np.interp(
                    age,
                    leading_age,
                    leading_volume,
                    left=leading_volume[0],
                    right=leading_volume[-1],
                )
            )
            volume = float(values["volume_m3_ha"]) * (fertilized / base if base > 0 else 1.0)
        values["track_name"] = target_track
        values["age"] = int(age)
        values["volume_m3_ha"] = volume
        rows.append(values)
    return pd.DataFrame(rows, columns=source_yield.columns)


def fertilization_accounts(
    schedule: pd.DataFrame,
    block_areas: pd.DataFrame,
    config: FertilizationConfig,
) -> pd.DataFrame:
    """Compute fertilization emissions from a schedule and block areas.

    Parameters
    ----------
    schedule : pandas.DataFrame
        Schedule with ``block_id``, ``treatment``, and ``offset``.
    block_areas : pandas.DataFrame
        Block areas with ``block_id`` and ``area_ha``.
    config : FertilizationConfig
        Emission assumptions.

    Returns
    -------
    pandas.DataFrame
        ``offset``, ``account``, and ``value`` rows for every fertilizer event.

    Raises
    ------
    ValueError
        When the schedule or block-area table is missing required columns, or a
        scheduled block has no area.
    """
    required = {"block_id", "treatment", "offset"}
    missing = sorted(required.difference(schedule.columns))
    if missing:
        raise ValueError(f"schedule is missing columns: {missing}")
    if not {"block_id", "area_ha"}.issubset(block_areas.columns):
        raise ValueError("block_areas must contain block_id and area_ha")
    areas = (
        block_areas.assign(
            block_id=pd.to_numeric(block_areas["block_id"], errors="raise").astype(int),
            area_ha=pd.to_numeric(block_areas["area_ha"], errors="raise").astype(float),
        )
        .groupby("block_id", as_index=True)["area_ha"]
        .sum()
    )
    frame = schedule.copy()
    frame["treatment"] = frame["treatment"].astype(str).str.strip().str.lower()
    frame = frame.loc[frame["treatment"].isin(FERTILIZATION_TREATMENTS)]
    if frame.empty:
        return pd.DataFrame(columns=["offset", "account", "value"])
    frame["block_id"] = pd.to_numeric(frame["block_id"], errors="raise").astype(int)
    frame["offset"] = pd.to_numeric(frame["offset"], errors="raise").astype(int)
    missing_blocks = sorted(set(frame["block_id"]).difference(areas.index))
    if missing_blocks:
        raise ValueError(f"schedule blocks have no area: {missing_blocks[:5]}")
    frame["area_ha"] = frame["block_id"].map(areas)
    rows: list[dict[str, object]] = []
    for (offset, treatment), group in frame.groupby(["offset", "treatment"], sort=True):
        area = float(group["area_ha"].sum())
        co2 = area * config.co2_kg_ha / 1000.0
        ch4 = area * config.ch4_kg_ha / 1000.0
        n2o = area * config.n2o_kg_ha[str(treatment)] / 1000.0
        co2e = co2 + ch4 * config.gwp_ch4 + n2o * config.gwp_n2o
        values = {
            "fertilization.area_ha": area,
            "fertilization.dose_kg_n": area * config.dose_kg_n_ha,
            "fertilization.co2_t": co2,
            "fertilization.ch4_t": ch4,
            "fertilization.n2o_t": n2o,
            "fertilization.co2e_t": co2e,
        }
        for account, value in values.items():
            rows.append({"offset": int(str(offset)), "account": account, "value": value})
    accounts = pd.DataFrame(rows, columns=["offset", "account", "value"])
    if accounts.empty:
        return accounts
    return (
        accounts.groupby(["offset", "account"], as_index=False)
        .agg(value=("value", "sum"))
        .sort_values(["offset", "account"], kind="stable")
        .reset_index(drop=True)
    )


def block_areas_from_dataset(dataset_dir: Path) -> pd.DataFrame:
    """Read block areas from a compiled dataset.

    Parameters
    ----------
    dataset_dir : Path
        Compiled dataset directory.

    Returns
    -------
    pandas.DataFrame
        ``block_id`` and summed ``area_ha`` rows.

    Raises
    ------
    ValueError
        When the dataset has no fragments table.
    """
    path = Path(dataset_dir) / "fragments.parquet"
    if not path.is_file():
        raise ValueError(f"missing dataset fragments: {path}")
    fragments = pd.read_parquet(path)
    if not {"block_id", "area_ha"}.issubset(fragments.columns):
        raise ValueError("fragments need block_id and area_ha")
    return (
        fragments.assign(
            block_id=pd.to_numeric(fragments["block_id"], errors="raise").astype(int),
            area_ha=pd.to_numeric(fragments["area_ha"], errors="raise").astype(float),
        )
        .groupby("block_id", as_index=False)
        .agg(area_ha=("area_ha", "sum"))
    )


def _applications(
    value: object,
    base_dir: Path,
    findings: list[Problem],
) -> tuple[FertilizationApplication, ...]:
    """Parse the optional materialized-curve applications."""
    if value is None:
        return ()
    if not isinstance(value, list):
        findings.append(Problem("FERTILIZATION-CONFIG", "applications", "must be a list"))
        return ()
    result: list[FertilizationApplication] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            findings.append(
                Problem(
                    "FERTILIZATION-CONFIG",
                    f"applications[{index}]",
                    "must be a mapping",
                )
            )
            continue
        treatment = str(item.get("treatment", "")).strip().lower()
        if treatment not in FERTILIZATION_TREATMENTS:
            findings.append(
                Problem(
                    "FERTILIZATION-CONFIG",
                    f"applications[{index}].treatment",
                    f"must be one of {FERTILIZATION_TREATMENTS}",
                )
            )
            continue
        source_track = str(item.get("source_track", "")).strip()
        if not source_track:
            findings.append(
                Problem(
                    "FERTILIZATION-CONFIG",
                    f"applications[{index}].source_track",
                    "must be a non-empty track name",
                )
            )
            continue
        key = (treatment, source_track)
        if key in seen:
            findings.append(
                Problem(
                    "FERTILIZATION-CONFIG",
                    f"applications[{index}]",
                    f"duplicate application for {treatment} on {source_track!r}",
                )
            )
            continue
        seen.add(key)
        curve_value = item.get("curve")
        if not isinstance(curve_value, str) or not curve_value.strip():
            findings.append(
                Problem(
                    "FERTILIZATION-CONFIG",
                    f"applications[{index}].curve",
                    "must be a curve CSV path",
                )
            )
            continue
        curve = Path(curve_value)
        if not curve.is_absolute():
            curve = base_dir / curve
        if not curve.is_file():
            findings.append(
                Problem(
                    "FERTILIZATION-CONFIG",
                    f"applications[{index}].curve",
                    f"curve not found: {curve}",
                )
            )
            continue
        target_track = str(item.get("target_track", f"{source_track}+{treatment.upper()}")).strip()
        if not target_track:
            findings.append(
                Problem(
                    "FERTILIZATION-CONFIG",
                    f"applications[{index}].target_track",
                    "must be a non-empty track name",
                )
            )
            continue
        result.append(
            FertilizationApplication(
                treatment=treatment,
                source_track=source_track,
                curve=curve,
                target_track=target_track,
            )
        )
    return tuple(result)


def _mapping(value: object, name: str, findings: list[Problem]) -> Mapping[str, Any]:
    """Return a YAML mapping, recording a finding when it is absent or invalid."""
    if not isinstance(value, Mapping):
        findings.append(Problem("FERTILIZATION-CONFIG", name, "must be a mapping"))
        return {}
    return value


def _number(value: object, name: str, findings: list[Problem]) -> float | None:
    """Return a finite number, recording a finding when it is invalid."""
    try:
        result = float(str(value))
    except (TypeError, ValueError):
        findings.append(Problem("FERTILIZATION-CONFIG", name, "must be a number"))
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        findings.append(Problem("FERTILIZATION-CONFIG", name, "must be finite"))
        return None
    return result


def _integer(value: object, name: str, findings: list[Problem]) -> int | None:
    """Return an integer, recording a finding when it is invalid."""
    number = _number(value, name, findings)
    if number is None:
        return None
    if number != int(number):
        findings.append(Problem("FERTILIZATION-CONFIG", name, "must be an integer"))
        return None
    return int(number)
