"""Vector stand density management diagrams and point placement.

A diagram is stored as ordered isopleths, not as a raster. The x axis is trees per
hectare, the y axis is mean tree volume in cubic metres, and both are interpolated in
log space. The module validates the source and the review record, places a point in a
density zone, and builds the observed envelope that the AU report uses to flag
extrapolation.

The committed diagram is illustrative and provisional. It is not a digitisation of a
published diagram; a real diagram needs a source copy and a named review before a
report may use it (ADR 0013).
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .schema import SDMD_ZONES, Problem

SDMD_DIAGRAM_SCHEMA_VERSION = "ws4.sdmd.diagram.v1"

ISOPLETH_KINDS: tuple[str, ...] = (
    "top_height",
    "qmd",
    "crown_closure",
    "competition",
    "self_thinning",
)

BOUNDARY_KINDS: tuple[str, ...] = ("crown_closure", "competition", "self_thinning")

SOURCE_KINDS: tuple[str, ...] = ("published", "synthetic")

DIAGRAM_REVIEW_STATUSES: tuple[str, ...] = ("unreviewed", "provisional", "reviewed", "rejected")


class SdmdDiagramError(ValueError):
    """Raised when a diagram is malformed, invalid, or not usable for a report."""


@dataclass(frozen=True)
class DiagramSource:
    """Provenance for a digitised diagram.

    Attributes
    ----------
    citation : str
        Short citation of the published source, or a statement that the data are
        illustrative.
    version : str
        Digitisation version or source vintage.
    licence : str
        Licence or permission that allows the digitisation.
    kind : {"published", "synthetic"}
        Whether the diagram is a published source or an illustrative fixture.
    """

    citation: str
    version: str
    licence: str
    kind: str


@dataclass(frozen=True)
class DiagramReview:
    """The named review of a digitisation.

    Attributes
    ----------
    status : {"unreviewed", "provisional", "reviewed", "rejected"}
        The review state.
    reviewer : str
        The reviewer's role or identifier. Required when the status is ``reviewed``.
    reviewed_utc : str
        When the review happened. Required when the status is ``reviewed``.
    """

    status: str
    reviewer: str
    reviewed_utc: str


@dataclass(frozen=True)
class Isopleth:
    """One ordered curve on the diagram.

    Attributes
    ----------
    kind : {"top_height", "qmd", "crown_closure", "competition", "self_thinning"}
        The curve family.
    value : float
        The isopleth value: metres for top height, centimetres for QMD, percent for
        crown closure, and a nominal value for a boundary.
    unit : str
        The value's unit.
    points : tuple of tuple of float
        Ordered ``(tph, mean_tree_volume_m3)`` points with strictly increasing TPH.
    """

    kind: str
    value: float
    unit: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class SdmdDiagram:
    """A reviewed or provisional vector density diagram.

    Attributes
    ----------
    diagram_id : str
        Stable diagram identifier.
    species_group : str
        The species group the diagram applies to.
    region : str
        The region the diagram applies to.
    bec_zone : str
        BEC zone.
    bec_subzone : str
        BEC subzone.
    bec_variant : str or None
        BEC variant, when the diagram is variant-specific.
    site_index : float
        The site index the diagram represents.
    source : DiagramSource
        Digitisation provenance.
    review : DiagramReview
        Forester review state.
    isopleths : tuple of Isopleth
        The curves.
    cai_band : tuple of tuple of float or None
        The display-only polygon for the source's "Density Range for Maximizing
        CAI" band, in ``(tph, mean_tree_volume_m3)`` order. It has no numeric
        level and never feeds placement or constraints.
    """

    diagram_id: str
    species_group: str
    region: str
    bec_zone: str
    bec_subzone: str
    bec_variant: str | None
    site_index: float
    source: DiagramSource
    review: DiagramReview
    isopleths: tuple[Isopleth, ...]
    cai_band: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class DiagramPlacement:
    """Where one point sits on the diagram.

    Attributes
    ----------
    tph : float
        Trees per hectare.
    mean_tree_volume_m3 : float
        Mean tree volume in cubic metres.
    zone : str
        One of ``understocked``, ``density-management``, ``competition``,
        ``self-thinning``, or ``outside``.
    top_height_m : float or None
        Interpolated top height, when the point is inside the isopleth range.
    qmd_cm : float or None
        Interpolated quadratic mean diameter, when inside the isopleth range.
    flags : tuple of str
        Why the placement may be untrustworthy, such as ``outside-axis-domain`` or
        ``above-self-thinning``.
    """

    tph: float
    mean_tree_volume_m3: float
    zone: str
    top_height_m: float | None
    qmd_cm: float | None
    flags: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the placement as a JSON-serializable mapping.

        Returns
        -------
        dict
            The placement fields.
        """
        return {
            "tph": self.tph,
            "mean_tree_volume_m3": self.mean_tree_volume_m3,
            "zone": self.zone,
            "top_height_m": self.top_height_m,
            "qmd_cm": self.qmd_cm,
            "flags": list(self.flags),
        }


def load_diagram(path: str | Path) -> SdmdDiagram:
    """Load and validate a diagram from JSON.

    Parameters
    ----------
    path : str or Path
        The JSON file.

    Returns
    -------
    SdmdDiagram
        The validated diagram.

    Raises
    ------
    SdmdDiagramError
        If the file is missing, the schema version differs, a field is malformed, or
        the diagram fails :func:`validate_diagram`.
    """
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SdmdDiagramError(f"diagram not found: {source}") from error
    except json.JSONDecodeError as error:
        raise SdmdDiagramError(f"diagram is not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise SdmdDiagramError("diagram must be a JSON object")
    data: dict[str, object] = {str(key): value for key, value in raw.items()}
    if _text(data.get("schema_version")) != SDMD_DIAGRAM_SCHEMA_VERSION:
        message = f"diagram schema_version must be {SDMD_DIAGRAM_SCHEMA_VERSION!r}"
        raise SdmdDiagramError(message)
    source_payload = _mapping(data.get("source"), "source")
    review_payload = _mapping(data.get("review"), "review")
    diagram = SdmdDiagram(
        diagram_id=_text(data.get("diagram_id")),
        species_group=_text(data.get("species_group")),
        region=_text(data.get("region")),
        bec_zone=_text(data.get("bec_zone")),
        bec_subzone=_text(data.get("bec_subzone")),
        bec_variant=_optional_text(data.get("bec_variant")),
        site_index=_number(data.get("site_index"), "site_index"),
        source=DiagramSource(
            citation=_text(source_payload.get("citation")),
            version=_text(source_payload.get("version")),
            licence=_text(source_payload.get("licence")),
            kind=_text(source_payload.get("kind")),
        ),
        review=DiagramReview(
            status=_text(review_payload.get("status")),
            reviewer=_text(review_payload.get("reviewer")),
            reviewed_utc=_text(review_payload.get("reviewed_utc")),
        ),
        isopleths=_isopleths(data.get("isopleths")),
        cai_band=_optional_band(data.get("cai_band")),
    )
    problems = validate_diagram(diagram)
    if problems:
        detail = "; ".join(f"{item.code} {item.where}: {item.message}" for item in problems)
        raise SdmdDiagramError(detail)
    return diagram


def validate_diagram(diagram: SdmdDiagram) -> list[Problem]:
    """Validate the identity, source, review, and curves of a diagram.

    Parameters
    ----------
    diagram : SdmdDiagram
        The diagram.

    Returns
    -------
    list of Problem
        The findings. The list is empty when the diagram is valid.
    """
    problems: list[Problem] = []
    for field, value in (
        ("diagram_id", diagram.diagram_id),
        ("species_group", diagram.species_group),
        ("region", diagram.region),
        ("bec_zone", diagram.bec_zone),
        ("bec_subzone", diagram.bec_subzone),
    ):
        if not value.strip():
            problems.append(Problem("SDMD-DIAGRAM-FIELD", field, "value must not be empty"))
    if diagram.site_index <= 0:
        problems.append(Problem("SDMD-DIAGRAM-FIELD", "site_index", "value must be positive"))
    problems.extend(_validate_source(diagram.source))
    problems.extend(_validate_review(diagram.review))
    kinds = [isopleth.kind for isopleth in diagram.isopleths]
    for kind in ISOPLETH_KINDS:
        count = kinds.count(kind)
        if kind in BOUNDARY_KINDS and count != 1:
            message = f"a diagram needs exactly one {kind} isopleth"
            problems.append(Problem("SDMD-DIAGRAM-ISOPLETH", kind, message))
        elif kind not in BOUNDARY_KINDS and count < 2:
            message = f"a diagram needs at least two {kind} isopleths to interpolate"
            problems.append(Problem("SDMD-DIAGRAM-ISOPLETH", kind, message))
    for isopleth in diagram.isopleths:
        problems.extend(_validate_isopleth(isopleth))
    if diagram.cai_band is not None:
        problems.extend(_validate_cai_band(diagram.cai_band))
    return problems


def _validate_source(source: DiagramSource) -> list[Problem]:
    """Validate the digitisation provenance.

    Parameters
    ----------
    source : DiagramSource
        The provenance record.

    Returns
    -------
    list of Problem
        The findings.
    """
    problems: list[Problem] = []
    for field, value in (
        ("citation", source.citation),
        ("version", source.version),
        ("licence", source.licence),
    ):
        if not value.strip():
            problems.append(
                Problem("SDMD-DIAGRAM-SOURCE", f"source.{field}", "value must not be empty")
            )
    if source.kind not in SOURCE_KINDS:
        problems.append(
            Problem(
                "SDMD-DIAGRAM-SOURCE",
                "source.kind",
                f"must be one of {', '.join(SOURCE_KINDS)}",
            )
        )
    return problems


def _validate_review(review: DiagramReview) -> list[Problem]:
    """Validate the review record.

    Parameters
    ----------
    review : DiagramReview
        The review record.

    Returns
    -------
    list of Problem
        The findings.
    """
    problems: list[Problem] = []
    if review.status not in DIAGRAM_REVIEW_STATUSES:
        problems.append(
            Problem(
                "SDMD-DIAGRAM-REVIEW",
                "review.status",
                f"must be one of {', '.join(DIAGRAM_REVIEW_STATUSES)}",
            )
        )
    if review.status == "reviewed":
        for field, value in (("reviewer", review.reviewer), ("reviewed_utc", review.reviewed_utc)):
            if not value.strip():
                problems.append(
                    Problem(
                        "SDMD-DIAGRAM-REVIEW",
                        f"review.{field}",
                        "a reviewed diagram needs this value",
                    )
                )
    return problems


def _validate_isopleth(isopleth: Isopleth) -> list[Problem]:
    """Validate one isopleth's value and ordered points.

    Parameters
    ----------
    isopleth : Isopleth
        The curve.

    Returns
    -------
    list of Problem
        The findings.
    """
    where = f"isopleth.{isopleth.kind}"
    problems: list[Problem] = []
    if isopleth.kind not in ISOPLETH_KINDS:
        problems.append(Problem("SDMD-DIAGRAM-ISOPLETH", where, f"unknown kind {isopleth.kind!r}"))
    if isopleth.value <= 0:
        problems.append(Problem("SDMD-DIAGRAM-ISOPLETH", where, "value must be positive"))
    if not isopleth.unit.strip():
        problems.append(Problem("SDMD-DIAGRAM-ISOPLETH", where, "unit must not be empty"))
    if len(isopleth.points) < 2:
        problems.append(
            Problem("SDMD-DIAGRAM-ISOPLETH", where, "needs at least two ordered points")
        )
        return problems
    previous = -math.inf
    for tph, volume in isopleth.points:
        if tph <= 0 or volume <= 0:
            problems.append(Problem("SDMD-DIAGRAM-ISOPLETH", where, "points must be positive"))
            break
        if tph <= previous:
            problems.append(
                Problem(
                    "SDMD-DIAGRAM-ISOPLETH",
                    where,
                    "points must be ordered by strictly increasing TPH",
                )
            )
            break
        previous = tph
    return problems


def _validate_cai_band(points: tuple[tuple[float, float], ...]) -> list[Problem]:
    """Validate the optional display-only CAI band polygon.

    Parameters
    ----------
    points : tuple of tuple of float
        The ``(tph, mean_tree_volume_m3)`` ring.

    Returns
    -------
    list of Problem
        The findings. The list is empty when the ring is usable.
    """
    problems: list[Problem] = []
    if len(points) < 3:
        problems.append(
            Problem(
                "SDMD-DIAGRAM-CAI",
                "cai_band",
                "a CAI band needs at least three polygon points",
            )
        )
        return problems
    for tph, volume in points:
        if tph <= 0 or volume <= 0:
            problems.append(Problem("SDMD-DIAGRAM-CAI", "cai_band", "points must be positive"))
            break
    return problems


def isopleth_y(isopleth: Isopleth, tph: float) -> float | None:
    """Interpolate an isopleth's mean tree volume at a density.

    The interpolation is linear in log10 space, which is how the axes of a classic
    diagram are read. A density outside the digitised points returns ``None``.

    Parameters
    ----------
    isopleth : Isopleth
        The curve.
    tph : float
        Trees per hectare.

    Returns
    -------
    float or None
        Mean tree volume in cubic metres, or ``None`` outside the curve domain.

    Raises
    ------
    SdmdDiagramError
        If ``tph`` is not positive.
    """
    if tph <= 0:
        raise SdmdDiagramError("tph must be positive")
    points = isopleth.points
    if tph < points[0][0] or tph > points[-1][0]:
        return None
    for index in range(1, len(points)):
        x0, y0 = points[index - 1]
        x1, y1 = points[index]
        if tph <= x1:
            fraction = (math.log10(tph) - math.log10(x0)) / (math.log10(x1) - math.log10(x0))
            return 10 ** (math.log10(y0) + fraction * (math.log10(y1) - math.log10(y0)))
    return points[-1][1]


def interpolate_value(
    diagram: SdmdDiagram,
    kind: str,
    tph: float,
    mean_tree_volume_m3: float,
) -> float | None:
    """Interpolate an isopleth family's value at a point.

    Parameters
    ----------
    diagram : SdmdDiagram
        The diagram.
    kind : str
        ``top_height`` or ``qmd``.
    tph : float
        Trees per hectare.
    mean_tree_volume_m3 : float
        Mean tree volume in cubic metres.

    Returns
    -------
    float or None
        The interpolated metres or centimetres, or ``None`` when the point is outside
        the family's vertical range or the family does not bracket it.
    """
    samples: list[tuple[float, float]] = []
    for isopleth in diagram.isopleths:
        if isopleth.kind != kind:
            continue
        height = isopleth_y(isopleth, tph)
        if height is not None:
            samples.append((height, isopleth.value))
    if len(samples) < 2:
        return None
    samples.sort()
    if mean_tree_volume_m3 < samples[0][0] or mean_tree_volume_m3 > samples[-1][0]:
        return None
    for (y0, value0), (y1, value1) in itertools.pairwise(samples):
        if y0 <= mean_tree_volume_m3 <= y1:
            if y1 == y0:
                return value0
            fraction = (mean_tree_volume_m3 - y0) / (y1 - y0)
            return value0 + fraction * (value1 - value0)
    return None


def place_point(
    diagram: SdmdDiagram,
    tph: float,
    mean_tree_volume_m3: float,
) -> DiagramPlacement:
    """Place one point on the diagram and name its zone.

    Parameters
    ----------
    diagram : SdmdDiagram
        A validated diagram.
    tph : float
        Trees per hectare.
    mean_tree_volume_m3 : float
        Mean tree volume in cubic metres.

    Returns
    -------
    DiagramPlacement
        The zone, interpolated top height and QMD, and any flags.

    Raises
    ------
    SdmdDiagramError
        If either coordinate is not positive.
    """
    if tph <= 0 or mean_tree_volume_m3 <= 0:
        raise SdmdDiagramError("diagram coordinates must be positive")
    closure = _boundary_y(diagram, "crown_closure", tph)
    competition = _boundary_y(diagram, "competition", tph)
    self_thinning = _boundary_y(diagram, "self_thinning", tph)
    flags: list[str] = []
    if closure is None or competition is None or self_thinning is None:
        zone = "outside"
        flags.append("outside-axis-domain")
    elif mean_tree_volume_m3 > self_thinning:
        zone = "outside"
        flags.append("above-self-thinning")
    elif mean_tree_volume_m3 > competition:
        zone = "competition"
    elif mean_tree_volume_m3 < closure:
        zone = "understocked"
    else:
        zone = "density-management"
    top_height = interpolate_value(diagram, "top_height", tph, mean_tree_volume_m3)
    qmd = interpolate_value(diagram, "qmd", tph, mean_tree_volume_m3)
    if top_height is None or qmd is None:
        flags.append("outside-isopleth-range")
    if zone not in SDMD_ZONES:
        raise SdmdDiagramError(f"zone {zone!r} is not part of the schema")
    return DiagramPlacement(
        tph=tph,
        mean_tree_volume_m3=mean_tree_volume_m3,
        zone=zone,
        top_height_m=top_height,
        qmd_cm=qmd,
        flags=tuple(flags),
    )


def observed_envelope(points: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Build the convex observed envelope of SDMD points.

    The hull is computed in log10 space because the diagram's axes are logarithmic.
    The returned vertices are in the original units and are counter-clockwise.

    Parameters
    ----------
    points : sequence of tuple of float
        ``(tph, mean_tree_volume_m3)`` observations.

    Returns
    -------
    tuple of tuple of float
        The hull vertices.

    Raises
    ------
    SdmdDiagramError
        If fewer than three distinct positive points are supplied.
    """
    if len(points) < 3:
        raise SdmdDiagramError("an observed envelope needs at least three points")
    logged: list[tuple[float, float]] = []
    for tph, volume in points:
        if tph <= 0 or volume <= 0:
            raise SdmdDiagramError("envelope coordinates must be positive")
        logged.append((math.log10(tph), math.log10(volume)))
    hull = _convex_hull(logged)
    if len(hull) < 3:
        raise SdmdDiagramError("the observed points do not span an area")
    return tuple((10**x, 10**y) for x, y in hull)


def inside_envelope(
    point: tuple[float, float],
    envelope: Sequence[tuple[float, float]],
) -> bool:
    """Test whether a point is inside a convex observed envelope.

    Parameters
    ----------
    point : tuple of float
        ``(tph, mean_tree_volume_m3)``.
    envelope : sequence of tuple of float
        A counter-clockwise convex hull from :func:`observed_envelope`.

    Returns
    -------
    bool
        ``True`` on or inside the hull. The test is performed in log10 space, where
        the hull is convex.
    """
    if len(envelope) < 3 or point[0] <= 0 or point[1] <= 0:
        return False
    logged = [(math.log10(x), math.log10(y)) for x, y in envelope]
    x, y = math.log10(point[0]), math.log10(point[1])
    for index in range(len(logged)):
        x0, y0 = logged[index]
        x1, y1 = logged[(index + 1) % len(logged)]
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if cross < -1e-12:
            return False
    return True


def _convex_hull(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return the counter-clockwise convex hull of distinct points.

    Parameters
    ----------
    points : sequence of tuple of float
        The points.

    Returns
    -------
    list of tuple of float
        The hull vertices.
    """
    unique = sorted(set(points))
    if len(unique) < 3:
        return unique

    def cross(
        origin: tuple[float, float],
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> float:
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (
            second[0] - origin[0]
        )

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _boundary_y(diagram: SdmdDiagram, kind: str, tph: float) -> float | None:
    """Return the single boundary curve's value at a density.

    Parameters
    ----------
    diagram : SdmdDiagram
        The diagram.
    kind : str
        The boundary kind.
    tph : float
        Trees per hectare.

    Returns
    -------
    float or None
        The mean tree volume at the boundary, or ``None`` outside its domain.
    """
    for isopleth in diagram.isopleths:
        if isopleth.kind == kind:
            return isopleth_y(isopleth, tph)
    return None


def _isopleths(value: object) -> tuple[Isopleth, ...]:
    """Parse the isopleth list from JSON.

    Parameters
    ----------
    value : object
        The decoded ``isopleths`` value.

    Returns
    -------
    tuple of Isopleth
        The parsed curves.

    Raises
    ------
    SdmdDiagramError
        If the value is not a list of well-formed isopleth objects.
    """
    if not isinstance(value, list):
        raise SdmdDiagramError("diagram isopleths must be a list")
    result: list[Isopleth] = []
    for item in value:
        payload = _mapping(item, "isopleth")
        kind = _text(payload.get("kind"))
        points_raw = payload.get("points")
        if not isinstance(points_raw, list):
            raise SdmdDiagramError(f"isopleth {kind!r} points must be a list")
        points: list[tuple[float, float]] = []
        for point in points_raw:
            if not isinstance(point, list) or len(point) != 2:
                raise SdmdDiagramError(f"isopleth {kind!r} points must be [tph, volume]")
            points.append((_number(point[0], "tph"), _number(point[1], "mean_tree_volume_m3")))
        result.append(
            Isopleth(
                kind=kind,
                value=_number(payload.get("value"), "isopleth.value"),
                unit=_text(payload.get("unit")),
                points=tuple(points),
            )
        )
    return tuple(result)


def _optional_band(value: object) -> tuple[tuple[float, float], ...] | None:
    """Parse the optional display-only CAI band polygon from JSON.

    Parameters
    ----------
    value : object
        The decoded ``cai_band`` value.

    Returns
    -------
    tuple of tuple of float or None
        The ordered ring, or ``None`` when the field is absent.

    Raises
    ------
    SdmdDiagramError
        If the value is present but is not a list of ``[tph, volume]`` pairs.
    """
    if value is None:
        return None
    if not isinstance(value, list):
        raise SdmdDiagramError("diagram cai_band must be a list")
    points: list[tuple[float, float]] = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise SdmdDiagramError("diagram cai_band points must be [tph, volume]")
        points.append((_number(point[0], "tph"), _number(point[1], "mean_tree_volume_m3")))
    return tuple(points)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """Require a decoded JSON object.

    Parameters
    ----------
    value : object
        The decoded value.
    name : str
        The field name, used in the message.

    Returns
    -------
    mapping
        The object.

    Raises
    ------
    SdmdDiagramError
        If the value is not an object.
    """
    if not isinstance(value, Mapping):
        raise SdmdDiagramError(f"diagram {name} must be an object")
    return value


def _text(value: object) -> str:
    """Return trimmed text for a decoded value.

    Parameters
    ----------
    value : object
        The decoded value.

    Returns
    -------
    str
        The text, or an empty string for a missing value.
    """
    return "" if value is None else str(value).strip()


def _optional_text(value: object) -> str | None:
    """Return trimmed text or ``None``.

    Parameters
    ----------
    value : object
        The decoded value.

    Returns
    -------
    str or None
        The text, or ``None`` when it is missing or blank.
    """
    text = _text(value)
    return text or None


def _number(value: object, name: str) -> float:
    """Require a finite number.

    Parameters
    ----------
    value : object
        The decoded value.
    name : str
        The field name, used in the message.

    Returns
    -------
    float
        The number.

    Raises
    ------
    SdmdDiagramError
        If the value is not a finite number.
    """
    if isinstance(value, bool) or value is None:
        raise SdmdDiagramError(f"diagram {name} must be a number")
    try:
        number = float(str(value))
    except ValueError as error:
        raise SdmdDiagramError(f"diagram {name} must be a number") from error
    if not math.isfinite(number):
        raise SdmdDiagramError(f"diagram {name} must be finite")
    return number
