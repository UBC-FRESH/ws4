"""Load explicit road and culvert exposure by watershed and period.

The exposure table is an input to the hydrology screening path. It is not a
spatial product: WS4 does not buffer roads, match culverts to streams, assign a
watershed to a road, or infer a missing period.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

HYDROLOGY_EXPOSURE_SCHEMA = "ws4.hydrology.exposure.v1"
HYDROLOGY_EXPOSURE_REVIEW_STATUSES: tuple[str, ...] = (
    "not_reviewed",
    "review_pending",
    "reviewed",
)
HYDROLOGY_EXPOSURE_FEATURES: tuple[str, ...] = (
    "road_built_km",
    "road_used_km",
    "road_decommissioned_km",
    "culvert_count",
    "culvert_exposed_count",
)
HYDROLOGY_EXPOSURE_DERIVED_FEATURES: tuple[str, ...] = (
    "road_built_density_km_per_km2",
    "road_used_density_km_per_km2",
    "road_decommissioned_density_km_per_km2",
    "culvert_exposure_per_km2",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class HydrologyExposureError(RuntimeError):
    """Raised when a road/culvert exposure table cannot be consumed."""


@dataclass(frozen=True)
class HydrologyExposureRow:
    """One watershed/period road and culvert exposure record.

    Attributes
    ----------
    watershed_id : str
        FEMIC watershed identifier.
    period : int
        Non-negative screening period.
    road_built_km : float
        Road length built in the period, in kilometres.
    road_used_km : float
        Road length used in the period, in kilometres.
    road_decommissioned_km : float
        Road length decommissioned in the period, in kilometres.
    culvert_count : int
        Number of culverts in the watershed.
    culvert_exposed_count : int
        Number of culverts exposed to the flood path.
    """

    watershed_id: str
    period: int
    road_built_km: float
    road_used_km: float
    road_decommissioned_km: float
    culvert_count: int
    culvert_exposed_count: int

    def to_dict(self) -> dict[str, object]:
        """Return the row in the exposure-table shape.

        Returns
        -------
        dict[str, object]
            The row fields with numeric values preserved.
        """
        return {
            "watershed_id": self.watershed_id,
            "period": self.period,
            "road_built_km": self.road_built_km,
            "road_used_km": self.road_used_km,
            "road_decommissioned_km": self.road_decommissioned_km,
            "culvert_count": self.culvert_count,
            "culvert_exposed_count": self.culvert_exposed_count,
        }


@dataclass(frozen=True)
class HydrologyExposure:
    """Loaded and checksummed road/culvert exposure table.

    Attributes
    ----------
    path : Path
        Resolved exposure JSON path.
    sha256 : str
        SHA-256 digest of the file bytes.
    exposure_id : str
        Stable exposure identifier.
    generated_utc : str
        Producer generation timestamp.
    source_id : str
        Source or process that produced the table.
    review_status : str
        ``not_reviewed``, ``review_pending``, or ``reviewed``.
    reviewer_id : str | None
        Reviewer identifier when reviewed.
    schedule_sha256 : str
        SHA-256 of the schedule this table represents.
    watershed_ids : tuple[str, ...]
        Declared watersheds.
    periods : tuple[int, ...]
        Declared periods, sorted ascending.
    rows : tuple[HydrologyExposureRow, ...]
        Rows sorted by watershed and period.
    caveats : tuple[str, ...]
        Source and interpretation caveats.
    """

    path: Path
    sha256: str
    exposure_id: str
    generated_utc: str
    source_id: str
    review_status: str
    reviewer_id: str | None
    schedule_sha256: str
    watershed_ids: tuple[str, ...]
    periods: tuple[int, ...]
    rows: tuple[HydrologyExposureRow, ...]
    caveats: tuple[str, ...]

    def row(self, watershed_id: str, period: int) -> HydrologyExposureRow:
        """Return one watershed/period row.

        Parameters
        ----------
        watershed_id : str
            Declared watershed identifier.
        period : int
            Declared period.

        Returns
        -------
        HydrologyExposureRow
            The matching row.

        Raises
        ------
        HydrologyExposureError
            If the watershed/period pair is not declared.
        """
        for row in self.rows:
            if row.watershed_id == watershed_id and row.period == period:
                return row
        raise HydrologyExposureError(
            f"Exposure has no row for watershed {watershed_id!r} period {period}."
        )

    def features_for(self, watershed_id: str, period: int) -> dict[str, float]:
        """Return the canonical exposure features for one watershed/period.

        Parameters
        ----------
        watershed_id : str
            Declared watershed identifier.
        period : int
            Declared period.

        Returns
        -------
        dict[str, float]
            Feature names mapped to numeric values. Counts are returned as
            floats so they can enter the response-surface feature vector.
        """
        row = self.row(watershed_id, period)
        return {
            "road_built_km": row.road_built_km,
            "road_used_km": row.road_used_km,
            "road_decommissioned_km": row.road_decommissioned_km,
            "culvert_count": float(row.culvert_count),
            "culvert_exposed_count": float(row.culvert_exposed_count),
        }

    def to_dict(self) -> dict[str, object]:
        """Return the exposure table as a JSON-serializable mapping.

        Returns
        -------
        dict[str, object]
            Schema, identity, review, schedule binding, rows, and caveats.
        """
        return {
            "schema_version": HYDROLOGY_EXPOSURE_SCHEMA,
            "exposure_id": self.exposure_id,
            "generated_utc": self.generated_utc,
            "source_id": self.source_id,
            "review_status": self.review_status,
            "reviewer_id": self.reviewer_id,
            "schedule_sha256": self.schedule_sha256,
            "watershed_ids": list(self.watershed_ids),
            "periods": list(self.periods),
            "rows": [row.to_dict() for row in self.rows],
            "caveats": list(self.caveats),
        }


def load_hydrology_exposure(path: Path) -> HydrologyExposure:
    """Load and validate a ``ws4.hydrology.exposure.v1`` JSON table.

    Parameters
    ----------
    path : Path
        Exposure JSON path.

    Returns
    -------
    HydrologyExposure
        Checksummed table with declared watersheds, periods, and a complete
        watershed/period grid.

    Raises
    ------
    HydrologyExposureError
        If the file is missing, is not UTF-8 JSON, has a wrong schema, omits a
        declared watershed/period, contains duplicates or invalid values, or
        is unreviewed without a reviewer.
    """
    resolved = path.expanduser().resolve()
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise HydrologyExposureError(
            f"Unable to read hydrology exposure: {resolved}: {exc}"
        ) from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise HydrologyExposureError(f"Exposure is not UTF-8: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise HydrologyExposureError(f"Invalid exposure JSON: {resolved}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise HydrologyExposureError("Exposure table must be a JSON object.")
    if payload.get("schema_version") != HYDROLOGY_EXPOSURE_SCHEMA:
        raise HydrologyExposureError(
            f"Unsupported exposure schema {payload.get('schema_version')!r}."
        )
    exposure_id = _required_text(payload.get("exposure_id"), "exposure_id")
    generated_utc = _required_text(payload.get("generated_utc"), "generated_utc")
    source_id = _required_text(payload.get("source_id"), "source_id")
    review_status = _required_text(payload.get("review_status"), "review_status")
    if review_status not in HYDROLOGY_EXPOSURE_REVIEW_STATUSES:
        supported = ", ".join(HYDROLOGY_EXPOSURE_REVIEW_STATUSES)
        raise HydrologyExposureError(
            f"review_status must be one of: {supported}; got {review_status!r}"
        )
    reviewer_id = _optional_text(payload.get("reviewer_id"), "reviewer_id")
    if review_status == "reviewed" and reviewer_id is None:
        raise HydrologyExposureError("Reviewed exposure requires reviewer_id.")
    schedule_sha256 = _required_text(payload.get("schedule_sha256"), "schedule_sha256").lower()
    if SHA256_PATTERN.fullmatch(schedule_sha256) is None:
        raise HydrologyExposureError("schedule_sha256 must be a 64-character hex digest.")
    watershed_ids = _text_list(
        payload.get("watershed_ids"),
        "watershed_ids",
        allow_empty=False,
    )
    if len(set(watershed_ids)) != len(watershed_ids):
        raise HydrologyExposureError("watershed_ids must be unique.")
    periods = _int_list(payload.get("periods"), "periods", allow_empty=False)
    if len(set(periods)) != len(periods):
        raise HydrologyExposureError("periods must be unique.")
    periods = tuple(sorted(periods))
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, list) or not rows_payload:
        raise HydrologyExposureError("Exposure table must contain at least one row.")
    declared_watersheds = set(watershed_ids)
    declared_periods = set(periods)
    seen: set[tuple[str, int]] = set()
    rows: list[HydrologyExposureRow] = []
    for index, item in enumerate(rows_payload, start=1):
        if not isinstance(item, Mapping):
            raise HydrologyExposureError(f"Exposure row {index} must be an object.")
        watershed_id = _required_text(
            item.get("watershed_id"), f"exposure row {index} watershed_id"
        )
        if watershed_id not in declared_watersheds:
            raise HydrologyExposureError(
                f"Exposure row {index} names undeclared watershed {watershed_id!r}."
            )
        period = _required_int(item.get("period"), f"exposure row {index} period")
        if period not in declared_periods:
            raise HydrologyExposureError(f"Exposure row {index} names undeclared period {period}.")
        key = (watershed_id, period)
        if key in seen:
            raise HydrologyExposureError(
                f"Duplicate exposure row for watershed {watershed_id!r} period {period}."
            )
        seen.add(key)
        rows.append(
            HydrologyExposureRow(
                watershed_id=watershed_id,
                period=period,
                road_built_km=_required_number(
                    item.get("road_built_km"), f"exposure row {index} road_built_km"
                ),
                road_used_km=_required_number(
                    item.get("road_used_km"), f"exposure row {index} road_used_km"
                ),
                road_decommissioned_km=_required_number(
                    item.get("road_decommissioned_km"),
                    f"exposure row {index} road_decommissioned_km",
                ),
                culvert_count=_required_int(
                    item.get("culvert_count"), f"exposure row {index} culvert_count"
                ),
                culvert_exposed_count=_required_int(
                    item.get("culvert_exposed_count"),
                    f"exposure row {index} culvert_exposed_count",
                ),
            )
        )
    expected = {(watershed_id, period) for watershed_id in watershed_ids for period in periods}
    missing = sorted(expected - seen)
    if missing:
        first = missing[0]
        raise HydrologyExposureError(
            f"Exposure is missing {len(missing)} declared row(s), starting with "
            f"watershed {first[0]!r} period {first[1]}."
        )
    if len(seen) != len(expected):
        raise HydrologyExposureError("Exposure rows do not match the declared grid.")
    caveats = _text_list(payload.get("caveats"), "caveats", allow_empty=True)
    rows.sort(key=lambda row: (row.watershed_id, row.period))
    return HydrologyExposure(
        path=resolved,
        sha256=digest,
        exposure_id=exposure_id,
        generated_utc=generated_utc,
        source_id=source_id,
        review_status=review_status,
        reviewer_id=reviewer_id,
        schedule_sha256=schedule_sha256,
        watershed_ids=tuple(watershed_ids),
        periods=periods,
        rows=tuple(rows),
        caveats=caveats,
    )


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HydrologyExposureError(f"{field} must be a non-empty string.")
    return value.strip()


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field)


def _required_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HydrologyExposureError(f"{field} must be a finite non-negative number.")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise HydrologyExposureError(f"{field} must be a finite non-negative number.")
    return number


def _required_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HydrologyExposureError(f"{field} must be a non-negative integer.")
    return value


def _text_list(value: object, field: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise HydrologyExposureError(f"{field} must be a list of non-empty strings.")
    items = tuple(_required_text(item, field) for item in value)
    if not allow_empty and not items:
        raise HydrologyExposureError(f"{field} must not be empty.")
    return items


def _int_list(value: object, field: str, *, allow_empty: bool) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise HydrologyExposureError(f"{field} must be a list of non-negative integers.")
    items = tuple(_required_int(item, field) for item in value)
    if not allow_empty and not items:
        raise HydrologyExposureError(f"{field} must not be empty.")
    return items
