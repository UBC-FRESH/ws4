"""PDF-to-isopleth digitisation helpers for the public SDMD diagrams.

The helper keeps the mechanical part of digitisation in one place: calibrate the
printed log axes, read the vector path for a named drawing index, convert its points
to trees per hectare and mean tree volume, and write a validated diagram JSON.

The path indices and isopleth values remain a review decision. The caller supplies
them in a :class:`DiagramSpec`; the module does not guess which curve is which.
"""

from __future__ import annotations

import itertools
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .diagram import load_diagram

__all__ = [
    "AxisCalibration",
    "CurveSpec",
    "DiagramSpec",
    "LabelMatch",
    "LabelledCurve",
    "PathCandidate",
    "PrintedLabel",
    "calibrate_axes",
    "curve_points",
    "load_spec",
    "match_printed_labels",
    "ordered_curve",
    "read_curve",
    "read_labelled_curves",
    "read_ordered_curves",
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
class PrintedLabel:
    """A printed isopleth value and its page position.

    Attributes
    ----------
    value : float
        The printed numeric value.
    x : float
        The label centre's PDF x coordinate.
    y : float
        The label centre's PDF y coordinate.
    """

    value: float
    x: float
    y: float


@dataclass(frozen=True)
class PathCandidate:
    """One PDF path that may belong to a labelled curve family.

    Attributes
    ----------
    path_index : int
        Index in ``page.get_drawings()``.
    points : tuple of tuple of float
        The path vertices in PDF coordinates.
    """

    path_index: int
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class LabelMatch:
    """One printed label assigned to one PDF path.

    Attributes
    ----------
    value : float
        The printed value.
    path_index : int
        The matched drawing index.
    distance : float
        Distance in PDF points between the label centre and the path.
    """

    value: float
    path_index: int
    distance: float


@dataclass(frozen=True)
class LabelledCurve:
    """A labelled curve read from a PDF path.

    Attributes
    ----------
    value : float
        The printed isopleth value.
    path_index : int
        Index in ``page.get_drawings()``.
    points : tuple of tuple of float
        Ordered ``(tph, mean_tree_volume_m3)`` points.
    label_distance : float or None
        Distance in PDF points between the printed label and the path, or
        ``None`` for a curve inferred from its position in a complete series.
    """

    value: float
    path_index: int
    points: tuple[tuple[float, float], ...]
    label_distance: float | None = None


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


def match_printed_labels(
    labels: Sequence[PrintedLabel],
    paths: Sequence[PathCandidate],
    *,
    max_distance: float = 15.0,
    min_margin: float = 0.5,
    higher_value_is_upper: bool = True,
) -> tuple[LabelMatch, ...]:
    """Match printed curve labels to the nearest distinct PDF paths.

    The match is deterministic and refuses an ambiguous assignment. Every label
    must be close to one path, no two labels may claim the same path, and the
    assigned paths must remain vertically ordered by value.

    Parameters
    ----------
    labels : sequence of PrintedLabel
        The printed labels.
    paths : sequence of PathCandidate
        The candidate paths.
    max_distance : float, optional
        Maximum label-to-path distance in PDF points. Defaults to 15.
    min_margin : float, optional
        Minimum distance advantage of the nearest path over the runner-up.
        Defaults to 0.5 PDF points.
    higher_value_is_upper : bool, optional
        Whether a larger label value belongs to a higher curve (smaller PDF y).
        Defaults to True, which is correct for top-height and QMD.

    Returns
    -------
    tuple of LabelMatch
        One match per label.

    Raises
    ------
    ValueError
        If a label is too far from every path, two labels compete for the same
        path, or the assignments violate vertical order.
    """
    if not labels:
        raise ValueError("no printed labels were found")
    if not paths:
        raise ValueError("no candidate paths were found")
    used: dict[int, float] = {}
    matches: list[LabelMatch] = []
    for label in labels:
        ranked = sorted(
            ((_label_path_distance(label, path), path.path_index) for path in paths),
            key=lambda item: (item[0], item[1]),
        )
        distance, path_index = ranked[0]
        if distance > max_distance:
            raise ValueError(
                f"label {label.value:g} is {distance:.1f} points from the nearest path"
            )
        if len(ranked) > 1 and ranked[1][0] - distance < min_margin:
            raise ValueError(
                f"label {label.value:g} is ambiguous between paths {path_index} and {ranked[1][1]}"
            )
        if path_index in used:
            raise ValueError(
                f"labels {used[path_index]:g} and {label.value:g} both claim path {path_index}"
            )
        used[path_index] = label.value
        matches.append(LabelMatch(label.value, path_index, distance))

    ordered = sorted(matches, key=lambda item: item.value)
    by_index = {path.path_index: path for path in paths}
    reference_x = max(min(point[0] for point in path.points) for path in paths) + 1.0
    previous_y: float | None = None
    for match in ordered:
        y = _path_y_at_x(by_index[match.path_index], reference_x)
        if previous_y is not None:
            ordered_correctly = y < previous_y if higher_value_is_upper else y > previous_y
            if not ordered_correctly:
                raise ValueError(
                    f"label {match.value:g} is not vertically ordered against the lower value"
                )
        previous_y = y
    return tuple(matches)


def _label_path_distance(label: PrintedLabel, path: PathCandidate) -> float:
    """Return the shortest distance from a label centre to a polyline."""
    point = (label.x, label.y)
    return min(
        _point_segment_distance(point, start, end) for start, end in itertools.pairwise(path.points)
    )


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Return the distance from a point to a line segment."""
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    fraction = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    fraction = max(0.0, min(1.0, fraction))
    return math.hypot(px - (ax + fraction * dx), py - (ay + fraction * dy))


def _path_y_at_x(path: PathCandidate, x: float) -> float:
    """Interpolate a path's PDF y coordinate at a PDF x coordinate."""
    ordered = sorted(path.points)
    for start, end in itertools.pairwise(ordered):
        if start[0] <= x <= end[0]:
            if end[0] == start[0]:
                return (start[1] + end[1]) / 2.0
            fraction = (x - start[0]) / (end[0] - start[0])
            return start[1] + fraction * (end[1] - start[1])
    raise ValueError(f"path {path.path_index} does not span x={x:.1f}")


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
    has_curve = False
    for item in items:
        if not item:
            continue
        tag = item[0]
        if tag == "l":
            points.extend(_point(item[1], calibration))
            points.extend(_point(item[2], calibration))
        elif tag == "c":
            has_curve = True
            if not points:
                points.extend(_point(item[1], calibration))
            # The control points are not data: a control point can overshoot
            # the curve and create a false terminal zig-zag when sorted by TPH.
            points.extend(_point(item[4], calibration))
    if has_curve:
        return _ordered_curve_from_path(points)
    return ordered_curve(points)


def _ordered_curve_from_path(
    points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    """Keep path order and turn a terminal backward bend into an up-tick.

    High-QMD source curves often finish with a near-vertical upward bend. The
    Bezier control point can lie to the right of the final endpoint, so sorting
    all points by TPH would put the endpoint before the control point and create
    a zig-zag. The endpoint sequence is monotone until that bend; a backward
    endpoint with a higher volume is represented as a very short vertical
    segment, and a backward endpoint with a lower volume is discarded.
    """
    usable = [(_positive(x, "tph"), _positive(y, "volume")) for x, y in points]
    if not usable:
        raise ValueError("a curve needs at least two positive points")
    result: list[tuple[float, float]] = [usable[0]]
    last_forward_x = usable[0][0]
    vertical = False
    for x, y in usable[1:]:
        previous_x, previous_y = result[-1]
        if x > previous_x:
            result.append((x, y))
            last_forward_x = x
            vertical = False
        elif y > previous_y:
            if vertical:
                result[-1] = (result[-1][0], y)
            else:
                epsilon = max(1e-9, abs(last_forward_x) * 1e-9)
                result.append((last_forward_x + epsilon, y))
                vertical = True
    if len(result) < 2:
        raise ValueError("a curve needs at least two positive points")
    return tuple(result)


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


def read_labelled_curves(
    pdf_path: str | Path,
    *,
    dash: str,
    width: float,
    unit: str,
    calibration: AxisCalibration,
    page_number: int = 0,
    max_distance: float = 15.0,
    min_margin: float = 0.5,
    min_path_width: float = 20.0,
) -> tuple[LabelledCurve, ...]:
    """Read one labelled curve family by matching printed labels to PDF paths.

    This is the deterministic part of the line-type import. It does not choose
    labels or path indices by hand: it finds the paths with the requested dash
    pattern and width, reads the printed labels with the requested unit, and
    requires a unique, close, vertically ordered match for every label.

    Parameters
    ----------
    pdf_path : str or Path
        The source PDF.
    dash : str
        The required PDF dash pattern, for example ``"[ 3 2 ] 0"``.
    width : float
        The required stroke width.
    unit : str
        The printed unit, ``"m"`` or ``"cm"``.
    calibration : AxisCalibration
        The axis calibration.
    page_number : int, optional
        Zero-based page number. Defaults to the first page.
    max_distance : float, optional
        Maximum label-to-path distance in PDF points. Defaults to 15.
    min_margin : float, optional
        Minimum distance advantage over the runner-up path. Defaults to 0.5.
    min_path_width : float, optional
        Minimum path bounding-box width in PDF points. Defaults to 20.

    Returns
    -------
    tuple of LabelledCurve
        One curve per printed label, ordered by value.

    Raises
    ------
    ValueError
        If no candidate paths or labels exist, or if the label-to-path match is
        ambiguous, too distant, duplicated, or vertically unordered.
    """
    import pymupdf

    with pymupdf.open(pdf_path) as document:  # type: ignore[no-untyped-call, unused-ignore]  # PyMuPDF has no stubs
        page = document[page_number]
        drawings = page.get_drawings()
        paths: list[PathCandidate] = []
        for index, drawing in enumerate(drawings):
            if drawing.get("dashes") != dash:
                continue
            if abs(float(drawing.get("width") or 0.0) - width) > 1e-3:
                continue
            rect = drawing["rect"]
            if rect.width < min_path_width or rect.height <= 3.0:
                continue
            points = _pdf_path_points(drawing["items"])
            if len(points) >= 2:
                paths.append(PathCandidate(index, tuple(points)))
        labels = _printed_labels(page, unit)
        matches = match_printed_labels(
            labels,
            paths,
            max_distance=max_distance,
            min_margin=min_margin,
        )
        return tuple(
            LabelledCurve(
                value=match.value,
                path_index=match.path_index,
                points=curve_points(drawings[match.path_index]["items"], calibration),
                label_distance=match.distance,
            )
            for match in sorted(matches, key=lambda item: item.value)
        )


def read_ordered_curves(
    pdf_path: str | Path,
    *,
    dash: str,
    width: float,
    values: Sequence[float],
    calibration: AxisCalibration,
    unit: str | None = None,
    page_number: int = 0,
    max_distance: float = 15.0,
    min_margin: float = 0.5,
    min_path_width: float = 20.0,
) -> tuple[LabelledCurve, ...]:
    """Read a complete ordered series and verify its printed anchors.

    Use this when a source family has more curves than printed labels. The full
    value sequence is supplied explicitly; every candidate path must be used,
    and any printed labels must agree with the resulting order. This prevents
    silently skipping unlabelled curves.

    Parameters
    ----------
    pdf_path : str or Path
        The source PDF.
    dash : str
        The required PDF dash pattern.
    width : float
        The required stroke width.
    values : sequence of float
        Every value in the family, including unlabelled interior values.
    calibration : AxisCalibration
        The axis calibration.
    unit : str or None, optional
        When supplied, verify printed labels with this unit against the ordered
        assignments.
    page_number : int, optional
        Zero-based page number. Defaults to the first page.
    max_distance : float, optional
        Maximum label-to-path distance for anchor verification.
    min_margin : float, optional
        Minimum distance advantage for anchor verification.
    min_path_width : float, optional
        Minimum path bounding-box width in PDF points.

    Returns
    -------
    tuple of LabelledCurve
        One curve per value, ordered by value.

    Raises
    ------
    ValueError
        If the number of paths differs from the number of values, a label does
        not agree with the ordered assignment, or the paths are not separable.
    """
    import pymupdf

    with pymupdf.open(pdf_path) as document:  # type: ignore[no-untyped-call, unused-ignore]  # PyMuPDF has no stubs
        page = document[page_number]
        drawings = page.get_drawings()
        paths = _candidate_paths(
            drawings,
            dash=dash,
            width=width,
            min_path_width=min_path_width,
        )
        expected = sorted(float(value) for value in values)
        if len(paths) != len(expected):
            raise ValueError(
                f"expected {len(expected)} paths for the ordered series, found {len(paths)}"
            )
        reference_x = max(min(point[0] for point in path.points) for path in paths) + 1.0
        ordered_paths = sorted(
            paths,
            key=lambda path: _path_y_at_x(path, reference_x),
            reverse=True,
        )
        assigned = dict(zip(expected, ordered_paths, strict=True))
        if unit is not None:
            label_matches = match_printed_labels(
                _printed_labels(page, unit),
                paths,
                max_distance=max_distance,
                min_margin=min_margin,
            )
            for match in label_matches:
                if assigned[match.value].path_index != match.path_index:
                    raise ValueError(
                        f"label {match.value:g} does not agree with the ordered path series"
                    )
        return tuple(
            LabelledCurve(
                value=value,
                path_index=assigned[value].path_index,
                points=curve_points(
                    drawings[assigned[value].path_index]["items"],
                    calibration,
                ),
            )
            for value in expected
        )


def _candidate_paths(
    drawings: Sequence[object],
    *,
    dash: str,
    width: float,
    min_path_width: float,
) -> list[PathCandidate]:
    """Return the drawing paths matching a dash/width family."""
    paths: list[PathCandidate] = []
    for index, drawing in enumerate(drawings):
        get = getattr(drawing, "get", None)
        if not callable(get):
            continue
        if get("dashes") != dash:
            continue
        if abs(float(get("width") or 0.0) - width) > 1e-3:
            continue
        rect = get("rect")
        if rect is None or getattr(rect, "width", 0.0) < min_path_width:
            continue
        if getattr(rect, "height", 0.0) <= 3.0:
            continue
        items = get("items")
        if not isinstance(items, list):
            continue
        points = _pdf_path_points(items)
        if len(points) >= 2:
            paths.append(PathCandidate(index, tuple(points)))
    return paths


def _printed_labels(page: object, unit: str) -> tuple[PrintedLabel, ...]:
    """Read printed ``value unit`` labels from one PDF page.

    Parameters
    ----------
    page : object
        A PyMuPDF page. PyMuPDF has no type stubs, so the page is treated as an
        opaque object and its text dictionary is validated below.
    unit : str
        The required unit.

    Returns
    -------
    tuple of PrintedLabel
        The labels in page order.
    """
    pattern = re.compile(rf"^(\d+(?:\.\d+)?)\s*{re.escape(unit)}$")
    get_text = getattr(page, "get_text", None)
    if not callable(get_text):
        return ()
    payload = cast(dict[str, object], get_text("dict"))  # PyMuPDF has no type stubs.
    blocks = payload.get("blocks", [])
    if not isinstance(blocks, list):
        return ()
    labels: list[PrintedLabel] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        lines = block.get("lines", [])
        if not isinstance(lines, list):
            continue
        for line in lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans", [])
            if not isinstance(spans, list):
                continue
            text = " ".join(str(span.get("text", "")) for span in spans if isinstance(span, dict))
            text = " ".join(text.split())
            match = pattern.fullmatch(text)
            if match is None:
                continue
            bbox = line.get("bbox")
            if not isinstance(bbox, list | tuple) or len(bbox) != 4:
                continue
            try:
                x0, y0, x1, y1 = (float(value) for value in bbox)
            except (TypeError, ValueError):
                continue
            labels.append(PrintedLabel(float(match.group(1)), (x0 + x1) / 2.0, (y0 + y1) / 2.0))
    return tuple(labels)


def _pdf_path_points(items: Sequence[Sequence[object]]) -> list[tuple[float, float]]:
    """Return a path's PDF vertices in drawing order.

    Parameters
    ----------
    items : sequence of sequence of object
        The ``items`` list from one drawing.

    Returns
    -------
    list of tuple of float
        The vertices, with consecutive duplicates removed.

    Raises
    ------
    ValueError
        If an item's point is not a PDF point.
    """
    points: list[tuple[float, float]] = []
    for item in items:
        if not item:
            continue
        for value in item[1:]:
            x = getattr(value, "x", None)
            y = getattr(value, "y", None)
            if not isinstance(x, int | float) or not isinstance(y, int | float):
                continue
            point = (float(x), float(y))
            if not points or points[-1] != point:
                points.append(point)
    return points


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
