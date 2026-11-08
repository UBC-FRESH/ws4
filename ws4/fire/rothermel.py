"""The Rothermel surface-fire kernel.

This is an original Python implementation of the Rothermel (1972) surface-fire spread model
with the standard corrections used by modern implementations. The input units are metric and
explicit; the calculation follows the model's internal imperial formulation and converts the
results back to metric. The standard Anderson fuel models and Scott-Burgan moisture scenarios
are the validation set.

The kernel answers one question: under this fuel, moisture, wind, and slope, how fast does the
head fire spread and how much heat does it release? It does not grow a perimeter; that is the
growth engine's job.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .environment import FireEnvironment
from .fuel import FireFuelError, FuelModel, FuelMoisture

KERNEL_VERSION: Final[str] = "rothermel-1972-v1"
DEFAULT_HEAT_YIELD_KJ_KG: Final[float] = 18_000.0
DEFAULT_CONSUMPTION_FRACTION: Final[float] = 0.8


def _exp_decay(rate: float, sav: float) -> float:
    """Return ``exp(-rate / sav)``, treating a zero SAV as an absent class."""
    return 0.0 if sav <= 0.0 else math.exp(-rate / sav)


@dataclass(frozen=True)
class RothermelResult:
    """The surface-fire result for one fuel, moisture, and environment.

    Attributes
    ----------
    fuel_model : str
        The fuel model name.
    kernel_version : str
        The kernel implementation identifier.
    rate_of_spread_m_min : float
        Head fire rate of spread in metres per minute.
    reaction_intensity_kw_m2 : float
        Total reaction intensity in kilowatts per square metre.
    reaction_intensity_dead_kw_m2 : float
        Dead-fuel reaction intensity.
    reaction_intensity_live_kw_m2 : float
        Live-fuel reaction intensity.
    wind_factor : float
        The Rothermel wind coefficient.
    slope_factor : float
        The Rothermel slope coefficient.
    heat_source_kw_m2 : float
        The heat source term.
    heat_sink_kj_m3 : float
        The heat sink term.
    packing_ratio : float
        The fuel-bed packing ratio.
    relative_packing_ratio : float
        Packing ratio divided by the optimum.
    characteristic_sav_m2_m3 : float
        The characteristic surface-to-volume ratio.
    bulk_density_kg_m3 : float
        The fuel-bed bulk density.
    characteristic_dead_moisture_percent : float
        The characteristic dead-fuel moisture.
    characteristic_live_moisture_percent : float
        The characteristic live-fuel moisture.
    live_moisture_of_extinction_percent : float
        The live-fuel moisture of extinction.
    fuel_consumed_kg_m2 : float
        The fuel consumed in the flaming zone.
    head_fire_intensity_kw_m : float
        Byram head fire intensity.
    flame_length_m : float
        Byram flame length.
    residence_time_s : float
        The estimated flaming residence time.
    """

    fuel_model: str
    kernel_version: str
    rate_of_spread_m_min: float
    reaction_intensity_kw_m2: float
    reaction_intensity_dead_kw_m2: float
    reaction_intensity_live_kw_m2: float
    wind_factor: float
    slope_factor: float
    heat_source_kw_m2: float
    heat_sink_kj_m3: float
    packing_ratio: float
    relative_packing_ratio: float
    characteristic_sav_m2_m3: float
    bulk_density_kg_m3: float
    characteristic_dead_moisture_percent: float
    characteristic_live_moisture_percent: float
    live_moisture_of_extinction_percent: float
    fuel_consumed_kg_m2: float
    head_fire_intensity_kw_m: float
    flame_length_m: float
    residence_time_s: float

    def to_dict(self) -> dict[str, object]:
        """Return the result as a JSON-serializable mapping.

        Returns
        -------
        dict
            The result fields and units.
        """
        return {
            "fuel_model": self.fuel_model,
            "kernel_version": self.kernel_version,
            "rate_of_spread_m_min": self.rate_of_spread_m_min,
            "reaction_intensity_kw_m2": self.reaction_intensity_kw_m2,
            "reaction_intensity_dead_kw_m2": self.reaction_intensity_dead_kw_m2,
            "reaction_intensity_live_kw_m2": self.reaction_intensity_live_kw_m2,
            "wind_factor": self.wind_factor,
            "slope_factor": self.slope_factor,
            "heat_source_kw_m2": self.heat_source_kw_m2,
            "heat_sink_kj_m3": self.heat_sink_kj_m3,
            "packing_ratio": self.packing_ratio,
            "relative_packing_ratio": self.relative_packing_ratio,
            "characteristic_sav_m2_m3": self.characteristic_sav_m2_m3,
            "bulk_density_kg_m3": self.bulk_density_kg_m3,
            "characteristic_dead_moisture_percent": self.characteristic_dead_moisture_percent,
            "characteristic_live_moisture_percent": self.characteristic_live_moisture_percent,
            "live_moisture_of_extinction_percent": self.live_moisture_of_extinction_percent,
            "fuel_consumed_kg_m2": self.fuel_consumed_kg_m2,
            "head_fire_intensity_kw_m": self.head_fire_intensity_kw_m,
            "flame_length_m": self.flame_length_m,
            "residence_time_s": self.residence_time_s,
            "units": {
                "rate_of_spread": "m/min",
                "reaction_intensity": "kW/m2",
                "head_fire_intensity": "kW/m",
                "flame_length": "m",
                "fuel_consumed": "kg/m2",
                "residence_time": "s",
            },
        }


def surface_fire(
    fuel: FuelModel,
    moisture: FuelMoisture,
    environment: FireEnvironment,
    *,
    heat_yield_kj_kg: float = DEFAULT_HEAT_YIELD_KJ_KG,
    consumption_fraction: float = DEFAULT_CONSUMPTION_FRACTION,
) -> RothermelResult:
    """Compute the Rothermel surface-fire result.

    Parameters
    ----------
    fuel : FuelModel
        The surface fuel model.
    moisture : FuelMoisture
        The five fuel-class moisture values.
    environment : FireEnvironment
        Midflame wind and slope.
    heat_yield_kj_kg : float, optional
        Heat yield for the Byram intensity (default 18000 kJ/kg).
    consumption_fraction : float, optional
        The fraction of the total fuel load consumed in the flaming zone
        (default 0.8).

    Returns
    -------
    RothermelResult
        Rate of spread, reaction intensity, intensity, flame length, and provenance.

    Raises
    ------
    FireFuelError
        If the inputs are not finite or the fuel bed has no load.
    """
    if not isinstance(fuel, FuelModel):
        raise FireFuelError("fuel must be a FuelModel")
    if not isinstance(moisture, FuelMoisture):
        raise FireFuelError("moisture must be a FuelMoisture")
    if not isinstance(environment, FireEnvironment):
        raise FireFuelError("environment must be a FireEnvironment")
    if not math.isfinite(heat_yield_kj_kg) or heat_yield_kj_kg <= 0.0:
        raise FireFuelError("heat_yield_kj_kg must be positive")
    if not 0.0 <= consumption_fraction <= 1.0:
        raise FireFuelError("consumption_fraction must be between 0 and 1")

    # Convert the metric contract to the model's imperial formulation.
    w = [load * 0.02048 for load in fuel.loads_t_ha]
    s = [sav / 3.281 for sav in fuel.sav_m2_m3]
    h = [heat * 0.429922614 for heat in fuel.heat_kj_kg]
    m = [value / 100.0 for value in moisture.as_tuple()]
    delta = fuel.depth_cm * 0.0328084
    mx_dead = fuel.moisture_of_extinction_percent / 100.0
    u = environment.wind_kmh * 54.6806649
    slope = environment.slope_percent / 100.0

    if fuel.model_type == "D":
        kt = (1.2 - m[3]) / 0.9 if 0.3 <= m[3] < 1.2 else 0.0
        f1 = w[0] * s[0] / 32.0
        f4 = (w[3] * kt) * s[3] / 32.0
        denominator = f1 + f4
        if denominator > 0.0:
            s[0] = (f1 * s[0] + f4 * s[3]) / denominator
        w[0] += w[3] * kt
        w[3] -= w[3] * kt

    rhop = 32.0
    st = 0.0555
    se = 0.01
    a = [s[index] * w[index] / rhop for index in range(5)]
    a_dead = a[0] + a[1] + a[2]
    a_live = a[3] + a[4]
    a_tot = a_dead + a_live
    if a_tot <= 0.0 or delta <= 0.0:
        raise FireFuelError("fuel bed has no combustible load")
    f = [
        a[0] / a_dead if a_dead > 0.0 else 0.0,
        a[1] / a_dead if a_dead > 0.0 else 0.0,
        a[2] / a_dead if a_dead > 0.0 else 0.0,
        a[3] / a_live if a_live > 0.0 else 0.0,
        a[4] / a_live if a_live > 0.0 else 0.0,
    ]
    f_dead = a_dead / a_tot
    f_live = a_live / a_tot
    wn = [value * (1.0 - st) for value in w]
    wn_dead = f[0] * wn[0] + f[1] * wn[1] + f[2] * wn[2]
    wn_live = wn[3] + wn[4]
    mf_dead = f[0] * m[0] + f[1] * m[1] + f[2] * m[2]
    mf_live = f[3] * m[3] + f[4] * m[4]
    sigma_dead = f[0] * s[0] + f[1] * s[1] + f[2] * s[2]
    sigma_live = f[3] * s[3] + f[4] * s[4]
    sigma_tot = f_dead * sigma_dead + f_live * sigma_live
    h_dead = f[0] * h[0] + f[1] * h[1] + f[2] * h[2]
    h_live = f[3] * h[3] + f[4] * h[4]
    beta = (sum(w) / rhop) / delta
    e138 = [_exp_decay(138.0, value) for value in s]
    e500 = [_exp_decay(500.0, value) for value in s]
    numerator = w[0] * e138[0] + w[1] * e138[1] + w[2] * e138[2]
    denominator = w[3] * e500[3] + w[4] * e500[4]
    live_dead_ratio = (
        numerator / denominator if denominator > 0.0 else (math.inf if numerator > 0.0 else 0.0)
    )
    mfpd_denominator = w[0] * e138[0] + w[1] * e138[1] + w[2] * e138[2]
    if mfpd_denominator > 0.0:
        mfpd = (
            w[0] * m[0] * e138[0] + w[1] * m[1] * e138[1] + w[2] * m[2] * e138[2]
        ) / mfpd_denominator
    else:
        mfpd = 0.0
    mx_live = (
        2.9 * live_dead_ratio * (1.0 - mfpd / mx_dead) - 0.226
        if math.isfinite(live_dead_ratio)
        else mx_dead
    )
    if not math.isfinite(mx_live) or mx_live < mx_dead:
        mx_live = mx_dead
    ns = 0.174 * se**-0.19
    ratio_dead = mf_dead / mx_dead
    ratio_live = mf_live / mx_live if mx_live > 0.0 else 0.0
    nm_dead = (
        0.0
        if ratio_dead > 1.0
        else 1.0 - 2.59 * ratio_dead + 5.11 * ratio_dead**2 - 3.52 * ratio_dead**3
    )
    nm_live = (
        0.0
        if ratio_live > 1.0
        else 1.0 - 2.59 * ratio_live + 5.11 * ratio_live**2 - 3.52 * ratio_live**3
    )
    beta_op = 3.348 * sigma_tot**-0.8189
    rpr = beta / beta_op
    gamma_max = sigma_tot**1.5 / (495.0 + 0.0594 * sigma_tot**1.5)
    sum_dead = wn_dead * h_dead * nm_dead * ns
    sum_live = wn_live * h_live * nm_live * ns
    a_coefficient = 133.0 * sigma_tot**-0.7913
    ir_dead = gamma_max * (rpr * math.exp(1.0 - rpr)) ** a_coefficient * sum_dead
    ir_live = gamma_max * (rpr * math.exp(1.0 - rpr)) ** a_coefficient * sum_live
    ir = ir_dead + ir_live
    xi = (192.0 + 0.2595 * sigma_tot) ** -1 * math.exp(
        (0.792 + 0.681 * math.sqrt(sigma_tot)) * (beta + 0.1)
    )
    c_coefficient = 7.47 * math.exp(-0.133 * sigma_tot**0.55)
    b_coefficient = 0.02526 * sigma_tot**0.54
    e_coefficient = 0.715 * math.exp(-3.59e-4 * sigma_tot)
    fw = c_coefficient * u**b_coefficient * rpr ** (-e_coefficient) if u > 0.0 else 0.0
    fs = 5.275 * beta**-0.3 * slope**2
    rhob = sum(w) / delta
    qig = [
        250.0 + 1116.0 * value if weight > 0.0 else 0.0 for value, weight in zip(m, w, strict=True)
    ]
    eps = f_dead * (
        f[0] * qig[0] * e138[0] + f[1] * qig[1] * e138[1] + f[2] * qig[2] * e138[2]
    ) + f_live * (f[3] * qig[3] * e138[3] + f[4] * qig[4] * e138[4])
    denominator = rhob * eps
    if denominator <= 0.0:
        raise FireFuelError("fuel bed has no heat sink")
    ros_ft_min = ir * xi * (1.0 + fw + fs) / denominator
    ros_m_min = 0.3048 * ros_ft_min
    total_load_kg_m2 = sum(fuel.loads_t_ha) * 0.1
    fuel_consumed = max(0.0, total_load_kg_m2 * consumption_fraction)
    intensity = heat_yield_kj_kg * fuel_consumed * (ros_m_min / 60.0)
    flame_length = 0.0 if intensity <= 0.0 else 0.0775 * intensity**0.46
    residence_time = 0.0 if sigma_tot <= 0.0 else 384.0 * 60.0 / sigma_tot
    return RothermelResult(
        fuel_model=fuel.name,
        kernel_version=KERNEL_VERSION,
        rate_of_spread_m_min=ros_m_min,
        reaction_intensity_kw_m2=ir * 0.1893,
        reaction_intensity_dead_kw_m2=ir_dead * 0.1893,
        reaction_intensity_live_kw_m2=ir_live * 0.1893,
        wind_factor=fw,
        slope_factor=fs,
        heat_source_kw_m2=ir * xi * (1.0 + fw + fs) * 0.1893,
        heat_sink_kj_m3=rhob * eps * 37.25894580781,
        packing_ratio=beta,
        relative_packing_ratio=rpr,
        characteristic_sav_m2_m3=sigma_tot * 3.281,
        bulk_density_kg_m3=rhob * 16.0184634,
        characteristic_dead_moisture_percent=mf_dead * 100.0,
        characteristic_live_moisture_percent=mf_live * 100.0,
        live_moisture_of_extinction_percent=mx_live * 100.0,
        fuel_consumed_kg_m2=fuel_consumed,
        head_fire_intensity_kw_m=intensity,
        flame_length_m=flame_length,
        residence_time_s=residence_time,
    )
