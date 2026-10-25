"""Read and validate FEMIC LidarBC product bundles.

WS4 is a consumer of the FEMIC producer contract. This module pins a bundle,
verifies its manifest and checksums, and maps terrain/canopy rasters to
polygon support without re-running FEMIC discovery or materialization.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # geopandas objects are untyped in the consumer adapter

from ws4.model.schema import load_manifest

FEMIC_LIDAR_MANIFEST_SCHEMA = "femic.lidar.product.v1"
FEMIC_LIDAR_LAYOUT_VERSION = "femic.lidar.bundle.v1"
FEMIC_LIDAR_LICENCE_ID = "OGL-BC"
FEMIC_LIDAR_MANIFEST_NAME = "manifest.json"
FEMIC_LIDAR_SELECTION_PATH = "provenance/selection.json"
FEMIC_LIDAR_SIDECAR_NAME = "lidar_products.json"


class FemicLidarError(RuntimeError):
    """Raised when a FEMIC LidarBC bundle cannot be consumed."""


@dataclass(frozen=True)
class FemicLidarProduct:
    """One pinned product record from a FEMIC bundle manifest."""

    product: str
    relative_path: str
    sha256: str
    size_bytes: int
    crs: str
    resolution_m: float | None
    vertical_datum: str
    licence_id: str
    source_tile_ids: tuple[str, ...]
    derived: bool
    lineage: tuple[str, ...]


@dataclass(frozen=True)
class FemicLidarBundle:
    """Pinned FEMIC LidarBC bundle metadata."""

    bundle_dir: Path
    manifest_path: Path
    bundle_id: str
    bundle_version: str
    source: dict[str, object]
    selection: dict[str, object]
    processing: dict[str, object]
    products: dict[str, FemicLidarProduct]
    manifest_sha256: str
    total_bytes: int


@dataclass(frozen=True)
class FemicLidarValidation:
    """Validation report for a FEMIC LidarBC bundle."""

    bundle_dir: Path
    is_valid: bool
    checked_utc: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    product_count: int
    total_bytes: int

    def to_dict(self) -> dict[str, object]:
        """Return the validation report as a JSON-serializable mapping."""
        return {
            "bundle_dir": str(self.bundle_dir),
            "is_valid": self.is_valid,
            "checked_utc": self.checked_utc,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "product_count": self.product_count,
            "total_bytes": self.total_bytes,
        }


@dataclass(frozen=True)
class LidarPolygonSummary:
    """One polygon-level support summary from a FEMIC product."""

    polygon_id: str
    product: str
    valid_pixels: int
    statistics: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        """Return the summary as a JSON-serializable mapping."""
        return {
            "polygon_id": self.polygon_id,
            "product": self.product,
            "valid_pixels": self.valid_pixels,
            "statistics": self.statistics,
        }


def load_femic_lidar_bundle(
    bundle_dir: Path,
    *,
    expected_bundle_id: str | None = None,
    expected_bundle_version: str | None = None,
    verify_checksums: bool = True,
) -> FemicLidarBundle:
    """Load and validate a FEMIC LidarBC bundle for consumption."""
    report, bundle = _validate(
        bundle_dir,
        verify_checksums=verify_checksums,
        expected_bundle_id=expected_bundle_id,
        expected_bundle_version=expected_bundle_version,
    )
    if bundle is None or not report.is_valid:
        raise FemicLidarError("Invalid FEMIC LidarBC bundle: " + "; ".join(report.errors))
    return bundle


def validate_femic_lidar_bundle(
    bundle_dir: Path,
    *,
    verify_checksums: bool = True,
) -> FemicLidarValidation:
    """Validate a FEMIC LidarBC bundle without raising on contract errors."""
    report, _ = _validate(
        bundle_dir,
        verify_checksums=verify_checksums,
        expected_bundle_id=None,
        expected_bundle_version=None,
    )
    return report


def bundle_pin(bundle: FemicLidarBundle) -> dict[str, object]:
    """Return the stable pin fields WS4 records in its dataset provenance."""
    return {
        "bundle_id": bundle.bundle_id,
        "bundle_version": bundle.bundle_version,
        "manifest_sha256": bundle.manifest_sha256,
        "products": {
            name: {"sha256": product.sha256, "relative_path": product.relative_path}
            for name, product in sorted(bundle.products.items())
        },
    }


def register_femic_lidar_bundle(
    dataset_dir: Path,
    bundle_dir: Path,
    *,
    expected_bundle_id: str | None = None,
    expected_bundle_version: str | None = None,
    registered_utc: str | None = None,
) -> dict[str, object]:
    """Register a validated FEMIC bundle in a compiled WS4 dataset.

    Writes the pin to the dataset manifest metadata and a
    ``lidar_products.json`` sidecar. The bundle is referenced, not copied.
    """
    dataset_root = dataset_dir.expanduser().resolve()
    manifest_path = dataset_root / "manifest.json"
    if not manifest_path.is_file():
        raise FemicLidarError(f"Dataset manifest is missing: {manifest_path}")
    bundle = load_femic_lidar_bundle(
        bundle_dir,
        expected_bundle_id=expected_bundle_id,
        expected_bundle_version=expected_bundle_version,
    )
    manifest = load_manifest(dataset_root)
    registration: dict[str, object] = {
        **bundle_pin(bundle),
        "bundle_dir": _bundle_reference(dataset_root, bundle.bundle_dir),
        "source_id": bundle.source.get("source_id"),
        "licence_id": bundle.source.get("licence_id"),
        "native_crs": bundle.source.get("native_crs"),
        "registered_utc": registered_utc or datetime.now(UTC).isoformat(),
    }
    metadata = dict(manifest.metadata)
    metadata["lidar_products"] = registration
    manifest = manifest.model_copy(update={"metadata": metadata})
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    sidecar = dataset_root / FEMIC_LIDAR_SIDECAR_NAME
    sidecar.write_text(json.dumps(registration, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return registration


def read_registered_femic_lidar(dataset_dir: Path) -> dict[str, object] | None:
    """Read the registered FEMIC LidarBC pin from a dataset, if present."""
    dataset_root = dataset_dir.expanduser().resolve()
    sidecar = dataset_root / FEMIC_LIDAR_SIDECAR_NAME
    if sidecar.is_file():
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FemicLidarError(f"Invalid LidarBC sidecar: {sidecar}") from exc
        if not isinstance(payload, dict):
            raise FemicLidarError(f"LidarBC sidecar must be an object: {sidecar}")
        return {str(key): value for key, value in payload.items()}
    manifest_path = dataset_root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = load_manifest(dataset_root)
    except (OSError, ValueError) as exc:
        raise FemicLidarError(f"Unable to read dataset manifest: {exc}") from exc
    value = manifest.metadata.get("lidar_products")
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return None


def validate_registered_femic_lidar(dataset_dir: Path) -> FemicLidarValidation:
    """Revalidate the bundle currently pinned by a dataset."""
    registration = read_registered_femic_lidar(dataset_dir)
    if registration is None:
        raise FemicLidarError("Dataset has no registered FEMIC LidarBC product.")
    bundle_ref = registration.get("bundle_dir")
    if not isinstance(bundle_ref, str) or not bundle_ref.strip():
        raise FemicLidarError("Registered LidarBC pin has no bundle_dir.")
    bundle_path = Path(bundle_ref)
    if not bundle_path.is_absolute():
        bundle_path = dataset_dir.expanduser().resolve() / bundle_path
    return validate_femic_lidar_bundle(bundle_path)


def summarize_femic_lidar_for_polygons(
    bundle: FemicLidarBundle,
    polygons_path: Path,
    *,
    product: str = "slope",
    id_field: str | None = None,
    statistics: tuple[str, ...] = ("mean", "p95"),
) -> tuple[LidarPolygonSummary, ...]:
    """Summarize one bundle raster over polygon support.

    Geometry and raster CRS must already match. No reprojection or resampling
    is performed.
    """
    try:
        import geopandas as gpd
        import numpy as np
        import rasterio  # type: ignore[import-untyped]
        import rasterio.mask  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - dependency boundary
        raise FemicLidarError(
            "Polygon summaries require the `geo` optional dependencies plus rasterio."
        ) from exc
    if product not in bundle.products:
        raise FemicLidarError(f"Bundle does not contain product {product!r}.")
    record = bundle.products[product]
    raster_path = bundle.bundle_dir / record.relative_path
    try:
        frame = gpd.read_file(polygons_path)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise FemicLidarError(f"Unable to read polygon support: {exc}") from exc
    if frame.crs is None:
        raise FemicLidarError("Polygon support has no CRS.")
    if frame.crs.to_string() != record.crs:
        raise FemicLidarError(
            f"Polygon CRS {frame.crs.to_string()!r} does not match product CRS "
            f"{record.crs!r}; reprojection is not allowed."
        )
    if id_field is not None and id_field not in frame.columns:
        raise FemicLidarError(f"Polygon support is missing id field {id_field!r}.")
    summaries: list[LidarPolygonSummary] = []
    with rasterio.open(raster_path) as source:
        for index, row in frame.iterrows():
            geometry = row.geometry
            if geometry is None or geometry.is_empty:
                continue
            try:
                masked, _ = rasterio.mask.mask(
                    source,
                    [geometry],
                    crop=True,
                    filled=False,
                )
            except ValueError:
                continue
            values = np.asarray(masked[0].compressed(), dtype=float)
            if values.size == 0:
                continue
            stats: dict[str, float] = {}
            for stat in statistics:
                if stat == "mean":
                    stats[stat] = float(np.mean(values))
                elif stat == "p95":
                    stats[stat] = float(np.percentile(values, 95))
                elif stat == "min":
                    stats[stat] = float(np.min(values))
                elif stat == "max":
                    stats[stat] = float(np.max(values))
                elif stat == "p90":
                    stats[stat] = float(np.percentile(values, 90))
                elif stat.startswith("cover_ge_"):
                    threshold = float(stat.removeprefix("cover_ge_"))
                    stats[stat] = float(np.mean(values >= threshold) * 100.0)
                else:
                    raise FemicLidarError(f"Unsupported summary statistic {stat!r}.")
            polygon_id = str(row[id_field]) if id_field is not None else str(index)
            summaries.append(
                LidarPolygonSummary(
                    polygon_id=polygon_id,
                    product=product,
                    valid_pixels=int(values.size),
                    statistics=stats,
                )
            )
    return tuple(summaries)


def _validate(
    bundle_dir: Path,
    *,
    verify_checksums: bool,
    expected_bundle_id: str | None,
    expected_bundle_version: str | None,
) -> tuple[FemicLidarValidation, FemicLidarBundle | None]:
    root = bundle_dir.expanduser().resolve()
    manifest_path = root / FEMIC_LIDAR_MANIFEST_NAME
    errors: list[str] = []
    warnings: list[str] = []
    bundle: FemicLidarBundle | None = None
    product_count = 0
    total_bytes = 0
    try:
        raw = manifest_path.read_bytes()
        manifest = _require_object(json.loads(raw), context="manifest")
        manifest_sha = hashlib.sha256(raw).hexdigest()
        if manifest.get("schema_version") != FEMIC_LIDAR_MANIFEST_SCHEMA:
            errors.append(f"Unsupported manifest schema {manifest.get('schema_version')!r}.")
        if manifest.get("layout_version") != FEMIC_LIDAR_LAYOUT_VERSION:
            errors.append(f"Unsupported layout version {manifest.get('layout_version')!r}.")
        bundle_id = _require_string(manifest, "bundle_id")
        bundle_version = _require_string(manifest, "bundle_version")
        if expected_bundle_id is not None and bundle_id != expected_bundle_id:
            errors.append("Bundle id does not match the pinned id.")
        if expected_bundle_version is not None and bundle_version != expected_bundle_version:
            errors.append("Bundle version does not match the pinned version.")
        source = _require_object(manifest.get("source"), context="source")
        selection = _require_object(manifest.get("selection"), context="selection")
        processing = _require_object(manifest.get("processing"), context="processing")
        if source.get("licence_id") != FEMIC_LIDAR_LICENCE_ID:
            errors.append("Bundle licence is not OGL-BC.")
        if not isinstance(source.get("native_crs"), str) or not source["native_crs"]:
            errors.append("Bundle source has no native CRS.")
        selection_tiles = selection.get("tile_ids")
        if not isinstance(selection_tiles, list):
            errors.append("Bundle selection has no tile_ids.")
            selection_tiles = []
        product_records = manifest.get("products")
        if not isinstance(product_records, list) or not product_records:
            errors.append("Bundle manifest has no products.")
            product_records = []
        products: dict[str, FemicLidarProduct] = {}
        for index, item in enumerate(product_records, start=1):
            record = _require_object(item, context=f"product {index}")
            product = _require_string(record, "product")
            relative_path = _require_string(record, "relative_path")
            sha256 = _require_string(record, "sha256")
            size_bytes = _require_int(record, "size_bytes")
            crs = _require_string(record, "crs")
            vertical_datum = _require_string(record, "vertical_datum")
            licence_id = _require_string(record, "licence_id")
            resolution = _optional_float(record.get("resolution_m"))
            source_tiles = record.get("source_tile_ids")
            if not isinstance(source_tiles, list):
                errors.append(f"Product {product!r} has no source_tile_ids.")
                source_tiles = []
            unknown_tiles = {str(value) for value in source_tiles} - {
                str(value) for value in selection_tiles
            }
            if unknown_tiles:
                errors.append(
                    f"Product {product!r} references tiles outside the selection: "
                    + ", ".join(sorted(unknown_tiles))
                )
            path = (root / relative_path).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                errors.append(f"Product {product!r} path escapes the bundle.")
                continue
            if not path.is_file():
                errors.append(f"Product {product!r} file is missing: {relative_path}")
            else:
                if path.stat().st_size != size_bytes:
                    errors.append(f"Product {product!r} size mismatch.")
                if verify_checksums and _sha256_file(path) != sha256:
                    errors.append(f"Product {product!r} checksum mismatch.")
            product_count += 1
            total_bytes += size_bytes
            products[product] = FemicLidarProduct(
                product=product,
                relative_path=relative_path,
                sha256=sha256,
                size_bytes=size_bytes,
                crs=crs,
                resolution_m=resolution,
                vertical_datum=vertical_datum,
                licence_id=licence_id,
                source_tile_ids=tuple(str(value) for value in source_tiles),
                derived=bool(record.get("derived", False)),
                lineage=_string_tuple(record.get("lineage", [])),
            )
        summary = _require_object(manifest.get("summary"), context="summary")
        if summary.get("product_count") != product_count:
            errors.append("Manifest product_count does not match products.")
        if summary.get("total_bytes") != total_bytes:
            errors.append("Manifest total_bytes does not match products.")
        if not errors:
            bundle = FemicLidarBundle(
                bundle_dir=root,
                manifest_path=manifest_path,
                bundle_id=bundle_id,
                bundle_version=bundle_version,
                source=source,
                selection=selection,
                processing=processing,
                products=products,
                manifest_sha256=manifest_sha,
                total_bytes=total_bytes,
            )
    except (OSError, json.JSONDecodeError, FemicLidarError) as exc:
        errors.append(str(exc))
    report = FemicLidarValidation(
        bundle_dir=root,
        is_valid=not errors,
        checked_utc=datetime.now(UTC).isoformat(),
        errors=tuple(errors),
        warnings=tuple(warnings),
        product_count=product_count,
        total_bytes=total_bytes,
    )
    return report, bundle


def _require_object(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise FemicLidarError(f"{context} must be an object.")
    return {str(key): item for key, item in value.items()}


def _require_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FemicLidarError(f"Manifest field {key!r} must be a non-empty string.")
    return value.strip()


def _require_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise FemicLidarError(f"Manifest field {key!r} must be an integer.")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FemicLidarError("Numeric manifest field must be a number.")
    return float(value)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _bundle_reference(dataset_root: Path, bundle_root: Path) -> str:
    try:
        return str(bundle_root.resolve().relative_to(dataset_root))
    except ValueError:
        return str(bundle_root.resolve())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class LidarMappingResult:
    """Fragment and block terrain/canopy mapping from a registered bundle."""

    bundle_id: str
    bundle_version: str
    manifest_sha256: str
    crs: str
    resolution_m: float | None
    products: tuple[str, ...]
    statistics: tuple[str, ...]
    fragments: tuple[dict[str, object], ...]
    blocks: tuple[dict[str, object], ...]
    aggregation_rules: dict[str, str]
    generated_utc: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return the mapping as a JSON-serializable mapping."""
        return {
            "bundle_id": self.bundle_id,
            "bundle_version": self.bundle_version,
            "manifest_sha256": self.manifest_sha256,
            "crs": self.crs,
            "resolution_m": self.resolution_m,
            "products": list(self.products),
            "statistics": list(self.statistics),
            "aggregation_rules": self.aggregation_rules,
            "fragment_count": len(self.fragments),
            "block_count": len(self.blocks),
            "generated_utc": self.generated_utc,
            "warnings": list(self.warnings),
            "fragments": list(self.fragments),
            "blocks": list(self.blocks),
        }


def load_registered_femic_lidar_bundle(dataset_dir: Path) -> FemicLidarBundle:
    """Load the bundle pinned by a dataset registration."""
    registration = read_registered_femic_lidar(dataset_dir)
    if registration is None:
        raise FemicLidarError("Dataset has no registered FEMIC LidarBC product.")
    bundle_ref = registration.get("bundle_dir")
    if not isinstance(bundle_ref, str) or not bundle_ref.strip():
        raise FemicLidarError("Registered LidarBC pin has no bundle_dir.")
    bundle_path = Path(bundle_ref)
    if not bundle_path.is_absolute():
        bundle_path = dataset_dir.expanduser().resolve() / bundle_path
    bundle_id = registration.get("bundle_id")
    bundle_version = registration.get("bundle_version")
    return load_femic_lidar_bundle(
        bundle_path,
        expected_bundle_id=bundle_id if isinstance(bundle_id, str) else None,
        expected_bundle_version=bundle_version if isinstance(bundle_version, str) else None,
    )


def map_femic_lidar_to_fragments(
    bundle: FemicLidarBundle,
    fragments_path: Path,
    *,
    products: tuple[str, ...] = ("slope", "chm"),
    statistics: tuple[str, ...] = ("mean", "p95"),
    id_field: str = "fragment_id",
    block_field: str = "block_id",
    area_field: str = "area_ha",
    generated_utc: str | None = None,
) -> LidarMappingResult:
    """Map native bundle rasters to WS4 fragment and block support.

    Fragment support uses each fragment polygon directly. Block support uses
    the dissolved block geometry. No resampling or reprojection is performed.
    """
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover - dependency boundary
        raise FemicLidarError("Lidar mapping requires `ws4[lidar]`.") from exc
    for product in products:
        if product not in bundle.products:
            raise FemicLidarError(f"Bundle does not contain product {product!r}.")
    try:
        frame = gpd.read_file(fragments_path)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise FemicLidarError(f"Unable to read fragments: {exc}") from exc
    if frame.empty:
        raise FemicLidarError("Fragment inventory contains no features.")
    if frame.crs is None:
        raise FemicLidarError("Fragment inventory has no CRS.")
    for field in (id_field, block_field):
        if field not in frame.columns:
            raise FemicLidarError(f"Fragment inventory is missing field {field!r}.")
    product_crs = {bundle.products[product].crs for product in products}
    if len(product_crs) != 1:
        raise FemicLidarError("Selected products do not share one CRS.")
    if frame.crs.to_string() != next(iter(product_crs)):
        raise FemicLidarError(
            f"Fragment CRS {frame.crs.to_string()!r} does not match product CRS "
            f"{next(iter(product_crs))!r}; reprojection is not allowed."
        )
    area_present = area_field in frame.columns
    warnings: list[str] = []
    if not area_present:
        warnings.append(f"Optional area field {area_field!r} is missing.")
    fragment_rows: dict[str, dict[str, object]] = {}
    for _, record in frame.iterrows():
        fragment_id = _id_text(record[id_field])
        fragment_rows[fragment_id] = {
            id_field: record[id_field],
            block_field: record[block_field],
            area_field: float(record[area_field]) if area_present else None,
        }
        for product in products:
            fragment_rows[fragment_id][f"{product}_valid_pixels"] = 0
            for stat in statistics:
                fragment_rows[fragment_id][f"{product}_{stat}"] = None
    for product in products:
        summaries = summarize_femic_lidar_for_polygons(
            bundle,
            fragments_path,
            product=product,
            id_field=id_field,
            statistics=statistics,
        )
        for summary in summaries:
            row = fragment_rows.get(_id_text(summary.polygon_id))
            if row is None:
                continue
            row[f"{product}_valid_pixels"] = summary.valid_pixels
            for stat, value in summary.statistics.items():
                row[f"{product}_{stat}"] = value
    missing_fragments = sum(
        1
        for row in fragment_rows.values()
        if all(_valid_pixels(row, product) == 0 for product in products)
    )
    if missing_fragments:
        warnings.append(
            f"{missing_fragments} fragments had no valid pixels for the selected products."
        )
    blocks_frame = frame[[block_field, "geometry"]].dissolve(by=block_field, as_index=False)
    block_rows: dict[str, dict[str, object]] = {}
    for _, record in blocks_frame.iterrows():
        block_id = _id_text(record[block_field])
        block_rows[block_id] = {block_field: record[block_field]}
        for product in products:
            block_rows[block_id][f"{product}_valid_pixels"] = 0
            for stat in statistics:
                block_rows[block_id][f"{product}_{stat}"] = None
    with tempfile.TemporaryDirectory(prefix="ws4_lidar_blocks_") as temporary:
        block_path = Path(temporary) / "blocks.gpkg"
        blocks_frame.to_file(block_path, driver="GPKG", layer="blocks")
        for product in products:
            summaries = summarize_femic_lidar_for_polygons(
                bundle,
                block_path,
                product=product,
                id_field=block_field,
                statistics=statistics,
            )
            for summary in summaries:
                row = block_rows.get(_id_text(summary.polygon_id))
                if row is None:
                    continue
                row[f"{product}_valid_pixels"] = summary.valid_pixels
                for stat, value in summary.statistics.items():
                    row[f"{product}_{stat}"] = value
    if area_present:
        areas = frame.groupby(block_field, as_index=False)[area_field].sum()
        for _, record in areas.iterrows():
            block_rows[_id_text(record[block_field])][area_field] = float(record[area_field])
    resolutions: list[float] = []
    for product in products:
        resolution = bundle.products[product].resolution_m
        if resolution is not None:
            resolutions.append(resolution)
    result = LidarMappingResult(
        bundle_id=bundle.bundle_id,
        bundle_version=bundle.bundle_version,
        manifest_sha256=bundle.manifest_sha256,
        crs=next(iter(product_crs)),
        resolution_m=min(resolutions) if resolutions else None,
        products=products,
        statistics=statistics,
        fragments=tuple(fragment_rows.values()),
        blocks=tuple(block_rows.values()),
        aggregation_rules={
            "fragments": "zonal statistics over each fragment polygon",
            "blocks": "zonal statistics over the dissolved block geometry",
            "resolution": "native product resolution; no resampling",
            "crs": "product CRS; no reprojection",
        },
        generated_utc=generated_utc or datetime.now(UTC).isoformat(),
        warnings=tuple(warnings),
    )
    return result


def write_lidar_mapping(result: LidarMappingResult, output_dir: Path) -> dict[str, Path]:
    """Write fragment/block mapping CSVs and a provenance manifest."""
    root = output_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    fragment_path = root / "lidar_fragments.csv"
    block_path = root / "lidar_blocks.csv"
    manifest_path = root / "lidar_mapping_manifest.json"
    pd.DataFrame(result.fragments).to_csv(fragment_path, index=False)
    pd.DataFrame(result.blocks).to_csv(block_path, index=False)
    manifest_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "fragments": fragment_path,
        "blocks": block_path,
        "manifest": manifest_path,
    }


def _id_text(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _valid_pixels(row: dict[str, object], product: str) -> int:
    value = row.get(f"{product}_valid_pixels")
    return value if isinstance(value, int) else 0


@dataclass(frozen=True)
class CanopyMappingResult:
    """Canopy and optional tree/VRI mapping for WS4 support."""

    bundle_id: str
    bundle_version: str
    manifest_sha256: str
    crs: str
    resolution_m: float | None
    fragments: tuple[dict[str, object], ...]
    blocks: tuple[dict[str, object], ...]
    vri_summary: dict[str, object] | None
    tree_summary: dict[str, object] | None
    aggregation_rules: dict[str, str]
    caveats: tuple[str, ...]
    generated_utc: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return the canopy mapping as a JSON-serializable mapping."""
        return {
            "bundle_id": self.bundle_id,
            "bundle_version": self.bundle_version,
            "manifest_sha256": self.manifest_sha256,
            "crs": self.crs,
            "resolution_m": self.resolution_m,
            "aggregation_rules": self.aggregation_rules,
            "caveats": list(self.caveats),
            "fragment_count": len(self.fragments),
            "block_count": len(self.blocks),
            "vri_summary": self.vri_summary,
            "tree_summary": self.tree_summary,
            "generated_utc": self.generated_utc,
            "warnings": list(self.warnings),
            "fragments": list(self.fragments),
            "blocks": list(self.blocks),
        }


def map_femic_canopy_to_fragments(
    bundle: FemicLidarBundle,
    fragments_path: Path,
    *,
    vri_path: Path | None = None,
    vri_height_field: str = "proj_height_1",
    vri_cover_field: str | None = "crown_closure",
    tree_product: str | None = None,
    tree_height_field: str = "height_m",
    tree_species_field: str | None = "species",
    id_field: str = "fragment_id",
    block_field: str = "block_id",
    area_field: str = "area_ha",
    generated_utc: str | None = None,
) -> CanopyMappingResult:
    """Map CHM/canopy metrics, VRI uncertainty, and optional tree summaries."""
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover - dependency boundary
        raise FemicLidarError("Canopy mapping requires `ws4[lidar]`.") from exc
    if "chm" not in bundle.products:
        raise FemicLidarError("Bundle does not contain product 'chm'.")
    base = map_femic_lidar_to_fragments(
        bundle,
        fragments_path,
        products=("chm",),
        statistics=("mean", "p90", "p95", "max", "cover_ge_2", "cover_ge_5", "cover_ge_10"),
        id_field=id_field,
        block_field=block_field,
        area_field=area_field,
        generated_utc=generated_utc,
    )
    frame = gpd.read_file(fragments_path)
    fragments = [dict(row) for row in base.fragments]
    blocks = [dict(row) for row in base.blocks]
    warnings = list(base.warnings)
    vri_summary: dict[str, object] | None = None
    if vri_path is not None:
        vri_frame = gpd.read_file(vri_path)
        if vri_frame.crs is None or frame.crs is None:
            raise FemicLidarError("VRI and fragment layers must both have a CRS.")
        if vri_frame.crs.to_string() != frame.crs.to_string():
            raise FemicLidarError("VRI CRS does not match fragment CRS.")
        if vri_height_field not in vri_frame.columns:
            raise FemicLidarError(f"VRI is missing height field {vri_height_field!r}.")
        if vri_cover_field is not None and vri_cover_field not in vri_frame.columns:
            raise FemicLidarError(f"VRI is missing cover field {vri_cover_field!r}.")
        fragment_vri = _vri_support_values(
            frame[[id_field, "geometry"]],
            id_field,
            vri_frame,
            vri_height_field,
            vri_cover_field,
        )
        block_frame = frame[[block_field, "geometry"]].dissolve(by=block_field, as_index=False)
        block_vri = _vri_support_values(
            block_frame,
            block_field,
            vri_frame,
            vri_height_field,
            vri_cover_field,
        )
        _apply_vri_rows(fragments, id_field, fragment_vri)
        _apply_vri_rows(blocks, block_field, block_vri)
        vri_summary = _vri_summary(fragments)
    tree_summary: dict[str, object] | None = None
    if tree_product is not None:
        if tree_product not in bundle.products:
            raise FemicLidarError(f"Bundle does not contain product {tree_product!r}.")
        tree_path = bundle.bundle_dir / bundle.products[tree_product].relative_path
        tree_frame = gpd.read_file(tree_path)
        if tree_frame.crs is None:
            raise FemicLidarError("Tree product has no CRS.")
        if tree_frame.crs.to_string() != frame.crs.to_string():
            raise FemicLidarError("Tree product CRS does not match fragment CRS.")
        tree_fragment = _tree_support_values(
            frame[[id_field, "geometry"]],
            id_field,
            tree_frame,
            tree_height_field,
            tree_species_field,
        )
        block_frame = frame[[block_field, "geometry"]].dissolve(by=block_field, as_index=False)
        tree_block = _tree_support_values(
            block_frame,
            block_field,
            tree_frame,
            tree_height_field,
            tree_species_field,
        )
        _apply_tree_rows(fragments, id_field, tree_fragment)
        _apply_tree_rows(blocks, block_field, tree_block)
        supports_with_trees = 0
        for row in fragments:
            count = row.get("tree_count")
            if isinstance(count, int) and count > 0:
                supports_with_trees += 1
        tree_summary = {
            "tree_count": len(tree_frame),
            "supports_with_trees": supports_with_trees,
            "height_field": tree_height_field,
            "species_field": tree_species_field,
        }
    result = CanopyMappingResult(
        bundle_id=base.bundle_id,
        bundle_version=base.bundle_version,
        manifest_sha256=base.manifest_sha256,
        crs=base.crs,
        resolution_m=base.resolution_m,
        fragments=tuple(fragments),
        blocks=tuple(blocks),
        vri_summary=vri_summary,
        tree_summary=tree_summary,
        aggregation_rules={
            "fragments": "zonal CHM statistics over each fragment polygon",
            "blocks": "zonal CHM statistics over the dissolved block geometry",
            "vri": "area-weighted VRI overlap per support",
            "trees": "tree points joined within each support",
            "resolution": "native CHM resolution; no resampling",
            "crs": "product CRS; no reprojection",
        },
        caveats=(
            "CHM height is DSM minus DEM on native grids.",
            "CHM cover at >=2 m is not VRI crown-closure equivalence.",
            "VRI comparison is uncertainty evidence, not field accuracy.",
            "Individual-tree summaries are optional and source-dependent.",
        ),
        generated_utc=generated_utc or datetime.now(UTC).isoformat(),
        warnings=tuple(warnings),
    )
    return result


def write_canopy_mapping(result: CanopyMappingResult, output_dir: Path) -> dict[str, Path]:
    """Write canopy fragment/block CSVs and provenance manifest."""
    root = output_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    fragment_path = root / "canopy_fragments.csv"
    block_path = root / "canopy_blocks.csv"
    manifest_path = root / "canopy_mapping_manifest.json"
    pd.DataFrame(result.fragments).to_csv(fragment_path, index=False)
    pd.DataFrame(result.blocks).to_csv(block_path, index=False)
    manifest_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "fragments": fragment_path,
        "blocks": block_path,
        "manifest": manifest_path,
    }


def _vri_support_values(
    support: Any,  # noqa: ANN401 - geopandas frame
    id_field: str,
    vri: Any,  # noqa: ANN401 - geopandas frame
    height_field: str,
    cover_field: str | None,
) -> dict[str, tuple[float | None, float | None, float]]:
    import geopandas as gpd

    left = support[[id_field, "geometry"]].copy()
    right = vri[[height_field, "geometry"]].copy()
    if cover_field is not None:
        right[cover_field] = vri[cover_field]
    intersection = gpd.overlay(left, right, how="intersection", keep_geom_type=False)
    if intersection.empty:
        return {}
    intersection["_area"] = intersection.geometry.area
    values: dict[str, tuple[float | None, float | None, float]] = {}
    for support_id, group in intersection.groupby(id_field):
        area = float(group["_area"].sum())
        if area <= 0:
            continue
        height = float((group[height_field] * group["_area"]).sum() / area)
        cover = (
            float((group[cover_field] * group["_area"]).sum() / area)
            if cover_field is not None
            else None
        )
        values[_id_text(support_id)] = (height, cover, area)
    return values


def _apply_vri_rows(
    rows: list[dict[str, object]],
    id_field: str,
    values: dict[str, tuple[float | None, float | None, float]],
) -> None:
    for row in rows:
        value = values.get(_id_text(row[id_field]))
        if value is None:
            row["vri_height_m"] = None
            row["vri_cover_pct"] = None
            row["chm_p95_minus_vri_height_m"] = None
            row["chm_cover_ge_2_minus_vri_cover_pct"] = None
            continue
        height, cover, _ = value
        row["vri_height_m"] = height
        row["vri_cover_pct"] = cover
        chm_height = _float_or_none(row.get("chm_p95"))
        chm_cover = _float_or_none(row.get("chm_cover_ge_2"))
        row["chm_p95_minus_vri_height_m"] = (
            chm_height - height if chm_height is not None and height is not None else None
        )
        row["chm_cover_ge_2_minus_vri_cover_pct"] = (
            chm_cover - cover if chm_cover is not None and cover is not None else None
        )


def _vri_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    height_deltas = [_float_or_none(row.get("chm_p95_minus_vri_height_m")) for row in rows]
    cover_deltas = [_float_or_none(row.get("chm_cover_ge_2_minus_vri_cover_pct")) for row in rows]
    height_values = [value for value in height_deltas if value is not None]
    cover_values = [value for value in cover_deltas if value is not None]
    return {
        "matched_supports": len(height_values),
        "height_bias_m": _mean(height_values),
        "height_mae_m": _mean([abs(value) for value in height_values]),
        "cover_bias_pct": _mean(cover_values),
        "cover_mae_pct": _mean([abs(value) for value in cover_values]),
    }


def _tree_support_values(
    support: Any,  # noqa: ANN401 - geopandas frame
    id_field: str,
    trees: Any,  # noqa: ANN401 - geopandas frame
    height_field: str,
    species_field: str | None,
) -> dict[str, dict[str, object]]:
    import geopandas as gpd
    import numpy as np

    left = support[[id_field, "geometry"]].copy()
    joined = gpd.sjoin(trees, left, how="inner", predicate="within")
    values: dict[str, dict[str, object]] = {}
    for support_id, group in joined.groupby(id_field):
        heights = np.asarray(group[height_field], dtype=float)
        heights = heights[np.isfinite(heights)]
        species: dict[str, int] = {}
        if species_field is not None and species_field in group.columns:
            species = {
                str(key): int(value)
                for key, value in group[species_field].fillna("unknown").value_counts().items()
            }
        values[_id_text(support_id)] = {
            "tree_count": len(group),
            "tree_height_mean_m": float(np.mean(heights)) if heights.size else None,
            "tree_height_p95_m": float(np.percentile(heights, 95)) if heights.size else None,
            "tree_species_counts": species,
        }
    return values


def _apply_tree_rows(
    rows: list[dict[str, object]],
    id_field: str,
    values: dict[str, dict[str, object]],
) -> None:
    for row in rows:
        value = values.get(_id_text(row[id_field]))
        if value is None:
            row["tree_count"] = 0
            row["tree_height_mean_m"] = None
            row["tree_height_p95_m"] = None
            row["tree_species_counts"] = {}
            continue
        row.update(value)


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mean(values: list[float]) -> float | None:
    return float(sum(values) / len(values)) if values else None


@dataclass(frozen=True)
class LidarDatasetIntegrationResult:
    """Fields and provenance written into a compiled dataset."""

    dataset_dir: Path
    bundle_id: str
    fragment_fields: tuple[str, ...]
    block_fields: tuple[str, ...]
    fragment_rows: int
    block_rows: int
    generated_utc: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return the integration result as a JSON-serializable mapping."""
        return {
            "dataset_dir": str(self.dataset_dir),
            "bundle_id": self.bundle_id,
            "fragment_fields": list(self.fragment_fields),
            "block_fields": list(self.block_fields),
            "fragment_rows": self.fragment_rows,
            "block_rows": self.block_rows,
            "generated_utc": self.generated_utc,
            "warnings": list(self.warnings),
        }


def integrate_lidar_mapping_into_dataset(
    dataset_dir: Path,
    fragment_mapping_path: Path,
    *,
    block_mapping_path: Path | None = None,
    overwrite: bool = False,
    generated_utc: str | None = None,
) -> LidarDatasetIntegrationResult:
    """Add prefixed LiDAR fields to a compiled dataset's fragment/block tables."""
    dataset_root = dataset_dir.expanduser().resolve()
    manifest_path = dataset_root / "manifest.json"
    if not manifest_path.is_file():
        raise FemicLidarError(f"Dataset manifest is missing: {manifest_path}")
    registration = read_registered_femic_lidar(dataset_root)
    if registration is None:
        raise FemicLidarError("Dataset has no registered FEMIC LidarBC product.")
    manifest = load_manifest(dataset_root)
    fragment_mapping = _read_mapping_csv(fragment_mapping_path, "fragment_id")
    block_mapping = (
        _read_mapping_csv(block_mapping_path, "block_id")
        if block_mapping_path is not None
        else None
    )
    fragments = pd.read_parquet(dataset_root / "fragments.parquet")
    blocks = pd.read_parquet(dataset_root / "blocks.parquet")
    warnings: list[str] = []
    fragment_fields, fragments = _merge_mapping(
        fragments,
        fragment_mapping,
        "fragment_id",
        overwrite=overwrite,
    )
    block_fields: tuple[str, ...] = ()
    if block_mapping is not None:
        block_fields, blocks = _merge_mapping(
            blocks,
            block_mapping,
            "block_id",
            overwrite=overwrite,
        )
    _write_parquet_atomic(fragments, dataset_root / "fragments.parquet")
    _write_parquet_atomic(blocks, dataset_root / "blocks.parquet")
    timestamp = generated_utc or datetime.now(UTC).isoformat()
    metadata = dict(manifest.metadata)
    metadata["lidar_fields"] = {
        "bundle_id": registration.get("bundle_id"),
        "bundle_version": registration.get("bundle_version"),
        "fragment_fields": list(fragment_fields),
        "block_fields": list(block_fields),
        "fragment_mapping_sha256": _sha256_file(fragment_mapping_path),
        "block_mapping_sha256": (
            _sha256_file(block_mapping_path) if block_mapping_path is not None else None
        ),
        "support_fields": {
            "fragments": "fragment_id",
            "blocks": "block_id",
        },
        "generated_utc": timestamp,
    }
    manifest = manifest.model_copy(update={"metadata": metadata})
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    bundle_id = registration.get("bundle_id")
    return LidarDatasetIntegrationResult(
        dataset_dir=dataset_root,
        bundle_id=bundle_id if isinstance(bundle_id, str) else "",
        fragment_fields=fragment_fields,
        block_fields=block_fields,
        fragment_rows=len(fragments),
        block_rows=len(blocks),
        generated_utc=timestamp,
        warnings=tuple(warnings),
    )


def _read_mapping_csv(path: Path, key: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if key not in frame.columns:
        raise FemicLidarError(f"Mapping CSV is missing key {key!r}: {path}")
    if frame[key].duplicated().any():
        raise FemicLidarError(f"Mapping CSV has duplicate {key!r} rows: {path}")
    return frame


def _merge_mapping(
    table: pd.DataFrame,
    mapping: pd.DataFrame,
    key: str,
    *,
    overwrite: bool,
) -> tuple[tuple[str, ...], pd.DataFrame]:
    excluded = {key, "block_id", "area_ha"}
    field_map = {column: f"lidar_{column}" for column in mapping.columns if column not in excluded}
    if not field_map:
        raise FemicLidarError("Mapping CSV has no data fields to integrate.")
    existing = [name for name in field_map.values() if name in table.columns]
    if existing and not overwrite:
        raise FemicLidarError(
            "Dataset already has LiDAR fields; use overwrite: " + ", ".join(existing)
        )
    known = set(table[key])
    mapped = set(mapping[key])
    unknown = mapped - known
    if unknown:
        raise FemicLidarError(
            f"Mapping references unknown {key!r} values: "
            + ", ".join(str(value) for value in sorted(unknown)[:5])
        )
    subset = mapping[[key, *field_map]].rename(columns=field_map)
    merged = table.merge(subset, on=key, how="left", validate="one_to_one")
    return tuple(field_map.values()), merged


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)
