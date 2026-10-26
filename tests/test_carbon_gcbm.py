"""Tests for the GCBM results reader and comparison."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from ws4.carbon.gcbm import (
    GcbmResultsError,
    gcbm_accounts,
    read_gcbm_results,
    write_gcbm_results,
)


def _database(tmp_path: Path) -> Path:
    """Create a minimal GCBM-shaped results database."""
    path = tmp_path / "gcbm_output.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        create table PoolDimension (id integer primary key, poolName text);
        create table DateDimension (id integer primary key, step integer, year integer,
            month integer, day integer, fracOfStep real, lengthOfStepInYears real);
        create table ClassifierSetDimension (id integer primary key, Classifier1 text);
        create table LocationDimension (id integer primary key, classifierSetDimId integer,
            dateDimId integer, landClassDimId integer, ageClassDimId integer, area real);
        create table Pools (id integer primary key, locationDimId integer, poolId integer,
            poolValue real);
        create table ModuleInfoDimension (id integer primary key, libraryType integer,
            libraryInfoId integer, moduleType integer, moduleId integer, moduleName text);
        create table DisturbanceTypeDimension (id integer primary key,
            disturbanceType text, disturbanceTypeName text);
        create table Fluxes (id integer primary key, locationDimId integer,
            moduleInfoDimId integer, disturbanceDimId integer, poolSrcDimId integer,
            poolDstDimId integer, fluxValue real);
        """
    )
    connection.executemany(
        "insert into PoolDimension (id, poolName) values (?, ?)",
        [(1, "SoftwoodMerch"), (2, "AboveGroundSlowSoil"), (3, "Products"), (4, "Atmosphere")],
    )
    connection.executemany(
        "insert into DateDimension values (?, ?, ?, 0, 0, 0, 1)",
        [(1, 0, 0), (2, 1, 2010)],
    )
    connection.execute("insert into ClassifierSetDimension values (1, 'A')")
    connection.executemany(
        "insert into LocationDimension values (?, 1, ?, 1, 1, 10.0)",
        [(1, 1), (2, 2)],
    )
    connection.executemany(
        "insert into Pools (locationDimId, poolId, poolValue) values (?, ?, ?)",
        [(1, 1, 10.0), (1, 2, 5.0), (2, 1, 11.0), (2, 2, 5.0), (2, 3, 1.0)],
    )
    connection.execute("insert into ModuleInfoDimension values (1, 3, 14, 0, 6, 'CBMGrowthModule')")
    connection.execute("insert into DisturbanceTypeDimension values (1, '1', 'Wildfire')")
    connection.execute("insert into Fluxes values (1, 2, 1, null, 1, 2, 0.5)")
    connection.commit()
    connection.close()
    return path


def test_read_gcbm_results_and_accounts(tmp_path: Path) -> None:
    """The reader joins locations and dates and the accounts total the pools."""
    results = read_gcbm_results(_database(tmp_path))
    assert results.pools.shape[0] == 5
    assert results.fluxes.shape[0] == 1
    accounts = gcbm_accounts(results)
    by_name = accounts.set_index(["offset", "account"])["value"]
    assert by_name.loc[(0, "carbon.biomass.total")] == 10.0
    assert by_name.loc[(0, "carbon.ecosystem.total")] == 15.0
    assert by_name.loc[(1, "carbon.biomass.total")] == 11.0
    assert by_name.loc[(1, "carbon.products.total")] == 1.0
    assert by_name.loc[(1, "carbon.ecosystem.total")] == 16.0
    assert by_name.loc[(1, "carbon.stock.change")] == 1.0


def test_write_gcbm_results(tmp_path: Path) -> None:
    """The writer writes the pools, fluxes, accounts, and manifest."""
    results = read_gcbm_results(_database(tmp_path))
    summary = write_gcbm_results(results, tmp_path / "out")
    assert summary.pools_path.is_file()
    assert summary.fluxes_path.is_file()
    assert summary.accounts_path.is_file()
    assert summary.manifest_path.is_file()
    assert summary.ecosystem_start_tc == 15.0
    assert summary.ecosystem_end_tc == 16.0


def test_read_gcbm_results_rejects_missing_tables(tmp_path: Path) -> None:
    """A non-GCBM SQLite file is rejected with a clear error."""
    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    with pytest.raises(GcbmResultsError, match="missing tables"):
        read_gcbm_results(path)
