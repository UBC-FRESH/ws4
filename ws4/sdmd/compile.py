"""AU-level SDMD reporting and trajectory plausibility.

The report places an AU's observed points, builds their convex envelope, and assesses
FVS or PSP trajectories against it. A trajectory that leaves the envelope is called an
extrapolation, not a result. An initial volume above the supplied limit is rejected. A
report cannot use a diagram that a forester has not reviewed.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from .diagram import (
    SdmdDiagram,
    SdmdDiagramError,
    inside_envelope,
    observed_envelope,
)


class SdmdReportError(ValueError):
    """Raised when an AU report cannot be built from the supplied evidence."""


@dataclass(frozen=True)
class Trajectory:
    """One named sequence of diagram points.

    Attributes
    ----------
    label : str
        A short label, such as ``fvs-no-cut`` or ``ct60``.
    points : tuple of tuple of float
        ``(tph, mean_tree_volume_m3)`` points in age order.
    """

    label: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class TrajectoryAssessment:
    """The plausibility of one trajectory against the observed envelope.

    Attributes
    ----------
    label : str
        The trajectory label.
    point_count : int
        Number of points assessed.
    status : {"inside", "extrapolated"}
        Whether every point stayed inside the envelope.
    first_outside : tuple of float or None
        The first point outside the envelope, when there is one.
    """

    label: str
    point_count: int
    status: str
    first_outside: tuple[float, float] | None

    def to_dict(self) -> dict[str, object]:
        """Return the assessment as a JSON-serializable mapping.

        Returns
        -------
        dict
            The assessment fields.
        """
        return {
            "label": self.label,
            "point_count": self.point_count,
            "status": self.status,
            "first_outside": (None if self.first_outside is None else list(self.first_outside)),
        }


@dataclass(frozen=True)
class AuReport:
    """The SDMD evidence bundle for one analysis unit.

    Attributes
    ----------
    au_id : str
        The analysis unit.
    diagram_id : str
        The diagram used.
    status : {"supported", "extrapolated", "rejected", "unsupported"}
        The overall plausibility.
    review_status : str
        The diagram's review status.
    observed_count : int
        Number of usable observed points.
    observed_age_min : int or None
        Youngest observed age.
    observed_age_max : int or None
        Oldest observed age.
    envelope : tuple of tuple of float
        The convex observed envelope, or an empty tuple when unsupported.
    trajectories : tuple of TrajectoryAssessment
        One assessment per supplied trajectory.
    initial_volume_m3_ha : float or None
        The supplied initial volume.
    initial_volume_limit_m3_ha : float or None
        The supplied plausibility limit.
    data_gaps : tuple of str
        Named gaps and caveats.
    """

    au_id: str
    diagram_id: str
    status: str
    review_status: str
    observed_count: int
    observed_age_min: int | None
    observed_age_max: int | None
    envelope: tuple[tuple[float, float], ...]
    trajectories: tuple[TrajectoryAssessment, ...]
    initial_volume_m3_ha: float | None
    initial_volume_limit_m3_ha: float | None
    data_gaps: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the report as a JSON-serializable mapping.

        Returns
        -------
        dict
            The report fields, with tuples converted to lists.
        """
        return {
            "au_id": self.au_id,
            "diagram_id": self.diagram_id,
            "status": self.status,
            "review_status": self.review_status,
            "observed_count": self.observed_count,
            "observed_age_min": self.observed_age_min,
            "observed_age_max": self.observed_age_max,
            "envelope": [list(point) for point in self.envelope],
            "trajectories": [item.to_dict() for item in self.trajectories],
            "initial_volume_m3_ha": self.initial_volume_m3_ha,
            "initial_volume_limit_m3_ha": self.initial_volume_limit_m3_ha,
            "data_gaps": list(self.data_gaps),
        }


def assess_trajectory(
    trajectory: Trajectory,
    envelope: Sequence[tuple[float, float]],
) -> TrajectoryAssessment:
    """Assess a trajectory against a convex observed envelope.

    Parameters
    ----------
    trajectory : Trajectory
        The trajectory.
    envelope : sequence of tuple of float
        The observed envelope from :func:`ws4.sdmd.diagram.observed_envelope`.

    Returns
    -------
    TrajectoryAssessment
        Inside when every point is inside, otherwise extrapolated with the first
        outside point.

    Raises
    ------
    SdmdReportError
        If the trajectory has no points.
    """
    if not trajectory.points:
        raise SdmdReportError(f"trajectory {trajectory.label!r} has no points")
    for point in trajectory.points:
        if not inside_envelope(point, envelope):
            return TrajectoryAssessment(
                label=trajectory.label,
                point_count=len(trajectory.points),
                status="extrapolated",
                first_outside=point,
            )
    return TrajectoryAssessment(
        label=trajectory.label,
        point_count=len(trajectory.points),
        status="inside",
        first_outside=None,
    )


def build_au_report(
    *,
    au_id: str,
    diagram: SdmdDiagram,
    observed: pd.DataFrame,
    trajectories: Sequence[Trajectory] = (),
    initial_volume_m3_ha: float | None = None,
    initial_volume_limit_m3_ha: float | None = None,
    allow_unreviewed: bool = False,
) -> AuReport:
    """Build the SDMD evidence report for one AU.

    Parameters
    ----------
    au_id : str
        The analysis unit.
    diagram : SdmdDiagram
        The diagram. It must be reviewed unless ``allow_unreviewed`` is set.
    observed : pandas.DataFrame
        SDMD points with ``tph`` and ``mean_tree_volume_m3`` columns, and optional
        ``au_id`` and ``age`` columns.
    trajectories : sequence of Trajectory, optional
        FVS or PSP trajectories to assess.
    initial_volume_m3_ha : float, optional
        The AU's initial volume.
    initial_volume_limit_m3_ha : float, optional
        The highest initial volume the evidence supports. A higher volume is rejected.
    allow_unreviewed : bool
        Permit a provisional diagram for method work. Defaults to ``False``.

    Returns
    -------
    AuReport
        The report.

    Raises
    ------
    SdmdReportError
        If the AU id is empty, a volume is negative, or an unreviewed diagram is used
        without ``allow_unreviewed``.
    """
    if not au_id.strip():
        raise SdmdReportError("au_id must not be empty")
    if not allow_unreviewed and diagram.review.status != "reviewed":
        message = (
            f"diagram {diagram.diagram_id!r} is {diagram.review.status}; "
            "a report needs a reviewed diagram"
        )
        raise SdmdReportError(message)
    if initial_volume_m3_ha is not None and initial_volume_m3_ha < 0:
        raise SdmdReportError("initial_volume_m3_ha must not be negative")
    if initial_volume_limit_m3_ha is not None and initial_volume_limit_m3_ha <= 0:
        raise SdmdReportError("initial_volume_limit_m3_ha must be positive")
    selected = observed
    if "au_id" in selected.columns:
        selected = selected.loc[selected["au_id"].astype("string") == au_id]
    gaps: list[str] = []
    points, rejected = _observed_points(selected)
    if rejected:
        gaps.append(f"{rejected} observed point(s) had non-positive coordinates")
    ages = _ages(selected)
    if diagram.review.status != "reviewed":
        gaps.append(f"diagram review status is {diagram.review.status}")
    if len(points) < 3:
        gaps.append("fewer than three distinct observed points")
        return AuReport(
            au_id=au_id,
            diagram_id=diagram.diagram_id,
            status="unsupported",
            review_status=diagram.review.status,
            observed_count=len(points),
            observed_age_min=ages[0],
            observed_age_max=ages[1],
            envelope=(),
            trajectories=(),
            initial_volume_m3_ha=initial_volume_m3_ha,
            initial_volume_limit_m3_ha=initial_volume_limit_m3_ha,
            data_gaps=tuple(gaps),
        )
    try:
        envelope = observed_envelope(points)
    except SdmdDiagramError:
        gaps.append("observed points do not span an area")
        return AuReport(
            au_id=au_id,
            diagram_id=diagram.diagram_id,
            status="unsupported",
            review_status=diagram.review.status,
            observed_count=len(points),
            observed_age_min=ages[0],
            observed_age_max=ages[1],
            envelope=(),
            trajectories=(),
            initial_volume_m3_ha=initial_volume_m3_ha,
            initial_volume_limit_m3_ha=initial_volume_limit_m3_ha,
            data_gaps=tuple(gaps),
        )
    assessments = tuple(assess_trajectory(trajectory, envelope) for trajectory in trajectories)
    extrapolated = [item for item in assessments if item.status == "extrapolated"]
    for item in extrapolated:
        gaps.append(f"trajectory {item.label} leaves the observed envelope")
    rejected_volume = (
        initial_volume_m3_ha is not None
        and initial_volume_limit_m3_ha is not None
        and initial_volume_m3_ha > initial_volume_limit_m3_ha
    )
    if rejected_volume:
        gaps.append(
            "initial volume exceeds the evidence limit: "
            f"{initial_volume_m3_ha:g} > {initial_volume_limit_m3_ha:g} m3/ha"
        )
        status = "rejected"
    elif extrapolated:
        status = "extrapolated"
    else:
        status = "supported"
    return AuReport(
        au_id=au_id,
        diagram_id=diagram.diagram_id,
        status=status,
        review_status=diagram.review.status,
        observed_count=len(points),
        observed_age_min=ages[0],
        observed_age_max=ages[1],
        envelope=envelope,
        trajectories=assessments,
        initial_volume_m3_ha=initial_volume_m3_ha,
        initial_volume_limit_m3_ha=initial_volume_limit_m3_ha,
        data_gaps=tuple(gaps),
    )


def _observed_points(frame: pd.DataFrame) -> tuple[list[tuple[float, float]], int]:
    """Extract usable diagram coordinates from an observed frame.

    Parameters
    ----------
    frame : pandas.DataFrame
        A frame with ``tph`` and ``mean_tree_volume_m3``.

    Returns
    -------
    tuple of (list of tuple of float, int)
        The positive points and the number rejected for a non-positive coordinate.

    Raises
    ------
    SdmdReportError
        If a required column is missing.
    """
    for column in ("tph", "mean_tree_volume_m3"):
        if column not in frame.columns:
            raise SdmdReportError(f"observed points are missing column {column}")
    points: list[tuple[float, float]] = []
    rejected = 0
    for tph, volume in zip(frame["tph"], frame["mean_tree_volume_m3"], strict=True):
        tph_value = float(str(tph))
        volume_value = float(str(volume))
        if (
            not math.isfinite(tph_value)
            or not math.isfinite(volume_value)
            or tph_value <= 0
            or volume_value <= 0
        ):
            rejected += 1
            continue
        points.append((tph_value, volume_value))
    return points, rejected


def _ages(frame: pd.DataFrame) -> tuple[int | None, int | None]:
    """Return the observed age range.

    Parameters
    ----------
    frame : pandas.DataFrame
        A frame with an optional ``age`` column.

    Returns
    -------
    tuple of (int or None, int or None)
        The youngest and oldest age, or two ``None`` values.
    """
    if "age" not in frame.columns or frame.empty:
        return None, None
    ages = pd.to_numeric(frame["age"], errors="coerce").dropna()
    if ages.empty:
        return None, None
    return _as_int(ages.min()), _as_int(ages.max())


def _as_int(value: object) -> int:
    """Convert a scalar age to an integer without losing a nullable value.

    Parameters
    ----------
    value : object
        The scalar from a pandas reduction.

    Returns
    -------
    int
        The age as an integer.
    """
    return int(float(str(value)))
