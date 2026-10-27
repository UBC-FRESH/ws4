"""Post-fire recovery ingest from a published spectral-recovery layer.

The layer is the NTEMS post-disturbance recovery product. Its fire classes are
``1`` faster than the ecozonal baseline, ``2`` slower, and ``3`` not recovered by
the end of the observation period. A block outside the fire footprint is not
assigned a recovery status; it is reported as outside the footprint.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

RECOVERY_SCHEMA_VERSION = "ws4.recovery.source.v1"
RECOVERY_SOURCE_ID = "ntems-post-disturbance-recovery-rate"
RECOVERY_LICENCE = "Open Government Licence - Canada"
RECOVERY_CITATION = (
    "White et al. 2022, Mapping, validating, and interpreting spatio-temporal "
    "trends in post-disturbance forest recovery, Remote Sensing of Environment "
    "271, 112904."
)
RECOVERY_STATUS = {1: "faster", 2: "slower", 3: "not_recovered"}
RECOVERY_CLASSES = (1, 2, 3)


class RecoveryError(RuntimeError):
    """Raised when a recovery raster or block table is unusable."""


@dataclass(frozen=True)
class RecoverySource:
    """Provenance for one recovery-rate raster subset.

    Parameters
    ----------
    source_id : str
        Product identifier.
    source_version : str
        Required source version or vintage.
    disturbance_years : str
        Disturbance window represented by the layer.
    observation_years : str
        Observation window used for recovery.
    resolution_m : float
        Native pixel size in metres.
    crs : str
        Raster CRS.
    licence : str
        Source licence.
    citation : str
        Source citation.
    notes : str or None
        Optional provenance note.
    """

    source_id: str
    source_version: str
    disturbance_years: str
    observation_years: str
    resolution_m: float
    crs: str
    licence: str = RECOVERY_LICENCE
    citation: str = RECOVERY_CITATION
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-serializable source descriptor.

        Returns
        -------
        dict
            Versioned source metadata.
        """
        return {
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "disturbance_years": self.disturbance_years,
            "observation_years": self.observation_years,
            "resolution_m": self.resolution_m,
            "crs": self.crs,
            "licence": self.licence,
            "citation": self.citation,
            "status_classes": RECOVERY_STATUS,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RecoverySource:
        """Validate and build a source descriptor.

        Parameters
        ----------
        payload : mapping
            Decoded metadata.

        Returns
        -------
        RecoverySource
            The validated descriptor.

        Raises
        ------
        RecoveryError
            If the schema or required fields are invalid.
        """
        if payload.get("schema_version") != RECOVERY_SCHEMA_VERSION:
            raise RecoveryError(f"recovery schema_version must be {RECOVERY_SCHEMA_VERSION!r}")
        version = str(payload.get("source_version", "")).strip()
        if not version:
            raise RecoveryError("recovery source_version must not be empty")
        return cls(
            source_id=str(payload.get("source_id", RECOVERY_SOURCE_ID)),
            source_version=version,
            disturbance_years=str(payload.get("disturbance_years", "1986-2012")),
            observation_years=str(payload.get("observation_years", "1985-2017")),
            resolution_m=float(str(payload.get("resolution_m", 30.0))),
            crs=str(payload.get("crs", "")),
            licence=str(payload.get("licence", RECOVERY_LICENCE)),
            citation=str(payload.get("citation", RECOVERY_CITATION)),
            notes=None if payload.get("notes") is None else str(payload["notes"]),
        )


def _block_id_column(frame: pd.DataFrame, block_id_field: str | None) -> str:
    """Return the block-id column, accepting common aliases."""
    if block_id_field is not None:
        if block_id_field not in frame.columns:
            raise RecoveryError(f"block id field {block_id_field!r} is not in the blocks file")
        return block_id_field
    for candidate in ("block_id", "BLOCK", "block", "FEATURE_ID", "feature_id", "id"):
        if candidate in frame.columns:
            return candidate
    raise RecoveryError(
        "blocks file has no block_id, BLOCK, block, FEATURE_ID, feature_id, or id column"
    )


def sample_recovery_raster(
    raster_path: str | Path,
    blocks_path: str | Path,
    *,
    source_version: str,
    source_id: str = RECOVERY_SOURCE_ID,
    disturbance_years: str = "1986-2012",
    observation_years: str = "1985-2017",
    licence: str = RECOVERY_LICENCE,
    citation: str = RECOVERY_CITATION,
    block_id_field: str | None = None,
    notes: str | None = None,
) -> tuple[pd.DataFrame, RecoverySource]:
    """Summarize recovery classes at block polygons.

    Parameters
    ----------
    raster_path : str or Path
        Recovery-rate GeoTIFF (values 1, 2, 3; nodata otherwise).
    blocks_path : str or Path
        Block polygon layer.
    source_version : str
        Required source version or vintage.
    source_id : str, optional
        Product identifier.
    disturbance_years : str, optional
        Disturbance window.
    observation_years : str, optional
        Observation window.
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
    tuple of (pandas.DataFrame, RecoverySource)
        Per-block status fractions and source metadata.

    Raises
    ------
    RecoveryError
        If the raster, blocks, CRS, class values, or block coverage are invalid.
    """
    import geopandas as gpd
    import rasterio
    from rasterio.mask import mask as raster_mask
    from shapely.geometry import mapping

    if not source_version.strip():
        raise RecoveryError("recovery source_version must not be empty")
    raster = Path(raster_path)
    blocks = Path(blocks_path)
    if not raster.is_file():
        raise RecoveryError(f"recovery raster does not exist: {raster}")
    if not blocks.is_file():
        raise RecoveryError(f"blocks file does not exist: {blocks}")
    frame = gpd.read_file(blocks)
    if frame.crs is None:
        raise RecoveryError("blocks file has no CRS")
    id_column = _block_id_column(frame, block_id_field)
    if frame[id_column].duplicated().any():
        raise RecoveryError(f"blocks file has duplicate {id_column!r} values")

    with rasterio.open(raster) as source:
        if source.count != 1:
            raise RecoveryError("recovery raster must have exactly one band")
        if source.crs is None:
            raise RecoveryError("recovery raster has no CRS")
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
            values = values[np.isin(values, RECOVERY_CLASSES)]
            if values.size == 0:
                rows.append(
                    {
                        "block_id": int(block_id),
                        "area_ha": float(getattr(record, "area_ha", 0.0) or 0.0),
                        "burned_area_ha": 0.0,
                        "valid_pixels": 0,
                        "faster_fraction": 0.0,
                        "slower_fraction": 0.0,
                        "not_recovered_fraction": 0.0,
                        "dominant_status": "outside_footprint",
                        "dominant_fraction": 0.0,
                    }
                )
                continue
            total = int(values.size)
            counts = {code: int((values == code).sum()) for code in RECOVERY_CLASSES}
            dominant = max(RECOVERY_CLASSES, key=lambda code: counts[code])
            rows.append(
                {
                    "block_id": int(block_id),
                    "area_ha": float(getattr(record, "area_ha", 0.0) or 0.0),
                    "burned_area_ha": total
                    * float(abs(source.transform.a * source.transform.e))
                    / 10000.0,
                    "valid_pixels": total,
                    "faster_fraction": counts[1] / total,
                    "slower_fraction": counts[2] / total,
                    "not_recovered_fraction": counts[3] / total,
                    "dominant_status": RECOVERY_STATUS[dominant],
                    "dominant_fraction": counts[dominant] / total,
                }
            )
        if missing:
            preview = ", ".join(str(block) for block in missing[:10])
            raise RecoveryError(f"recovery raster does not cover {len(missing)} blocks: {preview}")
        resolution = float(abs(source.transform.a))
        crs = source.crs.to_string()
    status = pd.DataFrame(
        rows,
        columns=[
            "block_id",
            "area_ha",
            "burned_area_ha",
            "valid_pixels",
            "faster_fraction",
            "slower_fraction",
            "not_recovered_fraction",
            "dominant_status",
            "dominant_fraction",
        ],
    )
    metadata = RecoverySource(
        source_id=source_id,
        source_version=source_version,
        disturbance_years=disturbance_years,
        observation_years=observation_years,
        resolution_m=resolution,
        crs=crs,
        licence=licence,
        citation=citation,
        notes=notes,
    )
    return status, metadata


def sample_recovery_rasterized(
    raster_path: str | Path,
    blocks_path: str | Path,
    *,
    source_version: str,
    source_id: str = RECOVERY_SOURCE_ID,
    disturbance_years: str = "1986-2012",
    observation_years: str = "1985-2017",
    licence: str = RECOVERY_LICENCE,
    citation: str = RECOVERY_CITATION,
    block_id_field: str | None = None,
    notes: str | None = None,
) -> tuple[pd.DataFrame, RecoverySource]:
    """Summarize recovery classes by rasterizing block ids once.

    This is the efficient path for a full estate. It is equivalent to
    :func:`sample_recovery_raster` except that block ids are rasterized onto the
    recovery grid and counted with ``bincount``. Blocks whose ids are not
    rasterized have no footprint status.

    Parameters
    ----------
    raster_path : str or Path
        Recovery-rate GeoTIFF.
    blocks_path : str or Path
        Block polygon layer.
    source_version : str
        Required source version or vintage.
    source_id : str, optional
        Product identifier.
    disturbance_years : str, optional
        Disturbance window.
    observation_years : str, optional
        Observation window.
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
    tuple of (pandas.DataFrame, RecoverySource)
        Per-block status fractions and source metadata.
    """
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    from shapely.geometry import mapping

    if not source_version.strip():
        raise RecoveryError("recovery source_version must not be empty")
    raster = Path(raster_path)
    blocks = Path(blocks_path)
    if not raster.is_file():
        raise RecoveryError(f"recovery raster does not exist: {raster}")
    if not blocks.is_file():
        raise RecoveryError(f"blocks file does not exist: {blocks}")
    frame = gpd.read_file(blocks)
    if frame.crs is None:
        raise RecoveryError("blocks file has no CRS")
    id_column = _block_id_column(frame, block_id_field)
    if frame[id_column].duplicated().any():
        raise RecoveryError(f"blocks file has duplicate {id_column!r} values")
    with rasterio.open(raster) as source:
        if source.count != 1:
            raise RecoveryError("recovery raster must have exactly one band")
        if source.crs is None:
            raise RecoveryError("recovery raster has no CRS")
        projected = frame.to_crs(source.crs)
        ids = projected[id_column].astype(int).to_numpy()
        geometries = projected.geometry.to_numpy()
        shapes = ((mapping(geom), int(block)) for block, geom in zip(ids, geometries, strict=True))
        block_grid = rasterize(
            shapes,
            out_shape=(source.height, source.width),
            fill=0,
            all_touched=True,
            dtype="int32",
            transform=source.transform,
        )
        classes = source.read(1)
        max_id = int(ids.max()) if ids.size else 0
        counts = {
            code: np.bincount(block_grid[classes == code].ravel(), minlength=max_id + 1)
            for code in RECOVERY_CLASSES
        }
        resolution = float(abs(source.transform.a))
        crs = source.crs.to_string()
    areas = (
        {int(getattr(row, id_column)): float(row.area_ha) for row in frame.itertuples(index=False)}
        if "area_ha" in frame.columns
        else {int(block): 0.0 for block in ids}
    )
    rows: list[dict[str, object]] = []
    for block in sorted(areas):
        n1, n2, n3 = (int(counts[code][block]) for code in RECOVERY_CLASSES)
        valid = n1 + n2 + n3
        if valid == 0:
            rows.append(
                {
                    "block_id": block,
                    "area_ha": areas[block],
                    "burned_area_ha": 0.0,
                    "valid_pixels": 0,
                    "faster_fraction": 0.0,
                    "slower_fraction": 0.0,
                    "not_recovered_fraction": 0.0,
                    "dominant_status": "outside_footprint",
                    "dominant_fraction": 0.0,
                }
            )
            continue
        counts_by_class = {1: n1, 2: n2, 3: n3}
        dominant = max(RECOVERY_CLASSES, key=lambda code: counts_by_class[code])
        rows.append(
            {
                "block_id": block,
                "area_ha": areas[block],
                "burned_area_ha": valid * (resolution * resolution) / 10000.0,
                "valid_pixels": valid,
                "faster_fraction": n1 / valid,
                "slower_fraction": n2 / valid,
                "not_recovered_fraction": n3 / valid,
                "dominant_status": RECOVERY_STATUS[dominant],
                "dominant_fraction": counts_by_class[dominant] / valid,
            }
        )
    status = pd.DataFrame(rows)
    metadata = RecoverySource(
        source_id=source_id,
        source_version=source_version,
        disturbance_years=disturbance_years,
        observation_years=observation_years,
        resolution_m=resolution,
        crs=crs,
        licence=licence,
        citation=citation,
        notes=notes,
    )
    return status, metadata


def write_recovery_status(
    status: pd.DataFrame,
    source: RecoverySource,
    output_csv: str | Path,
    metadata_json: str | Path,
) -> None:
    """Write the block status table and source metadata.

    Parameters
    ----------
    status : pandas.DataFrame
        Per-block recovery status.
    source : RecoverySource
        Source descriptor.
    output_csv : str or Path
        Destination status CSV.
    metadata_json : str or Path
        Destination metadata JSON.
    """
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    status.to_csv(output, index=False)
    metadata = Path(metadata_json)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(source.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def summarize_recovery_status(status: pd.DataFrame) -> pd.DataFrame:
    """Summarize block count and area by dominant recovery status.

    Parameters
    ----------
    status : pandas.DataFrame
        Per-block recovery status.

    Returns
    -------
    pandas.DataFrame
        Rows for each dominant status with block count, total area, and burned
        area.
    """
    rows: list[dict[str, object]] = []
    for label, group in status.groupby("dominant_status", sort=True):
        rows.append(
            {
                "dominant_status": label,
                "blocks": len(group),
                "area_ha": float(group["area_ha"].sum()),
                "burned_area_ha": float(group["burned_area_ha"].sum()),
            }
        )
    return pd.DataFrame(rows)


__all__ = [
    "RECOVERY_CITATION",
    "RECOVERY_CLASSES",
    "RECOVERY_LICENCE",
    "RECOVERY_SCHEMA_VERSION",
    "RECOVERY_SOURCE_ID",
    "RECOVERY_STATUS",
    "RecoveryError",
    "RecoverySource",
    "sample_recovery_raster",
    "sample_recovery_rasterized",
    "summarize_recovery_status",
    "write_recovery_status",
]
