"""Load and validate the optional ``ws4.ecosystem.v1`` package.

The compiled management dataset is the contract. The ecosystem package is an optional sidecar
that declares the ecological state variables, the cohort table, and the bridge back to the
management state. This module owns the package manifest, the table contract, the load and
validation path, and the dataset join. A dataset with no package is valid and unchanged.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..model.schema import Problem
from .state import (
    BridgeSpec,
    CohortState,
    CohortStateError,
    NullBridge,
    StateSchema,
    StateVariable,
    _parse_state_schema,
    _typed_cohorts,
    problem,
)

SCHEMA_VERSION: Final[str] = "ws4.ecosystem.v1"
MANIFEST_NAME: Final[str] = "manifest.json"
PACKAGE_DIRECTORY: Final[str] = "ecosystem"

DEFAULT_TABLE_FILES: Final[dict[str, str]] = {
    "state_variables": "state_variables.csv",
    "cohorts": "cohorts.csv",
    "bridges": "bridges.csv",
}
OPTIONAL_FILES: Final[tuple[str, ...]] = ("processes", "scenarios", "calibration")


@dataclass(frozen=True)
class EcosystemTable:
    """One required table of an ecosystem package.

    Attributes
    ----------
    name : str
        Logical table name.
    file : str
        Default file name inside the package directory.
    columns : tuple of str
        Required columns. Extra columns are rejected.
    key : tuple of str
        Columns that must be jointly unique.
    """

    name: str
    file: str
    columns: tuple[str, ...]
    key: tuple[str, ...] = ()


TABLES: tuple[EcosystemTable, ...] = (
    EcosystemTable(
        "state_variables",
        "state_variables.csv",
        ("name", "dtype", "scope", "unit", "default", "description"),
        ("name",),
    ),
    EcosystemTable(
        "cohorts",
        "cohorts.csv",
        (
            "fragment_id",
            "cohort_id",
            "species",
            "age",
            "area_fraction",
            "biomass_t_ha",
            "fuel_t_ha",
            "snag_t_ha",
            "attributes_json",
        ),
        ("fragment_id", "cohort_id"),
    ),
    EcosystemTable(
        "bridges",
        "bridges.csv",
        ("bridge_id", "type", "params_json", "state_reads", "state_writes"),
        ("bridge_id",),
    ),
)

TABLES_BY_NAME: Final[dict[str, EcosystemTable]] = {table.name: table for table in TABLES}


class _Model(BaseModel):
    """Base manifest model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class EcosystemProducer(_Model):
    """The producer of an ecosystem package.

    Attributes
    ----------
    name : str
        Producer name.
    version : str
        Producer version.
    """

    name: str
    version: str


class EcosystemSource(_Model):
    """One upstream source of an ecosystem package.

    Attributes
    ----------
    path : str
        Public-safe source label.
    sha256 : str
        Hex SHA-256 digest of the source.
    """

    path: str
    sha256: str


class EcosystemManifest(_Model):
    """The manifest of an ecosystem package.

    Attributes
    ----------
    schema_version : str
        Package schema version.
    package_id : str
        Producer-assigned package identifier.
    created_utc : str
        Creation timestamp in ISO-8601 form.
    producer : EcosystemProducer
        The producer.
    sources : list of EcosystemSource
        Upstream sources and their hashes.
    table_files : dict of str to str
        Table name to file name.
    table_hashes : dict of str to str
        Optional table name to SHA-256 digest.
    processes : str or None
        Optional process-definition file, recorded but not loaded yet.
    scenarios : str or None
        Optional scenario-definition file, recorded but not loaded yet.
    calibration : str or None
        Optional calibration file, recorded but not loaded yet.
    metadata : dict of str to object
        Free-form, public-safe metadata.
    """

    schema_version: str
    package_id: str
    created_utc: str
    producer: EcosystemProducer
    sources: list[EcosystemSource] = Field(default_factory=list)
    table_files: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_TABLE_FILES))
    table_hashes: dict[str, str] = Field(default_factory=dict)
    processes: str | None = None
    scenarios: str | None = None
    calibration: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True)
class EcosystemPackage:
    """A loaded and optionally validated ecosystem package.

    Attributes
    ----------
    path : Path
        Package directory.
    manifest : EcosystemManifest
        Parsed manifest.
    tables : dict of str to pandas.DataFrame
        Loaded tables by logical name.
    table_hashes : dict of str to str
        SHA-256 digest of every loaded table and optional file.
    fingerprint : str
        Stable digest of the manifest and every loaded file.
    schema : StateSchema
        The parsed state variables and bridges.
    """

    path: Path
    manifest: EcosystemManifest
    tables: dict[str, pd.DataFrame]
    table_hashes: dict[str, str]
    fingerprint: str
    schema: StateSchema

    def table(self, name: str) -> pd.DataFrame:
        """Return one loaded table.

        Parameters
        ----------
        name : str
            The logical table name.

        Returns
        -------
        pandas.DataFrame
            The table.

        Raises
        ------
        KeyError
            If the table was not loaded.
        """
        return self.tables[name]

    def state_variable(self, name: str) -> StateVariable:
        """Return one declared state variable.

        Parameters
        ----------
        name : str
            The variable name.

        Returns
        -------
        StateVariable
            The declared variable.

        Raises
        ------
        KeyError
            If the variable is not declared.
        """
        return self.schema.variable(name)

    def bridge(self, bridge_id: str | None = None) -> BridgeSpec:
        """Return a declared bridge, by id or the first one.

        Parameters
        ----------
        bridge_id : str or None, optional
            The bridge identifier. None returns the first bridge.

        Returns
        -------
        BridgeSpec
            The bridge specification.
        """
        return self.schema.bridge(bridge_id)

    def null_bridge(self) -> NullBridge:
        """Return the first null bridge.

        Returns
        -------
        NullBridge
            The null bridge.
        """
        return self.schema.null_bridge()

    def cohort_state_from_areas(self, fragment_areas: Mapping[int, float]) -> CohortState:
        """Build the typed cohort state from an explicit fragment-area mapping.

        Parameters
        ----------
        fragment_areas : mapping of int to float
            The area of every dataset fragment, in hectares.

        Returns
        -------
        CohortState
            The typed cohort state.

        Raises
        ------
        CohortStateError
            If the cohort table or a fragment area is invalid.
        """
        return CohortState.from_tables(self.table("cohorts"), self.schema, fragment_areas)

    def cohort_state(self, dataset_dir: Path) -> CohortState:
        """Build the typed cohort state against a compiled dataset.

        Parameters
        ----------
        dataset_dir : Path
            The compiled dataset directory. The package reads only ``fragments.parquet``.

        Returns
        -------
        CohortState
            The typed cohort state.

        Raises
        ------
        CohortStateError
            If the dataset fragment table is missing a required column or a cohort names an
            unknown fragment.
        """
        fragments_path = Path(dataset_dir) / "fragments.parquet"
        if not fragments_path.is_file():
            raise CohortStateError(
                [
                    problem(
                        "ECOSYSTEM-DATASET-MISSING",
                        str(fragments_path),
                        "the compiled dataset has no fragments.parquet",
                    )
                ]
            )
        try:
            fragments = pd.read_parquet(fragments_path, columns=["fragment_id", "area_ha"])
        except (KeyError, OSError, ValueError) as error:
            raise CohortStateError(
                [
                    problem(
                        "ECOSYSTEM-DATASET-COLUMNS",
                        str(fragments_path),
                        f"fragment_id and area_ha are required: {error}",
                    )
                ]
            ) from error
        areas = {
            int(str(row.fragment_id)): float(str(row.area_ha))
            for row in fragments.itertuples(index=False)
        }
        return self.cohort_state_from_areas(areas)


class EcosystemPackageError(ValueError):
    """Raised when an ecosystem package cannot be loaded or validated.

    Parameters
    ----------
    findings : sequence of Problem
        The validation findings.
    """

    def __init__(self, findings: Sequence[Problem]) -> None:
        """Store the findings and build a readable message."""
        self.findings: tuple[Problem, ...] = tuple(findings)
        message = "; ".join(f"{item.code}: {item.message}" for item in self.findings)
        super().__init__(message or "invalid ecosystem package")


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file.

    Parameters
    ----------
    path : Path
        The file.

    Returns
    -------
    str
        The hex digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_digest(value: str) -> bool:
    """Return whether a string is a 64-character hexadecimal digest.

    Parameters
    ----------
    value : str
        The candidate digest.

    Returns
    -------
    bool
        True when the value is a SHA-256 hex digest.
    """
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _read_table(path: Path) -> pd.DataFrame:
    """Read a package CSV as strings, preserving leading zeros and empty cells.

    Parameters
    ----------
    path : Path
        The CSV file.

    Returns
    -------
    pandas.DataFrame
        The table with stripped string columns.
    """
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    for column in frame.columns:
        frame[column] = frame[column].astype(str).str.strip()
    return frame


def _manifest_path(root: Path) -> Path:
    """Return the manifest path of a package directory.

    Parameters
    ----------
    root : Path
        The package directory.

    Returns
    -------
    Path
        The manifest path.
    """
    return root / MANIFEST_NAME


def _package_fingerprint(root: Path, table_hashes: Mapping[str, str]) -> str:
    """Return a stable digest of the manifest and the loaded files.

    Parameters
    ----------
    root : Path
        The package directory.
    table_hashes : mapping of str to str
        The digest of each loaded table and optional file.

    Returns
    -------
    str
        The hex SHA-256 digest.
    """
    digest = hashlib.sha256()
    manifest = _manifest_path(root)
    if manifest.is_file():
        digest.update(manifest.read_bytes())
    for name in sorted(table_hashes):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(table_hashes[name].encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _load_manifest(root: Path, findings: list[Problem]) -> EcosystemManifest | None:
    """Load and parse the package manifest.

    Parameters
    ----------
    root : Path
        The package directory.
    findings : list of Problem
        The finding list to extend.

    Returns
    -------
    EcosystemManifest or None
        The manifest, or None when it is missing or malformed.
    """
    path = _manifest_path(root)
    if not path.is_file():
        findings.append(
            problem("ECOSYSTEM-MISSING-MANIFEST", str(path), "manifest.json was not found")
        )
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        findings.append(problem("ECOSYSTEM-BAD-MANIFEST", str(path), str(error)))
        return None
    try:
        return EcosystemManifest.model_validate(payload)
    except ValidationError as error:
        findings.append(problem("ECOSYSTEM-BAD-MANIFEST", str(path), str(error)))
        return None


def _load_tables(
    root: Path, manifest: EcosystemManifest, findings: list[Problem]
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Load the required tables and record every optional file hash.

    Parameters
    ----------
    root : Path
        The package directory.
    manifest : EcosystemManifest
        The parsed manifest.
    findings : list of Problem
        The finding list to extend.

    Returns
    -------
    tuple of (dict, dict)
        The tables by logical name and the SHA-256 digest of every loaded file.
    """
    unknown = sorted(set(manifest.table_files) - set(DEFAULT_TABLE_FILES))
    for name in unknown:
        findings.append(
            problem("ECOSYSTEM-UNKNOWN-TABLE", name, "the manifest names an unknown table")
        )
    tables: dict[str, pd.DataFrame] = {}
    hashes: dict[str, str] = {}
    for table in TABLES:
        file_name = manifest.table_files.get(table.name, table.file)
        path = root / file_name
        if not path.is_file():
            findings.append(
                problem("ECOSYSTEM-MISSING-TABLE", str(path), f"{table.name} table not found")
            )
            continue
        if path.suffix.lower() != ".csv":
            findings.append(
                problem(
                    "ECOSYSTEM-TABLE-FORMAT",
                    str(path),
                    "package tables must be CSV",
                )
            )
            continue
        hashes[table.name] = _sha256(path)
        try:
            frame = _read_table(path)
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
            findings.append(problem("ECOSYSTEM-BAD-TABLE", str(path), str(error)))
            continue
        missing = [column for column in table.columns if column not in frame.columns]
        if missing:
            findings.append(
                problem(
                    "ECOSYSTEM-MISSING-COLUMN",
                    str(path),
                    f"missing columns: {', '.join(missing)}",
                )
            )
            continue
        tables[table.name] = frame
    for name in OPTIONAL_FILES:
        file_name = getattr(manifest, name)
        if file_name is None:
            continue
        path = root / file_name
        if not path.is_file():
            findings.append(problem("ECOSYSTEM-MISSING-TABLE", str(path), f"{name} file not found"))
            continue
        hashes[name] = _sha256(path)
    return tables, hashes


def load_ecosystem_package(path: Path, *, validate: bool = True) -> EcosystemPackage:
    """Load an ecosystem package from a directory.

    Parameters
    ----------
    path : Path
        Package directory.
    validate : bool, optional
        Validate the package before returning it. Defaults to True.

    Returns
    -------
    EcosystemPackage
        The loaded package.

    Raises
    ------
    EcosystemPackageError
        When the package is missing, malformed, or invalid.
    """
    root = Path(path)
    findings: list[Problem] = []
    if not root.is_dir():
        raise EcosystemPackageError(
            [problem("ECOSYSTEM-MISSING-DIR", str(root), "package directory not found")]
        )
    manifest = _load_manifest(root, findings)
    if manifest is None:
        raise EcosystemPackageError(findings)
    tables, hashes = _load_tables(root, manifest, findings)
    if findings:
        raise EcosystemPackageError(findings)
    schema, schema_findings = _parse_state_schema(tables["state_variables"], tables["bridges"])
    if schema_findings:
        raise EcosystemPackageError(schema_findings)
    package = EcosystemPackage(
        path=root,
        manifest=manifest,
        tables=tables,
        table_hashes=hashes,
        fingerprint=_package_fingerprint(root, hashes),
        schema=schema,
    )
    if validate:
        findings.extend(_validate(package))
        if findings:
            raise EcosystemPackageError(findings)
    return package


def validate_ecosystem_package(path: Path) -> list[Problem]:
    """Validate an ecosystem package and return every finding.

    Parameters
    ----------
    path : Path
        Package directory.

    Returns
    -------
    list of Problem
        Every finding. An empty list means the package is valid.
    """
    try:
        package = load_ecosystem_package(path, validate=False)
    except EcosystemPackageError as exc:
        return list(exc.findings)
    return _validate(package)


def package_fingerprint(package: EcosystemPackage) -> str:
    """Return the stable fingerprint of a loaded package.

    Parameters
    ----------
    package : EcosystemPackage
        The loaded package.

    Returns
    -------
    str
        The hex SHA-256 digest.
    """
    return package.fingerprint


def find_ecosystem_package(dataset_dir: Path) -> Path | None:
    """Return the ecosystem package directory of a dataset, when one exists.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset directory.

    Returns
    -------
    Path or None
        The package directory, or None when the dataset has no ecosystem sidecar.
    """
    candidate = Path(dataset_dir) / PACKAGE_DIRECTORY
    return candidate if _manifest_path(candidate).is_file() else None


def load_dataset_ecosystem(dataset_dir: Path) -> EcosystemPackage | None:
    """Load a dataset's optional ecosystem package.

    A dataset with no package returns None, which is the backward-compatibility contract:
    the deterministic management model behaves exactly as it did before.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset directory.

    Returns
    -------
    EcosystemPackage or None
        The package, or None when the dataset has no ecosystem sidecar.

    Raises
    ------
    EcosystemPackageError
        When the package exists but is invalid.
    """
    package_path = find_ecosystem_package(dataset_dir)
    return None if package_path is None else load_ecosystem_package(package_path)


def _validate(package: EcosystemPackage) -> list[Problem]:
    """Validate a loaded package and return every finding.

    Parameters
    ----------
    package : EcosystemPackage
        The loaded package.

    Returns
    -------
    list of Problem
        The findings.
    """
    findings: list[Problem] = []
    manifest = package.manifest
    if manifest.schema_version != SCHEMA_VERSION:
        findings.append(
            problem(
                "ECOSYSTEM-SCHEMA-VERSION",
                "manifest.schema_version",
                f"expected {SCHEMA_VERSION!r}, found {manifest.schema_version!r}",
            )
        )
    if not manifest.package_id.strip():
        findings.append(
            problem("ECOSYSTEM-PACKAGE-ID", "manifest.package_id", "package_id must be non-empty")
        )
    try:
        datetime.fromisoformat(manifest.created_utc.replace("Z", "+00:00"))
    except ValueError:
        findings.append(
            problem(
                "ECOSYSTEM-TIMESTAMP",
                "manifest.created_utc",
                "created_utc must be ISO-8601",
            )
        )
    if not manifest.producer.name.strip() or not manifest.producer.version.strip():
        findings.append(
            problem(
                "ECOSYSTEM-PRODUCER",
                "manifest.producer",
                "producer name and version must be non-empty",
            )
        )
    for index, source in enumerate(manifest.sources):
        if not source.path.strip():
            findings.append(
                problem(
                    "ECOSYSTEM-SOURCE",
                    f"manifest.sources[{index}].path",
                    "source path label must be non-empty",
                )
            )
        if not _is_digest(source.sha256):
            findings.append(
                problem(
                    "ECOSYSTEM-SOURCE-HASH",
                    f"manifest.sources[{index}].sha256",
                    "source digest must be a 64-character SHA-256",
                )
            )
    for name, declared in sorted(manifest.table_hashes.items()):
        actual = package.table_hashes.get(name)
        if actual is None:
            findings.append(
                problem("ECOSYSTEM-HASH", name, "the manifest declares a hash for a missing file")
            )
        elif actual != declared:
            findings.append(
                problem("ECOSYSTEM-HASH", name, "the file digest does not match the manifest")
            )
    for name, frame in package.tables.items():
        table = TABLES_BY_NAME[name]
        extra = [column for column in frame.columns if column not in table.columns]
        if extra:
            findings.append(
                problem(
                    "ECOSYSTEM-EXTRA-COLUMN",
                    name,
                    f"unexpected columns: {', '.join(extra)}",
                )
            )
        if table.key:
            duplicates = frame[frame.duplicated(subset=list(table.key), keep=False)]
            if not duplicates.empty:
                values = ", ".join(
                    sorted(
                        {
                            "|".join(str(value) for value in row)
                            for row in duplicates[list(table.key)].itertuples(
                                index=False, name=None
                            )
                        }
                    )[:5]
                )
                findings.append(
                    problem(
                        "ECOSYSTEM-DUPLICATE",
                        name,
                        f"{', '.join(table.key)} must be unique; repeats: {values}",
                    )
                )
    _, cohort_findings = _typed_cohorts(package.table("cohorts"), package.schema)
    findings.extend(cohort_findings)
    return findings
