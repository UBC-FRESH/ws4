"""Read GCBM results and compare them with a WS4 carbon run.

GCBM writes a raw SQLite results database and spatial GeoTIFFs. This module reads the
database only; it does not require FLINT, Wine, or the GCBM executable at run time.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .libcbm import BIOMASS_POOLS, DOM_POOLS

GCBM_TABLES: tuple[str, ...] = (
    "Pools",
    "Fluxes",
    "LocationDimension",
    "DateDimension",
    "PoolDimension",
    "ModuleInfoDimension",
    "DisturbanceTypeDimension",
    "ClassifierSetDimension",
)


@dataclass(frozen=True)
class GcbmResults:
    """The tabular GCBM output.

    Attributes
    ----------
    path : Path
        Results database.
    sha256 : str
        Database digest.
    pools : pandas.DataFrame
        Long pool rows: ``offset``, ``year``, ``location_id``, ``classifier_set_id``,
        ``pool``, and ``value``.
    fluxes : pandas.DataFrame
        Long flux rows with the module, disturbance type, source pool, sink pool, and value.
    locations : pandas.DataFrame
        Location dimension rows with date, classifier set, land class, age class, and area.
    classifiers : pandas.DataFrame
        Classifier-set rows.
    dates : pandas.DataFrame
        Date dimension rows.
    """

    path: Path
    sha256: str
    pools: pd.DataFrame
    fluxes: pd.DataFrame
    locations: pd.DataFrame
    classifiers: pd.DataFrame
    dates: pd.DataFrame


@dataclass(frozen=True)
class GcbmRunResult:
    """The files written for a GCBM results summary.

    Attributes
    ----------
    output_dir : Path
        Output directory.
    pools_path : Path
        Pool table.
    fluxes_path : Path
        Flux table.
    accounts_path : Path
        Carbon account table.
    manifest_path : Path
        Summary manifest.
    ecosystem_start_tc : float
        Total ecosystem carbon at the first offset.
    ecosystem_end_tc : float
        Total ecosystem carbon at the last offset.
    """

    output_dir: Path
    pools_path: Path
    fluxes_path: Path
    accounts_path: Path
    manifest_path: Path
    ecosystem_start_tc: float
    ecosystem_end_tc: float


class GcbmResultsError(ValueError):
    """Raised when a GCBM results database cannot be read."""


def read_gcbm_results(path: Path) -> GcbmResults:
    """Read a raw GCBM results database.

    Parameters
    ----------
    path : Path
        The ``gcbm_output.db`` file.

    Returns
    -------
    GcbmResults
        The tabular output.

    Raises
    ------
    GcbmResultsError
        When the file is missing or a required table is absent.
    """
    database = Path(path)
    if not database.is_file():
        raise GcbmResultsError(f"GCBM results database not found: {database}")
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise GcbmResultsError(f"cannot open {database}: {exc}") from exc
    try:
        present = {
            str(row[0])
            for row in connection.execute("select name from sqlite_master where type='table'")
        }
        missing = sorted(set(GCBM_TABLES) - present)
        if missing:
            raise GcbmResultsError(f"GCBM results missing tables: {missing}")
        pools = pd.read_sql_query(
            """
            select d.step as offset, d.year as year, l.id as location_id,
                   l.classifierSetDimId as classifier_set_id,
                   p.poolName as pool, po.poolValue as value
            from Pools po
            join LocationDimension l on po.locationDimId = l.id
            join DateDimension d on l.dateDimId = d.id
            join PoolDimension p on po.poolId = p.id
            """,
            connection,
        )
        fluxes = pd.read_sql_query(
            """
            select d.step as offset, d.year as year, l.id as location_id,
                   mi.moduleName as module,
                   dt.disturbanceTypeName as disturbance_type,
                   src.poolName as source_pool, dst.poolName as sink_pool,
                   f.fluxValue as value
            from Fluxes f
            join LocationDimension l on f.locationDimId = l.id
            join DateDimension d on l.dateDimId = d.id
            join ModuleInfoDimension mi on f.moduleInfoDimId = mi.id
            join PoolDimension src on f.poolSrcDimId = src.id
            join PoolDimension dst on f.poolDstDimId = dst.id
            left join DisturbanceTypeDimension dt on f.disturbanceDimId = dt.id
            """,
            connection,
        )
        locations = pd.read_sql_query(
            """
            select l.id as location_id, l.classifierSetDimId as classifier_set_id,
                   l.dateDimId as date_id, l.landClassDimId as land_class_id,
                   l.ageClassDimId as age_class_id, l.area as area_ha
            from LocationDimension l
            """,
            connection,
        )
        classifiers = pd.read_sql_query("select * from ClassifierSetDimension", connection)
        dates = pd.read_sql_query("select * from DateDimension order by step", connection)
    except sqlite3.Error as exc:
        raise GcbmResultsError(f"cannot read {database}: {exc}") from exc
    finally:
        connection.close()
    return GcbmResults(
        path=database,
        sha256=hashlib.sha256(database.read_bytes()).hexdigest(),
        pools=pools,
        fluxes=fluxes,
        locations=locations,
        classifiers=classifiers,
        dates=dates,
    )


def gcbm_accounts(results: GcbmResults) -> pd.DataFrame:
    """Summarize GCBM pools into the WS4 ``carbon.*`` account names.

    Parameters
    ----------
    results : GcbmResults
        The GCBM results.

    Returns
    -------
    pandas.DataFrame
        ``offset``, ``account``, and ``value`` rows.
    """
    pools = results.pools.groupby(["offset", "pool"], sort=True)["value"].sum().unstack("pool")
    pools = pools.fillna(0.0)
    biomass = _sum(pools, BIOMASS_POOLS)
    dom = _sum(pools, DOM_POOLS)
    ecosystem = biomass + dom
    products = (
        pools["Products"] if "Products" in pools.columns else pd.Series(0.0, index=pools.index)
    )
    rows: list[dict[str, object]] = []
    for offset in pools.index:
        values = {
            "carbon.biomass.total": float(biomass.loc[offset]),
            "carbon.dom.total": float(dom.loc[offset]),
            "carbon.ecosystem.total": float(ecosystem.loc[offset]),
            "carbon.products.total": float(products.loc[offset]),
        }
        for account, value in values.items():
            rows.append({"offset": int(offset), "account": account, "value": value})
            rows.append(
                {
                    "offset": int(offset),
                    "account": account.replace("carbon.", "carbon.co2e.", 1),
                    "value": value * 44.0 / 12.0,
                }
            )
    accounts = pd.DataFrame(rows, columns=["offset", "account", "value"])
    ecosystem_rows = accounts.loc[accounts["account"] == "carbon.ecosystem.total"]
    change = ecosystem_rows["value"].diff().fillna(0.0)
    changes = pd.DataFrame(
        {
            "offset": ecosystem_rows["offset"].to_numpy(),
            "account": "carbon.stock.change",
            "value": change.to_numpy(),
        }
    )
    return pd.concat([accounts, changes], ignore_index=True)


def write_gcbm_results(
    results: GcbmResults,
    output_dir: Path,
) -> GcbmRunResult:
    """Write the GCBM pools, fluxes, accounts, and manifest.

    Parameters
    ----------
    results : GcbmResults
        The results.
    output_dir : Path
        Output directory.

    Returns
    -------
    GcbmRunResult
        The written files and totals.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    pools_path = root / "gcbm_pools.csv"
    fluxes_path = root / "gcbm_fluxes.csv"
    accounts_path = root / "gcbm_accounts.csv"
    manifest_path = root / "gcbm_manifest.json"
    results.pools.to_csv(pools_path, index=False)
    results.fluxes.to_csv(fluxes_path, index=False)
    accounts = gcbm_accounts(results)
    accounts.to_csv(accounts_path, index=False)
    ecosystem = accounts.loc[accounts["account"] == "carbon.ecosystem.total"]
    start = float(ecosystem["value"].iloc[0]) if not ecosystem.empty else 0.0
    end = float(ecosystem["value"].iloc[-1]) if not ecosystem.empty else 0.0
    manifest = {
        "source": str(results.path),
        "source_sha256": results.sha256,
        "locations": int(results.locations["location_id"].nunique()),
        "steps": int(results.dates["step"].nunique()),
        "start_year": int(results.dates["year"].min()),
        "end_year": int(results.dates["year"].max()),
        "units": {"carbon": "tC", "co2e": "tCO2e"},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return GcbmRunResult(
        output_dir=root,
        pools_path=pools_path,
        fluxes_path=fluxes_path,
        accounts_path=accounts_path,
        manifest_path=manifest_path,
        ecosystem_start_tc=start,
        ecosystem_end_tc=end,
    )


def compare_gcbm_to_carbon(
    gcbm_accounts_frame: pd.DataFrame,
    carbon_accounts_path: Path,
) -> pd.DataFrame:
    """Compare GCBM and WS4 carbon accounts by offset and account.

    Parameters
    ----------
    gcbm_accounts_frame : pandas.DataFrame
        GCBM accounts with ``offset``, ``account``, and ``value``.
    carbon_accounts_path : Path
        A WS4 ``carbon_accounts.csv``.

    Returns
    -------
    pandas.DataFrame
        ``offset``, ``account``, ``gcbm_tc``, ``ws4_tc``, ``difference_tc``, and
        ``relative`` rows for accounts present in both.
    """
    ws4 = pd.read_csv(carbon_accounts_path)
    merged = gcbm_accounts_frame.merge(
        ws4,
        on=["offset", "account"],
        how="inner",
        suffixes=("_gcbm", "_ws4"),
    )
    merged = merged.rename(columns={"value_gcbm": "gcbm_tc", "value_ws4": "ws4_tc"})
    merged["difference_tc"] = merged["gcbm_tc"] - merged["ws4_tc"]
    merged["relative"] = merged["difference_tc"] / merged["ws4_tc"].abs().clip(lower=1e-12)
    return merged.loc[:, ["offset", "account", "gcbm_tc", "ws4_tc", "difference_tc", "relative"]]


def _sum(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    """Sum the columns that exist."""
    present = [column for column in columns if column in frame.columns]
    if not present:
        return pd.Series(0.0, index=frame.index)
    return frame.loc[:, present].sum(axis=1)
