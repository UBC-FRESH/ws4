"""Tests for HWP lifecycle accounting and the carbon-system account set."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.carbon.hwp import HwpConfig, HwpConfigError, hwp_accounts, load_hwp_config
from ws4.carbon.libcbm import CarbonEngineError, CarbonRun, CbmDefaultsReference, carbon_accounts


def _config(**overrides: float) -> HwpConfig:
    """Return a small, exact test parameter set."""
    return HwpConfig(
        utilization_rate=overrides.get("utilization_rate", 0.85),
        proportion_solid_wood=overrides.get("proportion_solid_wood", 0.5),
        half_life_solid_wood=overrides.get("half_life_solid_wood", 1.0),
        half_life_paper=overrides.get("half_life_paper", 1.0),
        displacement_factor_solid=overrides.get("displacement_factor_solid", 1.0),
        displacement_factor_paper=overrides.get("displacement_factor_paper", 0.0),
        displacement_credit=overrides.get("displacement_credit", 1.0),
        period_length=int(overrides.get("period_length", 1.0)),
    )


def test_hwp_split_decay_and_displacement() -> None:
    """A harvest splits inflow 50/50, decays exactly, and credits solid wood."""
    eco = pd.Series([100.0, 90.0], index=[0, 1])
    production = pd.Series([100.0, 0.0], index=[0, 1])
    accounts = hwp_accounts(eco, production, _config())
    values = accounts.set_index(["offset", "account"])["value"]
    assert values.loc[(0, "carbon.hwp.solid_wood.total")] == pytest.approx(42.5)
    assert values.loc[(0, "carbon.hwp.paper.total")] == pytest.approx(42.5)
    assert values.loc[(0, "carbon.hwp.total")] == pytest.approx(85.0)
    assert values.loc[(0, "carbon.system.total")] == pytest.approx(185.0)
    assert values.loc[(0, "carbon.displacement.total")] == pytest.approx(42.5)
    assert values.loc[(0, "carbon.co2e.displacement")] == pytest.approx(42.5 * 44 / 12)
    assert values.loc[(1, "carbon.hwp.total")] == pytest.approx(42.5)
    assert values.loc[(1, "carbon.hwp.decay")] == pytest.approx(42.5)
    assert values.loc[(1, "carbon.co2e.hwp.eol")] == pytest.approx(42.5 * 44 / 12)
    assert values.loc[(1, "carbon.co2e.system.emissions")] == pytest.approx(52.5 * 44 / 12)


def test_system_emissions_telescope_with_realistic_offsets() -> None:
    """A post-offset harvest plus decay closes the stock-difference identity."""
    eco = pd.Series([100.0, 100.0, 90.0], index=[0, 1, 2])
    production = pd.Series([0.0, 100.0, 0.0], index=[0, 1, 2])
    accounts = hwp_accounts(eco, production, _config()).set_index(["offset", "account"])["value"]
    cumulative = accounts.loc[(2, "carbon.co2e.system.emissions.cumulative")]
    hwp_end = accounts.loc[(2, "carbon.hwp.total")]
    displacement = accounts.loc[(1, "carbon.displacement.total")]
    expected = (100.0 - 90.0 - hwp_end - displacement) * 44 / 12
    assert cumulative == pytest.approx(expected)


def test_no_harvest_keeps_system_equal_to_ecosystem() -> None:
    """With no product inflow, the system balance is the ecosystem balance."""
    eco = pd.Series([10.0, 12.0], index=[0, 1])
    production = pd.Series([0.0, 0.0], index=[0, 1])
    values = hwp_accounts(eco, production, _config()).set_index(["offset", "account"])["value"]
    assert values.loc[(0, "carbon.system.total")] == 10.0
    assert values.loc[(1, "carbon.system.total")] == 12.0
    assert values.loc[(1, "carbon.co2e.system.emissions")] == pytest.approx(-2.0 * 44 / 12)


def test_hwp_config_accepts_aliases_and_rejects_unknown_keys(tmp_path: Path) -> None:
    """The loader accepts the manuscript names but rejects a typo."""
    path = tmp_path / "hwp.yaml"
    path.write_text(
        "hwp:\n  util_rate: 0.8\n  solid_wood_fraction: 0.4\n"
        "  half_life_solid_wood: 80\n  half_life_paper: 2\n",
        encoding="utf-8",
    )
    config = load_hwp_config(path)
    assert config.utilization_rate == 0.8
    assert config.proportion_solid_wood == 0.4
    assert config.half_life_solid_wood == 80
    path.write_text("hwp:\n  typo_key: 1\n", encoding="utf-8")
    with pytest.raises(HwpConfigError, match="unknown HWP config key"):
        load_hwp_config(path)


def _run() -> CarbonRun:
    """Return a tiny CBM run with the product-production fluxes."""
    pools = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "SoftwoodMerch": [10.0, 0.0],
            "SoftwoodFoliage": [1.0, 0.0],
            "AboveGroundSlowSoil": [2.0, 2.0],
            "Products": [0.0, 8.0],
        }
    )
    flux = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "DisturbanceSoftProduction": [0.0, 10.0],
            "DisturbanceHardProduction": [0.0, 0.0],
            "DeltaBiomass_AG": [1.0, 0.0],
            "DeltaBiomass_BG": [0.5, 0.0],
            "DecaySlowAGToAir": [0.0, 0.1],
            "DisturbanceMerchToAir": [0.0, 0.2],
        }
    )
    return CarbonRun(
        pools=pools,
        flux=flux,
        classifiers=pd.DataFrame(),
        state=pd.DataFrame(),
        libcbm_version="2.10.2",
        defaults=CbmDefaultsReference(
            path=Path("cbm_defaults.db"), version="1.2.9300.391", sha256="b" * 64
        ),
    )


def test_carbon_accounts_adds_hwp_when_configured() -> None:
    """The account writer exposes HWP and system accounts when given a config."""
    accounts = carbon_accounts(_run(), hwp=_config())
    values = accounts.set_index(["offset", "account"])["value"]
    assert values.loc[(1, "carbon.hwp.inflow")] == pytest.approx(8.5)
    assert values.loc[(1, "carbon.hwp.total")] == pytest.approx(8.5)
    assert (1, "carbon.co2e.system.emissions") in values.index


def test_hwp_period_length_must_be_one_for_annual_run() -> None:
    """The libcbm run is annual; a multi-year HWP period would silently mis-scale."""
    with pytest.raises(CarbonEngineError, match="annual"):
        carbon_accounts(_run(), hwp=_config(period_length=2))
