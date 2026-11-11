"""Daily CFSDS breadth-corpus selection and integrity checks.

This module builds an observation-only breadth corpus. It verifies that each CFSDS event has
daily progression, daily weather, a matching raster, and fuel/terrain coverage. It does not run
the hourly FBP model and does not claim model skill.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from .fuel import FireFuelError

DAILY_MINIMUM: Final[int] = 20
YEAR_MINIMUM: Final[int] = 2
ECOZONE_MINIMUM: Final[int] = 2
CELSIUS_GRID_AREA_HA: Final[float] = 90.0 * 90.0 / 10_000.0
WEATHER_COLUMNS: Final[tuple[str, ...]] = ("ffmc", "bui", "ws", "rh", "prec")
NON_FUEL_CODES: Final[frozenset[int]] = frozenset({0, 101, 102})
UTM11_BOUNDS: Final[tuple[float, float, float, float]] = (
    300_000.0,
    4_500_000.0,
    700_000.0,
    9_400_000.0,
)


@dataclass(frozen=True)
class DailyCase:
    """One selected daily CFSDS breadth case.

    Parameters
    ----------
    case_id : str
        CFSDS fire identifier.
    year : int
        Fire year.
    days : int
        Number of growth days in the daily summary.
    final_area_ha : float
        Final cumulative area from the daily summary.
    raster_area_ha : float
        Final area measured from the daily raster.
    area_relative_error : float
        Absolute relative difference between summary and raster area.
    ecozone : int
        CFSDS ecozone code.
    lon, lat : float
        Final centroid longitude and latitude.
    fuel_code : int
        FireSTARR fuel code at the centroid.
    elevation_m : float
        Elevation at the centroid.
    status : str
        ``ready`` or ``rejected``.
    """

    case_id: str
    year: int
    days: int
    final_area_ha: float
    raster_area_ha: float
    area_relative_error: float
    ecozone: int
    lon: float
    lat: float
    fuel_code: int
    elevation_m: float
    status: str

    def __post_init__(self) -> None:
        """Validate the case record."""
        if not self.case_id:
            raise FireFuelError("case_id must be non-empty")
        if self.year < 1800 or self.year > 2100:
            raise FireFuelError("year must be between 1800 and 2100")
        if self.days < 1:
            raise FireFuelError("days must be positive")
        if self.final_area_ha <= 0 or self.raster_area_ha <= 0:
            raise FireFuelError("areas must be positive")
        if self.area_relative_error < 0:
            raise FireFuelError("area_relative_error must be non-negative")
        if self.status not in {"ready", "rejected"}:
            raise FireFuelError("status must be ready or rejected")

    @property
    def ready(self) -> bool:
        """Return whether the case passes the breadth checks.

        Returns
        -------
        bool
            True when status is ``ready``.
        """
        return self.status == "ready"

    def to_dict(self) -> dict[str, object]:
        """Return the case as a JSON-serializable mapping.

        Returns
        -------
        dict
            All fields plus readiness.
        """
        return {
            "case_id": self.case_id,
            "year": self.year,
            "days": self.days,
            "final_area_ha": self.final_area_ha,
            "raster_area_ha": self.raster_area_ha,
            "area_relative_error": self.area_relative_error,
            "ecozone": self.ecozone,
            "lon": self.lon,
            "lat": self.lat,
            "fuel_code": self.fuel_code,
            "elevation_m": self.elevation_m,
            "status": self.status,
            "ready": self.ready,
        }


@dataclass(frozen=True)
class DailyCorpusGate:
    """Coverage gate for the daily breadth corpus.

    Parameters
    ----------
    ready_cases : int
        Number of ready daily cases.
    year_count : int
        Number of distinct years.
    ecozone_count : int
        Number of distinct ecozones.
    """

    ready_cases: int
    year_count: int
    ecozone_count: int

    @property
    def status(self) -> str:
        """Return whether the breadth coverage gate passes.

        Returns
        -------
        str
            ``pass`` or ``blocked``.
        """
        if (
            self.ready_cases >= DAILY_MINIMUM
            and self.year_count >= YEAR_MINIMUM
            and self.ecozone_count >= ECOZONE_MINIMUM
        ):
            return "pass"
        return "blocked"

    def to_dict(self) -> dict[str, object]:
        """Return the gate as a JSON-serializable mapping.

        Returns
        -------
        dict
            Counts, minimums, status, and reason.
        """
        reason = (
            "Daily breadth gate passed."
            if self.status == "pass"
            else (
                f"Need {DAILY_MINIMUM} ready cases, {YEAR_MINIMUM} years, and "
                f"{ECOZONE_MINIMUM} ecozones; have {self.ready_cases}, "
                f"{self.year_count}, and {self.ecozone_count}."
            )
        )
        return {
            "status": self.status,
            "reason": reason,
            "ready_cases": self.ready_cases,
            "case_minimum": DAILY_MINIMUM,
            "year_count": self.year_count,
            "year_minimum": YEAR_MINIMUM,
            "ecozone_count": self.ecozone_count,
            "ecozone_minimum": ECOZONE_MINIMUM,
        }


def _quantile_indices(count: int, quota: int) -> list[int]:
    """Return deterministic area-quantile indices.

    Parameters
    ----------
    count : int
        Number of available cases.
    quota : int
        Number to select.

    Returns
    -------
    list of int
        Unique indices in increasing order.
    """
    if quota <= 0 or count <= 0:
        return []
    if quota >= count:
        return list(range(count))
    if quota == 1:
        return [0]
    return sorted({round(index * (count - 1) / (quota - 1)) for index in range(quota)})


def _as_float(value: object) -> float:
    """Return a pandas row value as a float.

    Parameters
    ----------
    value : object
        Row value.

    Returns
    -------
    float
        Numeric value.
    """
    return float(cast(Any, value))


def _as_int(value: object) -> int:
    """Return a pandas row value as an integer.

    Parameters
    ----------
    value : object
        Row value.

    Returns
    -------
    int
        Integer value.
    """
    return int(cast(Any, value))


def _sample_raster(path: Path, x: float, y: float) -> tuple[int, float]:
    """Return fuel code and elevation at a projected centroid.

    Parameters
    ----------
    path : Path
        Raster path.
    x, y : float
        Projected coordinates.

    Returns
    -------
    tuple of int and float
        Fuel code and elevation. Missing values are returned as zero.
    """
    with rasterio.open(path) as source:
        row, column = source.index(x, y)
        window = ((row, row + 1), (column, column + 1))
        value = float(source.read(1, window=window)[0, 0])
        if source.nodata is not None and value == float(source.nodata):
            value = 0.0
    return int(value), value


def _raster_area(path: str, expected_area: float) -> tuple[float, float, int]:
    """Measure a CFSDS raster and compare it with the daily-summary area.

    Parameters
    ----------
    path : str
        Raster path, including a ``/vsizip/`` prefix.
    expected_area : float
        Final area from the daily summary.

    Returns
    -------
    tuple of float, float, int
        Raster area, relative error, and number of burned days.
    """
    with rasterio.open(path) as source:
        values = source.read(1)
    burned = (values > 0) & (values != np.iinfo(values.dtype).max)
    area = float(burned.sum()) * CELSIUS_GRID_AREA_HA
    error = abs(area - expected_area) / expected_area
    days = len(np.unique(values[burned]))
    return area, error, days


def build_daily_corpus(
    data_root: str | Path,
    years: tuple[int, ...] = (2003, 2009, 2023),
    quotas: tuple[int, ...] = (7, 6, 7),
) -> tuple[tuple[DailyCase, ...], int, int]:
    """Build the daily CFSDS breadth corpus.

    Parameters
    ----------
    data_root : str or Path
        Directory containing the CFSDS group CSVs, raster zips, and FireSTARR fuel/DEM tiles.
    years : tuple of int, optional
        CFSDS years to include.
    quotas : tuple of int, optional
        Cases to select per year.

    Returns
    -------
    tuple
        Selected cases, candidate count, and rejected count.

    Raises
    ------
    FireFuelError
        If an input file is missing or the year/quota lengths differ.
    """
    root = Path(data_root)
    if len(years) != len(quotas):
        raise FireFuelError("years and quotas must have the same length")
    fuel_path = root / "fuel_11_0.tif"
    dem_path = root / "dem_11_0.tif"
    for path in (fuel_path, dem_path):
        if not path.is_file():
            raise FireFuelError(f"missing raster: {path}")
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:26911", always_xy=True)
    ready_by_year: dict[int, list[DailyCase]] = {}
    candidate_count = 0
    rejected_count = 0
    for year, quota in zip(years, quotas, strict=True):
        summary = root / f"Firegrowth_groups_v1_1_{year}.csv"
        raster_zip = root / f"{year}_fireDOYrasters.zip"
        if not summary.is_file() or not raster_zip.is_file():
            raise FireFuelError(f"missing CFSDS inputs for {year}")
        frame = pd.read_csv(summary)
        grouped = (
            frame.groupby("ID")
            .agg(
                days=("fireday", "max"),
                area=("cumuarea", "max"),
                ecozone=("ecozone", "first"),
                lon=("lon", "last"),
                lat=("lat", "last"),
                weather_rows=("fireday", "size"),
                **{
                    f"{name}_nulls": (name, lambda values: int(values.isna().sum()))
                    for name in WEATHER_COLUMNS
                },
            )
            .reset_index()
        )
        members = set(zipfile.ZipFile(raster_zip).namelist())
        candidates = grouped[
            (grouped["days"] >= 2) & (grouped["area"] >= 200.0) & (grouped["area"] <= 50_000.0)
        ].copy()
        candidates["raster_member"] = candidates["ID"].map(
            lambda value, known=members: (
                f"{value}_krig.tif" if f"{value}_krig.tif" in known else None
            )
        )
        candidates = candidates[candidates["raster_member"].notna()]
        candidate_count += len(candidates)
        year_cases: list[DailyCase] = []
        for row in candidates.itertuples(index=False):
            x, y = transformer.transform(_as_float(row.lon), _as_float(row.lat))
            if not (
                UTM11_BOUNDS[0] <= x <= UTM11_BOUNDS[2] and UTM11_BOUNDS[1] <= y <= UTM11_BOUNDS[3]
            ):
                continue
            fuel_code, _ = _sample_raster(fuel_path, x, y)
            _, elevation = _sample_raster(dem_path, x, y)
            weather_ok = all(
                _as_int(getattr(row, f"{name}_nulls")) == 0 for name in WEATHER_COLUMNS
            )
            case_path = f"/vsizip/{raster_zip.resolve()}/{row.raster_member}"
            raster_area, error, _ = _raster_area(case_path, _as_float(row.area))
            status = "ready"
            if error > 0.02 or not weather_ok or fuel_code in NON_FUEL_CODES or elevation <= 0:
                status = "rejected"
                rejected_count += 1
            year_cases.append(
                DailyCase(
                    case_id=str(row.ID),
                    year=year,
                    days=_as_int(row.days),
                    final_area_ha=_as_float(row.area),
                    raster_area_ha=raster_area,
                    area_relative_error=error,
                    ecozone=_as_int(row.ecozone),
                    lon=_as_float(row.lon),
                    lat=_as_float(row.lat),
                    fuel_code=fuel_code,
                    elevation_m=elevation,
                    status=status,
                )
            )
        ready = sorted(
            (case for case in year_cases if case.ready), key=lambda case: case.final_area_ha
        )
        indices = _quantile_indices(len(ready), quota)
        ready_by_year[year] = [ready[index] for index in indices]
    selected = tuple(case for year in years for case in ready_by_year[year])
    return selected, candidate_count, rejected_count


def daily_corpus_gate(cases: tuple[DailyCase, ...]) -> DailyCorpusGate:
    """Return the daily breadth coverage gate.

    Parameters
    ----------
    cases : tuple of DailyCase
        Selected daily cases.

    Returns
    -------
    DailyCorpusGate
        Counts and pass/blocked status.
    """
    ready = [case for case in cases if case.ready]
    return DailyCorpusGate(
        ready_cases=len(ready),
        year_count=len({case.year for case in ready}),
        ecozone_count=len({case.ecozone for case in ready}),
    )


def daily_manifest(
    cases: tuple[DailyCase, ...],
    candidate_count: int,
    rejected_count: int,
) -> dict[str, object]:
    """Return the daily breadth manifest.

    Parameters
    ----------
    cases : tuple of DailyCase
        Selected daily cases.
    candidate_count : int
        Number of candidate events inspected.
    rejected_count : int
        Number of candidate events rejected by integrity checks.

    Returns
    -------
    dict
        Gate, counts, coverage, limitations, and cases.
    """
    gate = daily_corpus_gate(cases)
    areas = [case.final_area_ha for case in cases]
    days = [case.days for case in cases]
    return {
        "corpus_kind": "daily_cfsds_breadth",
        "model_skill": False,
        "basis": (
            "Observation-only daily CFSDS progression, daily weather, and raster integrity. "
            "Not hourly/FBP validation and not a WS4 model run."
        ),
        "candidate_count": candidate_count,
        "rejected_count": rejected_count,
        "case_count": len(cases),
        "gate": gate.to_dict(),
        "year_counts": {
            str(year): sum(case.year == year for case in cases)
            for year in sorted({case.year for case in cases})
        },
        "ecozone_counts": {
            str(ecozone): sum(case.ecozone == ecozone for case in cases)
            for ecozone in sorted({case.ecozone for case in cases})
        },
        "area_range_ha": [min(areas), max(areas)] if areas else [],
        "day_range": [min(days), max(days)] if days else [],
        "limitations": (
            "Single fuel/terrain tile (UTM 11N), daily weather, satellite-derived perimeters, "
            "and no hourly model run. This is breadth evidence, not regional validation."
        ),
        "cases": [case.to_dict() for case in cases],
    }
