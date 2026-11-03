"""PDF-to-isopleth digitisation helpers for the public SDMD diagrams.

The helper keeps the mechanical part of digitisation in one place: calibrate the
printed log axes, read the vector path for a named drawing index, convert its points
to trees per hectare and mean tree volume, and write a validated diagram JSON.

The path indices and isopleth values remain a review decision. The caller supplies
them in a :class:`DiagramSpec`; the module does not guess which curve is which.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .diagram import load_diagram

__all__ = [
    "AxisCalibration",
    "CurveSpec",
    "DiagramSpec",
    "calibrate_axes",
    "curve_points",
    "load_spec",
    "ordered_curve",
    "read_curve",
    "write_diagram",
]


@dataclass(frozen=True)
class AxisCalibration:
    """A log-axis calibration from printed tick positions.

    Attributes
    ----------
    x_slope : float
        Slope of ``log10(tph)`` against the PDF x coordinate.
    x_intercept : float
        Intercept of ``log10(tph)`` against the PDF x coordinate.
    y_slope : float
        Slope of ``log10(volume)`` against the PDF y coordinate.
    y_intercept : float
        Intercept of ``log10(volume)`` against the PDF y coordinate.
    """

    x_slope: float
    x_intercept: float
    y_slope: float
    y_intercept: float

    def tph(self, x: float) -> float:
        """Return trees per hectare for a PDF x coordinate.

        Parameters
        ----------
        x : float
            The PDF x coordinate.

        Returns
        -------
        float
            Trees per hectare.

        Raises
        ------
        ValueError
            If the mapped value is not positive and finite.
        """
        return _positive(10 ** (self.x_slope * x + self.x_intercept), "tph")

    def volume(self, y: float) -> float:
        """Return mean tree volume for a PDF y coordinate.

        Parameters
        ----------
        y : float
            The PDF y coordinate.

        Returns
        -------
        float
            Mean tree volume in cubic metres.

        Raises
        ------
        ValueError
            If the mapped value is not positive and finite.
        """
        return _positive(10 ** (self.y_slope * y + self.y_intercept), "volume")

    def x_for_tph(self, tph: float) -> float:
        """Return the PDF x coordinate for a trees-per-hectare value.

        Parameters
        ----------
        tph : float
            Trees per hectare.

        Returns
        -------
        float
            The PDF x coordinate.

        Raises
        ------
        ValueError
            If the value is not positive or the calibration is degenerate.
        """
        value = _positive(tph, "tph")
        if self.x_slope == 0:
            raise ValueError("x calibration has a zero slope")
        return (math.log10(value) - self.x_intercept) / self.x_slope

    def y_for_volume(self, volume: float) -> float:
        """Return the PDF y coordinate for a mean tree volume.

        Parameters
        ----------
        volume : float
            Mean tree volume in cubic metres.

        Returns
        -------
        float
            The PDF y coordinate.

        Raises
        ------
        ValueError
            If the value is not positive or the calibration is degenerate.
        """
        value = _positive(volume, "volume")
        if self.y_slope == 0:
            raise ValueError("y calibration has a zero slope")
        return (math.log10(value) - self.y_intercept) / self.y_slope

    def to_data(self, x: float, y: float) -> tuple[float, float]:
        """Convert one PDF point to diagram coordinates.

        Parameters
        ----------
        x : float
            The PDF x coordinate.
        y : float
            The PDF y coordinate.

        Returns
        -------
        tuple of float
            The ``(tph, mean_tree_volume_m3)`` pair.
        """
        return self.tph(x), self.volume(y)


@dataclass(frozen=True)
class CurveSpec:
    """One curve to extract from a PDF.

    Attributes
    ----------
    kind : str
        One of the diagram isopleth kinds.
    value : float
        The printed isopleth value.
    unit : str
        The printed unit.
    path_index : int
        The index of the drawing in ``page.get_drawings()``.
    dash : str
        The dash pattern to require, for example ``"[ 6 4 ] 0"``.
    width : float
        The stroke width to require.
    """

    kind: str
    value: float
    unit: str
    path_index: int
    dash: str
    width: float


@dataclass(frozen=True)
class DiagramSpec:
    """The review decisions needed to write one diagram.

    Attributes
    ----------
    diagram_id : str
        Stable diagram identifier.
    species_group : str
        Species group code.
    region : str
        Region label.
    bec_zone : str
        BEC zone.
    bec_subzone : str
        BEC subzone.
    bec_variant : str or None
        BEC variant, when the diagram is variant-specific.
    site_index : float
        Site index the diagram represents.
    citation : str
        Source citation.
    version : str
        Source version.
    licence : str
        Licence or permission note.
    pdf_path : Path
        The source PDF.
    x_ticks : sequence of tuple of float
        ``(trees_per_hectare, pdf_x)`` calibration pairs.
    y_ticks : sequence of tuple of float
        ``(mean_tree_volume_m3, pdf_y)`` calibration pairs.
    curves : sequence of CurveSpec
        The curves and their path indices.
    review_status : str
        The review status to record. Defaults to ``provisional``.
    """

    diagram_id: str
    species_group: str
    region: str
    bec_zone: str
    bec_subzone: str
    bec_variant: str | None
    site_index: float
    citation: str
    version: str
    licence: str
    pdf_path: Path
    x_ticks: Sequence[tuple[float, float]]
    y_ticks: Sequence[tuple[float, float]]
    curves: Sequence[CurveSpec]
    review_status: str = "provisional"


def calibrate_axes(
    x_ticks: Sequence[tuple[float, float]],
    y_ticks: Sequence[tuple[float, float]],
) -> AxisCalibration:
    """Fit log-axis calibration from printed tick positions.

    Parameters
    ----------
    x_ticks : sequence of tuple of float
        ``(trees_per_hectare, pdf_x)`` pairs.
    y_ticks : sequence of tuple of float
        ``(mean_tree_volume_m3, pdf_y)`` pairs.

    Returns
    -------
    AxisCalibration
        The least-squares log-axis fit.

    Raises
    ------
    ValueError
        If fewer than two ticks are supplied on either axis, a tick is not positive,
        or the ticks do not span distinct positions.
    """
    x_slope, x_intercept = _fit_axis(x_ticks, "x")
    y_slope, y_intercept = _fit_axis(y_ticks, "y")
    return AxisCalibration(x_slope, x_intercept, y_slope, y_intercept)


def curve_points(
    items: Sequence[Sequence[object]],
    calibration: AxisCalibration,
) -> tuple[tuple[float, float], ...]:
    """Convert PyMuPDF path items to ordered diagram points.

    Parameters
    ----------
    items : sequence of sequence of object
        The ``items`` list from one drawing. Line items start with ``"l"`` and
        curve items start with ``"c"``.
    calibration : AxisCalibration
        The axis calibration.

    Returns
    -------
    tuple of tuple of float
        The ordered ``(tph, mean_tree_volume_m3)`` points.

    Raises
    ------
    ValueError
        If a path yields fewer than two usable points.
    """
    points: list[tuple[float, float]] = []
    for item in items:
        if not item:
            continue
        tag = item[0]
        if tag == "l":
            points.extend(_point(item[1], calibration))
            points.extend(_point(item[2], calibration))
        elif tag == "c":
            points.extend(_point(item[1], calibration))
            points.extend(_point(item[2], calibration))
            points.extend(_point(item[3], calibration))
            points.extend(_point(item[4], calibration))
    return ordered_curve(points)


def ordered_curve(
    points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    """Sort points by TPH, average duplicate TPH, and enforce positivity.

    Parameters
    ----------
    points : sequence of tuple of float
        The ``(tph, mean_tree_volume_m3)`` points.

    Returns
    -------
    tuple of tuple of float
        The ordered points with strictly increasing TPH.

    Raises
    ------
    ValueError
        If fewer than two positive points remain.
    """
    usable = sorted((_positive(x, "tph"), _positive(y, "volume")) for x, y in points)
    merged: list[tuple[float, float]] = []
    for x, y in usable:
        if merged and abs(x - merged[-1][0]) < 1e-9:
            merged[-1] = (x, (merged[-1][1] + y) / 2.0)
        else:
            merged.append((x, y))
    if len(merged) < 2:
        raise ValueError("a curve needs at least two positive points")
    return tuple(merged)


def read_curve(
    pdf_path: str | Path,
    *,
    path_index: int,
    dash: str,
    width: float,
    calibration: AxisCalibration,
    page_number: int = 0,
) -> tuple[tuple[float, float], ...]:
    """Read one drawing from a PDF and convert it to diagram points.

    Parameters
    ----------
    pdf_path : str or Path
        The source PDF.
    path_index : int
        The index in ``page.get_drawings()``.
    dash : str
        The dash pattern the drawing must carry, for example ``"[ 6 4 ] 0"``.
    width : float
        The stroke width the drawing must carry.
    calibration : AxisCalibration
        The axis calibration.
    page_number : int
        The zero-based page number. Defaults to the first page.

    Returns
    -------
    tuple of tuple of float
        The ordered diagram points.

    Raises
    ------
    ValueError
        If the drawing index is out of range or the dash/width do not match.
    """
    import pymupdf

    with pymupdf.open(pdf_path) as document:  # type: ignore[no-untyped-call, unused-ignore]  # PyMuPDF has no stubs
        page = document[page_number]
        drawings = page.get_drawings()
        if path_index < 0 or path_index >= len(drawings):
            raise ValueError(f"path index {path_index} is outside the page")
        drawing = drawings[path_index]
        if drawing.get("dashes") != dash or float(drawing.get("width", 0.0)) != width:
            raise ValueError(f"path {path_index} does not match dash {dash!r} width {width}")
        return curve_points(drawing["items"], calibration)


def write_diagram(spec: DiagramSpec, out_path: str | Path) -> None:
    """Write and validate one diagram JSON from a PDF spec.

    Parameters
    ----------
    spec : DiagramSpec
        The diagram metadata and curve assignments.
    out_path : str or Path
        The destination JSON.

    Raises
    ------
    ValueError
        If a curve cannot be read or the resulting diagram fails validation.
    """
    calibration = calibrate_axes(spec.x_ticks, spec.y_ticks)
    payload: dict[str, object] = {
        "schema_version": "ws4.sdmd.diagram.v1",
        "diagram_id": spec.diagram_id,
        "species_group": spec.species_group,
        "region": spec.region,
        "bec_zone": spec.bec_zone,
        "bec_subzone": spec.bec_subzone,
        "bec_variant": spec.bec_variant,
        "site_index": spec.site_index,
        "source": {
            "citation": spec.citation,
            "version": spec.version,
            "licence": spec.licence,
            "kind": "published",
        },
        "review": {
            "status": spec.review_status,
            "reviewer": "",
            "reviewed_utc": "",
        },
        "isopleths": [],
    }
    isopleths: list[dict[str, object]] = []
    for curve in spec.curves:
        points = read_curve(
            spec.pdf_path,
            path_index=curve.path_index,
            dash=curve.dash,
            width=curve.width,
            calibration=calibration,
        )
        isopleths.append(
            {
                "kind": curve.kind,
                "value": curve.value,
                "unit": curve.unit,
                "points": [list(point) for point in points],
            }
        )
    payload["isopleths"] = isopleths
    path = Path(out_path)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    load_diagram(path)


def _fit_axis(ticks: Sequence[tuple[float, float]], axis: str) -> tuple[float, float]:
    """Fit one log axis from value/pixel pairs."""
    if len(ticks) < 2:
        raise ValueError(f"{axis} axis needs at least two ticks")
    values = [math.log10(_positive(value, axis)) for value, _ in ticks]
    positions = [float(position) for _, position in ticks]
    mean_value = sum(values) / len(values)
    mean_position = sum(positions) / len(positions)
    denominator = sum((position - mean_position) ** 2 for position in positions)
    if denominator == 0:
        raise ValueError(f"{axis} ticks must span distinct positions")
    numerator = sum(
        (position - mean_position) * (value - mean_value)
        for position, value in zip(positions, values, strict=True)
    )
    slope = numerator / denominator
    intercept = mean_value - slope * mean_position
    return slope, intercept


def _point(point: object, calibration: AxisCalibration) -> list[tuple[float, float]]:
    """Convert one PyMuPDF point-like object to a diagram point."""
    x = getattr(point, "x", None)
    y = getattr(point, "y", None)
    if not isinstance(x, int | float) or not isinstance(y, int | float):
        raise ValueError("PDF path item is not a point")
    return [calibration.to_data(float(x), float(y))]


def _positive(value: float, name: str) -> float:
    """Return a positive finite float or raise."""
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return float(value)


def load_spec(path: str | Path) -> DiagramSpec:
    """Load a diagram spec from JSON.

    Parameters
    ----------
    path : str or Path
        The JSON spec. A relative ``pdf_path`` is resolved against the spec file.

    Returns
    -------
    DiagramSpec
        The decoded spec.

    Raises
    ------
    ValueError
        If the JSON is missing a required field or a curve is malformed.
    """
    import json

    spec_path = Path(path)
    raw = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("a diagram spec must be a JSON object")
    required = (
        "diagram_id",
        "species_group",
        "region",
        "bec_zone",
        "bec_subzone",
        "site_index",
        "citation",
        "version",
        "licence",
        "pdf_path",
        "x_ticks",
        "y_ticks",
        "curves",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError("diagram spec is missing: " + ", ".join(missing))
    pdf_path = Path(str(raw["pdf_path"]))
    if not pdf_path.is_absolute() and not pdf_path.is_file():
        pdf_path = spec_path.parent / pdf_path
    curves = []
    for item in raw["curves"]:
        if not isinstance(item, dict):
            raise ValueError("each curve spec must be an object")
        curves.append(
            CurveSpec(
                kind=str(item["kind"]),
                value=float(item["value"]),
                unit=str(item["unit"]),
                path_index=int(item["path_index"]),
                dash=str(item["dash"]),
                width=float(item["width"]),
            )
        )
    x_ticks = tuple((float(pair[0]), float(pair[1])) for pair in raw["x_ticks"])
    y_ticks = tuple((float(pair[0]), float(pair[1])) for pair in raw["y_ticks"])
    return DiagramSpec(
        diagram_id=str(raw["diagram_id"]),
        species_group=str(raw["species_group"]),
        region=str(raw["region"]),
        bec_zone=str(raw["bec_zone"]),
        bec_subzone=str(raw["bec_subzone"]),
        bec_variant=None if raw.get("bec_variant") is None else str(raw["bec_variant"]),
        site_index=float(raw["site_index"]),
        citation=str(raw["citation"]),
        version=str(raw["version"]),
        licence=str(raw["licence"]),
        pdf_path=pdf_path,
        x_ticks=x_ticks,
        y_ticks=y_ticks,
        curves=tuple(curves),
        review_status=str(raw.get("review_status", "provisional")),
    )
