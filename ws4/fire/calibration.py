"""Pre-registered calibration parameters and scoring for P161.

The protocol fixes two global multipliers, a 5 x 5 grid, and a weighted score over the P157
metrics. This module is deliberately small: it does not search adaptively and does not let the
holdout influence the parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

from .comparison import PerimeterMetrics
from .fuel import FireFuelError, _non_negative

WIND_MULTIPLIER_BOUNDS = (0.70, 1.30)
HEAD_ROS_MULTIPLIER_BOUNDS = (0.50, 1.50)
_WIND_LEVELS = (0.70, 0.85, 1.00, 1.15, 1.30)
_HEAD_ROS_LEVELS = (0.50, 0.75, 1.00, 1.25, 1.50)


@dataclass(frozen=True)
class CalibrationParameters:
    """The two global multipliers allowed by the P161 protocol.

    Parameters
    ----------
    wind_multiplier : float, optional
        Multiplier on ten-metre wind (default 1.0).
    head_ros_multiplier : float, optional
        Multiplier on final head rate of spread (default 1.0).

    Raises
    ------
    FireFuelError
        If a multiplier is non-positive.
    """

    wind_multiplier: float = 1.0
    head_ros_multiplier: float = 1.0

    def __post_init__(self) -> None:
        """Validate the multipliers."""
        if _non_negative(self.wind_multiplier, "wind_multiplier") <= 0.0:
            raise FireFuelError("wind_multiplier must be positive")
        if _non_negative(self.head_ros_multiplier, "head_ros_multiplier") <= 0.0:
            raise FireFuelError("head_ros_multiplier must be positive")

    def to_dict(self) -> dict[str, float]:
        """Return the parameters as a JSON-serializable mapping.

        Returns
        -------
        dict
            Both multipliers.
        """
        return {
            "wind_multiplier": self.wind_multiplier,
            "head_ros_multiplier": self.head_ros_multiplier,
        }


@dataclass(frozen=True)
class CalibrationScore:
    """The weighted P161 calibration score and its components.

    Parameters
    ----------
    total : float
        Weighted score; lower is better.
    area : float
        Area-bias component.
    perimeter : float
        Perimeter-bias component.
    centroid : float
        Capped centroid component.
    iou : float
        IoU component.
    sorensen : float
        Sorensen component.
    orientation : float
        Capped orientation component.
    """

    total: float
    area: float
    perimeter: float
    centroid: float
    iou: float
    sorensen: float
    orientation: float

    def to_dict(self) -> dict[str, float]:
        """Return the score and components as a JSON-serializable mapping.

        Returns
        -------
        dict
            Weighted total and each component.
        """
        return {
            "total": self.total,
            "area": self.area,
            "perimeter": self.perimeter,
            "centroid": self.centroid,
            "iou": self.iou,
            "sorensen": self.sorensen,
            "orientation": self.orientation,
        }


def calibration_score(metrics: PerimeterMetrics) -> CalibrationScore:
    """Return the pre-registered weighted score for one comparison.

    Parameters
    ----------
    metrics : PerimeterMetrics
        The P157 comparison metrics.

    Returns
    -------
    CalibrationScore
        Weighted total and components.

    Notes
    -----
    The weights and caps are fixed by
    ``notes/design/ws4-fire-calibration-protocol.md``.
    """
    area = 0.25 * abs(metrics.area_bias)
    perimeter = 0.15 * abs(metrics.perimeter_bias)
    centroid = 0.20 * min(metrics.centroid_distance_m / 1000.0 / 5.0, 1.0)
    iou = 0.20 * (1.0 - metrics.iou)
    sorensen = 0.10 * (1.0 - metrics.sorensen)
    orientation = 0.10 * min(metrics.orientation_error_deg / 30.0, 1.0)
    return CalibrationScore(
        total=area + perimeter + centroid + iou + sorensen + orientation,
        area=area,
        perimeter=perimeter,
        centroid=centroid,
        iou=iou,
        sorensen=sorensen,
        orientation=orientation,
    )


def parameter_grid() -> tuple[CalibrationParameters, ...]:
    """Return the fixed 5 x 5 calibration grid.

    Returns
    -------
    tuple of CalibrationParameters
        25 points in row-major order, including the 1.0/1.0 baseline.
    """
    return tuple(
        CalibrationParameters(wind_multiplier=wind, head_ros_multiplier=head)
        for head in _HEAD_ROS_LEVELS
        for wind in _WIND_LEVELS
    )


def is_within_protocol(parameters: CalibrationParameters) -> bool:
    """Return whether a parameter point lies inside the registered bounds.

    Parameters
    ----------
    parameters : CalibrationParameters
        Candidate parameters.

    Returns
    -------
    bool
        True when both multipliers are inside their registered bounds.
    """
    wind_low, wind_high = WIND_MULTIPLIER_BOUNDS
    head_low, head_high = HEAD_ROS_MULTIPLIER_BOUNDS
    return (
        wind_low <= parameters.wind_multiplier <= wind_high
        and head_low <= parameters.head_ros_multiplier <= head_high
    )
