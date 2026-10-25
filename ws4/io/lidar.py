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
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - dependency boundary
        raise FemicLidarError("Writing Lidar mapping requires pandas.") from exc
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
