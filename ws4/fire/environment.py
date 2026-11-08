"""The fire environment: wind, slope, and optional weather context.

The kernel takes a midflame wind speed and a slope percent. The remaining fields are context
for provenance and later FBP/weather work; they do not change the Rothermel surface-fire
calculation in this slice.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .fuel import FireFuelError, _non_negative, _number


@dataclass(frozen=True)
class FireEnvironment:
    """One fire-weather and terrain environment.

    Parameters
    ----------
    wind_kmh : float, optional
        Midflame wind speed in kilometres per hour (default 0).
    slope_percent : float, optional
        Site slope in percent (default 0).
    wind_direction_deg : float or None, optional
        Wind direction clockwise from north.
    aspect_deg : float or None, optional
        Slope aspect clockwise from north.
    elevation_m : float or None, optional
        Elevation in metres.
    temperature_c : float or None, optional
        Air temperature in degrees Celsius.
    relative_humidity_percent : float or None, optional
        Relative humidity in percent.
    """

    wind_kmh: float = 0.0
    slope_percent: float = 0.0
    wind_direction_deg: float | None = None
    aspect_deg: float | None = None
    elevation_m: float | None = None
    temperature_c: float | None = None
    relative_humidity_percent: float | None = None

    def __post_init__(self) -> None:
        """Validate the environment."""
        wind = _non_negative(self.wind_kmh, "wind_kmh")
        slope = _non_negative(self.slope_percent, "slope_percent")
        wind_direction = (
            None
            if self.wind_direction_deg is None
            else _number(self.wind_direction_deg, "wind_direction_deg") % 360.0
        )
        aspect = None if self.aspect_deg is None else _number(self.aspect_deg, "aspect_deg") % 360.0
        elevation = None if self.elevation_m is None else _number(self.elevation_m, "elevation_m")
        temperature = (
            None if self.temperature_c is None else _number(self.temperature_c, "temperature_c")
        )
        humidity = (
            None
            if self.relative_humidity_percent is None
            else _number(self.relative_humidity_percent, "relative_humidity_percent")
        )
        if humidity is not None and not 0.0 <= humidity <= 100.0:
            raise FireFuelError("relative_humidity_percent must be between 0 and 100")
        object.__setattr__(self, "wind_kmh", wind)
        object.__setattr__(self, "slope_percent", slope)
        object.__setattr__(self, "wind_direction_deg", wind_direction)
        object.__setattr__(self, "aspect_deg", aspect)
        object.__setattr__(self, "elevation_m", elevation)
        object.__setattr__(self, "temperature_c", temperature)
        object.__setattr__(self, "relative_humidity_percent", humidity)

    def to_dict(self) -> dict[str, object]:
        """Return the environment as a JSON-serializable mapping.

        Returns
        -------
        dict
            The environment fields.
        """
        return {
            "wind_kmh": self.wind_kmh,
            "slope_percent": self.slope_percent,
            "wind_direction_deg": self.wind_direction_deg,
            "aspect_deg": self.aspect_deg,
            "elevation_m": self.elevation_m,
            "temperature_c": self.temperature_c,
            "relative_humidity_percent": self.relative_humidity_percent,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> FireEnvironment:
        """Validate and construct an environment from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        FireEnvironment
            The validated environment.
        """
        return cls(
            wind_kmh=_non_negative(payload.get("wind_kmh", 0.0), "wind_kmh"),
            slope_percent=_non_negative(payload.get("slope_percent", 0.0), "slope_percent"),
            wind_direction_deg=None
            if payload.get("wind_direction_deg") is None
            else _number(payload["wind_direction_deg"], "wind_direction_deg"),
            aspect_deg=None
            if payload.get("aspect_deg") is None
            else _number(payload["aspect_deg"], "aspect_deg"),
            elevation_m=None
            if payload.get("elevation_m") is None
            else _number(payload["elevation_m"], "elevation_m"),
            temperature_c=None
            if payload.get("temperature_c") is None
            else _number(payload["temperature_c"], "temperature_c"),
            relative_humidity_percent=None
            if payload.get("relative_humidity_percent") is None
            else _number(payload["relative_humidity_percent"], "relative_humidity_percent"),
        )
