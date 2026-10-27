"""Harvested wood product (HWP) lifecycle accounting.

The forest carbon engine reports ecosystem pools and the merchantable carbon that a
disturbance transfers to products. This module turns that transfer into an explicit
product ledger so a WS4 study can report, and optimize against, the whole forest-sector
carbon balance:

* utilized fibre is split between paper and solid wood;
* each product pool decays with an exact per-period survival
  ``2 ** (-period_length / half_life)``;
* decay is an end-of-life (EOL) emission to the atmosphere;
* displacement credits avoided emissions from the solid-wood and paper pools; and
* the system balance is ecosystem carbon plus HWP stock minus displacement.

The conventions follow the corrected manuscript accounting in the public
``fresh-yan`` package: stock-difference ecosystem emissions, a products-only HWP
ledger, exact half-life decay, and displacement applied to product inflow. The
documented boundary is that decay is immediate EOL emission; landfill and long-lived
inert product pools are not represented in this first version.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

CO2_PER_CARBON = 44.0 / 12.0


class HwpConfigError(ValueError):
    """Raised when an HWP configuration is missing or invalid."""


@dataclass(frozen=True)
class HwpConfig:
    """Public assumptions for the harvested wood product lifecycle.

    Parameters
    ----------
    utilization_rate : float
        Fraction of merchantable carbon that becomes utilized product. The public
        manuscript convention is 0.85.
    proportion_solid_wood : float
        Share of utilized fibre allocated to solid wood; the remainder is paper.
    half_life_solid_wood : float
        Solid-wood half-life in years.
    half_life_paper : float
        Paper half-life in years.
    displacement_factor_solid : float
        Avoided carbon per tonne of carbon in solid-wood inflow, in tC avoided/tC
        product. The life-cycle ledger converts the total to tCO2e.
    displacement_factor_paper : float
        Avoided carbon per tonne of carbon in paper inflow. The manuscript uses zero
        for paper.
    displacement_credit : float
        Multiplier on the displacement credit, kept explicit for sensitivity runs.
    period_length : int
        Years per accounting period. Annual runs use 1.
    source : str
        Human-readable provenance for the parameter set.
    """

    utilization_rate: float = 0.85
    proportion_solid_wood: float = 0.5
    half_life_solid_wood: float = 100.0
    half_life_paper: float = 2.0
    displacement_factor_solid: float = 1.0
    displacement_factor_paper: float = 0.0
    displacement_credit: float = 1.0
    period_length: int = 1
    source: str = "public HWP assumptions"

    def __post_init__(self) -> None:
        """Validate the parameter ranges."""
        if not 0.0 <= self.utilization_rate <= 1.0:
            raise HwpConfigError("utilization_rate must be between 0 and 1")
        if not 0.0 <= self.proportion_solid_wood <= 1.0:
            raise HwpConfigError("proportion_solid_wood must be between 0 and 1")
        if self.half_life_solid_wood <= 0.0:
            raise HwpConfigError("half_life_solid_wood must be positive")
        if self.half_life_paper <= 0.0:
            raise HwpConfigError("half_life_paper must be positive")
        if self.displacement_factor_solid < 0.0 or self.displacement_factor_paper < 0.0:
            raise HwpConfigError("displacement factors must be non-negative")
        if self.displacement_credit < 0.0:
            raise HwpConfigError("displacement_credit must be non-negative")
        if self.period_length <= 0:
            raise HwpConfigError("period_length must be positive")

    def manifest(self) -> dict[str, object]:
        """Return the parameter set as a manifest-ready mapping.

        Returns
        -------
        dict of str to object
            The HWP assumptions and their units.
        """
        return {
            "utilization_rate": float(self.utilization_rate),
            "proportion_solid_wood": float(self.proportion_solid_wood),
            "half_life_solid_wood_years": float(self.half_life_solid_wood),
            "half_life_paper_years": float(self.half_life_paper),
            "displacement_factor_solid_tc_avoided_per_tc_product": float(
                self.displacement_factor_solid
            ),
            "displacement_factor_paper_tc_avoided_per_tc_product": float(
                self.displacement_factor_paper
            ),
            "displacement_credit": float(self.displacement_credit),
            "period_length_years": int(self.period_length),
            "source": self.source,
            "decay_convention": "exact_survival_2**(-period_length/half_life)",
            "eol_convention": "decay_to_atmosphere",
        }


def load_hwp_config(path: Path) -> HwpConfig:
    """Load HWP assumptions from YAML.

    The file may use a top-level ``hwp:`` block or the flat parameter mapping. Unknown
    keys are rejected so a typo cannot silently leave a default in place.

    Parameters
    ----------
    path : Path
        YAML configuration path.

    Returns
    -------
    HwpConfig
        The validated assumptions.

    Raises
    ------
    HwpConfigError
        When the file is missing, malformed, or has an unknown key.
    """
    source = Path(path)
    if not source.is_file():
        raise HwpConfigError(f"HWP config not found: {source}")
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise HwpConfigError(f"cannot read HWP config {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HwpConfigError(f"HWP config {source} must be a YAML mapping")
    block = payload.get("hwp", payload)
    if not isinstance(block, dict):
        raise HwpConfigError(f"HWP config {source} has a non-mapping 'hwp' block")

    aliases = {
        "util_rate": "utilization_rate",
        "solid_wood_fraction": "proportion_solid_wood",
        "solid_wood_half_life": "half_life_solid_wood",
        "paper_half_life": "half_life_paper",
        "solid_displacement_factor": "displacement_factor_solid",
        "paper_displacement_factor": "displacement_factor_paper",
        "credit": "displacement_credit",
    }
    allowed = {
        "utilization_rate",
        "proportion_solid_wood",
        "half_life_solid_wood",
        "half_life_paper",
        "displacement_factor_solid",
        "displacement_factor_paper",
        "displacement_credit",
        "period_length",
        "source",
    }
    values: dict[str, Any] = {}
    numeric = {
        "utilization_rate",
        "proportion_solid_wood",
        "half_life_solid_wood",
        "half_life_paper",
        "displacement_factor_solid",
        "displacement_factor_paper",
        "displacement_credit",
    }
    for key, value in block.items():
        normalized = aliases.get(str(key), str(key))
        if normalized not in allowed:
            raise HwpConfigError(f"unknown HWP config key: {key}")
        try:
            if normalized in numeric:
                values[normalized] = float(value)
            elif normalized == "period_length":
                values[normalized] = int(value)
            else:
                values[normalized] = str(value)
        except (TypeError, ValueError) as exc:
            raise HwpConfigError(
                f"invalid HWP config value for {normalized!r} in {source}: {value!r}"
            ) from exc
    try:
        return HwpConfig(**values)
    except TypeError as exc:
        raise HwpConfigError(f"invalid HWP config {source}: {exc}") from exc


def _series_by_offset(frame: pd.Series, offsets: pd.Index) -> pd.Series:
    """Return a float series aligned to ``offsets`` and filled with zero."""
    numeric = pd.to_numeric(frame, errors="coerce")
    return numeric.reindex(offsets).fillna(0.0)


def hwp_accounts(
    ecosystem: pd.Series,
    production: pd.Series,
    config: HwpConfig,
) -> pd.DataFrame:
    """Build long HWP and system accounts from ecosystem and product inflow series.

    Parameters
    ----------
    ecosystem : pandas.Series
        Ecosystem carbon (tC) indexed by annual offset (timestep).
    production : pandas.Series
        Merchantable carbon transferred to products (tC) indexed by annual offset.
        In a libcbm run this is the sum of ``DisturbanceSoftProduction`` and
        ``DisturbanceHardProduction``.
    config : HwpConfig
        HWP assumptions.

    Returns
    -------
    pandas.DataFrame
        Long rows with ``offset``, ``account``, and ``value``. Carbon pools are in
        ``tC``; CO2e accounts are in ``tCO2e``.

    Raises
    ------
    ValueError
        When the two inputs have no common offset.
    """
    offsets = pd.Index(sorted(set(ecosystem.index) & set(production.index)), name="offset")
    if offsets.empty:
        raise ValueError("HWP accounting needs at least one common ecosystem offset")
    eco = _series_by_offset(ecosystem, offsets)
    merch = _series_by_offset(production, offsets)
    solid_survival = 2.0 ** (-float(config.period_length) / config.half_life_solid_wood)
    paper_survival = 2.0 ** (-float(config.period_length) / config.half_life_paper)

    solid = 0.0
    paper = 0.0
    eco_prev = float(eco.iloc[0])
    hwp_prev = 0.0
    cumulative = 0.0
    rows: list[dict[str, object]] = []
    for index, offset in enumerate(offsets):
        inflow = float(merch.loc[offset]) * config.utilization_rate
        solid_in = inflow * config.proportion_solid_wood
        paper_in = inflow * (1.0 - config.proportion_solid_wood)
        solid_decay = solid * (1.0 - solid_survival)
        paper_decay = paper * (1.0 - paper_survival)
        solid = solid * solid_survival + solid_in
        paper = paper * paper_survival + paper_in
        hwp = solid + paper
        decay = solid_decay + paper_decay
        displacement_tc = (
            solid_in * config.displacement_factor_solid
            + paper_in * config.displacement_factor_paper
        ) * config.displacement_credit
        displacement_tco2e = displacement_tc * CO2_PER_CARBON
        eco_t = float(eco.loc[offset])
        system = eco_t + hwp
        if index == 0:
            eco_emission = 0.0
            system_emission = 0.0
        else:
            eco_emission = (eco_prev - eco_t) * CO2_PER_CARBON
            system_emission = (
                (eco_prev - eco_t) + (hwp_prev - hwp) - displacement_tc
            ) * CO2_PER_CARBON
        cumulative += system_emission
        values = {
            "carbon.hwp.solid_wood.total": solid,
            "carbon.hwp.paper.total": paper,
            "carbon.hwp.total": hwp,
            "carbon.hwp.inflow": inflow,
            "carbon.hwp.decay": decay,
            "carbon.displacement.total": displacement_tc,
            "carbon.system.total": system,
            "carbon.co2e.hwp.total": hwp * CO2_PER_CARBON,
            "carbon.co2e.hwp.eol": decay * CO2_PER_CARBON,
            "carbon.co2e.displacement": displacement_tco2e,
            "carbon.co2e.system.total": system * CO2_PER_CARBON,
            "carbon.co2e.ecosystem.emissions": eco_emission,
            "carbon.co2e.system.emissions": system_emission,
            "carbon.co2e.system.emissions.cumulative": cumulative,
        }
        for account, value in values.items():
            rows.append({"offset": int(str(offset)), "account": account, "value": float(value)})
        eco_prev = eco_t
        hwp_prev = hwp
    return pd.DataFrame(rows, columns=["offset", "account", "value"])


def hwp_manifest(config: HwpConfig) -> dict[str, object]:
    """Return a compact HWP manifest block.

    Parameters
    ----------
    config : HwpConfig
        HWP assumptions.

    Returns
    -------
    dict of str to object
        The manifest block, including the parameter set.
    """
    return {"model": "ws4.hwp.v1", "parameters": config.manifest()}
