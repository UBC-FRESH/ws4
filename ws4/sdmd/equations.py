"""Stand density equations re-implemented in Python.

This module is an independent Python implementation of the calculation logic in the
BC Government SDMD Shiny application (``bcgov/SDMD``, Apache-2.0) and the
``standview`` R package by M.W. Ritchie (USFS). It does not call, wrap, vendor, or
translate R code at runtime. The equation forms and coefficients come from the
published sources cited on each function; the unit handling follows the BC app so
the numbers reproduce it.

The BC app selects one of several published equation sets. Five are implemented
here because they are the ones with a complete volume and top-height calculation:
Long and Shaw (2005), Jang, Ritchie, and Zhang (2021), Long and Shaw (2012),
Drew and Flewelling (1979), and McCarter and Long (1986). The general
static/dynamic/structural framing follows the review by Weiskittel and colleagues
(2021, :doi:`10.1139/cjfr-2020-0289`).

Metric inputs are the public API. Internally the functions convert to the English
units in which the published coefficients were fitted, calculate, and convert back.
This is the same path the BC app uses, which makes the two implementations
comparable.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

SDMD_EQUATION_SCHEMA_VERSION = "ws4.sdmd.equations.v1"

ACRE_TO_HA = 0.404686
INCH_TO_CM = 2.54
FOOT_TO_M = 0.3048
FT3_PER_ACRE_TO_M3_PER_HA = 14.2913
TON_PER_ACRE_TO_MG_PER_HA = 2.2417
REINEKE_EXPONENT = 1.605
REINEKE_REFERENCE_CM = 25.4


class SdmdEquationError(ValueError):
    """Raised when an equation is unsupported or its inputs are invalid."""


@dataclass(frozen=True)
class EquationSpec:
    """One published equation set.

    Attributes
    ----------
    equation_id : int
        Identifier used by the BC app.
    label : str
        Short species and publication label.
    reference : str
        The publication the coefficients come from.
    default_max_sdi : float or None
        The BC app's default maximum SDI in metric units. ``None`` when maximum SDI
        is not part of the equation.
    max_sdi_range : tuple of float or None
        The BC app's accepted maximum-SDI range in metric units, when it has one.
    has_volume : bool
        Whether the set defines a volume equation.
    has_top_height : bool
        Whether the set defines a top-height equation.
    has_crown_cover : bool
        Whether the set defines a crown-cover equation.
    has_biomass : bool
        Whether the set defines a biomass equation.
    """

    equation_id: int
    label: str
    reference: str
    default_max_sdi: float | None
    max_sdi_range: tuple[float, float] | None
    has_volume: bool
    has_top_height: bool
    has_crown_cover: bool
    has_biomass: bool


EQUATIONS: tuple[EquationSpec, ...] = (
    EquationSpec(
        equation_id=2,
        label="Long and Shaw (2005) ponderosa pine",
        reference="Long, J.N. and Shaw, J.D. 2005. A density management diagram for "
        "even-aged ponderosa pine stands. Western Journal of Applied Forestry 20(4): 205-215.",
        default_max_sdi=1112.0,
        max_sdi_range=None,
        has_volume=True,
        has_top_height=False,
        has_crown_cover=False,
        has_biomass=False,
    ),
    EquationSpec(
        equation_id=3,
        label="Jang, Ritchie, and Zhang (2021) ponderosa pine",
        reference="Jang, W., Ritchie, M.W., and Zhang, J. 2021. Improved equations for "
        "the density management diagram isolines of ponderosa pine stands. Forest Science "
        "67(1): 93-102.",
        default_max_sdi=988.0,
        max_sdi_range=None,
        has_volume=True,
        has_top_height=True,
        has_crown_cover=True,
        has_biomass=True,
    ),
    EquationSpec(
        equation_id=6,
        label="Long and Shaw (2012) Sierra Nevada mixed-conifer",
        reference="Long, J.N. and Shaw, J.D. 2012. A density management diagram for "
        "even-aged Sierra Nevada mixed-conifer stands. Western Journal of Applied Forestry "
        "27(4): 187-195.",
        default_max_sdi=1359.0,
        max_sdi_range=(1112.0, 1482.0),
        has_volume=True,
        has_top_height=True,
        has_crown_cover=False,
        has_biomass=False,
    ),
    EquationSpec(
        equation_id=7,
        label="Drew and Flewelling (1979) Douglas-fir",
        reference="Drew, T.J. and Flewelling, J.W. 1979. Stand density management: an "
        "alternative approach and its application to Douglas-fir plantations. Forest "
        "Science 25(3): 518-532.",
        default_max_sdi=1482.0,
        max_sdi_range=None,
        has_volume=True,
        has_top_height=True,
        has_crown_cover=False,
        has_biomass=False,
    ),
    EquationSpec(
        equation_id=9,
        label="McCarter and Long (1986) lodgepole pine",
        reference="McCarter, J.B. and Long, J.N. 1986. A lodgepole pine density "
        "management diagram. Western Journal of Applied Forestry 1: 6-11.",
        default_max_sdi=1729.0,
        max_sdi_range=None,
        has_volume=True,
        has_top_height=True,
        has_crown_cover=False,
        has_biomass=False,
    ),
)

EQUATIONS_BY_ID: dict[int, EquationSpec] = {item.equation_id: item for item in EQUATIONS}

SUPPORTED_EQUATIONS: tuple[int, ...] = tuple(item.equation_id for item in EQUATIONS)


def equation_spec(equation_id: int) -> EquationSpec:
    """Return the equation set for an identifier.

    Parameters
    ----------
    equation_id : int
        The BC app's equation identifier.

    Returns
    -------
    EquationSpec
        The equation metadata.

    Raises
    ------
    SdmdEquationError
        When the identifier is not one of the implemented sets.
    """
    try:
        return EQUATIONS_BY_ID[equation_id]
    except KeyError:
        supported = ", ".join(str(item) for item in SUPPORTED_EQUATIONS)
        raise SdmdEquationError(
            f"unsupported equation {equation_id}; supported equations: {supported}"
        ) from None


def basal_area_m2_ha(tph: float, qmd_cm: float) -> float:
    """Return basal area from density and quadratic mean diameter.

    Parameters
    ----------
    tph : float
        Trees per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.

    Returns
    -------
    float
        Basal area in square metres per hectare.

    Raises
    ------
    SdmdEquationError
        When a value is not positive.
    """
    _require_positive(tph, "tph")
    _require_positive(qmd_cm, "qmd_cm")
    return tph * math.pi * (qmd_cm / 100.0) ** 2 / 4.0


def quadratic_mean_diameter_cm(ba_m2_ha: float, tph: float) -> float:
    """Return quadratic mean diameter from basal area and density.

    Parameters
    ----------
    ba_m2_ha : float
        Basal area in square metres per hectare.
    tph : float
        Trees per hectare.

    Returns
    -------
    float
        Quadratic mean diameter in centimetres.

    Raises
    ------
    SdmdEquationError
        When a value is not positive.
    """
    _require_positive(ba_m2_ha, "ba_m2_ha")
    _require_positive(tph, "tph")
    return 100.0 * math.sqrt(4.0 * ba_m2_ha / (math.pi * tph))


def trees_per_hectare(ba_m2_ha: float, qmd_cm: float) -> float:
    """Return density from basal area and quadratic mean diameter.

    Parameters
    ----------
    ba_m2_ha : float
        Basal area in square metres per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.

    Returns
    -------
    float
        Trees per hectare.

    Raises
    ------
    SdmdEquationError
        When a value is not positive.
    """
    _require_positive(ba_m2_ha, "ba_m2_ha")
    _require_positive(qmd_cm, "qmd_cm")
    return 4.0 * ba_m2_ha / (math.pi * (qmd_cm / 100.0) ** 2)


def stand_density_index(
    tph: float,
    qmd_cm: float,
    *,
    reference_cm: float = REINEKE_REFERENCE_CM,
    exponent: float = REINEKE_EXPONENT,
) -> float:
    """Return Reineke's stand density index.

    Parameters
    ----------
    tph : float
        Trees per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.
    reference_cm : float
        Reference diameter. Defaults to 25.4 cm, the 10-inch reference used by the BC
        app. Use 25.0 for the common metric convention.
    exponent : float
        Reineke's exponent. Defaults to 1.605.

    Returns
    -------
    float
        Stand density index in the reference-diameter convention.

    Raises
    ------
    SdmdEquationError
        When a value is not positive.
    """
    _require_positive(tph, "tph")
    _require_positive(qmd_cm, "qmd_cm")
    _require_positive(reference_cm, "reference_cm")
    _require_positive(exponent, "exponent")
    result: float = tph * (qmd_cm / reference_cm) ** exponent
    return result


def relative_density(tph: float, qmd_cm: float, max_sdi: float) -> float:
    """Return density as a fraction of the maximum stand density index.

    Parameters
    ----------
    tph : float
        Trees per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.
    max_sdi : float
        Maximum stand density index for the species and site.

    Returns
    -------
    float
        Relative density, where 1.0 is the self-thinning limit.

    Raises
    ------
    SdmdEquationError
        When a value is not positive.
    """
    _require_positive(max_sdi, "max_sdi")
    return stand_density_index(tph, qmd_cm) / max_sdi


def self_thinning_qmd_cm(
    tph: float,
    max_sdi: float,
    *,
    reference_cm: float = REINEKE_REFERENCE_CM,
    exponent: float = REINEKE_EXPONENT,
) -> float:
    """Return the quadratic mean diameter at the self-thinning limit.

    Parameters
    ----------
    tph : float
        Trees per hectare.
    max_sdi : float
        Maximum stand density index.
    reference_cm : float
        Reference diameter. Defaults to 25.4 cm.
    exponent : float
        Reineke's exponent. Defaults to 1.605.

    Returns
    -------
    float
        Quadratic mean diameter in centimetres where relative density is one.

    Raises
    ------
    SdmdEquationError
        When a value is not positive.
    """
    _require_positive(tph, "tph")
    _require_positive(max_sdi, "max_sdi")
    _require_positive(reference_cm, "reference_cm")
    _require_positive(exponent, "exponent")
    result: float = reference_cm * (max_sdi / tph) ** (1.0 / exponent)
    return result


def volume_m3_ha(
    equation_id: int,
    tph: float,
    qmd_cm: float,
    *,
    max_sdi: float | None = None,
) -> float:
    """Return total stem volume.

    Parameters
    ----------
    equation_id : int
        Equation set identifier. Must be one of :data:`SUPPORTED_EQUATIONS`.
    tph : float
        Trees per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.
    max_sdi : float, optional
        Maximum stand density index. Required by equation 7 and available as a default
        for the others.

    Returns
    -------
    float
        Total volume in cubic metres per hectare.

    Raises
    ------
    SdmdEquationError
        When the equation is unsupported, a value is not positive, or equation 7 is
        called without a maximum SDI.
    """
    spec = equation_spec(equation_id)
    if not spec.has_volume:
        raise SdmdEquationError(f"equation {equation_id} has no volume equation")
    _require_positive(tph, "tph")
    _require_positive(qmd_cm, "qmd_cm")
    if spec.max_sdi_range is not None:
        _maximum_sdi(equation_id, max_sdi)
    tpae = tph * ACRE_TO_HA
    qmde = qmd_cm / INCH_TO_CM
    if equation_id == 2:
        volume_ft3 = -152.0 + 0.017 * tpae * qmde**2.8
    elif equation_id == 3:
        volume_ft3 = (tpae**1.035384) * math.exp(
            -4.741209 + 3.060285 * math.log(qmde) - 2.319617 / math.sqrt(tpae)
        )
    elif equation_id == 6:
        volume_ft3 = 0.007 * (tpae**1.146) * (qmde**2.808)
    elif equation_id == 7:
        maximum = _maximum_sdi(equation_id, max_sdi) * ACRE_TO_HA
        rd = tpae * ((qmde / 10.0) ** 1.6) / maximum
        volume_ft3 = (1.0 / 68.682) * (
            6.8084 + (qmde * (1.0 - 0.32375 * rd**0.44709) ** -1.0) ** (1.0 / 0.36716)
        )
        volume_ft3 *= tpae
    else:
        volume_ft3 = (tpae / 54.4) * (
            ((qmde / (1.0 - 0.00759 * tpae**0.446)) ** (1.0 / 0.361)) - 5.14
        )
    result: float = max(volume_ft3, 0.0) / FT3_PER_ACRE_TO_M3_PER_HA
    return result


_volume_m3_ha = volume_m3_ha


def top_height_m(
    equation_id: int,
    tph: float,
    qmd_cm: float,
    *,
    max_sdi: float | None = None,
    volume_m3_ha: float | None = None,
) -> float:
    """Return top height.

    Parameters
    ----------
    equation_id : int
        Equation set identifier.
    tph : float
        Trees per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.
    max_sdi : float, optional
        Maximum stand density index, used by equation 7 when volume is not supplied.
    volume_m3_ha : float, optional
        Total volume. Equation 7 needs it; the function calculates it when omitted.

    Returns
    -------
    float
        Top height in metres.

    Raises
    ------
    SdmdEquationError
        When the equation is unsupported, a value is not positive, or the height is
        undefined for the inputs.
    """
    spec = equation_spec(equation_id)
    if not spec.has_top_height:
        raise SdmdEquationError(f"equation {equation_id} has no top-height equation")
    _require_positive(tph, "tph")
    _require_positive(qmd_cm, "qmd_cm")
    tpae = tph * ACRE_TO_HA
    qmde = qmd_cm / INCH_TO_CM
    if equation_id == 3:
        height_ft = (
            4.5
            + (314.29288264 + 17.46283433 * math.sqrt(tpae))
            * (1.0 - math.exp((-0.02719311 + 0.02898155 / math.sqrt(tpae)) * qmde)) ** 1.50607209
        )
    elif equation_id == 6:
        if qmde < 1.2:
            raise SdmdEquationError("equation 6 top height is undefined below a 1.2-inch QMD")
        height_ft = ((-1.143 + qmde) / (0.679 * tpae**-0.254)) ** 1.062
    elif equation_id == 7:
        volume = (
            volume_m3_ha
            if volume_m3_ha is not None
            else _volume_m3_ha(equation_id, tph, qmd_cm, max_sdi=max_sdi)
        )
        volume_ft3 = volume * FT3_PER_ACRE_TO_M3_PER_HA
        height_ft = ((volume_ft3 / tpae) / (0.008695 + 0.0007764 * qmde**2.1987)) ** (1.0 / 1.10319)
    else:
        mess1 = (1.0 / 54.4) * (((qmde / (1.0 - 0.00759 * tpae**0.446)) ** (1.0 / 0.361)) - 5.14)
        mess2 = 0.00396 + 0.000779 * qmde**2.27
        height_ft = (1.0 / 1.27) * (mess1 ** (1.0 / 0.916) / mess2) ** (1.0 / 1.09)
    if not math.isfinite(height_ft):
        raise SdmdEquationError(
            f"top height is undefined for equation {equation_id} at tph={tph}, qmd_cm={qmd_cm}"
        )
    result: float = height_ft * FOOT_TO_M
    return result


def crown_cover_pct(equation_id: int, tph: float, qmd_cm: float) -> float:
    """Return crown cover percentage.

    Parameters
    ----------
    equation_id : int
        Equation set identifier. Only equation 3 defines crown cover.
    tph : float
        Trees per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.

    Returns
    -------
    float
        Crown cover in percent, clipped to ``[0, 100]``.

    Raises
    ------
    SdmdEquationError
        When the equation has no crown-cover equation or a value is not positive.
    """
    spec = equation_spec(equation_id)
    if not spec.has_crown_cover:
        raise SdmdEquationError(f"equation {equation_id} has no crown-cover equation")
    _require_positive(tph, "tph")
    _require_positive(qmd_cm, "qmd_cm")
    tpae = tph * ACRE_TO_HA
    qmde = qmd_cm / INCH_TO_CM
    cover = 100.0 * (1.0 - math.exp(-0.0002236136 * (qmde**1.2746535623) * (tpae**0.9308677542)))
    return min(max(cover, 0.0), 100.0)


def biomass_mg_ha(equation_id: int, tph: float, qmd_cm: float) -> float:
    """Return above-ground biomass.

    Parameters
    ----------
    equation_id : int
        Equation set identifier. Only equation 3 defines biomass.
    tph : float
        Trees per hectare.
    qmd_cm : float
        Quadratic mean diameter in centimetres.

    Returns
    -------
    float
        Biomass in megagrams per hectare.

    Raises
    ------
    SdmdEquationError
        When the equation has no biomass equation or a value is not positive.
    """
    spec = equation_spec(equation_id)
    if not spec.has_biomass:
        raise SdmdEquationError(f"equation {equation_id} has no biomass equation")
    _require_positive(tph, "tph")
    _require_positive(qmd_cm, "qmd_cm")
    tpae = tph * ACRE_TO_HA
    qmde = qmd_cm / INCH_TO_CM
    tons_per_acre = (tpae**0.9936280) * math.exp(
        -7.2543293 + 2.4742879 * math.log(qmde) - 0.2006977 / math.sqrt(tpae)
    )
    result: float = tons_per_acre * TON_PER_ACRE_TO_MG_PER_HA
    return result


def volume_isoline(
    equation_id: int,
    target_m3_ha: float,
    tph_values: Sequence[float],
    *,
    max_sdi: float | None = None,
    qmd_bounds: tuple[float, float] = (1.0, 200.0),
) -> tuple[tuple[float, float], ...]:
    """Invert a volume equation into a density-diameter isoline.

    The volume equations increase monotonically with QMD at fixed density, so a
    bisection on QMD is stable. A density whose reachable volume never crosses the
    target is omitted.

    Parameters
    ----------
    equation_id : int
        Equation set identifier.
    target_m3_ha : float
        The volume isoline in cubic metres per hectare.
    tph_values : sequence of float
        Densities at which to solve.
    max_sdi : float, optional
        Maximum stand density index, used by equation 7.
    qmd_bounds : tuple of float
        Lower and upper QMD bounds for the search, in centimetres.

    Returns
    -------
    tuple of tuple of float
        ``(tph, qmd_cm)`` points, in input order. The list is empty when no density
        reaches the target.

    Raises
    ------
    SdmdEquationError
        When the target, a density, or a bound is not positive.
    """
    _require_positive(target_m3_ha, "target_m3_ha")
    low, high = qmd_bounds
    _require_positive(low, "qmd_bounds[0]")
    _require_positive(high, "qmd_bounds[1]")
    if high <= low:
        raise SdmdEquationError("qmd_bounds must increase")
    points: list[tuple[float, float]] = []
    for tph in tph_values:
        _require_positive(tph, "tph")
        low_value = volume_m3_ha(equation_id, tph, low, max_sdi=max_sdi) - target_m3_ha
        high_value = volume_m3_ha(equation_id, tph, high, max_sdi=max_sdi) - target_m3_ha
        if low_value == 0.0:
            points.append((tph, low))
            continue
        if low_value * high_value > 0.0:
            continue
        left, right = low, high
        for _ in range(80):
            middle = (left + right) / 2.0
            value = volume_m3_ha(equation_id, tph, middle, max_sdi=max_sdi) - target_m3_ha
            if value == 0.0:
                break
            if value * low_value < 0.0:
                right = middle
            else:
                left = middle
        points.append((tph, (left + right) / 2.0))
    return tuple(points)


def _maximum_sdi(equation_id: int, max_sdi: float | None) -> float:
    """Return the validated maximum SDI for an equation.

    Parameters
    ----------
    equation_id : int
        Equation set identifier.
    max_sdi : float or None
        A caller-supplied maximum, or ``None`` to use the BC app default.

    Returns
    -------
    float
        The maximum SDI in the 25.4 cm reference convention.

    Raises
    ------
    SdmdEquationError
        When the equation has no default and none is supplied, or the value is
        outside the equation's accepted range.
    """
    spec = equation_spec(equation_id)
    value = spec.default_max_sdi if max_sdi is None else max_sdi
    if value is None:
        raise SdmdEquationError(f"equation {equation_id} requires max_sdi")
    _require_positive(value, "max_sdi")
    if spec.max_sdi_range is not None:
        low, high = spec.max_sdi_range
        if not low <= value <= high:
            raise SdmdEquationError(
                f"max_sdi for equation {equation_id} must be between {low:g} and {high:g}"
            )
    return value


def _require_positive(value: float, name: str) -> None:
    """Refuse a non-positive or non-finite value.

    Parameters
    ----------
    value : float
        The value.
    name : str
        The field name, used in the message.

    Raises
    ------
    SdmdEquationError
        When the value is not finite and positive.
    """
    if not math.isfinite(value) or value <= 0.0:
        raise SdmdEquationError(f"{name} must be finite and positive")
