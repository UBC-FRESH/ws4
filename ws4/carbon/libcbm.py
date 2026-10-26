"""Run the CBM engine through libcbm and write the carbon run outputs.

The driver is behind a small protocol so a future CBM4 backend can replace libcbm
without changing the package contract, the SIT compiler, or the account names.
libcbm is an optional dependency: importing this module never imports it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from importlib import import_module
from pathlib import Path
from typing import Any

import pandas as pd

from ..model.schema import dataset_reference
from .fertilization import FERTILIZATION_TREATMENTS, FertilizationConfig
from .package import CarbonPackage, package_fingerprint
from .sit import SitTables

BIOMASS_POOLS: tuple[str, ...] = (
    "SoftwoodMerch",
    "SoftwoodFoliage",
    "SoftwoodOther",
    "SoftwoodCoarseRoots",
    "SoftwoodFineRoots",
    "HardwoodMerch",
    "HardwoodFoliage",
    "HardwoodOther",
    "HardwoodCoarseRoots",
    "HardwoodFineRoots",
)

DOM_POOLS: tuple[str, ...] = (
    "AboveGroundVeryFastSoil",
    "BelowGroundVeryFastSoil",
    "AboveGroundFastSoil",
    "BelowGroundFastSoil",
    "MediumSoil",
    "AboveGroundSlowSoil",
    "BelowGroundSlowSoil",
    "SoftwoodStemSnag",
    "SoftwoodBranchSnag",
    "HardwoodStemSnag",
    "HardwoodBranchSnag",
)

DECAY_FLUXES: tuple[str, ...] = (
    "DecayVFastAGToAir",
    "DecayVFastBGToAir",
    "DecayFastAGToAir",
    "DecayFastBGToAir",
    "DecayMediumToAir",
    "DecaySlowAGToAir",
    "DecaySlowBGToAir",
    "DecaySWStemSnagToAir",
    "DecaySWBranchSnagToAir",
    "DecayHWStemSnagToAir",
    "DecayHWBranchSnagToAir",
)

DISTURBANCE_FLUXES: tuple[str, ...] = (
    "DisturbanceMerchToAir",
    "DisturbanceFolToAir",
    "DisturbanceOthToAir",
    "DisturbanceCoarseToAir",
    "DisturbanceFineToAir",
    "DisturbanceVFastAGToAir",
    "DisturbanceVFastBGToAir",
    "DisturbanceFastAGToAir",
    "DisturbanceFastBGToAir",
    "DisturbanceMediumToAir",
    "DisturbanceSlowAGToAir",
    "DisturbanceSlowBGToAir",
    "DisturbanceSWStemSnagToAir",
    "DisturbanceSWBranchSnagToAir",
    "DisturbanceHWStemSnagToAir",
    "DisturbanceHWBranchSnagToAir",
)

CO2_PER_CARBON = 44.0 / 12.0


@dataclass(frozen=True)
class CbmDefaultsReference:
    """The installed CBM defaults database.

    Attributes
    ----------
    path : Path
        Database path.
    version : str
        Version parsed from the file name.
    sha256 : str
        Hex SHA-256 digest.
    """

    path: Path
    version: str
    sha256: str


@dataclass(frozen=True)
class CarbonRun:
    """The raw output of one CBM run.

    Attributes
    ----------
    pools : pandas.DataFrame
        Pool values, one row per stand and timestep.
    flux : pandas.DataFrame
        Flux values, one row per stand and timestep.
    classifiers : pandas.DataFrame
        Classifier values, one row per stand and timestep.
    state : pandas.DataFrame
        State variables, one row per stand and timestep.
    libcbm_version : str
        The libcbm version used.
    defaults : CbmDefaultsReference
        The CBM defaults database used.
    """

    pools: pd.DataFrame
    flux: pd.DataFrame
    classifiers: pd.DataFrame
    state: pd.DataFrame
    libcbm_version: str
    defaults: CbmDefaultsReference


@dataclass(frozen=True)
class CarbonRunResult:
    """The files and summary from a written carbon run.

    Attributes
    ----------
    output_dir : Path
        Run directory.
    pools_path : Path
        Wide pool table.
    flux_path : Path
        Wide flux table.
    accounts_path : Path
        Long carbon accounts.
    manifest_path : Path
        Carbon run manifest.
    ecosystem_start_tc : float
        Total ecosystem carbon at timestep 0.
    ecosystem_end_tc : float
        Total ecosystem carbon at the last timestep.
    n_steps : int
        Number of simulated timesteps.
    """

    output_dir: Path
    pools_path: Path
    flux_path: Path
    accounts_path: Path
    manifest_path: Path
    ecosystem_start_tc: float
    ecosystem_end_tc: float
    n_steps: int


class CarbonEngineError(ValueError):
    """Raised when the carbon engine cannot run or the defaults do not match."""


def installed_libcbm_version() -> str:
    """Return the installed libcbm version.

    Returns
    -------
    str
        The version string.

    Raises
    ------
    CarbonEngineError
        When libcbm is not installed.
    """
    try:
        from importlib import metadata
    except ImportError as exc:  # pragma: no cover - importlib always exists
        raise CarbonEngineError("cannot inspect the libcbm version") from exc
    try:
        return metadata.version("libcbm")
    except metadata.PackageNotFoundError as exc:
        raise CarbonEngineError(
            "libcbm is not installed; install the optional 'carbon' extra"
        ) from exc


def cbm_defaults_reference() -> CbmDefaultsReference:
    """Return the CBM defaults database bundled with libcbm.

    Returns
    -------
    CbmDefaultsReference
        The database path, version, and digest.

    Raises
    ------
    CarbonEngineError
        When libcbm is not installed.
    """
    try:
        resources = import_module("libcbm.resources")
    except ImportError as exc:
        raise CarbonEngineError(
            "libcbm is not installed; install the optional 'carbon' extra"
        ) from exc
    path = Path(resources.get_cbm_defaults_path())
    version = path.stem.removeprefix("cbm_defaults_v")
    return CbmDefaultsReference(
        path=path,
        version=version,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def check_cbm_defaults(
    package: CarbonPackage,
    *,
    allow_mismatch: bool = False,
) -> CbmDefaultsReference:
    """Check the package defaults against the installed libcbm database.

    Parameters
    ----------
    package : CarbonPackage
        The package whose manifest records the expected database.
    allow_mismatch : bool, optional
        When True, a mismatch is reported by the caller rather than raised.

    Returns
    -------
    CbmDefaultsReference
        The installed database.

    Raises
    ------
    CarbonEngineError
        When the installed database differs and ``allow_mismatch`` is False.
    """
    installed = cbm_defaults_reference()
    expected = package.manifest.cbm_defaults
    if expected.sha256 and expected.sha256 != installed.sha256 and not allow_mismatch:
        raise CarbonEngineError(
            "cbm_defaults mismatch: package expects "
            f"{expected.version} ({expected.sha256}), installed is "
            f"{installed.version} ({installed.sha256}); pass "
            "--allow-defaults-mismatch only for an explicit comparison"
        )
    return installed


def build_sit_config(package: CarbonPackage) -> dict[str, object]:
    """Build the libcbm SIT mapping configuration from a package.

    Parameters
    ----------
    package : CarbonPackage
        The loaded package.

    Returns
    -------
    dict of str to object
        The libcbm mapping configuration.
    """
    classifiers = package.table("classifiers")
    species_values = sorted(
        classifiers.loc[classifiers["classifier"] == "species", "value"].astype(str)
    )
    species_mapping = [
        {
            "user_species": value,
            "default_species": _default_species(value),
        }
        for value in species_values
    ]
    disturbances = package.table("disturbance_types")
    disturbance_mapping = [
        {
            "user_dist_type": str(row.user_dist_type),
            "default_dist_type": str(row.default_dist_type),
        }
        for row in disturbances.itertuples(index=False)
    ]
    track_map = package.tables.get("track_carbon_map")
    track_ecos = (
        sorted({str(value).strip() for value in track_map["eco_boundary"]})
        if track_map is not None and "eco_boundary" in track_map.columns
        else []
    )
    inventory = package.tables.get("inventory")
    if inventory is not None and "eco_boundary" in inventory.columns:
        track_ecos = sorted(
            {*track_ecos, *(str(value).strip() for value in inventory["eco_boundary"])}
        )
    if len(track_ecos) > 1:
        admin = package.manifest.boundaries.admin
        spatial_units: dict[str, object] = {
            "mapping_mode": "SeparateAdminEcoClassifiers",
            "admin_classifier": "admin_boundary",
            "eco_classifier": "eco_boundary",
            "admin_mapping": [
                {
                    "user_admin_boundary": admin,
                    "default_admin_boundary": admin,
                }
            ],
            "eco_mapping": [
                {
                    "user_eco_boundary": eco,
                    "default_eco_boundary": eco,
                }
                for eco in track_ecos
            ],
        }
    else:
        spatial_units = {
            "mapping_mode": "SingleDefaultSpatialUnit",
            "admin_boundary": package.manifest.boundaries.admin,
            "eco_boundary": package.manifest.boundaries.eco,
        }
    return {
        "mapping_config": {
            "nonforest": None,
            "species": {
                "species_classifier": package.manifest.mapping.species_classifier,
                "species_mapping": species_mapping,
            },
            "spatial_units": spatial_units,
            "disturbance_types": {
                "disturbance_type_mapping": disturbance_mapping,
            },
        }
    }


def run_libcbm(
    package: CarbonPackage,
    tables: SitTables,
    *,
    n_steps: int,
    density: bool = False,
    allow_defaults_mismatch: bool = False,
    fertilization: FertilizationConfig | None = None,
) -> CarbonRun:
    """Run libcbm on compiled SIT tables using a package's mapping.

    Parameters
    ----------
    package : CarbonPackage
        The package, used for the mapping configuration and defaults check.
    tables : SitTables
        The compiled SIT tables.
    n_steps : int
        Number of annual timesteps.
    density : bool, optional
        Return pools and fluxes as tC/ha rather than tC. Defaults to False.
    allow_defaults_mismatch : bool, optional
        Allow a package/defaults mismatch. Defaults to False.
    fertilization : FertilizationConfig or None, optional
        When set, apply the temporary growth response after fertilizer events.
        Defaults to None.

    Returns
    -------
    CarbonRun
        The engine output.

    Raises
    ------
    CarbonEngineError
        When libcbm is missing, the defaults mismatch, or the run fails.
    """
    defaults = check_cbm_defaults(package, allow_mismatch=allow_defaults_mismatch)
    run = run_libcbm_tables(
        tables,
        build_sit_config(package),
        n_steps=n_steps,
        density=density,
        fertilization=fertilization,
    )
    return replace(run, defaults=defaults)


def run_libcbm_tables(
    tables: SitTables,
    config: Mapping[str, object],
    *,
    n_steps: int,
    density: bool = False,
    fertilization: FertilizationConfig | None = None,
) -> CarbonRun:
    """Run libcbm on SIT tables with an explicit mapping configuration.

    This is the engine-only entry point used by the parity harness. It does not
    check a package manifest; callers that need the package check should use
    :func:`run_libcbm`.

    Parameters
    ----------
    tables : SitTables
        The compiled SIT tables.
    config : mapping of str to object
        The libcbm SIT mapping configuration.
    n_steps : int
        Number of annual timesteps.
    density : bool, optional
        Return pools and fluxes as tC/ha rather than tC. Defaults to False.
    fertilization : FertilizationConfig or None, optional
        When set, apply the temporary growth response after fertilizer events.
        Defaults to None.

    Returns
    -------
    CarbonRun
        The engine output.

    Raises
    ------
    CarbonEngineError
        When libcbm is missing or the run fails.
    """
    if n_steps <= 0:
        raise CarbonEngineError("n_steps must be positive")
    if fertilization is not None and fertilization.uses_curves:
        raise CarbonEngineError(
            "fertilization curve applications are compiled as transitions; "
            "do not pass a curve configuration as a growth multiplier"
        )
    defaults = cbm_defaults_reference()
    version = installed_libcbm_version()
    try:
        sit_cbm_factory = import_module("libcbm.input.sit.sit_cbm_factory")
        sit_reader = import_module("libcbm.input.sit.sit_reader")
        cbm_simulator = import_module("libcbm.model.cbm.cbm_simulator")
        cbm_output_class = import_module("libcbm.model.cbm.cbm_output").CBMOutput
    except ImportError as exc:
        raise CarbonEngineError(
            "libcbm is not installed; install the optional 'carbon' extra"
        ) from exc
    try:
        sit_data = sit_reader.parse(
            sit_classifiers=tables.classifiers,
            sit_disturbance_types=tables.disturbance_types,
            sit_age_classes=tables.age_classes,
            sit_inventory=tables.inventory,
            sit_yield=tables.yield_table,
            sit_events=tables.events,
            sit_transitions=tables.transitions,
            sit_eligibilities=None,
        )
        sit = sit_cbm_factory.initialize_sit(sit_data=sit_data, config=dict(config))
        classifiers, inventory = sit_cbm_factory.initialize_inventory(sit)
        output = cbm_output_class(
            density=density,
            classifier_map=sit.classifier_value_names,
            disturbance_type_map=sit.disturbance_name_map,
        )
        with sit_cbm_factory.initialize_cbm(sit) as cbm:
            processor = sit_cbm_factory.create_sit_rule_based_processor(sit, cbm)
            pre_dynamics = processor.pre_dynamics_func
            if fertilization is not None:
                fertilizer_ids = {
                    int(key)
                    for key, value in sit.disturbance_name_map.items()
                    if str(value).strip().lower() in FERTILIZATION_TREATMENTS
                }
                if not fertilizer_ids:
                    raise CarbonEngineError(
                        "fertilization is configured but the SIT tables have no f1/f2/f3 "
                        "disturbance types"
                    )
                pre_dynamics = _fertilization_pre_dynamics(
                    pre_dynamics,
                    fertilizer_ids=fertilizer_ids,
                    response_years=fertilization.response_years,
                    growth_multiplier=fertilization.growth_multiplier,
                )
            cbm_simulator.simulate(
                cbm,
                n_steps=n_steps,
                classifiers=classifiers,
                inventory=inventory,
                pre_dynamics_func=pre_dynamics,
                reporting_func=output.append_simulation_result,
            )
    except Exception as exc:
        raise CarbonEngineError(f"libcbm run failed: {exc}") from exc
    if output.pools is None or output.flux is None or output.state is None:
        raise CarbonEngineError("libcbm returned no output")
    classifiers_frame = (
        output.classifiers.to_pandas() if output.classifiers is not None else pd.DataFrame()
    )
    return CarbonRun(
        pools=output.pools.to_pandas(),
        flux=output.flux.to_pandas(),
        classifiers=classifiers_frame,
        state=output.state.to_pandas(),
        libcbm_version=version,
        defaults=defaults,
    )


def _fertilization_pre_dynamics(
    base: Callable[[int, Any], Any],
    *,
    fertilizer_ids: set[int],
    response_years: int,
    growth_multiplier: float,
) -> Callable[[int, Any], Any]:
    """Wrap a SIT pre-dynamics function with the temporary growth response.

    Parameters
    ----------
    base : callable
        The processor's pre-dynamics function.
    fertilizer_ids : set of int
        CBM disturbance-type ids for ``f1``, ``f2``, and ``f3``.
    response_years : int
        Number of years to keep the multiplier active.
    growth_multiplier : float
        Multiplier applied while the response is active.

    Returns
    -------
    callable
        A pre-dynamics function that writes ``growth_multiplier`` into the state
        before each annual growth operation.
    """

    def pre_dynamics(timestep: int, cbm_vars: Any) -> Any:  # noqa: ANN401
        result = base(timestep, cbm_vars)
        state = result.state
        disturbance = state["last_disturbance_type"].to_numpy()
        elapsed = state["time_since_last_disturbance"].to_numpy()
        values = [
            growth_multiplier
            if int(disturbance[index]) in fertilizer_ids and float(elapsed[index]) <= response_years
            else 1.0
            for index in range(len(disturbance))
        ]
        state["growth_multiplier"].assign(values)
        return result

    return pre_dynamics


def carbon_accounts(run: CarbonRun) -> pd.DataFrame:
    """Summarize a run into long carbon accounts.

    Parameters
    ----------
    run : CarbonRun
        The engine output.

    Returns
    -------
    pandas.DataFrame
        ``offset``, ``account``, and ``value`` rows.
    """
    pools = run.pools.groupby("timestep", sort=True).sum(numeric_only=True)
    flux = run.flux.groupby("timestep", sort=True).sum(numeric_only=True)
    rows: list[dict[str, object]] = []
    biomass = _sum_columns(pools, BIOMASS_POOLS)
    dom = _sum_columns(pools, DOM_POOLS)
    ecosystem = biomass + dom
    products = (
        pools["Products"] if "Products" in pools.columns else pd.Series(0.0, index=pools.index)
    )
    npp = _sum_columns(flux, ("DeltaBiomass_AG", "DeltaBiomass_BG"))
    decay = _sum_columns(flux, DECAY_FLUXES)
    disturbance = _sum_columns(flux, DISTURBANCE_FLUXES)
    net = decay + disturbance - npp
    for timestep in pools.index:
        offset = int(timestep)
        values = {
            "carbon.biomass.total": float(biomass.loc[timestep]),
            "carbon.dom.total": float(dom.loc[timestep]),
            "carbon.ecosystem.total": float(ecosystem.loc[timestep]),
            "carbon.products.total": float(products.loc[timestep]),
            "carbon.flux.npp": float(npp.loc[timestep]),
            "carbon.flux.decay": float(decay.loc[timestep]),
            "carbon.flux.disturbance": float(disturbance.loc[timestep]),
            "carbon.flux.net": float(net.loc[timestep]),
        }
        for name, value in values.items():
            rows.append({"offset": offset, "account": name, "value": value})
        for name in (
            "carbon.ecosystem.total",
            "carbon.flux.net",
            "carbon.products.total",
        ):
            rows.append(
                {
                    "offset": offset,
                    "account": name.replace("carbon.", "carbon.co2e.", 1),
                    "value": values[name] * CO2_PER_CARBON,
                }
            )
    accounts = pd.DataFrame(rows, columns=["offset", "account", "value"])
    ecosystem_accounts = accounts.loc[accounts["account"] == "carbon.ecosystem.total"]
    change = ecosystem_accounts["value"].diff().fillna(0.0)
    changes = pd.DataFrame(
        {
            "offset": ecosystem_accounts["offset"].to_numpy(),
            "account": "carbon.stock.change",
            "value": change.to_numpy(),
        }
    )
    return pd.concat([accounts, changes], ignore_index=True)


def write_carbon_run(
    run: CarbonRun,
    output_dir: Path,
    *,
    package: CarbonPackage,
    dataset_dir: Path,
    schedule: pd.DataFrame,
    n_steps: int,
    density: bool = False,
    extra_accounts: pd.DataFrame | None = None,
    extra_manifest: Mapping[str, object] | None = None,
) -> CarbonRunResult:
    """Write the pools, fluxes, accounts, and manifest for a run.

    Parameters
    ----------
    run : CarbonRun
        The engine output.
    output_dir : Path
        Run directory.
    package : CarbonPackage
        The package used.
    dataset_dir : Path
        The compiled dataset used.
    schedule : pandas.DataFrame
        The schedule used.
    n_steps : int
        Number of simulated timesteps.
    density : bool, optional
        Whether the pool and flux values are densities. Defaults to False.
    extra_accounts : pandas.DataFrame or None, optional
        Additional ``offset``, ``account``, and ``value`` rows to append to the
        carbon accounts. Used for the fertilization emissions audit.
    extra_manifest : mapping of str to object or None, optional
        Additional provenance to write under the ``fertilization`` manifest key.

    Returns
    -------
    CarbonRunResult
        The written files and summary totals.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    pools_path = root / "carbon_pools.csv"
    flux_path = root / "carbon_flux.csv"
    accounts_path = root / "carbon_accounts.csv"
    manifest_path = root / "carbon_manifest.json"
    run.pools.to_csv(pools_path, index=False)
    run.flux.to_csv(flux_path, index=False)
    run.pools.melt(
        id_vars=[column for column in ("timestep", "identifier") if column in run.pools],
        var_name="pool",
        value_name="value",
    ).to_csv(root / "carbon_pools_long.csv", index=False)
    run.flux.melt(
        id_vars=[column for column in ("timestep", "identifier") if column in run.flux],
        var_name="flux",
        value_name="value",
    ).to_csv(root / "carbon_flux_long.csv", index=False)
    accounts = carbon_accounts(run)
    if extra_accounts is not None and not extra_accounts.empty:
        accounts = pd.concat(
            [accounts, extra_accounts.loc[:, ["offset", "account", "value"]]],
            ignore_index=True,
        )
        accounts = accounts.sort_values(["offset", "account"], kind="stable").reset_index(drop=True)
    accounts.to_csv(accounts_path, index=False)
    ecosystem = accounts.loc[accounts["account"] == "carbon.ecosystem.total"]
    ecosystem_start = float(ecosystem["value"].iloc[0]) if not ecosystem.empty else 0.0
    ecosystem_end = float(ecosystem["value"].iloc[-1]) if not ecosystem.empty else 0.0
    schedule_hash = hashlib.sha256(schedule.to_csv(index=False).encode("utf-8")).hexdigest()
    manifest: dict[str, object] = {
        "package_id": package.manifest.package_id,
        "package_fingerprint": package_fingerprint(package),
        "dataset": dataset_reference(Path(dataset_dir)),
        "schedule_sha256": schedule_hash,
        "n_steps": int(n_steps),
        "density": bool(density),
        "units": package.manifest.units.model_dump(),
        "libcbm_version": run.libcbm_version,
        "cbm_defaults": {
            "version": run.defaults.version,
            "sha256": run.defaults.sha256,
            "path": str(run.defaults.path),
        },
    }
    if extra_manifest is not None:
        manifest["fertilization"] = dict(extra_manifest)
    if extra_accounts is not None and not extra_accounts.empty:
        fertilization = manifest.setdefault("fertilization", {})
        assert isinstance(fertilization, dict)
        for label, account in (
            ("total_area_ha", "fertilization.area_ha"),
            ("total_co2e_t", "fertilization.co2e_t"),
        ):
            values = extra_accounts.loc[extra_accounts["account"] == account, "value"]
            fertilization[label] = float(pd.to_numeric(values, errors="coerce").sum())
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return CarbonRunResult(
        output_dir=root,
        pools_path=pools_path,
        flux_path=flux_path,
        accounts_path=accounts_path,
        manifest_path=manifest_path,
        ecosystem_start_tc=ecosystem_start,
        ecosystem_end_tc=ecosystem_end,
        n_steps=n_steps,
    )


def merge_carbon_accounts(
    run_dir: Path,
    carbon_accounts: Path,
    *,
    carbon_manifest: Path | None = None,
) -> pd.DataFrame:
    """Merge ``carbon.*`` accounts into a simulation run's account values.

    Existing ``carbon.*`` and ``fertilization.*`` rows are replaced, so a rerun
    is idempotent. Non-carbon accounts are preserved. The optional carbon
    manifest is copied into the run directory as ``carbon_manifest.json``.

    Parameters
    ----------
    run_dir : Path
        A simulation run directory with ``account_values.csv``.
    carbon_accounts : Path
        The ``carbon_accounts.csv`` produced by :func:`write_carbon_run`.
    carbon_manifest : Path or None, optional
        The carbon run manifest to copy into the run directory.

    Returns
    -------
    pandas.DataFrame
        The merged account values.

    Raises
    ------
    CarbonEngineError
        When the run or carbon accounts are missing or malformed.
    """
    root = Path(run_dir)
    values_path = root / "account_values.csv"
    if not values_path.is_file():
        raise CarbonEngineError(f"missing simulation account values: {values_path}")
    accounts_path = Path(carbon_accounts)
    if not accounts_path.is_file():
        raise CarbonEngineError(f"missing carbon accounts: {accounts_path}")
    base = pd.read_csv(values_path)
    carbon = pd.read_csv(accounts_path)
    required = {"offset", "account", "value"}
    if not required.issubset(base.columns) or not required.issubset(carbon.columns):
        raise CarbonEngineError(
            "account_values.csv and carbon_accounts.csv need offset, account, and value"
        )
    base = base.loc[
        ~base["account"].astype(str).str.startswith(("carbon.", "fertilization."))
    ].copy()
    carbon = carbon.loc[:, ["offset", "account", "value"]].copy()
    merged = pd.concat([base, carbon], ignore_index=True)
    merged = merged.sort_values(["offset", "account"], kind="stable").reset_index(drop=True)
    merged.to_csv(values_path, index=False)
    if carbon_manifest is not None and Path(carbon_manifest).is_file():
        shutil.copy2(Path(carbon_manifest), root / "carbon_manifest.json")
    return merged


def _default_species(value: str) -> str:
    """Map a package species classifier value to a CBM default species."""
    normalized = value.strip().lower()
    if normalized == "softwood":
        return "Softwood forest type"
    if normalized == "hardwood":
        return "Hardwood forest type"
    return value


def _sum_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
) -> pd.Series:
    """Sum the columns that exist, returning zeros when none exist."""
    present = [column for column in columns if column in frame.columns]
    if not present:
        return pd.Series(0.0, index=frame.index)
    return frame.loc[:, present].sum(axis=1)


def mapping_reference(package: CarbonPackage) -> Mapping[str, object]:
    """Return a compact mapping reference for reporting.

    Parameters
    ----------
    package : CarbonPackage
        The loaded package.

    Returns
    -------
    mapping of str to object
        The package's join key and classifier names.
    """
    return {
        "track_key": package.manifest.mapping.track_key,
        "species_classifier": package.manifest.mapping.species_classifier,
        "disturbance_classifier": package.manifest.mapping.disturbance_classifier,
    }
