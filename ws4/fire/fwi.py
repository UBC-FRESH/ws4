"""Canadian Forest Fire Weather Index moisture codes.

The FWI System turns daily weather into the Fine Fuel Moisture Code (FFMC), Duff Moisture
Code (DMC), Drought Code (DC), Initial Spread Index (ISI), Buildup Index (BUI), Fire Weather
Index (FWI), and Daily Severity Rating (DSR). The equations are the standard Canadian Forest
Fire Danger Rating System equations; the implementation is original Python.

The codes are the moisture and weather input to the FBP surface-fire model. They are kept in
their own module so the FWI sequence can be validated against the reference implementation
before any FBP rate-of-spread equation is trusted.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from .fuel import FireFuelError, _integer, _non_negative, _number

FFMC_COEFFICIENT: Final[float] = 147.2772
DEFAULT_LATITUDE: Final[float] = 55.0

#: DMC day-length factors by latitude band and month.
_ELL01: Final[tuple[float, ...]] = (6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0)
_ELL02: Final[tuple[float, ...]] = (7.9, 8.4, 8.9, 9.5, 9.9, 10.2, 10.1, 9.7, 9.1, 8.6, 8.1, 7.8)
_ELL03: Final[tuple[float, ...]] = (10.1, 9.6, 9.1, 8.5, 8.1, 7.8, 7.9, 8.3, 8.9, 9.4, 9.9, 10.2)
_ELL04: Final[tuple[float, ...]] = (11.5, 10.5, 9.2, 7.9, 6.8, 6.2, 6.5, 7.4, 8.7, 10.0, 11.2, 11.8)
#: DC day-length factors by latitude band and month.
_FL01: Final[tuple[float, ...]] = (-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6)
_FL02: Final[tuple[float, ...]] = (6.4, 5.0, 2.4, 0.4, -1.6, -1.6, -1.6, -1.6, -1.6, 0.9, 3.8, 5.8)


@dataclass(frozen=True)
class DailyWeather:
    """One day of fire-weather observations.

    Parameters
    ----------
    year : int
        Calendar year, used only for ordering.
    month : int
        Month, 1 through 12.
    day : int
        Day of month, 1 through 31.
    temperature_c : float
        Dry-bulb temperature in degrees Celsius.
    relative_humidity_percent : float
        Relative humidity in percent.
    wind_kmh : float
        Ten-metre wind speed in kilometres per hour.
    precipitation_mm : float
        Precipitation in millimetres.
    latitude_deg : float, optional
        Latitude in decimal degrees (default 55).
    """

    year: int
    month: int
    day: int
    temperature_c: float
    relative_humidity_percent: float
    wind_kmh: float
    precipitation_mm: float
    latitude_deg: float = DEFAULT_LATITUDE

    def __post_init__(self) -> None:
        """Validate the daily weather."""
        year = _integer(self.year, "year")
        month = _integer(self.month, "month")
        day = _integer(self.day, "day")
        if month < 1 or month > 12:
            raise FireFuelError("month must be between 1 and 12")
        if day < 1 or day > 31:
            raise FireFuelError("day must be between 1 and 31")
        temperature = _number(self.temperature_c, "temperature_c")
        humidity = _number(self.relative_humidity_percent, "relative_humidity_percent")
        if humidity < 0.0 or humidity > 100.0:
            raise FireFuelError("relative_humidity_percent must be between 0 and 100")
        wind = _non_negative(self.wind_kmh, "wind_kmh")
        precipitation = _non_negative(self.precipitation_mm, "precipitation_mm")
        latitude = _number(self.latitude_deg, "latitude_deg")
        if latitude < -90.0 or latitude > 90.0:
            raise FireFuelError("latitude_deg must be between -90 and 90")
        object.__setattr__(self, "year", year)
        object.__setattr__(self, "month", month)
        object.__setattr__(self, "day", day)
        object.__setattr__(self, "temperature_c", temperature)
        object.__setattr__(self, "relative_humidity_percent", humidity)
        object.__setattr__(self, "wind_kmh", wind)
        object.__setattr__(self, "precipitation_mm", precipitation)
        object.__setattr__(self, "latitude_deg", latitude)

    def to_dict(self) -> dict[str, object]:
        """Return the weather as a JSON-serializable mapping.

        Returns
        -------
        dict
            The weather fields.
        """
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "temperature_c": self.temperature_c,
            "relative_humidity_percent": self.relative_humidity_percent,
            "wind_kmh": self.wind_kmh,
            "precipitation_mm": self.precipitation_mm,
            "latitude_deg": self.latitude_deg,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DailyWeather:
        """Validate and construct daily weather from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        DailyWeather
            The validated weather.
        """
        return cls(
            year=int(float(str(payload["year"]))),
            month=int(float(str(payload["month"]))),
            day=int(float(str(payload["day"]))),
            temperature_c=_number(payload["temperature_c"], "temperature_c"),
            relative_humidity_percent=_number(
                payload["relative_humidity_percent"], "relative_humidity_percent"
            ),
            wind_kmh=_non_negative(payload["wind_kmh"], "wind_kmh"),
            precipitation_mm=_non_negative(payload["precipitation_mm"], "precipitation_mm"),
            latitude_deg=_number(payload.get("latitude_deg", DEFAULT_LATITUDE), "latitude_deg"),
        )


@dataclass(frozen=True)
class FWIState:
    """One day of FWI System outputs.

    Parameters
    ----------
    ffmc : float
        Fine Fuel Moisture Code.
    dmc : float
        Duff Moisture Code.
    dc : float
        Drought Code.
    isi : float
        Initial Spread Index.
    bui : float
        Buildup Index.
    fwi : float
        Fire Weather Index.
    dsr : float
        Daily Severity Rating.
    """

    ffmc: float
    dmc: float
    dc: float
    isi: float
    bui: float
    fwi: float
    dsr: float

    def __post_init__(self) -> None:
        """Validate the codes."""
        ffmc = _number(self.ffmc, "ffmc")
        if ffmc < 0.0 or ffmc > 101.0:
            raise FireFuelError("ffmc must be between 0 and 101")
        for field in ("dmc", "dc", "isi", "bui", "fwi", "dsr"):
            value = _non_negative(getattr(self, field), field)
            object.__setattr__(self, field, value)
        object.__setattr__(self, "ffmc", ffmc)

    def to_dict(self) -> dict[str, float]:
        """Return the state as a JSON-serializable mapping.

        Returns
        -------
        dict
            The seven FWI codes.
        """
        return {
            "ffmc": self.ffmc,
            "dmc": self.dmc,
            "dc": self.dc,
            "isi": self.isi,
            "bui": self.bui,
            "fwi": self.fwi,
            "dsr": self.dsr,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> FWIState:
        """Validate and construct a state from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        FWIState
            The validated state.
        """
        return cls(
            ffmc=_number(payload["ffmc"], "ffmc"),
            dmc=_non_negative(payload["dmc"], "dmc"),
            dc=_non_negative(payload["dc"], "dc"),
            isi=_non_negative(payload["isi"], "isi"),
            bui=_non_negative(payload["bui"], "bui"),
            fwi=_non_negative(payload["fwi"], "fwi"),
            dsr=_non_negative(payload["dsr"], "dsr"),
        )


def initial_fwi_state(ffmc: float = 85.0, dmc: float = 6.0, dc: float = 15.0) -> FWIState:
    """Return the standard FWI starting state.

    Parameters
    ----------
    ffmc : float, optional
        Starting Fine Fuel Moisture Code (default 85).
    dmc : float, optional
        Starting Duff Moisture Code (default 6).
    dc : float, optional
        Starting Drought Code (default 15).

    Returns
    -------
    FWIState
        The initial state. The derived indices are zero until the first step.
    """
    return FWIState(ffmc=ffmc, dmc=dmc, dc=dc, isi=0.0, bui=0.0, fwi=0.0, dsr=0.0)


def fine_fuel_moisture_code(
    previous_ffmc: float,
    temperature_c: float,
    relative_humidity_percent: float,
    wind_kmh: float,
    precipitation_mm: float,
) -> float:
    """Return the next Fine Fuel Moisture Code.

    Parameters
    ----------
    previous_ffmc : float
        Yesterday's FFMC.
    temperature_c : float
        Dry-bulb temperature.
    relative_humidity_percent : float
        Relative humidity, clamped below 100 by the caller.
    wind_kmh : float
        Ten-metre wind speed.
    precipitation_mm : float
        Precipitation.

    Returns
    -------
    float
        The next FFMC.
    """
    ffmc = _number(previous_ffmc, "previous_ffmc")
    if ffmc < 0.0 or ffmc > 101.0:
        raise FireFuelError("previous_ffmc must be between 0 and 101")
    temp = _number(temperature_c, "temperature_c")
    rh = min(_number(relative_humidity_percent, "relative_humidity_percent"), 99.9999)
    wind = _non_negative(wind_kmh, "wind_kmh")
    precipitation = _non_negative(precipitation_mm, "precipitation_mm")
    wmo = FFMC_COEFFICIENT * (101.0 - ffmc) / (59.5 + ffmc)
    ra = precipitation - 0.5 if precipitation > 0.5 else precipitation
    if precipitation > 0.5:
        if wmo > 150.0:
            wmo = (
                wmo
                + 0.0015 * (wmo - 150.0) ** 2 * math.sqrt(ra)
                + 42.5 * ra * math.exp(-100.0 / (251.0 - wmo)) * (1.0 - math.exp(-6.93 / ra))
            )
        else:
            wmo = wmo + 42.5 * ra * math.exp(-100.0 / (251.0 - wmo)) * (1.0 - math.exp(-6.93 / ra))
    wmo = min(wmo, 250.0)
    ed = (
        0.942 * rh**0.679
        + 11.0 * math.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp) * (1.0 - 1.0 / math.exp(rh * 0.115))
    )
    ew = (
        0.618 * rh**0.753
        + 10.0 * math.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp) * (1.0 - 1.0 / math.exp(rh * 0.115))
    )
    z = 0.0
    if wmo < ed and wmo < ew:
        z = 0.424 * (1.0 - ((100.0 - rh) / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind) * (
            1.0 - ((100.0 - rh) / 100.0) ** 8
        )
    x = z * 0.581 * math.exp(0.0365 * temp)
    wm = ew - (ew - wmo) / (10.0**x) if wmo < ed and wmo < ew else wmo
    if wmo > ed:
        z = 0.424 * (1.0 - (rh / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind) * (
            1.0 - (rh / 100.0) ** 8
        )
        x = z * 0.581 * math.exp(0.0365 * temp)
        wm = ed + (wmo - ed) / (10.0**x)
    result = 59.5 * (250.0 - wm) / (FFMC_COEFFICIENT + wm)
    return min(101.0, max(0.0, result))


def duff_moisture_code(
    previous_dmc: float,
    temperature_c: float,
    relative_humidity_percent: float,
    precipitation_mm: float,
    latitude_deg: float,
    month: int,
    *,
    latitude_adjust: bool = True,
) -> float:
    """Return the next Duff Moisture Code.

    Parameters
    ----------
    previous_dmc : float
        Yesterday's DMC.
    temperature_c : float
        Dry-bulb temperature.
    relative_humidity_percent : float
        Relative humidity.
    precipitation_mm : float
        Precipitation.
    latitude_deg : float
        Latitude.
    month : int
        Month, 1 through 12.
    latitude_adjust : bool, optional
        Apply the standard latitude day-length adjustment (default True).

    Returns
    -------
    float
        The next DMC.
    """
    dmc = _non_negative(previous_dmc, "previous_dmc")
    temp = max(_number(temperature_c, "temperature_c"), -1.1)
    rh = _number(relative_humidity_percent, "relative_humidity_percent")
    precipitation = _non_negative(precipitation_mm, "precipitation_mm")
    latitude = _number(latitude_deg, "latitude_deg")
    month_index = _integer(month, "month") - 1
    if month_index < 0 or month_index > 11:
        raise FireFuelError("month must be between 1 and 12")
    day_length = _ELL01[month_index]
    if latitude_adjust:
        if 10.0 < latitude <= 30.0:
            day_length = _ELL02[month_index]
        elif -30.0 < latitude <= -10.0:
            day_length = _ELL03[month_index]
        elif -90.0 <= latitude <= -30.0:
            day_length = _ELL04[month_index]
        elif -10.0 <= latitude <= 10.0:
            day_length = 9.0
    rk = 1.894 * (temp + 1.1) * (100.0 - rh) * day_length * 1e-4
    if precipitation <= 1.5:
        pr = dmc
    else:
        ra = precipitation
        rw = 0.92 * ra - 1.27
        wmi = 20.0 + 280.0 / math.exp(0.023 * dmc)
        if dmc <= 33.0:
            b = 100.0 / (0.5 + 0.3 * dmc)
        elif dmc <= 65.0:
            b = 14.0 - 1.3 * math.log(dmc)
        else:
            b = 6.2 * math.log(dmc) - 17.2
        wmr = wmi + 1000.0 * rw / (48.77 + b * rw)
        pr = 43.43 * (5.6348 - math.log(wmr - 20.0))
    pr = max(pr, 0.0)
    return max(pr + rk, 0.0)


def drought_code(
    previous_dc: float,
    temperature_c: float,
    relative_humidity_percent: float,
    precipitation_mm: float,
    latitude_deg: float,
    month: int,
    *,
    latitude_adjust: bool = True,
) -> float:
    """Return the next Drought Code.

    Parameters
    ----------
    previous_dc : float
        Yesterday's DC.
    temperature_c : float
        Dry-bulb temperature.
    relative_humidity_percent : float
        Relative humidity. The DC equation uses temperature and precipitation.
    precipitation_mm : float
        Precipitation.
    latitude_deg : float
        Latitude.
    month : int
        Month, 1 through 12.
    latitude_adjust : bool, optional
        Apply the standard latitude day-length adjustment (default True).

    Returns
    -------
    float
        The next DC.
    """
    dc = _non_negative(previous_dc, "previous_dc")
    temp = max(_number(temperature_c, "temperature_c"), -2.8)
    _number(relative_humidity_percent, "relative_humidity_percent")
    precipitation = _non_negative(precipitation_mm, "precipitation_mm")
    latitude = _number(latitude_deg, "latitude_deg")
    month_index = _integer(month, "month") - 1
    if month_index < 0 or month_index > 11:
        raise FireFuelError("month must be between 1 and 12")
    day_length = _FL01[month_index]
    if latitude_adjust:
        if latitude <= -20.0:
            day_length = _FL02[month_index]
        elif -20.0 < latitude <= 20.0:
            day_length = 1.4
    pe = max((0.36 * (temp + 2.8) + day_length) / 2.0, 0.0)
    ra = precipitation
    rw = 0.83 * ra - 1.27
    smi = 800.0 * math.exp(-dc / 400.0)
    dr0 = dc - 400.0 * math.log(1.0 + 3.937 * rw / smi)
    dr = dc if precipitation <= 2.8 else max(dr0, 0.0)
    return max(dr + pe, 0.0)


def initial_spread_index(ffmc: float, wind_kmh: float, *, fbp: bool = False) -> float:
    """Return the Initial Spread Index.

    Parameters
    ----------
    ffmc : float
        Fine Fuel Moisture Code.
    wind_kmh : float
        Ten-metre wind speed.
    fbp : bool, optional
        Apply the FBP high-wind modification above 40 km/h (default False, the FWI form).

    Returns
    -------
    float
        The ISI.
    """
    code = _number(ffmc, "ffmc")
    if code < 0.0 or code > 101.0:
        raise FireFuelError("ffmc must be between 0 and 101")
    wind = _non_negative(wind_kmh, "wind_kmh")
    fm = FFMC_COEFFICIENT * (101.0 - code) / (59.5 + code)
    if fbp and wind >= 40.0:
        f_wind = 12.0 * (1.0 - math.exp(-0.0818 * (wind - 28.0)))
    else:
        f_wind = math.exp(0.05039 * wind)
    f_fuel = 91.9 * math.exp(-0.1386 * fm) * (1.0 + (fm**5.31) / 49_300_000.0)
    return float(0.208 * f_wind * f_fuel)


def buildup_index(dmc: float, dc: float) -> float:
    """Return the Buildup Index.

    Parameters
    ----------
    dmc : float
        Duff Moisture Code.
    dc : float
        Drought Code.

    Returns
    -------
    float
        The BUI.
    """
    duff = _non_negative(dmc, "dmc")
    drought = _non_negative(dc, "dc")
    if duff == 0.0 and drought == 0.0:
        return 0.0
    bui = 0.8 * drought * duff / (duff + 0.4 * drought)
    p = 0.0 if duff == 0.0 else (duff - bui) / duff
    cc = 0.92 + ((0.0114 * duff) ** 1.7)
    bui0 = max(duff - cc * p, 0.0)
    return bui0 if bui < duff else bui


def fire_weather_index(isi: float, bui: float) -> float:
    """Return the Fire Weather Index.

    Parameters
    ----------
    isi : float
        Initial Spread Index.
    bui : float
        Buildup Index.

    Returns
    -------
    float
        The FWI.
    """
    spread = _non_negative(isi, "isi")
    buildup = _non_negative(bui, "bui")
    if buildup > 80.0:
        bb = 0.1 * spread * (1000.0 / (25.0 + 108.64 / math.exp(0.023 * buildup)))
    else:
        bb = 0.1 * spread * (0.626 * buildup**0.809 + 2.0)
    if bb <= 1.0:
        return bb
    return math.exp(2.72 * ((0.434 * math.log(bb)) ** 0.647))


class FWIEngine:
    """Advance the FWI System one day at a time.

    Parameters
    ----------
    state : FWIState
        The starting FFMC/DMC/DC state.
    latitude_adjust : bool, optional
        Apply the standard latitude day-length adjustment (default True).
    """

    def __init__(self, state: FWIState, *, latitude_adjust: bool = True) -> None:
        """Retain the initial state and adjustment flag."""
        if not isinstance(state, FWIState):
            raise FireFuelError("state must be an FWIState")
        self.state = state
        self.latitude_adjust = latitude_adjust

    def step(self, weather: DailyWeather) -> FWIState:
        """Advance one day.

        Parameters
        ----------
        weather : DailyWeather
            The day's weather.

        Returns
        -------
        FWIState
            The new FWI state.
        """
        if not isinstance(weather, DailyWeather):
            raise FireFuelError("weather must be a DailyWeather")
        rh = min(weather.relative_humidity_percent, 99.9999)
        ffmc = fine_fuel_moisture_code(
            self.state.ffmc,
            weather.temperature_c,
            rh,
            weather.wind_kmh,
            weather.precipitation_mm,
        )
        dmc = duff_moisture_code(
            self.state.dmc,
            weather.temperature_c,
            rh,
            weather.precipitation_mm,
            weather.latitude_deg,
            weather.month,
            latitude_adjust=self.latitude_adjust,
        )
        dc = drought_code(
            self.state.dc,
            weather.temperature_c,
            rh,
            weather.precipitation_mm,
            weather.latitude_deg,
            weather.month,
            latitude_adjust=self.latitude_adjust,
        )
        isi = initial_spread_index(ffmc, weather.wind_kmh, fbp=False)
        bui = buildup_index(dmc, dc)
        fwi = fire_weather_index(isi, bui)
        state = FWIState(
            ffmc=ffmc,
            dmc=dmc,
            dc=dc,
            isi=isi,
            bui=bui,
            fwi=fwi,
            dsr=0.0272 * fwi**1.77,
        )
        self.state = state
        return state

    def run(self, weather: Sequence[DailyWeather]) -> tuple[FWIState, ...]:
        """Advance over a daily weather sequence.

        Parameters
        ----------
        weather : sequence of DailyWeather
            The daily weather, in chronological order.

        Returns
        -------
        tuple of FWIState
            One state per day.
        """
        return tuple(self.step(day) for day in weather)


def fwi_sequence(
    weather: Sequence[DailyWeather],
    initial: FWIState | None = None,
    *,
    latitude_adjust: bool = True,
) -> tuple[FWIState, ...]:
    """Run the FWI System over a daily weather sequence.

    Parameters
    ----------
    weather : sequence of DailyWeather
        The daily weather.
    initial : FWIState or None, optional
        The starting state. None uses the standard FFMC 85, DMC 6, DC 15.
    latitude_adjust : bool, optional
        Apply the standard latitude day-length adjustment (default True).

    Returns
    -------
    tuple of FWIState
        One state per day.
    """
    state = initial_fwi_state() if initial is None else initial
    return FWIEngine(state, latitude_adjust=latitude_adjust).run(weather)
