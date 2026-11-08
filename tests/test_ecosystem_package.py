"""Contract tests for the ``ws4.ecosystem.v1`` package, state, and null bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.ecosystem import (
    CohortState,
    CohortStateError,
    EcosystemPackage,
    EcosystemPackageError,
    NullBridge,
    StateError,
    StateSchema,
    find_ecosystem_package,
    load_dataset_ecosystem,
    load_ecosystem_package,
    package_fingerprint,
    validate_ecosystem_package,
)

STATE_ROWS: list[list[object]] = [
    ["name", "dtype", "scope", "unit", "default", "description"],
    ["species", "string", "cohort", "", "", "Species label"],
    ["age", "int", "cohort", "years", "", "Cohort age"],
    ["area_fraction", "float", "cohort", "", "", "Share of the fragment"],
    ["biomass_t_ha", "float", "cohort", "t/ha", "0.0", "Live biomass"],
    ["fuel_t_ha", "float", "cohort", "t/ha", "0.0", "Surface fuel"],
    ["snag_t_ha", "float", "cohort", "t/ha", "0.0", "Standing dead"],
    ["habitat_index", "float", "cohort", "", "0.5", "Synthetic habitat value"],
]

COHORT_ROWS: list[list[object]] = [
    [
        "fragment_id",
        "cohort_id",
        "species",
        "age",
        "area_fraction",
        "biomass_t_ha",
        "fuel_t_ha",
        "snag_t_ha",
        "attributes_json",
    ],
    [1, 1, "PL", 80, "0.7", "120.0", "30.0", "5.0", '{"habitat_index": 0.8}'],
    [1, 2, "PY", 20, "0.3", "40.0", "10.0", "2.0", "{}"],
    [2, 1, "PL", 60, "1.0", "90.0", "25.0", "4.0", "{}"],
]

BRIDGE_ROWS: list[list[object]] = [
    ["bridge_id", "type", "params_json", "state_reads", "state_writes"],
    ["null", "null", "{}", "", ""],
]


def write_package(
    root: Path,
    *,
    state_rows: list[list[object]] | None = None,
    cohort_rows: list[list[object]] | None = None,
    bridge_rows: list[list[object]] | None = None,
    manifest_overrides: dict[str, object] | None = None,
    hashes: bool = True,
) -> Path:
    """Write a synthetic ecosystem package and return its directory."""
    root.mkdir(parents=True, exist_ok=True)
    rows_by_name: dict[str, list[list[object]]] = {
        "state_variables": STATE_ROWS if state_rows is None else state_rows,
        "cohorts": COHORT_ROWS if cohort_rows is None else cohort_rows,
        "bridges": BRIDGE_ROWS if bridge_rows is None else bridge_rows,
    }
    for name, rows in rows_by_name.items():
        pd.DataFrame(rows[1:], columns=rows[0]).to_csv(root / f"{name}.csv", index=False)
    manifest: dict[str, object] = {
        "schema_version": "ws4.ecosystem.v1",
        "package_id": "synthetic",
        "created_utc": "2026-11-07T00:00:00Z",
        "producer": {"name": "test", "version": "1.0"},
        "sources": [{"path": "synthetic", "sha256": "a" * 64}],
    }
    if hashes:
        manifest["table_hashes"] = {
            name: hashlib.sha256((root / f"{name}.csv").read_bytes()).hexdigest()
            for name in rows_by_name
        }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def write_dataset(root: Path, fragments: pd.DataFrame | None = None) -> Path:
    """Write a minimal compiled dataset with a fragments table."""
    root.mkdir(parents=True, exist_ok=True)
    frame = (
        pd.DataFrame({"fragment_id": [1, 2, 3], "area_ha": [10.0, 5.0, 2.0]})
        if fragments is None
        else fragments
    )
    frame.to_parquet(root / "fragments.parquet", index=False)
    return root


def package_codes(path: Path) -> set[str]:
    """Return the finding codes of a package validation."""
    return {finding.code for finding in validate_ecosystem_package(path)}


def test_valid_package_loads_and_exposes_its_contract(tmp_path: Path) -> None:
    package = load_ecosystem_package(write_package(tmp_path))

    assert isinstance(package, EcosystemPackage)
    assert package.manifest.package_id == "synthetic"
    assert package.state_variable("species").dtype == "string"
    assert package.state_variable("biomass_t_ha").default == 0.0
    assert package.bridge().bridge_id == "null"
    assert package.bridge("null").type == "null"
    assert isinstance(package.null_bridge(), NullBridge)
    assert package.table("cohorts").shape[0] == 3


def test_package_fingerprint_is_stable(tmp_path: Path) -> None:
    first = load_ecosystem_package(write_package(tmp_path / "a"))
    second = load_ecosystem_package(write_package(tmp_path / "b"))

    assert package_fingerprint(first) == first.fingerprint
    assert first.fingerprint == second.fingerprint


def test_optional_process_file_is_hashed_and_recorded(tmp_path: Path) -> None:
    root = write_package(tmp_path)
    (root / "processes.yaml").write_text("processes: []\n", encoding="utf-8")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["processes"] = "processes.yaml"
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    package = load_ecosystem_package(root)

    assert "processes" in package.table_hashes
    assert package.manifest.processes == "processes.yaml"


def test_cohort_state_aggregates_area_weighted_values(tmp_path: Path) -> None:
    package = load_ecosystem_package(write_package(tmp_path))
    state = package.cohort_state_from_areas({1: 10.0, 2: 5.0, 3: 2.0})

    aggregate = state.aggregate_to_fragments().set_index("fragment_id")

    assert aggregate.loc[1, "age"] == pytest.approx(62.0)
    assert aggregate.loc[1, "biomass_t_ha"] == pytest.approx(96.0)
    assert aggregate.loc[1, "fuel_t_ha"] == pytest.approx(24.0)
    assert aggregate.loc[1, "snag_t_ha"] == pytest.approx(4.1)
    assert aggregate.loc[2, "age"] == pytest.approx(60.0)
    assert state.missing_fragments() == (3,)
    state.check_area_conservation()


def test_cohort_state_reports_species_fractions_and_areas(tmp_path: Path) -> None:
    package = load_ecosystem_package(write_package(tmp_path))
    state = package.cohort_state_from_areas({1: 10.0, 2: 5.0})

    species = state.species_fractions().set_index(["fragment_id", "species"])
    areas = state.cohort_areas().set_index(["fragment_id", "cohort_id"])

    assert species.loc[(1, "PL"), "area_fraction"] == pytest.approx(0.7)
    assert species.loc[(1, "PY"), "area_fraction"] == pytest.approx(0.3)
    assert species.loc[(1, "PL"), "area_ha"] == pytest.approx(7.0)
    assert areas.loc[(1, 1), "area_ha"] == pytest.approx(7.0)
    assert areas.loc[(1, 2), "area_ha"] == pytest.approx(3.0)


def test_cohort_state_joins_a_compiled_dataset(tmp_path: Path) -> None:
    dataset = write_dataset(tmp_path / "dataset")
    package = load_ecosystem_package(write_package(dataset / "ecosystem"))

    state = package.cohort_state(dataset)

    assert state.fragment_areas == {1: 10.0, 2: 5.0, 3: 2.0}
    assert state.missing_fragments() == (3,)
    assert find_ecosystem_package(dataset) == dataset / "ecosystem"
    assert load_dataset_ecosystem(dataset) is not None


def test_dataset_without_a_package_returns_none(tmp_path: Path) -> None:
    dataset = write_dataset(tmp_path / "dataset")

    assert find_ecosystem_package(dataset) is None
    assert load_dataset_ecosystem(dataset) is None


def test_null_bridge_leaves_management_unchanged(tmp_path: Path) -> None:
    package = load_ecosystem_package(write_package(tmp_path))
    management = pd.DataFrame({"fragment_id": [1, 2], "track_id": [4, 5]})
    ecological = package.cohort_state_from_areas({1: 10.0, 2: 5.0}).aggregate_to_fragments()

    result = package.null_bridge().apply(management, ecological)

    assert result.equals(management)
    assert result is not management


def test_empty_cohort_table_is_valid(tmp_path: Path) -> None:
    root = write_package(tmp_path, cohort_rows=[COHORT_ROWS[0]])
    package = load_ecosystem_package(root)
    state = package.cohort_state_from_areas({1: 10.0})

    assert state.aggregate_to_fragments().empty
    assert state.species_fractions().empty
    assert state.missing_fragments() == (1,)
    state.check_area_conservation()


def test_missing_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(EcosystemPackageError, match="not found"):
        load_ecosystem_package(tmp_path / "missing")


def test_missing_manifest_is_rejected(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)

    with pytest.raises(EcosystemPackageError, match=r"manifest\.json"):
        load_ecosystem_package(tmp_path)


def test_malformed_manifest_is_rejected(tmp_path: Path) -> None:
    root = write_package(tmp_path)
    (root / "manifest.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(EcosystemPackageError, match="BAD-MANIFEST"):
        load_ecosystem_package(root)


def test_unknown_manifest_field_is_rejected(tmp_path: Path) -> None:
    root = write_package(tmp_path, manifest_overrides={"surprise": True})

    with pytest.raises(EcosystemPackageError, match="BAD-MANIFEST"):
        load_ecosystem_package(root)


def test_wrong_schema_version_is_reported(tmp_path: Path) -> None:
    root = write_package(tmp_path, manifest_overrides={"schema_version": "0.1"})

    assert "ECOSYSTEM-SCHEMA-VERSION" in package_codes(root)


def test_missing_table_is_reported(tmp_path: Path) -> None:
    root = write_package(tmp_path)
    (root / "cohorts.csv").unlink()

    assert "ECOSYSTEM-MISSING-TABLE" in package_codes(root)


def test_missing_column_is_reported(tmp_path: Path) -> None:
    root = write_package(tmp_path)
    frame = pd.read_csv(root / "state_variables.csv", keep_default_na=False)
    frame.drop(columns=["unit"]).to_csv(root / "state_variables.csv", index=False)

    assert "ECOSYSTEM-MISSING-COLUMN" in package_codes(root)


def test_extra_column_is_reported(tmp_path: Path) -> None:
    root = write_package(tmp_path)
    frame = pd.read_csv(root / "bridges.csv", keep_default_na=False)
    frame["extra"] = "x"
    frame.to_csv(root / "bridges.csv", index=False)

    assert "ECOSYSTEM-EXTRA-COLUMN" in package_codes(root)


def test_non_csv_table_is_reported(tmp_path: Path) -> None:
    root = write_package(
        tmp_path,
        manifest_overrides={"table_files": {"cohorts": "cohorts.parquet"}},
        hashes=False,
    )
    (root / "cohorts.parquet").write_bytes(b"not a parquet")

    assert "ECOSYSTEM-TABLE-FORMAT" in package_codes(root)


def test_unknown_table_file_is_reported(tmp_path: Path) -> None:
    root = write_package(
        tmp_path,
        manifest_overrides={"table_files": {"surprise": "surprise.csv"}},
    )

    assert "ECOSYSTEM-UNKNOWN-TABLE" in package_codes(root)


def test_duplicate_state_variable_is_rejected(tmp_path: Path) -> None:
    state_rows: list[list[object]] = [
        *STATE_ROWS,
        ["species", "string", "cohort", "", "", "duplicate"],
    ]
    root = write_package(tmp_path, state_rows=state_rows)

    with pytest.raises(EcosystemPackageError, match="duplicate state variable"):
        load_ecosystem_package(root)


def test_missing_required_state_variable_is_rejected(tmp_path: Path) -> None:
    state_rows = [row for row in STATE_ROWS if row[0] != "fuel_t_ha"]
    root = write_package(tmp_path, state_rows=state_rows)

    assert "ECOSYSTEM-STATE-MISSING" in package_codes(root)


def test_bad_state_dtype_is_rejected(tmp_path: Path) -> None:
    state_rows = [list(row) for row in STATE_ROWS]
    state_rows[1][1] = "category"
    root = write_package(tmp_path, state_rows=state_rows)

    assert "ECOSYSTEM-STATE" in package_codes(root)


def test_bad_state_scope_is_rejected(tmp_path: Path) -> None:
    state_rows = [list(row) for row in STATE_ROWS]
    state_rows[1][2] = "planet"
    root = write_package(tmp_path, state_rows=state_rows)

    assert "ECOSYSTEM-STATE" in package_codes(root)


def test_bad_state_default_is_rejected(tmp_path: Path) -> None:
    state_rows = [list(row) for row in STATE_ROWS]
    state_rows[3][4] = "not-a-number"
    root = write_package(tmp_path, state_rows=state_rows)

    assert "ECOSYSTEM-STATE" in package_codes(root)


def test_missing_bridge_is_rejected(tmp_path: Path) -> None:
    root = write_package(tmp_path, bridge_rows=[BRIDGE_ROWS[0]])

    assert "ECOSYSTEM-BRIDGE-MISSING" in package_codes(root)


def test_unsupported_bridge_type_is_rejected(tmp_path: Path) -> None:
    bridge_rows: list[list[object]] = [BRIDGE_ROWS[0], ["yield", "yield", "{}", "", "species"]]
    root = write_package(tmp_path, bridge_rows=bridge_rows)

    assert "ECOSYSTEM-BRIDGE" in package_codes(root)


def test_bridge_unknown_state_variable_is_rejected(tmp_path: Path) -> None:
    bridge_rows: list[list[object]] = [BRIDGE_ROWS[0], ["null", "null", "{}", "invented", ""]]
    root = write_package(tmp_path, bridge_rows=bridge_rows)

    assert "ECOSYSTEM-BRIDGE" in package_codes(root)


def test_null_bridge_must_not_write_state(tmp_path: Path) -> None:
    bridge_rows: list[list[object]] = [BRIDGE_ROWS[0], ["null", "null", "{}", "", "species"]]
    root = write_package(tmp_path, bridge_rows=bridge_rows)

    assert "ECOSYSTEM-BRIDGE" in package_codes(root)


def test_duplicate_cohort_is_reported(tmp_path: Path) -> None:
    cohort_rows = [
        *COHORT_ROWS,
        [1, 1, "PL", 80, "0.1", "120.0", "30.0", "5.0", "{}"],
    ]
    root = write_package(tmp_path, cohort_rows=cohort_rows, hashes=False)

    assert "ECOSYSTEM-DUPLICATE" in package_codes(root)


def test_bad_cohort_fraction_is_reported(tmp_path: Path) -> None:
    cohort_rows = [list(row) for row in COHORT_ROWS]
    cohort_rows[1][4] = "0.5"
    root = write_package(tmp_path, cohort_rows=cohort_rows, hashes=False)

    assert "ECOSYSTEM-COHORT-FRACTION" in package_codes(root)


def test_bad_cohort_attribute_is_reported(tmp_path: Path) -> None:
    cohort_rows = [list(row) for row in COHORT_ROWS]
    cohort_rows[1][8] = '{"invented": 1}'
    root = write_package(tmp_path, cohort_rows=cohort_rows, hashes=False)

    assert "ECOSYSTEM-COHORT" in package_codes(root)


def test_fixed_cohort_attribute_is_reported(tmp_path: Path) -> None:
    cohort_rows = [list(row) for row in COHORT_ROWS]
    cohort_rows[1][8] = '{"age": 1}'
    root = write_package(tmp_path, cohort_rows=cohort_rows, hashes=False)

    assert "ECOSYSTEM-COHORT" in package_codes(root)


def test_blank_cohort_value_without_a_default_is_reported(tmp_path: Path) -> None:
    state_rows = [list(row) for row in STATE_ROWS]
    state_rows[4][4] = ""
    cohort_rows = [list(row) for row in COHORT_ROWS]
    cohort_rows[1][5] = ""
    root = write_package(tmp_path, state_rows=state_rows, cohort_rows=cohort_rows, hashes=False)

    assert "ECOSYSTEM-COHORT" in package_codes(root)


def test_bad_hash_is_reported(tmp_path: Path) -> None:
    root = write_package(tmp_path)
    frame = pd.read_csv(root / "cohorts.csv", keep_default_na=False)
    frame.loc[0, "age"] = 99
    frame.to_csv(root / "cohorts.csv", index=False)

    assert "ECOSYSTEM-HASH" in package_codes(root)


def test_bad_source_hash_is_reported(tmp_path: Path) -> None:
    root = write_package(
        tmp_path,
        manifest_overrides={"sources": [{"path": "synthetic", "sha256": "abc"}]},
    )

    assert "ECOSYSTEM-SOURCE-HASH" in package_codes(root)


def test_empty_producer_is_reported(tmp_path: Path) -> None:
    root = write_package(
        tmp_path,
        manifest_overrides={"producer": {"name": "", "version": "1"}},
    )

    assert "ECOSYSTEM-PRODUCER" in package_codes(root)


def test_bad_timestamp_is_reported(tmp_path: Path) -> None:
    root = write_package(
        tmp_path,
        manifest_overrides={"created_utc": "not-a-timestamp"},
    )

    assert "ECOSYSTEM-TIMESTAMP" in package_codes(root)


def test_empty_package_id_is_reported(tmp_path: Path) -> None:
    root = write_package(tmp_path, manifest_overrides={"package_id": ""})

    assert "ECOSYSTEM-PACKAGE-ID" in package_codes(root)


def test_unknown_cohort_fragment_is_rejected(tmp_path: Path) -> None:
    package = load_ecosystem_package(write_package(tmp_path))

    with pytest.raises(CohortStateError, match="outside the dataset"):
        package.cohort_state_from_areas({1: 10.0})


def test_dataset_without_fragments_is_rejected(tmp_path: Path) -> None:
    package = load_ecosystem_package(write_package(tmp_path / "package"))
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    with pytest.raises(CohortStateError, match=r"fragments\.parquet"):
        package.cohort_state(dataset)


def test_dataset_without_area_column_is_rejected(tmp_path: Path) -> None:
    package = load_ecosystem_package(write_package(tmp_path / "package"))
    dataset = write_dataset(tmp_path / "dataset", pd.DataFrame({"fragment_id": [1, 2]}))

    with pytest.raises(CohortStateError, match="area_ha"):
        package.cohort_state(dataset)


def test_state_schema_rejects_an_unknown_variable() -> None:
    schema = StateSchema(variables={}, bridges=())

    with pytest.raises(KeyError):
        schema.variable("missing")
    with pytest.raises(StateError, match="no bridge"):
        schema.bridge()
    with pytest.raises(StateError, match="no null bridge"):
        schema.null_bridge()
    with pytest.raises(StateError, match="unknown bridge"):
        schema.bridge("missing")


def test_cohort_state_rejects_a_bad_fragment_area() -> None:
    with pytest.raises(CohortStateError, match="positive"):
        CohortState.from_tables(
            pd.DataFrame(),
            _empty_schema(),
            {0: 1.0},
        )
    with pytest.raises(CohortStateError, match="finite and positive"):
        CohortState.from_tables(
            pd.DataFrame(),
            _empty_schema(),
            {1: 0.0},
        )


def _empty_schema() -> StateSchema:
    return StateSchema(variables={}, bridges=())
