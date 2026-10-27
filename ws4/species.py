"""Species-composition ingest and comparison contracts.

The first public layer is the NTEMS annual dominant tree species map. It carries
one class per 30 m cell, not species fractions. This module stores the class
fractions observed in each block, names the leading class, and compares it with
a reference such as VRI species labels. Mixedwood fractions are not invented
from a dominant-species product.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SPECIES_SOURCE_SCHEMA_VERSION = "ws4.species.source.v1"
SPECIES_COMPOSITION_SCHEMA_VERSION = "ws4.species.composition.v1"
SPECIES_FRACTION_SCHEMA_VERSION = "ws4.species.fraction.v1"
DEFAULT_SOURCE_ID = "ntems-ca-tree-species-classification"
DEFAULT_LICENCE = "Open Government Licence - Canada"


class SpeciesError(RuntimeError):
    """Raised when a species layer or composition table is unusable."""


@dataclass(frozen=True)
class SpeciesClass:
    """One class in a species raster.

    Parameters
    ----------
    code : int
        Raster value.
    name : str
        Common name.
    nfi_code : str or None
        National Forest Inventory species code.
    scientific_name : str or None
        Scientific name.
    """

    code: int
    name: str
    nfi_code: str | None = None
    scientific_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the class as a JSON-serializable mapping.

        Returns
        -------
        dict
            Class code, names, and optional NFI code.
        """
        return {
            "code": self.code,
            "name": self.name,
            "nfi_code": self.nfi_code,
            "scientific_name": self.scientific_name,
        }


@dataclass(frozen=True)
class SpeciesSource:
    """Provenance for one species raster.

    Parameters
    ----------
    source_id : str
        Product identifier.
    source_version : str
        Required source version or vintage.
    year : int
        Map year.
    resolution_m : float
        Native pixel size in metres.
    crs : str
        Raster CRS.
    licence : str
        Source licence.
    citation : str
        Source citation.
    classes : tuple of SpeciesClass
        Class map.
    notes : str or None
        Optional provenance note.
    """

    source_id: str
    source_version: str
    year: int
    resolution_m: float
    crs: str
    licence: str
    citation: str
    classes: tuple[SpeciesClass, ...]
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the source descriptor.

        Returns
        -------
        dict
            Versioned source metadata and class map.
        """
        return {
            "schema_version": SPECIES_SOURCE_SCHEMA_VERSION,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "year": self.year,
            "resolution_m": self.resolution_m,
            "crs": self.crs,
            "licence": self.licence,
            "citation": self.citation,
            "classes": [item.to_dict() for item in self.classes],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> SpeciesSource:
        """Validate and build a source descriptor.

        Parameters
        ----------
        payload : mapping
            Decoded metadata.

        Returns
        -------
        SpeciesSource
            The validated descriptor.

        Raises
        ------
        SpeciesError
            If the schema, version, year, or class map is invalid.
        """
        if payload.get("schema_version") != SPECIES_SOURCE_SCHEMA_VERSION:
            raise SpeciesError(
                f"species source schema_version must be {SPECIES_SOURCE_SCHEMA_VERSION!r}"
            )
        version = str(payload.get("source_version", "")).strip()
        if not version:
            raise SpeciesError("species source_version must not be empty")
        raw_classes = payload.get("classes")
        if not isinstance(raw_classes, list) or not raw_classes:
            raise SpeciesError("species source classes must be a non-empty list")
        classes = tuple(
            SpeciesClass(
                code=int(str(item["code"])),
                name=str(item["name"]),
                nfi_code=None if item.get("nfi_code") is None else str(item["nfi_code"]),
                scientific_name=(
                    None if item.get("scientific_name") is None else str(item["scientific_name"])
                ),
            )
            for item in raw_classes
            if isinstance(item, dict)
        )
        if len(classes) != len(raw_classes):
            raise SpeciesError("species source classes must be objects")
        return cls(
            source_id=str(payload.get("source_id", DEFAULT_SOURCE_ID)),
            source_version=version,
            year=int(str(payload.get("year", 0))),
            resolution_m=float(str(payload.get("resolution_m", 30.0))),
            crs=str(payload.get("crs", "")),
            licence=str(payload.get("licence", DEFAULT_LICENCE)),
            citation=str(payload.get("citation", "")),
            classes=classes,
            notes=None if payload.get("notes") is None else str(payload["notes"]),
        )


def read_class_map(path: str | Path) -> tuple[SpeciesClass, ...]:
    """Read a class map from CSV or JSON.

    Parameters
    ----------
    path : str or Path
        CSV with ``code`` and ``name`` columns, or a JSON array of class objects.

    Returns
    -------
    tuple of SpeciesClass
        The class map.

    Raises
    ------
    SpeciesError
        If the file is missing or has no usable classes.
    """
    source = Path(path)
    if not source.is_file():
        raise SpeciesError(f"species class map does not exist: {source}")
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise SpeciesError("species JSON class map must be a list")
        classes = tuple(
            SpeciesClass(
                code=int(str(item["code"])),
                name=str(item["name"]),
                nfi_code=None if item.get("nfi_code") is None else str(item["nfi_code"]),
                scientific_name=(
                    None if item.get("scientific_name") is None else str(item["scientific_name"])
                ),
            )
            for item in payload
            if isinstance(item, dict)
        )
    else:
        frame = pd.read_csv(source)
        if "code" not in frame or "name" not in frame:
            raise SpeciesError("species CSV class map needs code and name columns")
        classes = tuple(
            SpeciesClass(
                code=int(str(row["code"])),
                name=str(row["name"]),
                nfi_code=(None if pd.isna(row.get("nfi_code")) else str(row.get("nfi_code"))),
                scientific_name=(
                    None if pd.isna(row.get("scientific_name")) else str(row.get("scientific_name"))
                ),
            )
            for row in frame.to_dict("records")
        )
    if not classes:
        raise SpeciesError("species class map is empty")
    return classes


def _block_id_column(frame: pd.DataFrame, block_id_field: str | None) -> str:
    """Return the block-id column, accepting common aliases."""
    if block_id_field is not None:
        if block_id_field not in frame.columns:
            raise SpeciesError(f"block id field {block_id_field!r} is not in the blocks file")
        return block_id_field
    for candidate in ("block_id", "BLOCK", "block", "feature_id", "id"):
        if candidate in frame.columns:
            return candidate
    raise SpeciesError("blocks file has no block_id, BLOCK, block, feature_id, or id column")


def sample_species_raster(
    raster_path: str | Path,
    blocks_path: str | Path,
    class_map: Sequence[SpeciesClass],
    *,
    source_version: str,
    source_id: str = DEFAULT_SOURCE_ID,
    year: int = 2022,
    licence: str = DEFAULT_LICENCE,
    citation: str = (
        "Hermosilla et al. 2024, Characterizing long-term tree species dynamics in "
        "Canada's forested ecosystems, Forest Ecology and Management 122313."
    ),
    block_id_field: str | None = None,
    notes: str | None = None,
) -> tuple[pd.DataFrame, SpeciesSource]:
    """Sample a dominant-species raster at block polygons.

    Parameters
    ----------
    raster_path : str or Path
        Species GeoTIFF.
    blocks_path : str or Path
        Block polygon layer.
    class_map : sequence of SpeciesClass
        Raster value to species mapping.
    source_version : str
        Required source version or vintage.
    source_id : str, optional
        Product identifier.
    year : int, optional
        Map year.
    licence : str, optional
        Source licence.
    citation : str, optional
        Source citation.
    block_id_field : str or None, optional
        Block id column; auto-detected when omitted.
    notes : str or None, optional
        Optional provenance note.

    Returns
    -------
    tuple of (pandas.DataFrame, SpeciesSource)
        Long composition rows and the source descriptor. Each row has
        ``block_id``, ``species_code``, ``species_name``, ``pixel_count``,
        ``class_fraction``, and ``is_leading``.

    Raises
    ------
    SpeciesError
        If the raster, block geometry, class map, or block coverage is unusable.
    """
    import geopandas as gpd
    import rasterio
    from rasterio.mask import mask as raster_mask
    from shapely.geometry import mapping

    if not source_version.strip():
        raise SpeciesError("species source_version must not be empty")
    if not class_map:
        raise SpeciesError("species class map is empty")
    names = {item.code: item for item in class_map}
    raster = Path(raster_path)
    blocks = Path(blocks_path)
    if not raster.is_file():
        raise SpeciesError(f"species raster does not exist: {raster}")
    if not blocks.is_file():
        raise SpeciesError(f"blocks file does not exist: {blocks}")
    frame = gpd.read_file(blocks)
    id_column = _block_id_column(frame, block_id_field)
    if frame.crs is None:
        raise SpeciesError("blocks file has no CRS")
    if frame[id_column].duplicated().any():
        raise SpeciesError(f"blocks file has duplicate {id_column!r} values")

    with rasterio.open(raster) as source:
        if source.count != 1:
            raise SpeciesError("species raster must have exactly one band")
        if source.crs is None:
            raise SpeciesError("species raster has no CRS")
        blocks_in_raster = frame.to_crs(source.crs)
        rows: list[dict[str, object]] = []
        missing: list[object] = []
        for record in blocks_in_raster.itertuples(index=False):
            block_id = getattr(record, id_column)
            geometry = record.geometry
            try:
                clipped, _ = raster_mask(
                    source, [mapping(geometry)], crop=True, filled=False, all_touched=True
                )
            except ValueError:
                missing.append(block_id)
                continue
            data = clipped[0]
            values = np.asarray(data[~np.ma.getmaskarray(data)]).astype(int).ravel()
            if values.size == 0:
                missing.append(block_id)
                continue
            unknown = sorted(set(values.tolist()) - set(names))
            if unknown:
                raise SpeciesError(
                    f"species raster has unmapped classes {unknown[:10]} for block {block_id}"
                )
            total = int(values.size)
            counts = pd.Series(values).value_counts()
            leading_code = int(str(counts.index[0]))
            for code, count in counts.items():
                species = names[int(str(code))]
                rows.append(
                    {
                        "block_id": int(block_id),
                        "species_code": int(str(code)),
                        "species_name": species.name,
                        "nfi_code": species.nfi_code,
                        "pixel_count": int(str(count)),
                        "class_fraction": float(count) / float(total),
                        "is_leading": int(str(code)) == leading_code,
                    }
                )
        if missing:
            preview = ", ".join(str(block) for block in missing[:10])
            raise SpeciesError(f"species raster does not cover {len(missing)} blocks: {preview}")
        resolution = float(abs(source.transform.a))
        crs = source.crs.to_string()

    composition = pd.DataFrame(
        rows,
        columns=[
            "block_id",
            "species_code",
            "species_name",
            "nfi_code",
            "pixel_count",
            "class_fraction",
            "is_leading",
        ],
    )
    source_metadata = SpeciesSource(
        source_id=source_id,
        source_version=source_version,
        year=year,
        resolution_m=resolution,
        crs=crs,
        licence=licence,
        citation=citation,
        classes=tuple(class_map),
        notes=notes,
    )
    return composition, source_metadata


def write_species_composition(
    composition: pd.DataFrame,
    source: SpeciesSource,
    output_csv: str | Path,
    metadata_json: str | Path,
) -> None:
    """Write the composition table and source metadata.

    Parameters
    ----------
    composition : pandas.DataFrame
        Long composition table.
    source : SpeciesSource
        Source descriptor.
    output_csv : str or Path
        Destination composition CSV.
    metadata_json : str or Path
        Destination metadata JSON.
    """
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    composition.to_csv(output, index=False)
    metadata = Path(metadata_json)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(source.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def read_species_composition(
    composition_path: str | Path,
    metadata_path: str | Path,
) -> tuple[pd.DataFrame, SpeciesSource]:
    """Read a saved composition table and source metadata.

    Parameters
    ----------
    composition_path : str or Path
        Long composition CSV.
    metadata_path : str or Path
        Source metadata JSON.

    Returns
    -------
    tuple of (pandas.DataFrame, SpeciesSource)
        The table and source descriptor.

    Raises
    ------
    SpeciesError
        If the files are missing or the table lacks required columns.
    """
    composition = Path(composition_path)
    metadata = Path(metadata_path)
    if not composition.is_file():
        raise SpeciesError(f"species composition does not exist: {composition}")
    if not metadata.is_file():
        raise SpeciesError(f"species metadata does not exist: {metadata}")
    source = SpeciesSource.from_dict(json.loads(metadata.read_text(encoding="utf-8")))
    frame = pd.read_csv(composition)
    required = {"block_id", "species_code", "species_name", "class_fraction", "is_leading"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SpeciesError("species composition is missing: " + ", ".join(missing))
    return frame, source


def compare_leading_species(
    composition: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    block_id_column: str = "block_id",
    reference_code_column: str = "leading_species_code",
) -> pd.DataFrame:
    """Compare public leading species with a reference table.

    Parameters
    ----------
    composition : pandas.DataFrame
        Long composition table; leading rows are selected.
    reference : pandas.DataFrame
        Reference table with block id and leading species code.
    block_id_column : str, optional
        Block id column in the reference table.
    reference_code_column : str, optional
        Reference leading-species column.

    Returns
    -------
    pandas.DataFrame
        One row per block with public and reference labels and a match flag.

    Raises
    ------
    SpeciesError
        If required columns are missing.
    """
    if block_id_column not in reference or reference_code_column not in reference:
        raise SpeciesError(
            f"species reference needs {block_id_column!r} and {reference_code_column!r}"
        )
    leading = composition[composition["is_leading"].astype(bool)].copy()
    if leading["block_id"].duplicated().any():
        raise SpeciesError("species composition has more than one leading row per block")
    usable_reference = reference.dropna(subset=[reference_code_column])
    merged = leading.merge(
        usable_reference[[block_id_column, reference_code_column]],
        left_on="block_id",
        right_on=block_id_column,
        how="outer",
        indicator=True,
    )
    merged["public_code"] = merged["species_code"]
    merged["public_name"] = merged["species_name"]
    merged["reference_code"] = merged[reference_code_column]
    merged["match"] = merged["public_code"].astype("Int64") == merged["reference_code"].astype(
        "Int64"
    )
    merged["match"] = merged["match"].fillna(False).astype(bool)
    return merged[
        [
            "block_id",
            "public_code",
            "public_name",
            "reference_code",
            "match",
            "_merge",
        ]
    ]


def summarize_comparison(comparison: pd.DataFrame) -> dict[str, object]:
    """Summarize a leading-species comparison.

    Parameters
    ----------
    comparison : pandas.DataFrame
        Output of :func:`compare_leading_species`.

    Returns
    -------
    dict
        Compared blocks, matches, agreement percentage, and missing counts.
    """
    both = comparison[comparison["_merge"] == "both"]
    matches = int(both["match"].sum())
    return {
        "blocks_compared": len(both),
        "matches": matches,
        "agreement_pct": (100.0 * matches / len(both)) if len(both) else None,
        "missing_public": int((comparison["_merge"] == "right_only").sum()),
        "missing_reference": int((comparison["_merge"] == "left_only").sum()),
    }


def build_species_fractions(
    frame: pd.DataFrame,
    *,
    class_map: Sequence[SpeciesClass],
    code_map: Mapping[str, int],
    source_id: str,
    source_version: str,
    species_columns: Sequence[str] = (
        "species_cd_1",
        "species_cd_2",
        "species_cd_3",
        "species_cd_4",
        "species_cd_5",
        "species_cd_6",
    ),
    percent_columns: Sequence[str] = (
        "species_pct_1",
        "species_pct_2",
        "species_pct_3",
        "species_pct_4",
        "species_pct_5",
        "species_pct_6",
    ),
    block_id_column: str = "feature_id",
    allow_missing: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build a long species-fraction table from explicit species columns.

    Fractions are taken from the declared percentage columns. They are never
    normalized silently: a block whose percentages do not sum to 100 within
    one percentage point is an error.

    Parameters
    ----------
    frame : pandas.DataFrame
        Block table with species code and percentage columns.
    class_map : sequence of SpeciesClass
        Raster/NFI class map used to name the codes.
    code_map : mapping of str to int
        Source species code to NFI class code.
    source_id : str
        Source identifier.
    source_version : str
        Required source version or vintage.
    species_columns : sequence of str, optional
        Species code columns.
    percent_columns : sequence of str, optional
        Percentage columns, parallel to ``species_columns``.
    block_id_column : str, optional
        Block id column.
    allow_missing : bool, optional
        When True, blocks with no species rows are omitted and listed in the
        metadata instead of failing the whole table.

    Returns
    -------
    tuple of (pandas.DataFrame, dict)
        Long fraction rows and a JSON-ready metadata mapping.

    Raises
    ------
    SpeciesError
        If columns, codes, percentages, or block coverage are invalid.
    """
    if not source_version.strip():
        raise SpeciesError("species source_version must not be empty")
    if len(species_columns) != len(percent_columns):
        raise SpeciesError("species and percent columns must have equal length")
    if block_id_column not in frame:
        raise SpeciesError(f"species fraction table needs {block_id_column!r}")
    missing_columns = [
        column for column in [*species_columns, *percent_columns] if column not in frame
    ]
    if missing_columns:
        raise SpeciesError("species fraction table is missing: " + ", ".join(missing_columns))
    classes = {item.code: item for item in class_map}
    rows: list[dict[str, object]] = []
    missing_blocks: list[int] = []
    for record in frame.to_dict("records"):
        block = int(str(record[block_id_column]))
        pairs: list[tuple[str, float]] = []
        for species_column, percent_column in zip(species_columns, percent_columns, strict=True):
            species = record.get(species_column)
            percent = record.get(percent_column)
            if pd.isna(species) or pd.isna(percent):
                continue
            pairs.append((str(species).strip(), float(percent)))
        if not pairs:
            if allow_missing:
                missing_blocks.append(block)
                continue
            raise SpeciesError(f"species fraction block {block} has no species rows")
        total = sum(percent for _species, percent in pairs)
        if abs(total - 100.0) > 1.0:
            raise SpeciesError(f"species fractions for block {block} sum to {total:g}, not 100")
        leading_code = max(pairs, key=lambda item: item[1])[0]
        for species, percent in pairs:
            if species not in code_map:
                raise SpeciesError(f"species code {species!r} is not in the code map")
            code = int(code_map[species])
            if code not in classes:
                raise SpeciesError(f"NFI class {code} for {species!r} is not in the class map")
            rows.append(
                {
                    "block_id": block,
                    "species_code": code,
                    "species_name": classes[code].name,
                    "nfi_code": classes[code].nfi_code,
                    "fraction": percent / 100.0,
                    "is_leading": species == leading_code,
                }
            )
    if not rows:
        raise SpeciesError("species fraction table is empty")
    metadata = {
        "schema_version": SPECIES_FRACTION_SCHEMA_VERSION,
        "source_id": source_id,
        "source_version": source_version,
        "method": "Declared species percentages; no normalization or imputation.",
        "block_count": len({row["block_id"] for row in rows}),
        "missing_blocks": missing_blocks,
        "species_columns": list(species_columns),
        "percent_columns": list(percent_columns),
        "code_map": dict(code_map),
    }
    return pd.DataFrame(
        rows,
        columns=[
            "block_id",
            "species_code",
            "species_name",
            "nfi_code",
            "fraction",
            "is_leading",
        ],
    ), metadata


def write_species_fractions(
    fractions: pd.DataFrame,
    metadata: Mapping[str, object],
    output_csv: str | Path,
    metadata_json: str | Path,
) -> None:
    """Write a species-fraction table and metadata.

    Parameters
    ----------
    fractions : pandas.DataFrame
        Long fraction table.
    metadata : mapping
        JSON-ready metadata.
    output_csv : str or Path
        Destination CSV.
    metadata_json : str or Path
        Destination metadata JSON.
    """
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    fractions.to_csv(output, index=False)
    metadata_path = Path(metadata_json)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def summarize_species_fractions(fractions: pd.DataFrame) -> pd.DataFrame:
    """Summarize leading species and non-leading fraction by block.

    Parameters
    ----------
    fractions : pandas.DataFrame
        Long fraction table from :func:`build_species_fractions`.

    Returns
    -------
    pandas.DataFrame
        One row per block with leading code/name/fraction, non-leading fraction,
        and species count.
    """
    rows: list[dict[str, object]] = []
    for block, group in fractions.groupby("block_id", sort=True):
        leading = group[group["is_leading"].astype(bool)]
        if len(leading) != 1:
            raise SpeciesError(f"block {block} must have exactly one leading species")
        lead = leading.iloc[0]
        rows.append(
            {
                "block_id": int(str(block)),
                "leading_species_code": int(lead["species_code"]),
                "leading_species_name": str(lead["species_name"]),
                "leading_fraction": float(lead["fraction"]),
                "non_leading_fraction": 1.0 - float(lead["fraction"]),
                "species_count": len(group),
            }
        )
    return pd.DataFrame(rows)


__all__ = [
    "DEFAULT_LICENCE",
    "DEFAULT_SOURCE_ID",
    "SPECIES_COMPOSITION_SCHEMA_VERSION",
    "SPECIES_FRACTION_SCHEMA_VERSION",
    "SPECIES_SOURCE_SCHEMA_VERSION",
    "SpeciesClass",
    "SpeciesError",
    "SpeciesSource",
    "build_species_fractions",
    "compare_leading_species",
    "read_class_map",
    "read_species_composition",
    "sample_species_raster",
    "summarize_comparison",
    "summarize_species_fractions",
    "write_species_composition",
    "write_species_fractions",
]
