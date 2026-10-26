"""Load, validate, and resolve a FEMIC carbon input package.

The carbon package is the static, versioned input produced by FEMIC. WS4 joins it to
a compiled dataset by track name, then compiles the schedule-dependent SIT tables.
This module owns the package contract and the join; it does not run a carbon engine.

The contract is described in ``docs/reference/carbon.rst`` and in the FEMIC
``docs/reference/contracts/carbon-domain.rst`` page.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..model.schema import Problem

SCHEMA_VERSION = "0.1"
MANIFEST_NAME = "manifest.json"

EXPECTED_UNITS: dict[str, str] = {
    "area": "ha",
    "volume": "m3/ha",
    "carbon": "tC",
    "carbon_density": "tC/ha",
    "co2e": "tCO2e",
}

DEFAULT_TABLE_FILES: dict[str, str] = {
    "classifiers": "classifiers.csv",
    "disturbance_types": "disturbance_types.csv",
    "age_classes": "age_classes.csv",
    "inventory": "inventory.csv",
    "yield": "yield.csv",
    "track_carbon_map": "track_carbon_map.csv",
    "curve_carbon_map": "curve_carbon_map.csv",
    "species_map": "species_map.csv",
    "boundaries": "boundaries.csv",
}


@dataclass(frozen=True)
class CarbonTable:
    """One required table of a carbon package.

    Attributes
    ----------
    name : str
        Logical table name, as used in the manifest and the run record.
    file : str
        Default file name inside the package directory.
    columns : tuple of str
        Required columns. Extra columns are allowed and preserved.
    key : tuple of str
        Columns that must be jointly unique. An empty tuple means the table has no
        declared key.
    """

    name: str
    file: str
    columns: tuple[str, ...]
    key: tuple[str, ...] = ()


TABLES: tuple[CarbonTable, ...] = (
    CarbonTable(
        "classifiers",
        "classifiers.csv",
        ("classifier_id", "classifier", "value"),
        ("classifier_id", "value"),
    ),
    CarbonTable(
        "disturbance_types",
        "disturbance_types.csv",
        (
            "user_dist_type",
            "default_dist_type",
            "removes_biomass",
            "transition_reset_age",
            "regen_delay",
        ),
        ("user_dist_type",),
    ),
    CarbonTable("age_classes", "age_classes.csv", ("name", "class_size"), ("name",)),
    CarbonTable(
        "inventory",
        "inventory.csv",
        (
            "track_name",
            "age",
            "area_ha",
            "delay",
            "landclass",
            "historic_disturbance",
            "last_pass_disturbance",
        ),
    ),
    CarbonTable(
        "yield",
        "yield.csv",
        ("track_name", "species", "leading_species", "age", "volume_m3_ha"),
        ("track_name", "species", "age"),
    ),
    CarbonTable(
        "track_carbon_map",
        "track_carbon_map.csv",
        (
            "track_name",
            "classifier_set",
            "leading_species",
            "softwood_share",
            "hardwood_share",
            "landclass",
            "last_disturbance",
            "eco_boundary",
            "volume_feature_label",
        ),
        ("track_name",),
    ),
    CarbonTable(
        "curve_carbon_map",
        "curve_carbon_map.csv",
        ("track_name", "feature_label", "species", "share"),
        ("track_name", "feature_label", "species"),
    ),
    CarbonTable(
        "species_map",
        "species_map.csv",
        ("bc_species", "cbm_species", "wood_type", "confidence"),
        ("bc_species",),
    ),
    CarbonTable(
        "boundaries",
        "boundaries.csv",
        ("admin_boundary", "eco_boundary"),
    ),
)

TABLES_BY_NAME: dict[str, CarbonTable] = {table.name: table for table in TABLES}


class _Model(BaseModel):
    """Base model that rejects unknown manifest fields."""

    model_config = ConfigDict(extra="forbid")


class CarbonProducer(_Model):
    """The producer of a carbon package.

    Attributes
    ----------
    name : str
        Producer name, normally ``femic``.
    version : str
        Producer version.
    """

    name: str
    version: str


class CarbonSource(_Model):
    """One upstream source of a carbon package.

    Attributes
    ----------
    path : str
        Public-safe source label.
    sha256 : str
        Hex SHA-256 digest of the source.
    """

    path: str
    sha256: str


class CbmDefaults(_Model):
    """The CBM default parameter database used by the package.

    Attributes
    ----------
    version : str
        Database version string.
    sha256 : str
        Hex SHA-256 digest of the database file.
    source : str
        Where the database came from.
    """

    version: str
    sha256: str
    source: str


class CarbonUnits(_Model):
    """The units declared by a carbon package.

    Attributes
    ----------
    area : str
        Area unit.
    volume : str
        Merchantable volume unit.
    carbon : str
        Carbon mass unit.
    carbon_density : str
        Carbon density unit.
    co2e : str
        CO2-equivalent unit.
    """

    area: str
    volume: str
    carbon: str
    carbon_density: str
    co2e: str


class CarbonBoundaries(_Model):
    """The CBM administrative and ecological boundaries.

    Attributes
    ----------
    admin : str
        CBM administrative boundary name.
    eco : str
        CBM eco-boundary name.
    """

    admin: str
    eco: str


class CarbonMapping(_Model):
    """The classifier names used by the package.

    Attributes
    ----------
    track_key : {"track_name"}
        The dataset join key.
    species_classifier : str
        Name of the species classifier in the classifier table.
    disturbance_classifier : {"user_dist_type"}
        Name of the disturbance column used by events and transitions.
    """

    track_key: Literal["track_name"] = "track_name"
    species_classifier: str = "species"
    disturbance_classifier: Literal["user_dist_type"] = "user_dist_type"


class CarbonManifest(_Model):
    """The manifest of a carbon package.

    Attributes
    ----------
    schema_version : str
        Package schema version.
    package_id : str
        Producer-assigned package identifier.
    created_utc : str
        Creation timestamp in ISO-8601 form.
    producer : CarbonProducer
        The producer.
    sources : list of CarbonSource
        Upstream sources and their hashes.
    cbm_defaults : CbmDefaults
        The CBM default parameter database.
    units : CarbonUnits
        The declared units.
    boundaries : CarbonBoundaries
        The declared CBM boundaries.
    mapping : CarbonMapping
        The classifier names and join key.
    event_source : str
        Where events come from, normally ``ws4.schedule``.
    transition_source : str
        Where transitions come from, normally ``ws4.treatments``.
    table_files : dict of str to str
        Table name to file name.
    table_hashes : dict of str to str
        Optional table name to SHA-256 digest.
    """

    schema_version: str
    package_id: str
    created_utc: str
    producer: CarbonProducer
    sources: list[CarbonSource] = Field(default_factory=list)
    cbm_defaults: CbmDefaults
    units: CarbonUnits
    boundaries: CarbonBoundaries
    mapping: CarbonMapping = Field(default_factory=CarbonMapping)
    event_source: str = "ws4.schedule"
    transition_source: str = "ws4.treatments"
    table_files: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_TABLE_FILES))
    table_hashes: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class CarbonPackage:
    """A loaded and optionally validated carbon package.

    Attributes
    ----------
    path : Path
        Package directory.
    manifest : CarbonManifest
        Parsed manifest.
    tables : dict of str to pandas.DataFrame
        Loaded tables by logical name.
    table_hashes : dict of str to str
        SHA-256 digest of every loaded table file.
    fingerprint : str
        Stable digest of the manifest and every table file.
    """

    path: Path
    manifest: CarbonManifest
    tables: dict[str, pd.DataFrame]
    table_hashes: dict[str, str]
    fingerprint: str

    def table(self, name: str) -> pd.DataFrame:
        """Return a table by logical name.

        Parameters
        ----------
        name : str
            Logical table name.

        Returns
        -------
        pandas.DataFrame
            The table.

        Raises
        ------
        KeyError
            When the table is not part of the package.
        """
        return self.tables[name]


@dataclass(frozen=True)
class TrackResolution:
    """The result of joining package tracks to a compiled dataset.

    Attributes
    ----------
    mapping : dict of str to int
        Package track name to dataset track id.
    unmatched : tuple of str
        Dataset track names missing from the package.
    extra : tuple of str
        Package track names absent from the dataset.
    """

    mapping: dict[str, int]
    unmatched: tuple[str, ...]
    extra: tuple[str, ...]


class CarbonPackageError(ValueError):
    """Raised when a carbon package cannot be loaded or validated.

    Parameters
    ----------
    findings : sequence of Problem
        The validation findings.
    """

    def __init__(self, findings: Sequence[Problem]) -> None:
        """Store the findings and build a readable message."""
        self.findings: tuple[Problem, ...] = tuple(findings)
        message = "; ".join(f"{item.code}: {item.message}" for item in self.findings)
        super().__init__(message or "invalid carbon package")


def _problem(code: str, where: str, message: str) -> Problem:
    """Build one validation finding."""
    return Problem(code, where, message)


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_table(path: Path) -> pd.DataFrame:
    """Read a package CSV as strings, preserving classifier codes."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    for column in frame.columns:
        frame[column] = frame[column].astype(str).str.strip()
    return frame


def _manifest_path(root: Path) -> Path:
    """Return the manifest path of a package directory."""
    return root / MANIFEST_NAME


def _package_fingerprint(root: Path, table_hashes: Mapping[str, str]) -> str:
    """Return a stable digest of the manifest and the table hashes.

    The digest is independent of file order and of the working directory.
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


def _load_manifest(root: Path, findings: list[Problem]) -> CarbonManifest | None:
    """Load and parse the manifest, appending findings on failure."""
    path = _manifest_path(root)
    if not path.is_file():
        findings.append(_problem("CARBON-MISSING-MANIFEST", str(path), f"missing {MANIFEST_NAME}"))
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        return CarbonManifest.model_validate_json(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        findings.append(_problem("CARBON-MANIFEST-INVALID", str(path), str(exc)))
        return None


def _load_tables(
    root: Path,
    manifest: CarbonManifest,
    findings: list[Problem],
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Load every declared table and hash it."""
    tables: dict[str, pd.DataFrame] = {}
    hashes: dict[str, str] = {}
    unknown = sorted(set(manifest.table_files) - set(TABLES_BY_NAME))
    for name in unknown:
        findings.append(
            _problem(
                "CARBON-UNKNOWN-TABLE",
                f"manifest.table_files.{name}",
                f"unknown table {name!r}",
            )
        )
    for table in TABLES:
        file_name = manifest.table_files.get(table.name, table.file)
        path = root / file_name
        if not path.is_file():
            findings.append(
                _problem(
                    "CARBON-MISSING-TABLE",
                    str(path),
                    f"missing required table {table.name!r}",
                )
            )
            continue
        try:
            tables[table.name] = _read_table(path)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            findings.append(_problem("CARBON-TABLE-INVALID", str(path), str(exc)))
            continue
        hashes[table.name] = _sha256(path)
    return tables, hashes


def load_carbon_package(path: Path, *, validate: bool = True) -> CarbonPackage:
    """Load a carbon package from a directory.

    Parameters
    ----------
    path : Path
        Package directory.
    validate : bool, optional
        Validate the package before returning it. Defaults to True.

    Returns
    -------
    CarbonPackage
        The loaded package.

    Raises
    ------
    CarbonPackageError
        When the package is missing, malformed, or invalid.
    """
    root = Path(path)
    findings: list[Problem] = []
    if not root.is_dir():
        raise CarbonPackageError(
            [_problem("CARBON-MISSING-DIR", str(root), "package directory not found")]
        )
    manifest = _load_manifest(root, findings)
    if manifest is None:
        raise CarbonPackageError(findings)
    tables, hashes = _load_tables(root, manifest, findings)
    package = CarbonPackage(
        path=root,
        manifest=manifest,
        tables=tables,
        table_hashes=hashes,
        fingerprint=_package_fingerprint(root, hashes),
    )
    if findings:
        raise CarbonPackageError(findings)
    if validate:
        findings.extend(_validate(package))
        if findings:
            raise CarbonPackageError(findings)
    return package


def validate_carbon_package(path: Path) -> list[Problem]:
    """Validate a carbon package and return every finding.

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
        package = load_carbon_package(path, validate=False)
    except CarbonPackageError as exc:
        return list(exc.findings)
    return _validate(package)


def package_fingerprint(package: CarbonPackage) -> str:
    """Return the stable fingerprint of a loaded package.

    Parameters
    ----------
    package : CarbonPackage
        The loaded package.

    Returns
    -------
    str
        Hex SHA-256 digest.
    """
    return package.fingerprint


def _validate(package: CarbonPackage) -> list[Problem]:
    """Validate the loaded package and return every finding."""
    findings: list[Problem] = []
    manifest = package.manifest

    if manifest.schema_version != SCHEMA_VERSION:
        findings.append(
            _problem(
                "CARBON-SCHEMA-VERSION",
                "manifest.schema_version",
                f"expected {SCHEMA_VERSION!r}, found {manifest.schema_version!r}",
            )
        )
    for field_name, expected in EXPECTED_UNITS.items():
        actual = getattr(manifest.units, field_name)
        if actual != expected:
            findings.append(
                _problem(
                    "CARBON-UNIT",
                    f"manifest.units.{field_name}",
                    f"expected {expected!r}, found {actual!r}",
                )
            )
    if not manifest.mapping.species_classifier:
        findings.append(
            _problem(
                "CARBON-MAPPING",
                "manifest.mapping.species_classifier",
                "species classifier name is empty",
            )
        )
    for name in TABLES_BY_NAME:
        if name not in package.tables:
            continue
        expected_hash = manifest.table_hashes.get(name)
        actual_hash = package.table_hashes.get(name)
        if expected_hash and actual_hash and expected_hash != actual_hash:
            findings.append(
                _problem(
                    "CARBON-TABLE-HASH",
                    f"manifest.table_hashes.{name}",
                    f"expected {expected_hash}, found {actual_hash}",
                )
            )

    for table in TABLES:
        frame = package.tables.get(table.name)
        if frame is None:
            continue
        if frame.empty:
            findings.append(
                _problem(
                    "CARBON-TABLE-EMPTY",
                    table.name,
                    f"table {table.name!r} has no rows",
                )
            )
            continue
        missing = [column for column in table.columns if column not in frame.columns]
        for column in missing:
            findings.append(
                _problem(
                    "CARBON-MISSING-COLUMN",
                    f"{table.name}.{column}",
                    f"missing required column {column!r}",
                )
            )
        if not missing and table.key:
            duplicates = frame.duplicated(subset=list(table.key), keep=False)
            if bool(duplicates.any()):
                sample = frame.loc[duplicates, list(table.key)].head(5).to_dict("records")
                findings.append(
                    _problem(
                        "CARBON-DUPLICATE-KEY",
                        table.name,
                        f"duplicate values for {table.key}: {sample}",
                    )
                )

    species = _validate_species_map(package.tables.get("species_map"), findings)
    classifiers = _validate_classifiers(package.tables.get("classifiers"), findings)
    _validate_disturbance_types(package.tables.get("disturbance_types"), findings)
    _validate_age_classes(package.tables.get("age_classes"), findings)
    track_names = _validate_track_map(
        package.tables.get("track_carbon_map"),
        package.manifest,
        classifiers,
        species,
        findings,
    )
    _validate_inventory(
        package.tables.get("inventory"),
        track_names,
        package.tables.get("disturbance_types"),
        findings,
    )
    _validate_yield(
        package.tables.get("yield"),
        track_names,
        classifiers,
        species,
        findings,
    )
    _validate_curve_map(
        package.tables.get("curve_carbon_map"),
        track_names,
        classifiers,
        findings,
    )
    _validate_boundaries(package.tables.get("boundaries"), package.manifest, findings)
    return findings


def _validate_species_map(
    frame: pd.DataFrame | None,
    findings: list[Problem],
) -> set[str]:
    """Validate the species map and return the CBM species names."""
    if frame is None or frame.empty:
        return set()
    required = ("bc_species", "cbm_species", "wood_type", "confidence")
    if any(column not in frame.columns for column in required):
        return set()
    species: set[str] = set()
    for row in frame.itertuples(index=False):
        bc_species = str(row.bc_species).strip()
        cbm_species = str(row.cbm_species).strip()
        wood_type = str(row.wood_type).strip().lower()
        confidence = str(row.confidence).strip()
        if not bc_species:
            findings.append(
                _problem("CARBON-INVALID-VALUE", "species_map.bc_species", "empty value")
            )
        if not cbm_species:
            findings.append(
                _problem("CARBON-INVALID-VALUE", "species_map.cbm_species", "empty value")
            )
        else:
            species.add(cbm_species)
        if wood_type not in {"softwood", "hardwood"}:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "species_map.wood_type",
                    f"expected softwood or hardwood, found {wood_type!r}",
                )
            )
        if not confidence:
            findings.append(
                _problem("CARBON-INVALID-VALUE", "species_map.confidence", "empty value")
            )
    return species


def _validate_classifiers(
    frame: pd.DataFrame | None,
    findings: list[Problem],
) -> dict[int, tuple[str, set[str]]]:
    """Validate classifiers and return id to (name, values)."""
    if frame is None or frame.empty:
        return {}
    required = ("classifier_id", "classifier", "value")
    if any(column not in frame.columns for column in required):
        return {}
    ids = pd.to_numeric(frame["classifier_id"], errors="coerce")
    if bool(ids.isna().any()) or bool((ids <= 0).any()):
        findings.append(
            _problem(
                "CARBON-INVALID-VALUE",
                "classifiers.classifier_id",
                "classifier_id must be a positive integer",
            )
        )
    result: dict[int, tuple[str, set[str]]] = {}
    for row in frame.itertuples(index=False):
        try:
            classifier_id = int(str(row.classifier_id))
        except ValueError:
            continue
        classifier = str(row.classifier).strip()
        value = str(row.value).strip()
        if not classifier or not value:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "classifiers",
                    "classifier and value must be non-empty",
                )
            )
            continue
        current = result.get(classifier_id)
        if current is None:
            result[classifier_id] = (classifier, {value})
        else:
            name, values = current
            if name != classifier:
                findings.append(
                    _problem(
                        "CARBON-INVALID-VALUE",
                        "classifiers.classifier",
                        f"classifier_id {classifier_id} has names {name!r} and {classifier!r}",
                    )
                )
            values.add(value)
    return result


def _validate_disturbance_types(
    frame: pd.DataFrame | None,
    findings: list[Problem],
) -> None:
    """Validate disturbance types."""
    if frame is None or frame.empty:
        return
    required = (
        "user_dist_type",
        "default_dist_type",
        "removes_biomass",
        "transition_reset_age",
        "regen_delay",
    )
    if any(column not in frame.columns for column in required):
        return
    for row in frame.itertuples(index=False):
        user_type = str(row.user_dist_type).strip()
        default_type = str(row.default_dist_type).strip()
        if not user_type or not default_type:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "disturbance_types",
                    "user_dist_type and default_dist_type must be non-empty",
                )
            )
        if _parse_bool(str(row.removes_biomass)) is None:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "disturbance_types.removes_biomass",
                    f"expected true or false for {user_type!r}",
                )
            )
        for column in ("transition_reset_age", "regen_delay"):
            value = _number(str(getattr(row, column)))
            if value is None or value < 0:
                findings.append(
                    _problem(
                        "CARBON-INVALID-VALUE",
                        f"disturbance_types.{column}",
                        f"expected a non-negative number for {user_type!r}",
                    )
                )


def _validate_age_classes(frame: pd.DataFrame | None, findings: list[Problem]) -> None:
    """Validate the age-class table."""
    if frame is None or frame.empty:
        return
    if "name" not in frame.columns or "class_size" not in frame.columns:
        return
    sizes = pd.to_numeric(frame["class_size"], errors="coerce")
    if bool(sizes.isna().any()):
        findings.append(
            _problem(
                "CARBON-INVALID-VALUE",
                "age_classes.class_size",
                "class_size must be numeric",
            )
        )
        return
    if float(sizes.iloc[0]) != 0.0:
        findings.append(
            _problem(
                "CARBON-INVALID-VALUE",
                "age_classes.class_size",
                "the first age class must have class_size 0",
            )
        )
    if bool((sizes.iloc[1:] <= 0).any()):
        findings.append(
            _problem(
                "CARBON-INVALID-VALUE",
                "age_classes.class_size",
                "age classes after the first must have class_size > 0",
            )
        )
    if len(sizes) > 2 and sizes.iloc[1:].nunique() != 1:
        findings.append(
            _problem(
                "CARBON-INVALID-VALUE",
                "age_classes.class_size",
                "the package requires a constant age-class width",
            )
        )


def _validate_track_map(
    frame: pd.DataFrame | None,
    manifest: CarbonManifest,
    classifiers: Mapping[int, tuple[str, set[str]]],
    species: set[str],
    findings: list[Problem],
) -> set[str]:
    """Validate the track map and return its track names."""
    if frame is None or frame.empty:
        return set()
    required = (
        "track_name",
        "classifier_set",
        "leading_species",
        "softwood_share",
        "hardwood_share",
        "landclass",
        "last_disturbance",
        "eco_boundary",
        "volume_feature_label",
    )
    if any(column not in frame.columns for column in required):
        return set()
    classifier_order = sorted(classifiers)
    for row in frame.itertuples(index=False):
        track_name = str(row.track_name).strip()
        classifier_set = str(row.classifier_set).strip()
        leading_species = str(row.leading_species).strip()
        eco_boundary = str(row.eco_boundary).strip()
        feature_label = str(row.volume_feature_label).strip()
        if not track_name:
            findings.append(
                _problem("CARBON-INVALID-VALUE", "track_carbon_map.track_name", "empty value")
            )
        values = [part.strip() for part in classifier_set.split(";")] if classifier_set else []
        if len(values) != len(classifier_order):
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "track_carbon_map.classifier_set",
                    f"{track_name!r} has {len(values)} values for "
                    f"{len(classifier_order)} classifiers",
                )
            )
        else:
            for classifier_id, value in zip(classifier_order, values, strict=True):
                if value not in classifiers[classifier_id][1]:
                    findings.append(
                        _problem(
                            "CARBON-INVALID-VALUE",
                            "track_carbon_map.classifier_set",
                            f"{track_name!r} uses undefined classifier value {value!r}",
                        )
                    )
        if leading_species not in species:
            findings.append(
                _problem(
                    "CARBON-UNKNOWN-SPECIES",
                    "track_carbon_map.leading_species",
                    f"{track_name!r} uses {leading_species!r}, not in species_map",
                )
            )
        softwood = _number(str(row.softwood_share))
        hardwood = _number(str(row.hardwood_share))
        if softwood is None or not 0.0 <= softwood <= 1.0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "track_carbon_map.softwood_share",
                    f"{track_name!r} has an invalid softwood share",
                )
            )
        if hardwood is None or not 0.0 <= hardwood <= 1.0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "track_carbon_map.hardwood_share",
                    f"{track_name!r} has an invalid hardwood share",
                )
            )
        if softwood is not None and hardwood is not None and softwood + hardwood > 1.000001:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "track_carbon_map",
                    f"{track_name!r} has shares that sum to more than one",
                )
            )
        landclass = _integer(str(row.landclass))
        if landclass is None or not 0 <= landclass <= 22:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "track_carbon_map.landclass",
                    f"{track_name!r} has an invalid land class",
                )
            )
        if not str(row.last_disturbance).strip():
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "track_carbon_map.last_disturbance",
                    f"{track_name!r} has an empty last disturbance",
                )
            )
        if eco_boundary != manifest.boundaries.eco:
            findings.append(
                _problem(
                    "CARBON-ECO-MISMATCH",
                    "track_carbon_map.eco_boundary",
                    f"{track_name!r} uses {eco_boundary!r}, manifest uses "
                    f"{manifest.boundaries.eco!r}",
                )
            )
        if not feature_label:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "track_carbon_map.volume_feature_label",
                    f"{track_name!r} has an empty volume feature label",
                )
            )
    return set(frame["track_name"].astype(str).str.strip())


def _validate_inventory(
    frame: pd.DataFrame | None,
    track_names: set[str],
    disturbance_types: pd.DataFrame | None,
    findings: list[Problem],
) -> None:
    """Validate the initial inventory."""
    if frame is None or frame.empty:
        return
    required = (
        "track_name",
        "age",
        "area_ha",
        "delay",
        "landclass",
        "historic_disturbance",
        "last_pass_disturbance",
    )
    if any(column not in frame.columns for column in required):
        return
    known_disturbances: set[str] = set()
    if disturbance_types is not None and not disturbance_types.empty:
        for column in ("user_dist_type", "default_dist_type"):
            if column in disturbance_types.columns:
                known_disturbances.update(
                    disturbance_types[column].astype(str).str.strip().tolist()
                )
    for row in frame.itertuples(index=False):
        track_name = str(row.track_name).strip()
        if track_name not in track_names:
            findings.append(
                _problem(
                    "CARBON-UNKNOWN-TRACK",
                    "inventory.track_name",
                    f"{track_name!r} is not in track_carbon_map",
                )
            )
        age = _number(str(row.age))
        area = _number(str(row.area_ha))
        delay = _number(str(row.delay))
        landclass = _integer(str(row.landclass))
        if age is None or age < 0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "inventory.age",
                    f"{track_name!r} has an invalid age",
                )
            )
        if area is None or area <= 0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "inventory.area_ha",
                    f"{track_name!r} has an invalid area",
                )
            )
        if delay is None or delay < 0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "inventory.delay",
                    f"{track_name!r} has an invalid delay",
                )
            )
        if landclass is None or not 0 <= landclass <= 22:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "inventory.landclass",
                    f"{track_name!r} has an invalid land class",
                )
            )
        for column in ("historic_disturbance", "last_pass_disturbance"):
            value = str(getattr(row, column)).strip()
            if not value:
                findings.append(
                    _problem(
                        "CARBON-INVALID-VALUE",
                        f"inventory.{column}",
                        f"{track_name!r} has an empty disturbance",
                    )
                )
            elif known_disturbances and value not in known_disturbances:
                findings.append(
                    _problem(
                        "CARBON-UNKNOWN-DISTURBANCE",
                        f"inventory.{column}",
                        f"{track_name!r} uses unknown disturbance {value!r}",
                    )
                )


def _validate_yield(
    frame: pd.DataFrame | None,
    track_names: set[str],
    classifiers: Mapping[int, tuple[str, set[str]]],
    species: set[str],
    findings: list[Problem],
) -> None:
    """Validate the yield table and that every track has at least one row."""
    if frame is None or frame.empty:
        return
    required = ("track_name", "species", "leading_species", "age", "volume_m3_ha")
    if any(column not in frame.columns for column in required):
        return
    species_values: set[str] = set()
    for _classifier_id, (name, values) in classifiers.items():
        if name == "species":
            species_values = values
    seen_tracks: set[str] = set()
    for row in frame.itertuples(index=False):
        track_name = str(row.track_name).strip()
        seen_tracks.add(track_name)
        if track_name not in track_names:
            findings.append(
                _problem(
                    "CARBON-UNKNOWN-TRACK",
                    "yield.track_name",
                    f"{track_name!r} is not in track_carbon_map",
                )
            )
        species_value = str(row.species).strip()
        if species_values and species_value not in species_values:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "yield.species",
                    f"{track_name!r} uses undefined species classifier value {species_value!r}",
                )
            )
        leading_species = str(row.leading_species).strip()
        if leading_species not in species:
            findings.append(
                _problem(
                    "CARBON-UNKNOWN-SPECIES",
                    "yield.leading_species",
                    f"{track_name!r} uses {leading_species!r}, not in species_map",
                )
            )
        age = _number(str(row.age))
        volume = _number(str(row.volume_m3_ha))
        if age is None or age < 0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "yield.age",
                    f"{track_name!r} has an invalid age",
                )
            )
        if volume is None or volume < 0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "yield.volume_m3_ha",
                    f"{track_name!r} has an invalid volume",
                )
            )
    for track_name in sorted(track_names - seen_tracks):
        findings.append(
            _problem(
                "CARBON-MISSING-YIELD",
                "yield.track_name",
                f"{track_name!r} has no yield row",
            )
        )


def _validate_curve_map(
    frame: pd.DataFrame | None,
    track_names: set[str],
    classifiers: Mapping[int, tuple[str, set[str]]],
    findings: list[Problem],
) -> None:
    """Validate the curve map."""
    if frame is None or frame.empty:
        return
    required = ("track_name", "feature_label", "species", "share")
    if any(column not in frame.columns for column in required):
        return
    species_values: set[str] = set()
    for _classifier_id, (name, values) in classifiers.items():
        if name == "species":
            species_values = values
    for row in frame.itertuples(index=False):
        track_name = str(row.track_name).strip()
        feature_label = str(row.feature_label).strip()
        species_value = str(row.species).strip()
        share = _number(str(row.share))
        if track_name not in track_names:
            findings.append(
                _problem(
                    "CARBON-UNKNOWN-TRACK",
                    "curve_carbon_map.track_name",
                    f"{track_name!r} is not in track_carbon_map",
                )
            )
        if not feature_label:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "curve_carbon_map.feature_label",
                    f"{track_name!r} has an empty feature label",
                )
            )
        if species_values and species_value not in species_values:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "curve_carbon_map.species",
                    f"{track_name!r} uses undefined species classifier value {species_value!r}",
                )
            )
        if share is None or not 0.0 <= share <= 1.0:
            findings.append(
                _problem(
                    "CARBON-INVALID-VALUE",
                    "curve_carbon_map.share",
                    f"{track_name!r} has an invalid share",
                )
            )


def _validate_boundaries(
    frame: pd.DataFrame | None,
    manifest: CarbonManifest,
    findings: list[Problem],
) -> None:
    """Validate that the boundary table declares the manifest boundaries."""
    if frame is None or frame.empty:
        return
    required = ("admin_boundary", "eco_boundary")
    if any(column not in frame.columns for column in required):
        return
    pairs = {
        (str(admin).strip(), str(eco).strip())
        for admin, eco in zip(frame["admin_boundary"], frame["eco_boundary"], strict=True)
    }
    expected = (manifest.boundaries.admin, manifest.boundaries.eco)
    if expected not in pairs:
        findings.append(
            _problem(
                "CARBON-BOUNDARY-MISMATCH",
                "boundaries",
                f"no row declares {expected[0]!r} / {expected[1]!r}",
            )
        )


def resolve_tracks(
    package: CarbonPackage,
    tracks: pd.DataFrame,
    *,
    allow_unmatched: bool = False,
) -> TrackResolution:
    """Join package track names to a compiled dataset's tracks.

    Parameters
    ----------
    package : CarbonPackage
        The loaded package.
    tracks : pandas.DataFrame
        The compiled dataset's ``tracks`` table, with ``track_id`` and ``name``.
    allow_unmatched : bool, optional
        When True, return unmatched dataset tracks instead of raising. Defaults to
        False.

    Returns
    -------
    TrackResolution
        The mapping and the unmatched/extra track names.

    Raises
    ------
    CarbonPackageError
        When the tracks table is malformed, track names are duplicated, or dataset
        tracks are missing from the package and ``allow_unmatched`` is False.
    """
    findings: list[Problem] = []
    for column in ("track_id", "name"):
        if column not in tracks.columns:
            findings.append(
                _problem(
                    "CARBON-MISSING-COLUMN",
                    f"tracks.{column}",
                    f"missing required column {column!r}",
                )
            )
    if findings:
        raise CarbonPackageError(findings)

    names = tracks["name"].astype(str).str.strip()
    duplicates = names[names.duplicated(keep=False)]
    if not duplicates.empty:
        raise CarbonPackageError(
            [
                _problem(
                    "CARBON-DUPLICATE-TRACK-NAME",
                    "tracks.name",
                    f"duplicate track names: {sorted(set(duplicates.tolist()))[:10]}",
                )
            ]
        )

    package_table = package.tables.get("track_carbon_map")
    if package_table is None or "track_name" not in package_table.columns:
        raise CarbonPackageError(
            [
                _problem(
                    "CARBON-MISSING-TABLE",
                    "track_carbon_map",
                    "package has no track map",
                )
            ]
        )
    package_names = set(package_table["track_name"].astype(str).str.strip())
    dataset_names = [str(name) for name in names.tolist()]
    mapping = {
        name: int(track_id)
        for name, track_id in zip(dataset_names, tracks["track_id"].tolist(), strict=True)
        if name in package_names
    }
    unmatched = tuple(sorted(set(dataset_names) - package_names))
    extra = tuple(sorted(package_names - set(dataset_names)))
    if unmatched and not allow_unmatched:
        raise CarbonPackageError(
            [
                _problem(
                    "CARBON-UNMATCHED-TRACK",
                    "tracks.name",
                    f"{len(unmatched)} dataset tracks are missing from the carbon "
                    f"package, starting with {list(unmatched[:10])}",
                )
            ]
        )
    return TrackResolution(mapping=mapping, unmatched=unmatched, extra=extra)


def _parse_bool(value: str) -> bool | None:
    """Parse a boolean-like string, returning None when it is not recognized."""
    text = value.strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _number(value: str) -> float | None:
    """Parse a finite float, returning None when it is not a finite number."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _integer(value: str) -> int | None:
    """Parse an integer, returning None when it is not an integer."""
    number = _number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)
