"""Dynamic Habitat Index (DHI) ingest and account support.

The account is a **static habitat-productivity surrogate**. It attaches a DHI
value to each block, then reports the surviving DHI area as a schedule removes
blocks. It does not model species, habitat suitability, regrowth, or recovery.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

DHI_SOURCE_SCHEMA_VERSION = "ws4.dhi.source.v1"
DHI_ACCOUNT_PREFIX = "feature.DHI"

DEFAULT_BAND_NAMES: tuple[str, ...] = ("cum", "min", "var")
DEFAULT_SOURCE_ID = "silvis-dhi-modis6.1-terra-ndvi-composite"
DEFAULT_YEAR_RANGE = "2003-2022"
DEFAULT_LICENCE = "Public; no restrictions (SILVIS Lab)"


class DhiError(RuntimeError):
    """Raised when a DHI product or account cannot be read or applied."""


@dataclass(frozen=True)
class DhiSource:
    """Provenance for one DHI raster subset.

    Parameters
    ----------
    source_id : str
        Product identifier.
    source_version : str
        Required product version or vintage label.
    year_range : str
        Composite or annual year range.
    resolution_m : float
        Nominal source resolution in metres.
    crs : str
        Raster CRS.
    licence : str
        Source licence or terms.
    bands : tuple of str
        Band names in raster order.
    scale : float
        Divisor that maps stored values to the 0-1 index.
    bbox : tuple of float
        Raster subset bounds as ``(left, bottom, right, top)``.
    valid_pixels : int
        Count of valid pixels in the subset.
    source_path : str
        Path or URL of the exact source artifact.
    source_sha256 : str
        SHA-256 of the source artifact.
    retrieved_utc : str
        ISO-8601 retrieval timestamp.
    notes : str or None
        Optional provenance note.
    """

    source_id: str
    source_version: str
    year_range: str
    resolution_m: float
    crs: str
    licence: str
    bands: tuple[str, ...]
    scale: float
    bbox: tuple[float, float, float, float]
    valid_pixels: int
    source_path: str
    source_sha256: str
    retrieved_utc: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-serializable form.

        Returns
        -------
        dict
            The source descriptor, including its schema version.
        """
        return {
            "schema_version": DHI_SOURCE_SCHEMA_VERSION,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "year_range": self.year_range,
            "resolution_m": self.resolution_m,
            "crs": self.crs,
            "licence": self.licence,
            "bands": list(self.bands),
            "scale": self.scale,
            "bbox": list(self.bbox),
            "valid_pixels": self.valid_pixels,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "retrieved_utc": self.retrieved_utc,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DhiSource:
        """Validate and build a source descriptor.

        Parameters
        ----------
        payload : mapping
            A decoded ``dhi_metadata.json`` object.

        Returns
        -------
        DhiSource
            The validated descriptor.

        Raises
        ------
        DhiError
            If the schema version or a required field is missing.
        """
        if payload.get("schema_version") != DHI_SOURCE_SCHEMA_VERSION:
            raise DhiError(f"DHI source schema_version must be {DHI_SOURCE_SCHEMA_VERSION!r}")
        required = (
            "source_id",
            "source_version",
            "year_range",
            "resolution_m",
            "crs",
            "licence",
            "bands",
            "scale",
            "bbox",
            "valid_pixels",
            "source_path",
            "source_sha256",
            "retrieved_utc",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise DhiError(f"DHI source is missing fields: {', '.join(missing)}")
        bands = payload["bands"]
        bbox = payload["bbox"]
        if not isinstance(bands, list) or not bands:
            raise DhiError("DHI source bands must be a non-empty list")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise DhiError("DHI source bbox must have four numbers")
        version = str(payload["source_version"]).strip()
        if not version:
            raise DhiError("DHI source source_version must not be empty")
        if float(str(payload["scale"])) <= 0:
            raise DhiError("DHI source scale must be positive")
        if int(str(payload["valid_pixels"])) <= 0:
            raise DhiError("DHI source valid_pixels must be positive")
        return cls(
            source_id=str(payload["source_id"]),
            source_version=version,
            year_range=str(payload["year_range"]),
            resolution_m=float(str(payload["resolution_m"])),
            crs=str(payload["crs"]),
            licence=str(payload["licence"]),
            bands=tuple(str(band) for band in bands),
            scale=float(str(payload["scale"])),
            bbox=(
                float(str(bbox[0])),
                float(str(bbox[1])),
                float(str(bbox[2])),
                float(str(bbox[3])),
            ),
            valid_pixels=int(str(payload["valid_pixels"])),
            source_path=str(payload["source_path"]),
            source_sha256=str(payload["source_sha256"]),
            retrieved_utc=str(payload["retrieved_utc"]),
            notes=None if payload.get("notes") is None else str(payload["notes"]),
        )


@dataclass(frozen=True)
class DhiAccount:
    """Block DHI values and source metadata used by the simulator.

    Parameters
    ----------
    values : mapping of int to mapping of str to float
        Normalized 0-1 DHI values by block id and band name.
    source : DhiSource
        Provenance for those values.
    """

    values: Mapping[int, Mapping[str, float]]
    source: DhiSource

    @property
    def bands(self) -> tuple[str, ...]:
        """Return the DHI band names.

        Returns
        -------
        tuple of str
            Band names in source order.
        """
        return self.source.bands

    def validate(self, block_area: Mapping[int, float]) -> None:
        """Require a DHI value for every block in the dataset.

        Parameters
        ----------
        block_area : mapping of int to float
            Block areas in hectares.

        Raises
        ------
        DhiError
            If a block is missing or a value is outside ``[0, 1]``.
        """
        missing = sorted(set(block_area) - set(self.values))
        if missing:
            preview = ", ".join(str(block) for block in missing[:10])
            raise DhiError(f"DHI values are missing for {len(missing)} blocks: {preview}")
        invalid = [
            (block, band, value)
            for block, bands in self.values.items()
            for band, value in bands.items()
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0
        ]
        if invalid:
            block, band, value = invalid[0]
            raise DhiError(f"DHI value for block {block} band {band!r} is outside [0, 1]: {value}")

    def account_values(
        self,
        block_area: Mapping[int, float],
        *,
        excluded_blocks: set[int] | frozenset[int] = frozenset(),
    ) -> dict[str, float]:
        """Return total and area-weighted mean DHI values for the surviving blocks.

        Parameters
        ----------
        block_area : mapping of int to float
            Block areas in hectares.
        excluded_blocks : set of int, optional
            Blocks treated so far and removed from the habitat total.

        Returns
        -------
        dict of str to float
            ``feature.DHI.<band>`` totals, means, and the surviving area.
        """
        self.validate(block_area)
        surviving = [block for block in block_area if block not in excluded_blocks]
        area = sum(max(0.0, float(block_area[block])) for block in surviving)
        result: dict[str, float] = {}
        for band in self.bands:
            total = sum(
                float(self.values[block][band]) * max(0.0, float(block_area[block]))
                for block in surviving
            )
            result[f"{DHI_ACCOUNT_PREFIX}.{band}"] = total
            result[f"{DHI_ACCOUNT_PREFIX}.{band}.mean"] = total / area if area > 0 else 0.0
        result[f"{DHI_ACCOUNT_PREFIX}.area"] = area
        return result

    def write(self, out_dir: Path) -> None:
        """Write the run-local values and metadata used by reports and the web API.

        Parameters
        ----------
        out_dir : Path
            The run directory.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = [
            {"block_id": block, **{band: bands[band] for band in self.bands}}
            for block, bands in sorted(self.values.items())
        ]
        pd.DataFrame(rows, columns=["block_id", *self.bands]).to_csv(
            out_dir / "dhi_values.csv", index=False
        )
        (out_dir / "dhi_metadata.json").write_text(
            json.dumps(self.source.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _block_id_column(frame: pd.DataFrame, block_id_field: str | None) -> str:
    """Return the block id column, using a small set of accepted aliases."""
    if block_id_field is not None:
        if block_id_field not in frame.columns:
            raise DhiError(f"block id field {block_id_field!r} is not in the blocks file")
        return block_id_field
    for candidate in ("block_id", "BLOCK", "block", "id"):
        if candidate in frame.columns:
            return candidate
    raise DhiError("blocks file has no block_id, BLOCK, block, or id column")


def sample_dhi_raster(
    raster_path: str | Path,
    blocks_path: str | Path,
    *,
    source_version: str,
    source_id: str = DEFAULT_SOURCE_ID,
    year_range: str = DEFAULT_YEAR_RANGE,
    licence: str = DEFAULT_LICENCE,
    band_names: Sequence[str] = DEFAULT_BAND_NAMES,
    scale: float = 255.0,
    resolution_m: float = 500.0,
    block_id_field: str | None = None,
    retrieved_utc: str | None = None,
    notes: str | None = None,
) -> tuple[pd.DataFrame, DhiSource]:
    """Sample a DHI raster at block polygons.

    The sampled mean is normalized by ``scale`` and clipped to ``[0, 1]``. A
    block with no valid pixels is an error: the source does not cover the AOI.

    Parameters
    ----------
    raster_path : str or Path
        DHI GeoTIFF subset.
    blocks_path : str or Path
        Block polygon layer.
    source_version : str
        Required product version or vintage label.
    source_id : str, optional
        Product identifier.
    year_range : str, optional
        Composite or annual year range.
    licence : str, optional
        Source licence or terms.
    band_names : sequence of str, optional
        Band names in raster order.
    scale : float, optional
        Divisor that maps stored values to the 0-1 index.
    resolution_m : float, optional
        Nominal source resolution in metres.
    block_id_field : str or None, optional
        Block id column; auto-detected when omitted.
    retrieved_utc : str or None, optional
        Retrieval timestamp; the current UTC time when omitted.
    notes : str or None, optional
        Optional provenance note.

    Returns
    -------
    tuple of (pandas.DataFrame, DhiSource)
        The normalized values and their source descriptor.

    Raises
    ------
    DhiError
        If the raster, blocks, CRS, coverage, or band count is unusable.
    """
    import geopandas as gpd
    import rasterio
    from rasterio.mask import mask as raster_mask
    from shapely.geometry import mapping

    raster = Path(raster_path)
    blocks = Path(blocks_path)
    if not raster.is_file():
        raise DhiError(f"DHI raster does not exist: {raster}")
    if not blocks.is_file():
        raise DhiError(f"blocks file does not exist: {blocks}")
    if scale <= 0:
        raise DhiError("scale must be positive")
    if not source_version.strip():
        raise DhiError("source_version must not be empty")
    names = tuple(str(name).strip() for name in band_names)
    if not names or any(not name for name in names):
        raise DhiError("band_names must be a non-empty list")

    frame = gpd.read_file(blocks)
    id_column = _block_id_column(frame, block_id_field)
    if frame[id_column].duplicated().any():
        raise DhiError(f"blocks file has duplicate {id_column!r} values")
    if frame.crs is None:
        raise DhiError("blocks file has no CRS")

    with rasterio.open(raster) as source:
        if frame.crs != source.crs:
            frame = frame.to_crs(source.crs)
        if source.count < len(names):
            raise DhiError(
                f"DHI raster has {source.count} bands; {len(names)} names were requested"
            )
        if source.crs is None:
            raise DhiError("DHI raster has no CRS")
        array = source.read(masked=True)
        band_valid = int(np.count_nonzero(~np.ma.getmaskarray(array[0])))
        if band_valid == 0:
            raise DhiError("DHI raster has no valid pixels")
        rows: list[dict[str, object]] = []
        missing: list[object] = []
        for record in frame.itertuples(index=False):
            block_id = getattr(record, id_column)
            geometry = record.geometry
            try:
                clipped, _ = raster_mask(
                    source, [mapping(geometry)], crop=True, filled=False, all_touched=True
                )
            except ValueError:
                missing.append(block_id)
                continue
            values: dict[str, float] = {}
            empty = False
            for band_index, name in enumerate(names, start=1):
                data = clipped[band_index - 1]
                valid = data[~np.ma.getmaskarray(data)]
                if valid.size == 0:
                    empty = True
                    break
                values[name] = min(1.0, max(0.0, float(valid.mean()) / float(scale)))
            if empty:
                missing.append(block_id)
                continue
            rows.append({"block_id": int(block_id), **values})
        if missing:
            preview = ", ".join(str(block) for block in missing[:10])
            raise DhiError(f"DHI raster does not cover {len(missing)} blocks: {preview}")
        bounds = source.bounds
        crs = source.crs.to_string()

    source_metadata = DhiSource(
        source_id=source_id,
        source_version=source_version,
        year_range=year_range,
        resolution_m=float(resolution_m),
        crs=crs,
        licence=licence,
        bands=names,
        scale=float(scale),
        bbox=(float(bounds.left), float(bounds.bottom), float(bounds.right), float(bounds.top)),
        valid_pixels=band_valid,
        source_path=str(raster),
        source_sha256=_sha256(raster),
        retrieved_utc=retrieved_utc or datetime.now(UTC).isoformat(),
        notes=notes,
    )
    result = pd.DataFrame.from_records(rows, columns=["block_id", *names])
    result["block_id"] = result["block_id"].astype(int)
    return result, source_metadata


def write_dhi_ingest(
    values: pd.DataFrame,
    source: DhiSource,
    output_csv: str | Path,
    metadata_json: str | Path,
) -> None:
    """Write the block values and source metadata for a DHI ingest run.

    Parameters
    ----------
    values : pandas.DataFrame
        Normalized block values with ``block_id`` and one column per band.
    source : DhiSource
        Provenance for the values.
    output_csv : str or Path
        Destination values CSV.
    metadata_json : str or Path
        Destination metadata JSON.
    """
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    values.to_csv(output, index=False)
    Path(metadata_json).parent.mkdir(parents=True, exist_ok=True)
    Path(metadata_json).write_text(
        json.dumps(source.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_dhi_account(values_path: str | Path, metadata_path: str | Path) -> DhiAccount:
    """Read a saved DHI values/metadata pair for simulation.

    Parameters
    ----------
    values_path : str or Path
        CSV with ``block_id`` and one column per band.
    metadata_path : str or Path
        ``dhi_metadata.json`` source descriptor.

    Returns
    -------
    DhiAccount
        The values and provenance.

    Raises
    ------
    DhiError
        If either file is missing, the metadata is invalid, or a required band is
        absent from the CSV.
    """
    values_file = Path(values_path)
    metadata_file = Path(metadata_path)
    if not values_file.is_file():
        raise DhiError(f"DHI values file does not exist: {values_file}")
    if not metadata_file.is_file():
        raise DhiError(f"DHI metadata file does not exist: {metadata_file}")
    source = DhiSource.from_dict(json.loads(metadata_file.read_text(encoding="utf-8")))
    frame = pd.read_csv(values_file)
    if "block_id" not in frame.columns:
        raise DhiError("DHI values CSV is missing block_id")
    missing = [band for band in source.bands if band not in frame.columns]
    if missing:
        raise DhiError(f"DHI values CSV is missing bands: {', '.join(missing)}")
    if frame["block_id"].duplicated().any():
        raise DhiError("DHI values CSV has duplicate block_id values")
    if frame[list(source.bands)].isna().any().any():
        raise DhiError("DHI values CSV has missing band values")
    values: dict[int, dict[str, float]] = {}
    for record in frame.to_dict("records"):
        block = int(record["block_id"])
        values[block] = {band: float(record[band]) for band in source.bands}
    return DhiAccount(values=values, source=source)


__all__ = [
    "DEFAULT_BAND_NAMES",
    "DEFAULT_LICENCE",
    "DEFAULT_SOURCE_ID",
    "DEFAULT_YEAR_RANGE",
    "DHI_ACCOUNT_PREFIX",
    "DHI_SOURCE_SCHEMA_VERSION",
    "DhiAccount",
    "DhiError",
    "DhiSource",
    "read_dhi_account",
    "sample_dhi_raster",
    "write_dhi_ingest",
]
