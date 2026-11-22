"""Provisional yield bridge from species biomass to merchantable volume.

The compiled management dataset and its yield curves remain authoritative. This bridge is a
small, versioned mapping used by the stochastic engine to expose an ecological volume view; it
does not overwrite the compiled dataset and it is not calibrated to observed data.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from .state import CohortState

BRIDGE_VERSION: Final[str] = "ws4.volume-bridge.v1"


class BridgeError(RuntimeError):
    """Raised when a bridge parameter or table is invalid."""


def _volume_rate(value: object, field: str) -> float:
    """Return a finite, non-negative volume rate."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BridgeError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise BridgeError(f"{field} must be non-negative")
    return number


def _track_key(value: object) -> int:
    """Return a non-negative integer track id from a table value."""
    if isinstance(value, bool):
        raise BridgeError("track_id must be a non-negative integer")
    try:
        number = float(str(value).strip())
    except ValueError as error:
        raise BridgeError("track_id must be a non-negative integer") from error
    if not math.isfinite(number) or not number.is_integer() or number < 0.0:
        raise BridgeError("track_id must be a non-negative integer")
    return int(number)


@dataclass(frozen=True)
class VolumeBridgeConfig:
    """Parameters of the provisional species-biomass bridge.

    Parameters
    ----------
    volume_m3_per_t : mapping of str to float
        Species-specific merchantable volume per tonne of live biomass.
    default_volume_m3_per_t : float
        Rate for species not listed.
    merchantable_fraction : float
        Fraction of live biomass treated as merchantable.
    bridge_id : str
        Stable bridge id.
    calibration_status : str
        Status label, default ``provisional``.
    calibration_source : str
        Provenance note.
    age_volume_curves : mapping of str to mapping of int to float, optional
        Species age-to-volume-per-hectare curves. These override the biomass rate.
    track_age_volume_curves : mapping of int to mapping of int to float, optional
        Compiled track age-to-volume-per-hectare curves. A cohort with a matching
        ``track_id`` uses this curve before the species curve.
    """

    volume_m3_per_t: Mapping[str, float] = field(default_factory=dict)
    default_volume_m3_per_t: float = 1.0
    merchantable_fraction: float = 1.0
    bridge_id: str = "volume-bridge"
    calibration_status: str = "provisional"
    calibration_source: str = "Default coefficients; not fitted to observed data."
    age_volume_curves: Mapping[str, Mapping[int, float]] = field(default_factory=dict)
    track_age_volume_curves: Mapping[int, Mapping[int, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and canonicalize the parameters."""
        if not isinstance(self.volume_m3_per_t, Mapping):
            raise BridgeError("volume_m3_per_t must be a mapping")
        rates: dict[str, float] = {}
        for species, rate in self.volume_m3_per_t.items():
            if not isinstance(species, str) or not species.strip():
                raise BridgeError("species names must be non-empty strings")
            rates[species.strip()] = _volume_rate(rate, f"volume_m3_per_t[{species!r}]")
        object.__setattr__(self, "volume_m3_per_t", rates)
        object.__setattr__(
            self,
            "default_volume_m3_per_t",
            _volume_rate(self.default_volume_m3_per_t, "default_volume_m3_per_t"),
        )
        fraction = _volume_rate(self.merchantable_fraction, "merchantable_fraction")
        if fraction > 1.0:
            raise BridgeError("merchantable_fraction must be between 0 and 1")
        object.__setattr__(self, "merchantable_fraction", fraction)
        if not self.bridge_id.strip():
            raise BridgeError("bridge_id must be non-empty")
        if not self.calibration_status.strip():
            raise BridgeError("calibration_status must be non-empty")
        if not isinstance(self.age_volume_curves, Mapping):
            raise BridgeError("age_volume_curves must be a mapping")
        curves: dict[str, dict[int, float]] = {}
        for species, raw_curve in self.age_volume_curves.items():
            if not isinstance(species, str) or not species.strip():
                raise BridgeError("age curve species names must be non-empty strings")
            if not isinstance(raw_curve, Mapping) or not raw_curve:
                raise BridgeError(f"age curve for {species!r} must be a non-empty mapping")
            curve: dict[int, float] = {}
            for raw_age, raw_volume in raw_curve.items():
                if isinstance(raw_age, bool) or not isinstance(raw_age, int) or raw_age < 0:
                    raise BridgeError("age curve keys must be non-negative integers")
                curve[raw_age] = _volume_rate(raw_volume, f"age curve {species!r} at {raw_age}")
            curves[species.strip()] = dict(sorted(curve.items()))
        object.__setattr__(self, "age_volume_curves", curves)
        if not isinstance(self.track_age_volume_curves, Mapping):
            raise BridgeError("track_age_volume_curves must be a mapping")
        track_curves: dict[int, dict[int, float]] = {}
        for raw_track, raw_curve in self.track_age_volume_curves.items():
            if isinstance(raw_track, bool) or not isinstance(raw_track, int) or raw_track < 0:
                raise BridgeError("track ids must be non-negative integers")
            if not isinstance(raw_curve, Mapping) or not raw_curve:
                raise BridgeError(f"age curve for track {raw_track!r} must be a non-empty mapping")
            track_curve: dict[int, float] = {}
            for raw_age, raw_volume in raw_curve.items():
                if isinstance(raw_age, bool) or not isinstance(raw_age, int) or raw_age < 0:
                    raise BridgeError("age curve keys must be non-negative integers")
                track_curve[raw_age] = _volume_rate(
                    raw_volume, f"track age curve {raw_track!r} at {raw_age}"
                )
            track_curves[raw_track] = dict(sorted(track_curve.items()))
        object.__setattr__(self, "track_age_volume_curves", track_curves)

    def rate(self, species: str) -> float:
        """Return the volume rate for one species.

        Parameters
        ----------
        species : str
            Species label.

        Returns
        -------
        float
            Species rate or the default.
        """
        return self.volume_m3_per_t.get(species, self.default_volume_m3_per_t)

    def to_dict(self) -> dict[str, object]:
        """Return the parameters as a JSON-serializable mapping.

        Returns
        -------
        dict
            Version, coefficients, age curves, status, and provenance.
        """
        return {
            "schema_version": BRIDGE_VERSION,
            "bridge_id": self.bridge_id,
            "volume_m3_per_t": dict(sorted(self.volume_m3_per_t.items())),
            "default_volume_m3_per_t": self.default_volume_m3_per_t,
            "merchantable_fraction": self.merchantable_fraction,
            "age_volume_curves": {
                species: dict(sorted(curve.items()))
                for species, curve in sorted(self.age_volume_curves.items())
            },
            "track_age_volume_curves": {
                str(track): dict(sorted(curve.items()))
                for track, curve in sorted(self.track_age_volume_curves.items())
            },
            "calibration_status": self.calibration_status,
            "calibration_source": self.calibration_source,
        }

    def age_volume(self, species: str, age: float, track_id: int | None = None) -> float | None:
        """Return interpolated volume per hectare from an age curve.

        Parameters
        ----------
        species : str
            Species label.
        age : float
            Cohort age in years.
        track_id : int or None, optional
            Compiled track identity. A matching track curve takes precedence.

        Returns
        -------
        float or None
            Interpolated volume, or None when neither the track nor the species has a curve.
        """
        curve = None
        if track_id is not None:
            curve = self.track_age_volume_curves.get(track_id)
        if curve is None:
            curve = self.age_volume_curves.get(species)
        if not curve:
            return None
        ages = sorted(curve)
        if age <= ages[0]:
            return curve[ages[0]]
        if age >= ages[-1]:
            return curve[ages[-1]]
        for lower, upper in itertools.pairwise(ages):
            if lower <= age <= upper:
                fraction = (age - lower) / (upper - lower)
                return curve[lower] + fraction * (curve[upper] - curve[lower])
        return curve[ages[-1]]

    def write(self, path: str | Path) -> Path:
        """Write the parameter table to JSON.

        Parameters
        ----------
        path : str or Path
            Destination path.

        Returns
        -------
        Path
            The written path.
        """
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return destination


def cohort_volume_per_ha(
    config: VolumeBridgeConfig,
    *,
    species: str,
    track_id: int | None,
    age: float,
    biomass_t_ha: float,
) -> float:
    """Return merchantable volume per hectare for one cohort.

    Uses the track curve first, then the species curve, then the biomass rate, in the same
    order as :class:`SpeciesVolumeBridge`.

    Parameters
    ----------
    config : VolumeBridgeConfig
        Bridge parameters.
    species : str
        Species label.
    track_id : int or None
        Compiled track id, when present.
    age : float
        Cohort age in years.
    biomass_t_ha : float
        Live biomass in tonnes per hectare.

    Returns
    -------
    float
        Merchantable volume in cubic metres per hectare.
    """
    if track_id is not None:
        curve = config.track_age_volume_curves.get(int(track_id))
        if curve:
            points = sorted(curve)
            return float(
                np.interp(age, np.array(points), np.array([curve[point] for point in points]))
            )
    curve = config.age_volume_curves.get(species)
    if curve:
        points = sorted(curve)
        return float(np.interp(age, np.array(points), np.array([curve[point] for point in points])))
    rate = config.volume_m3_per_t.get(species, config.default_volume_m3_per_t)
    return float(biomass_t_ha * rate * config.merchantable_fraction)


@dataclass(frozen=True)
class CohortVolumeModel:
    """Per-cohort volume used when harvest removes area.

    Parameters
    ----------
    config : VolumeBridgeConfig
        Bridge parameters.
    """

    config: VolumeBridgeConfig

    def volume_per_ha(
        self, *, species: str, track_id: int | None, age: float, biomass_t_ha: float
    ) -> float:
        """Return merchantable volume per hectare for one cohort."""
        return cohort_volume_per_ha(
            self.config,
            species=species,
            track_id=track_id,
            age=age,
            biomass_t_ha=biomass_t_ha,
        )


class SpeciesVolumeBridge:
    """Map cohort biomass to merchantable volume without changing the dataset.

    Parameters
    ----------
    config : VolumeBridgeConfig, optional
        Bridge parameters; the defaults are provisional.
    """

    def __init__(self, config: VolumeBridgeConfig | None = None) -> None:
        """Retain the bridge parameters."""
        self.config = config or VolumeBridgeConfig()

    def table(self, state: CohortState) -> pd.DataFrame:
        """Return fragment-level merchantable volume.

        Parameters
        ----------
        state : CohortState
            The ecological cohort state.

        Returns
        -------
        pandas.DataFrame
            One row per fragment with ``fragment_id``, ``area_ha``,
            ``biomass_t_ha``, ``volume_m3_ha``, and ``volume_m3``.
        """
        columns = ["fragment_id", "area_ha", "biomass_t_ha", "volume_m3_ha", "volume_m3"]
        frame = state.cohorts
        if frame.empty:
            return pd.DataFrame(columns=columns)
        fragments = pd.to_numeric(frame["fragment_id"], errors="raise").astype(int)
        areas = fragments.map(state.fragment_areas).to_numpy(dtype=float)
        weights = frame["area_fraction"].to_numpy(dtype=float)
        absolute_area = weights * areas
        ages = frame["age"].to_numpy(dtype=float)
        species = frame["species"].astype(str)
        volume = np.zeros(len(frame), dtype=float)
        assigned = np.zeros(len(frame), dtype=bool)
        if "track_id" in frame.columns:
            tracks = pd.to_numeric(frame["track_id"], errors="coerce")
            for track, curve in self.config.track_age_volume_curves.items():
                mask = (tracks == track).to_numpy()
                if not bool(mask.any()):
                    continue
                points = sorted(curve)
                volume[mask] = (
                    np.interp(
                        ages[mask],
                        np.array(points, dtype=float),
                        np.array([curve[point] for point in points], dtype=float),
                    )
                    * absolute_area[mask]
                )
                assigned[mask] = True
        for name, curve in self.config.age_volume_curves.items():
            mask = (~assigned) & (species == name).to_numpy()
            if not bool(mask.any()):
                continue
            points = sorted(curve)
            volume[mask] = (
                np.interp(
                    ages[mask],
                    np.array(points, dtype=float),
                    np.array([curve[point] for point in points], dtype=float),
                )
                * absolute_area[mask]
            )
            assigned[mask] = True
        if not bool(assigned.all()):
            rates = species.map(self.config.rate).to_numpy(dtype=float)
            volume[~assigned] = (
                frame.loc[~assigned, "biomass_t_ha"].to_numpy(dtype=float)
                * absolute_area[~assigned]
                * rates[~assigned]
                * self.config.merchantable_fraction
            )
        result = pd.DataFrame(
            {
                "fragment_id": fragments,
                "area_ha": areas,
                "biomass_t_ha": frame["biomass_t_ha"].to_numpy(dtype=float) * absolute_area,
                "volume_m3": volume,
            }
        )
        grouped = result.groupby("fragment_id", sort=True).agg(
            area_ha=("area_ha", "first"),
            biomass_t_ha=("biomass_t_ha", "sum"),
            volume_m3=("volume_m3", "sum"),
        )
        grouped["biomass_t_ha"] = grouped["biomass_t_ha"] / grouped["area_ha"]
        grouped["volume_m3_ha"] = grouped["volume_m3"] / grouped["area_ha"]
        return grouped.reset_index()[columns]

    def apply(self, management: pd.DataFrame, state: CohortState) -> pd.DataFrame:
        """Return the management frame with a volume bridge attached.

        Parameters
        ----------
        management : pandas.DataFrame
            Management state with a ``fragment_id`` column.
        state : CohortState
            The ecological cohort state.

        Returns
        -------
        pandas.DataFrame
            A copy of the management frame with ``volume_m3_ha`` and ``volume_m3``.

        Raises
        ------
        BridgeError
            If the management frame has no ``fragment_id`` column.
        """
        if "fragment_id" not in management.columns:
            raise BridgeError("management frame needs a fragment_id column")
        return management.copy(deep=True).merge(
            self.table(state), on="fragment_id", how="left", validate="one_to_one"
        )


def _curve_from_frame(frame: pd.DataFrame, curve_id: int) -> dict[int, float]:
    """Return one validated curve from a compiled curves table."""
    subset = frame.loc[frame["curve_id"] == curve_id]
    if subset.empty:
        raise BridgeError(f"curve {curve_id} is missing")
    curve: dict[int, float] = {}
    for row in subset.itertuples(index=False):
        raw_x = float(str(row.x))
        raw_y = float(str(row.y))
        if not raw_x.is_integer() or raw_x < 0.0:
            raise BridgeError("curve ages must be non-negative integers")
        age = int(raw_x)
        if age in curve:
            raise BridgeError(f"curve {curve_id} has duplicate age {age}")
        if not math.isfinite(raw_y) or raw_y < 0.0:
            raise BridgeError("curve volumes must be finite and non-negative")
        curve[age] = raw_y
    return dict(sorted(curve.items()))


def age_volume_curves_from_frame(
    frame: pd.DataFrame, species_curves: Mapping[str, int]
) -> dict[str, dict[int, float]]:
    """Build validated age-volume curves from a compiled curves table.

    Parameters
    ----------
    frame : pandas.DataFrame
        Curve table with ``curve_id``, ``x``, and ``y`` columns.
    species_curves : mapping of str to int
        Species label to compiled curve id.

    Returns
    -------
    dict
        Species to age-to-volume-per-hectare mapping.

    Raises
    ------
    BridgeError
        If columns are missing, a curve is absent, an age is not a non-negative integer,
        a volume is invalid, or an age is duplicated.
    """
    for column in ("curve_id", "x", "y"):
        if column not in frame.columns:
            raise BridgeError(f"curve table needs a {column!r} column")
    curves: dict[str, dict[int, float]] = {}
    for species, curve_id in species_curves.items():
        if not isinstance(species, str) or not species.strip():
            raise BridgeError("species names must be non-empty strings")
        curves[species.strip()] = _curve_from_frame(frame, curve_id)
    return curves


def track_age_volume_curves_from_frame(
    frame: pd.DataFrame, track_curves: Mapping[int, int]
) -> dict[int, dict[int, float]]:
    """Build validated track age-volume curves from a compiled curves table.

    Parameters
    ----------
    frame : pandas.DataFrame
        Curve table with ``curve_id``, ``x``, and ``y`` columns.
    track_curves : mapping of int to int
        Compiled track id to curve id, usually from the ``features`` table.

    Returns
    -------
    dict
        Track to age-to-volume-per-hectare mapping.

    Raises
    ------
    BridgeError
        If columns are missing, a track or curve is invalid, an age is not a non-negative
        integer, a volume is invalid, or an age is duplicated.
    """
    for column in ("curve_id", "x", "y"):
        if column not in frame.columns:
            raise BridgeError(f"curve table needs a {column!r} column")
    curves: dict[int, dict[int, float]] = {}
    for raw_track, curve_id in track_curves.items():
        if isinstance(raw_track, bool) or not isinstance(raw_track, int) or raw_track < 0:
            raise BridgeError("track ids must be non-negative integers")
        curves[raw_track] = _curve_from_frame(frame, curve_id)
    return curves
