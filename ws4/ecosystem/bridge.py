"""Provisional yield bridge from species biomass to merchantable volume.

The compiled management dataset and its yield curves remain authoritative. This bridge is a
small, versioned mapping used by the stochastic engine to expose an ecological volume view; it
does not overwrite the compiled dataset and it is not calibrated to observed data.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

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
    """

    volume_m3_per_t: Mapping[str, float] = field(default_factory=dict)
    default_volume_m3_per_t: float = 1.0
    merchantable_fraction: float = 1.0
    bridge_id: str = "volume-bridge"
    calibration_status: str = "provisional"
    calibration_source: str = "Default coefficients; not fitted to observed data."

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
            Version, coefficients, status, and provenance.
        """
        return {
            "schema_version": BRIDGE_VERSION,
            "bridge_id": self.bridge_id,
            "volume_m3_per_t": dict(sorted(self.volume_m3_per_t.items())),
            "default_volume_m3_per_t": self.default_volume_m3_per_t,
            "merchantable_fraction": self.merchantable_fraction,
            "calibration_status": self.calibration_status,
            "calibration_source": self.calibration_source,
        }

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
        if state.cohorts.empty:
            return pd.DataFrame(columns=columns)
        rows: list[dict[str, object]] = []
        for fragment, group in state.cohorts.groupby("fragment_id", sort=True):
            fragment_id = int(str(fragment))
            area = float(state.fragment_areas[fragment_id])
            biomass = float((group["biomass_t_ha"] * group["area_fraction"] * area).sum())
            volume = 0.0
            for _, row in group.iterrows():
                species = str(row["species"])
                volume += (
                    float(row["biomass_t_ha"])
                    * float(row["area_fraction"])
                    * area
                    * self.config.rate(species)
                    * self.config.merchantable_fraction
                )
            rows.append(
                {
                    "fragment_id": fragment_id,
                    "area_ha": area,
                    "biomass_t_ha": biomass / area if area > 0.0 else 0.0,
                    "volume_m3_ha": volume / area if area > 0.0 else 0.0,
                    "volume_m3": volume,
                }
            )
        return pd.DataFrame(rows, columns=columns)

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
