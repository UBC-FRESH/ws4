"""Optional flood-risk accounts for the WS4 optimizer.

This module turns a pinned FEMIC response bundle, an explicit support mapping,
and a schedule into ``flood.*`` account rows. It is a screening model, not a
process simulation, and it refuses schedules outside the response-surface
scenario envelope.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ws4.io.hydrology import (
    HYDROLOGY_READINESS_POLICIES,
    FemicHydrologyError,
    HydrologyMapping,
    assess_femic_hydrology_readiness,
    enforce_hydrology_readiness,
    load_hydrology_mapping,
    load_registered_femic_hydrology_bundle,
    screen_schedule_flood_risk,
)

HYDROLOGY_FLOOD_SCREEN_CONFIG_SCHEMA = "ws4.hydrology.flood_screen.v1"
DEFAULT_FLOOD_REFUSAL_PENALTY = 1e12


class FloodRiskRefusalError(RuntimeError):
    """Raised when a schedule is outside the flood-response envelope."""


@dataclass(frozen=True)
class FloodScreenConfig:
    """Configuration for schedule-level flood-risk accounts.

    Attributes
    ----------
    mapping_path : Path
        Mapping directory or manifest.
    covariates : dict of str to float
        Global response features not derived from the schedule.
    scenario_tolerance : float
        Maximum feature difference allowed when selecting a response scenario.
    refusal_penalty : float
        Objective penalty applied when a schedule is refused.
    readiness_policy : str
        ``allow_provisional`` (default), ``require_reviewed``, or
        ``require_ready``.
    allow_tail_failures : bool
        Permit a tail-check block only under ``allow_provisional``.
    """

    mapping_path: Path
    covariates: dict[str, float]
    scenario_tolerance: float
    refusal_penalty: float
    readiness_policy: str
    allow_tail_failures: bool


class FloodRiskModel:
    """Compute optional ``flood.*`` accounts for one compiled dataset.

    Parameters
    ----------
    dataset_dir : Path
        Compiled WS4 dataset with a registered FEMIC hydrology bundle.
    config_path : Path
        ``ws4.hydrology.flood_screen.v1`` JSON configuration.
    """

    def __init__(self, dataset_dir: Path, config_path: Path) -> None:
        self.dataset_dir = dataset_dir.expanduser().resolve()
        self.config = load_flood_screen_config(config_path)
        self.bundle = load_registered_femic_hydrology_bundle(self.dataset_dir)
        self.mapping: HydrologyMapping = load_hydrology_mapping(self.config.mapping_path)
        self.readiness = assess_femic_hydrology_readiness(self.bundle)
        enforce_hydrology_readiness(
            self.readiness,
            policy=self.config.readiness_policy,
            allow_tail_failures=self.config.allow_tail_failures,
        )
        self.mapping_manifest_path = (
            self.config.mapping_path / "hydrology_mapping.json"
            if self.config.mapping_path.is_dir()
            else self.config.mapping_path
        )

    @property
    def refusal_penalty(self) -> float:
        """Return the objective penalty for an out-of-envelope schedule.

        Returns
        -------
        float
            Configured refusal penalty.
        """
        return self.config.refusal_penalty

    def values(self, schedule: pd.DataFrame, years: int) -> pd.DataFrame:
        """Return ``flood.*`` account rows for a schedule.

        Parameters
        ----------
        schedule : pandas.DataFrame
            Schedule frame with ``block_id``, ``treatment``, and ``offset``.
        years : int
            Horizon in years. Account rows are emitted for every offset so a
            periodic target can read the cumulative state at its period end.

        Returns
        -------
        pandas.DataFrame
            Rows with ``offset``, ``account``, and ``value``. Empty when the
            schedule has no treatments.

        Raises
        ------
        FloodRiskRefusal
            When the schedule is outside the response-surface envelope or a
            required FEMIC input is missing.
        """
        try:
            screen = screen_schedule_flood_risk(
                self.dataset_dir,
                self.bundle,
                self.mapping,
                schedule,
                mapping_manifest_path=self.mapping_manifest_path,
                covariates=self.config.covariates,
                scenario_tolerance=self.config.scenario_tolerance,
                periods=range(years),
            )
        except FemicHydrologyError as exc:
            raise FloodRiskRefusalError(str(exc)) from exc
        rows: list[dict[str, object]] = []
        for item in screen.rows:
            receptor = str(item["receptor_id"])
            period = _period_label(_finite_float(item["return_period"], "return_period"))
            offset = int(_finite_float(item["period"], "period"))
            prefix = f"flood.{receptor}.{period}"
            rows.append(
                {
                    "offset": offset,
                    "account": f"{prefix}.ratio",
                    "value": _finite_float(item["response_ratio"], "response_ratio"),
                }
            )
            rows.append(
                {
                    "offset": offset,
                    "account": f"{prefix}.peak_flow_m3s",
                    "value": _finite_float(
                        item["screening_peak_flow_m3s"],
                        "screening_peak_flow_m3s",
                    ),
                }
            )
            exceedance = item.get("exceedance_probability")
            if exceedance is not None:
                rows.append(
                    {
                        "offset": offset,
                        "account": f"{prefix}.exceedance_probability",
                        "value": _finite_float(exceedance, "exceedance_probability"),
                    }
                )
            damage = item.get("expected_annual_damage")
            if damage is not None:
                rows.append(
                    {
                        "offset": offset,
                        "account": f"{prefix}.expected_annual_damage",
                        "value": _finite_float(damage, "expected_annual_damage"),
                    }
                )
        return pd.DataFrame(rows, columns=["offset", "account", "value"])


def load_flood_screen_config(path: Path) -> FloodScreenConfig:
    """Load a flood-screen model configuration.

    Parameters
    ----------
    path : Path
        JSON configuration path.

    Returns
    -------
    FloodScreenConfig
        Parsed configuration with the mapping resolved relative to the config.

    Raises
    ------
    FloodRiskRefusal
        If the configuration is malformed.
    """
    resolved = path.expanduser().resolve()
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FloodRiskRefusalError(f"Unable to read flood-screen config: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FloodRiskRefusalError(f"Invalid flood-screen config JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise FloodRiskRefusalError("Flood-screen config must be a JSON object.")
    if payload.get("schema_version") != HYDROLOGY_FLOOD_SCREEN_CONFIG_SCHEMA:
        raise FloodRiskRefusalError(
            f"Unsupported flood-screen config schema {payload.get('schema_version')!r}."
        )
    mapping_value = payload.get("mapping")
    if not isinstance(mapping_value, str) or not mapping_value.strip():
        raise FloodRiskRefusalError("Flood-screen config requires a mapping path.")
    mapping_path = Path(mapping_value)
    if not mapping_path.is_absolute():
        mapping_path = resolved.parent / mapping_path
    mapping_path = mapping_path.resolve()
    if not mapping_path.exists():
        raise FloodRiskRefusalError(f"Flood-screen mapping does not exist: {mapping_path}")
    covariates_value = payload.get("covariates", {})
    if not isinstance(covariates_value, Mapping):
        raise FloodRiskRefusalError("Flood-screen covariates must be an object.")
    covariates = {
        str(key): _finite_float(value, f"covariate {key!r}")
        for key, value in covariates_value.items()
    }
    tolerance = _finite_float(
        payload.get("scenario_tolerance", 0.05),
        "scenario_tolerance",
    )
    if tolerance <= 0:
        raise FloodRiskRefusalError("Flood-screen scenario_tolerance must be positive.")
    penalty = _finite_float(
        payload.get("refusal_penalty", DEFAULT_FLOOD_REFUSAL_PENALTY),
        "refusal_penalty",
    )
    if penalty <= 0:
        raise FloodRiskRefusalError("Flood-screen refusal_penalty must be positive.")
    readiness_policy = str(payload.get("readiness_policy", "allow_provisional"))
    if readiness_policy not in HYDROLOGY_READINESS_POLICIES:
        raise FloodRiskRefusalError(
            f"Unsupported flood-screen readiness_policy {readiness_policy!r}."
        )
    allow_tail = payload.get("allow_tail_failures", False)
    if not isinstance(allow_tail, bool):
        raise FloodRiskRefusalError("Flood-screen allow_tail_failures must be boolean.")
    return FloodScreenConfig(
        mapping_path=mapping_path,
        covariates=covariates,
        scenario_tolerance=tolerance,
        refusal_penalty=penalty,
        readiness_policy=readiness_policy,
        allow_tail_failures=allow_tail,
    )


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise FloodRiskRefusalError(f"Flood-screen {field_name} must be numeric.")
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise FloodRiskRefusalError(f"Flood-screen {field_name} must be numeric.") from exc
    if not math.isfinite(parsed):
        raise FloodRiskRefusalError(f"Flood-screen {field_name} must be finite.")
    return parsed


def _period_label(period: float) -> str:
    return f"{period:g}"
