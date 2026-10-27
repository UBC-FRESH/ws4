"""Compile carbon stock and emission yield curves from libcbm single stands.

This is the WS4 port of the public "simulated clearcut" curve method. A managed
curve is not read from a spun-up age-0 state: the stand grows on its source
trajectory to a rotation age, a clearcut transfers the pools and emits the
disturbance losses, and the post-event trajectory becomes the age-0 curve. The
``cycle`` mode repeats the clearcut and extracts the last cycle, so the curve
represents a regenerated stand rather than only the first rotation.

The output is an audit and interchange artifact. It contains stock and flux
curves per track, including merchantable carbon, so a caller can build HWP
inflows and a reduced carbon account set without rerunning libcbm for every
schedule. The exact block ledger remains the optimizer's authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..model.schema import dataset_reference
from .libcbm import (
    BIOMASS_POOLS,
    DECAY_FLUXES,
    DISTURBANCE_FLUXES,
    DOM_POOLS,
    CarbonRun,
    run_libcbm,
)
from .package import CarbonPackage, package_fingerprint
from .sit import build_sit_tables_from_tables, read_dataset_tables

CURVE_MODES: tuple[str, ...] = ("single", "cycle")

# Biomass increment plus the turnover fluxes, matching the public fresh-yan
# ``gross_growth`` definition. ``carbon.flux.npp`` remains the narrower biomass
# increment used by the run account writer.
GROWTH_FLUXES: tuple[str, ...] = (
    "DeltaBiomass_AG",
    "DeltaBiomass_BG",
    "TurnoverMerchLitterInput",
    "TurnoverFolLitterInput",
    "TurnoverOthLitterInput",
    "TurnoverCoarseLitterInput",
    "TurnoverFineLitterInput",
)


@dataclass(frozen=True)
class CarbonCurveResult:
    """The files and totals from one carbon-curve compile.

    Attributes
    ----------
    output_dir : Path
        Directory holding the curves.
    curves_path : Path
        Long stock and flux curve table.
    manifest_path : Path
        Provenance and method manifest.
    track_count : int
        Number of curves written.
    rotation_age : int
        Rotation age used for the simulated clearcut.
    mode : str
        ``single`` or ``cycle``.
    """

    output_dir: Path
    curves_path: Path
    manifest_path: Path
    track_count: int
    rotation_age: int
    mode: str


def _sum(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    """Sum the columns that exist, returning zeros when none do."""
    present = [column for column in columns if column in frame.columns]
    if not present:
        return pd.Series(0.0, index=frame.index)
    return frame.loc[:, present].sum(axis=1)


def _stand_fragments(track_id: int) -> pd.DataFrame:
    """Return one one-hectare stand on a track for a single-stand run."""
    return pd.DataFrame(
        {
            "fragment_id": [1],
            "block_id": [1],
            "track_id": [int(track_id)],
            "area_ha": [1.0],
            "age": [1],
        }
    )


def _managed_sources(
    package: CarbonPackage,
    treatments: pd.DataFrame,
) -> dict[int, tuple[int, str]]:
    """Map each regeneration target track to its harvest source and treatment.

    The package disturbance map says which treatments remove biomass. A target may
    have more than one source in a general matrix; this first version takes the
    first deterministic source and records the choice in the manifest.
    """
    rules = package.table("disturbance_types")
    removing: set[str] = set()
    for row in rules.itertuples(index=False):
        flag = str(getattr(row, "removes_biomass", "false")).strip().lower()
        if flag in {"true", "1", "yes", "y"}:
            removing.add(str(row.user_dist_type).strip().lower())
    result: dict[int, tuple[int, str]] = {}
    for row in treatments.itertuples(index=False):
        treatment = str(row.treatment).strip()
        if treatment.lower() not in removing:
            continue
        new_track = getattr(row, "new_track", None)
        if new_track is None or pd.isna(new_track):
            continue
        source = int(str(row.track_id))
        target = int(str(new_track))
        if source == target:
            continue
        result.setdefault(target, (source, treatment))
    return result


def _schedule_for_curve(
    *,
    target_track: str | None,
    treatment: str | None,
    rotation_age: int,
    mode: str,
) -> pd.DataFrame:
    """Build the single-stand clearcut schedule for one curve."""
    if target_track is None or treatment is None:
        return pd.DataFrame(
            {
                "block_id": pd.Series(dtype="int64"),
                "treatment": pd.Series(dtype="string"),
                "offset": pd.Series(dtype="int64"),
            }
        )
    rotations = 5 if mode == "cycle" else 1
    rows: list[dict[str, object]] = []
    for rotation in range(1, rotations + 1):
        row: dict[str, object] = {
            "block_id": 1,
            "treatment": treatment,
            "offset": rotation_age * rotation - 1,
        }
        if rotation > 1:
            row["target_track"] = target_track
            row["target_area_ha"] = 1.0
        rows.append(row)
    return pd.DataFrame(rows)


def _curve_rows(
    run: CarbonRun,
    *,
    track_name: str,
    start: int,
    length: int,
) -> pd.DataFrame:
    """Extract one stand's curve rows from a libcbm run."""
    pools = run.pools.groupby("timestep", sort=True).sum(numeric_only=True)
    flux = run.flux.groupby("timestep", sort=True).sum(numeric_only=True)
    selected_pools = pools.loc[start : start + length]
    selected_flux = flux.loc[start : start + length]
    biomass = _sum(selected_pools, BIOMASS_POOLS)
    dom = _sum(selected_pools, DOM_POOLS)
    merch = _sum(selected_pools, ("SoftwoodMerch", "HardwoodMerch"))
    products = (
        selected_pools["Products"]
        if "Products" in selected_pools.columns
        else pd.Series(0.0, index=selected_pools.index)
    )
    total_emission = _sum(selected_flux, (*DECAY_FLUXES, *DISTURBANCE_FLUXES))
    gross_growth = _sum(selected_flux, GROWTH_FLUXES)
    frame = pd.DataFrame(
        {
            "track_name": track_name,
            "age": list(range(len(selected_pools))),
            "ecosystem_tc_ha": (biomass + dom).to_numpy(),
            "biomass_tc_ha": biomass.to_numpy(),
            "dom_tc_ha": dom.to_numpy(),
            "merch_tc_ha": merch.to_numpy(),
            "products_tc_ha": products.to_numpy(),
            "total_emission_tc_ha": total_emission.to_numpy(),
            "gross_growth_tc_ha": gross_growth.to_numpy(),
            "net_emission_tc_ha": (total_emission - gross_growth).to_numpy(),
        }
    )
    return frame


def generate_carbon_curves(
    package: CarbonPackage,
    dataset_dir: Path,
    output_dir: Path,
    *,
    rotation_age: int = 120,
    years: int = 300,
    mode: str = "cycle",
    tracks: list[str] | None = None,
    allow_defaults_mismatch: bool = False,
) -> CarbonCurveResult:
    """Generate stock and emission yield curves for package tracks.

    Parameters
    ----------
    package : CarbonPackage
        The validated FEMIC package.
    dataset_dir : Path
        The compiled dataset that supplies track names and treatments.
    output_dir : Path
        Directory for the long curve table and manifest.
    rotation_age : int, optional
        Age at which the simulated clearcut occurs. Defaults to 120.
    years : int, optional
        Number of post-event annual curve points. Defaults to 300.
    mode : {"single", "cycle"}, optional
        One clearcut or repeated clearcuts. Defaults to ``cycle``.
    tracks : list of str or None, optional
        Restrict the compile to these package track names. Defaults to all tracks.
    allow_defaults_mismatch : bool, optional
        Allow a package/defaults mismatch for an explicit comparison.

    Returns
    -------
    CarbonCurveResult
        The written curve table and manifest.

    Raises
    ------
    ValueError
        When the mode or rotation age is invalid, or a requested track is unknown.
    CarbonEngineError
        When libcbm cannot run.
    """
    if mode not in CURVE_MODES:
        raise ValueError(f"carbon curve mode must be one of {CURVE_MODES}, got {mode!r}")
    if rotation_age <= 0:
        raise ValueError("rotation_age must be positive")
    if years <= 0:
        raise ValueError("years must be positive")
    _fragments, tracks_frame, treatments = read_dataset_tables(Path(dataset_dir))
    track_names = {
        int(str(row.track_id)): str(row.name) for row in tracks_frame.itertuples(index=False)
    }
    package_tracks = set(package.table("track_carbon_map")["track_name"].astype(str))
    requested = set(tracks) if tracks else package_tracks
    unknown = requested - package_tracks
    if unknown:
        raise ValueError(f"unknown package tracks: {', '.join(sorted(unknown))}")
    sources = _managed_sources(package, treatments)
    source_by_target_name = {
        track_names.get(target, ""): (source, treatment)
        for target, (source, treatment) in sources.items()
        if track_names.get(target)
    }
    rows: list[pd.DataFrame] = []
    for track_id, track_name in sorted(track_names.items(), key=lambda item: item[1]):
        if track_name not in requested:
            continue
        source = source_by_target_name.get(track_name)
        treatment: str | None = None
        target_name: str | None = None
        if source is None:
            stand_track_id = track_id
            schedule = _schedule_for_curve(
                target_track=None,
                treatment=None,
                rotation_age=rotation_age,
                mode=mode,
            )
            total_steps = years + 1
            start = 0
        else:
            stand_track_id, treatment = source
            target_name = track_name
            schedule = _schedule_for_curve(
                target_track=target_name,
                treatment=treatment,
                rotation_age=rotation_age,
                mode=mode,
            )
            rotations = 5 if mode == "cycle" else 1
            total_steps = rotation_age * rotations + years + 1
            start = rotation_age * rotations
        stand = _stand_fragments(stand_track_id)
        # The transition table is global: a target track that is absent from the
        # one-block inventory is still reached through the source track's transition.
        tables = build_sit_tables_from_tables(
            package,
            stand,
            tracks_frame,
            treatments,
            schedule,
        )
        run = run_libcbm(
            package,
            tables,
            n_steps=total_steps,
            allow_defaults_mismatch=allow_defaults_mismatch,
        )
        curve = _curve_rows(
            run,
            track_name=track_name,
            start=start,
            length=years,
        )
        rows.append(curve)
    if not rows:
        raise ValueError("no carbon curves were generated")
    result = pd.concat(rows, ignore_index=True)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    curves_path = root / "carbon_curves.csv"
    manifest_path = root / "carbon_curves_manifest.json"
    result.to_csv(curves_path, index=False)
    manifest = {
        "model": "ws4.carbon_curves.v1",
        "method": "simulated_clearcut",
        "mode": mode,
        "rotation_age_years": int(rotation_age),
        "post_event_years": int(years),
        "package_id": package.manifest.package_id,
        "package_fingerprint": package_fingerprint(package),
        "dataset": dataset_reference(Path(dataset_dir)),
        "tracks": sorted(result["track_name"].unique().tolist()),
        "managed_source_map": {
            track_names.get(target, str(target)): {
                "source_track": track_names.get(source, str(source)),
                "treatment": treatment,
            }
            for target, (source, treatment) in sorted(sources.items())
            if track_names.get(target) in requested
        },
        "units": {
            "age": "years",
            "ecosystem_tc_ha": "tC/ha",
            "biomass_tc_ha": "tC/ha",
            "dom_tc_ha": "tC/ha",
            "merch_tc_ha": "tC/ha",
            "products_tc_ha": "tC/ha",
            "total_emission_tc_ha": "tC/ha/year",
            "gross_growth_tc_ha": "tC/ha/year",
            "net_emission_tc_ha": "tC/ha/year",
        },
        "caveat": (
            "The curve is an audit/interchange artifact. The block-level libcbm ledger "
            "remains the exact optimizer path."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return CarbonCurveResult(
        output_dir=root,
        curves_path=curves_path,
        manifest_path=manifest_path,
        track_count=int(result["track_name"].nunique()),
        rotation_age=int(rotation_age),
        mode=mode,
    )
