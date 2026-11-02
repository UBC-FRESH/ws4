"""Typed forest-condition report-card contract and Markdown renderer.

A report card is a small, report-only view over already-computed WS4 indicators.
It does not calculate condition, growth, habitat, or alerts.  The contract carries
provenance, uncertainty, applicability, advisory alerts, and review status so a
card cannot silently become an operational early-warning product.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import pandas as pd

SCHEMA_VERSION = "ws4.forest_condition.report.v1"
INDICATOR_STATUSES: frozenset[str] = frozenset(
    {"ok", "outside_domain", "missing", "review_required"}
)
REVIEW_STATUSES: frozenset[str] = frozenset({"draft", "provisional", "reviewed"})
ALERT_SEVERITIES: frozenset[str] = frozenset({"info", "watch", "warning"})
TREND_VALUES: frozenset[str] = frozenset({"improving", "stable", "declining", "not_available"})
IndicatorStatus = Literal["ok", "outside_domain", "missing", "review_required"]
ReviewStatus = Literal["draft", "provisional", "reviewed"]
AlertSeverity = Literal["info", "watch", "warning"]


def _text(value: object, where: str) -> str:
    """Return a non-empty string or raise ``ValueError``."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, where: str) -> str | None:
    """Return ``None`` or a non-empty string."""
    if value is None:
        return None
    return _text(value, where)


def _number(value: object, where: str, *, minimum: float | None = None) -> float:
    """Return a finite number, optionally with a lower bound."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{where} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{where} must be >= {minimum}")
    return number


def _optional_number(value: object, where: str) -> float | None:
    """Return ``None`` or a finite non-negative number."""
    if value is None:
        return None
    return _number(value, where, minimum=0.0)


def _mapping(value: object, where: str) -> Mapping[str, object]:
    """Return a string-keyed mapping or raise ``ValueError``."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return cast(Mapping[str, object], value)


@dataclass(frozen=True)
class ConditionIndicator:
    """One condition indicator on a report card.

    Parameters
    ----------
    name : str
        Stable indicator name.
    value : float
        Indicator value.
    unit : str
        Measurement unit.
    source : str
        Source product or calculation name.
    source_version : str
        Source version, vintage, or model-card identifier.
    uncertainty : float or None, optional
        RMSE or interval half-width, in ``unit``.
    uncertainty_kind : str or None, optional
        Description of the uncertainty measure.
    applicability : str or None, optional
        Applicability domain or abstention reason.
    status : {"ok", "outside_domain", "missing", "review_required"}, optional
        Indicator status.
    trend : {"improving", "stable", "declining", "not_available"}, optional
        Comparable trend.
    note : str or None, optional
        Free-text note.
    """

    name: str
    value: float
    unit: str
    source: str
    source_version: str
    uncertainty: float | None = None
    uncertainty_kind: str | None = None
    applicability: str | None = None
    status: IndicatorStatus = "ok"
    trend: str = "not_available"
    note: str | None = None

    def __post_init__(self) -> None:
        """Validate the indicator fields."""
        _text(self.name, "indicator.name")
        _text(self.unit, "indicator.unit")
        _text(self.source, "indicator.source")
        _text(self.source_version, "indicator.source_version")
        _number(self.value, "indicator.value")
        if self.uncertainty is not None:
            _number(self.uncertainty, "indicator.uncertainty", minimum=0.0)
        if self.status not in INDICATOR_STATUSES:
            raise ValueError(f"indicator.status must be one of {sorted(INDICATOR_STATUSES)}")
        if self.trend not in TREND_VALUES:
            raise ValueError(f"indicator.trend must be one of {sorted(TREND_VALUES)}")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation.

        Returns
        -------
        dict[str, object]
            Indicator fields in JSON-compatible form.
        """
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "source_version": self.source_version,
            "uncertainty": self.uncertainty,
            "uncertainty_kind": self.uncertainty_kind,
            "applicability": self.applicability,
            "status": self.status,
            "trend": self.trend,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ConditionIndicator:
        """Build and validate an indicator from a mapping.

        Parameters
        ----------
        payload : Mapping[str, object]
            Decoded indicator object.

        Returns
        -------
        ConditionIndicator
            Validated indicator.
        """
        return cls(
            name=_text(payload.get("name"), "indicator.name"),
            value=_number(payload.get("value"), "indicator.value"),
            unit=_text(payload.get("unit"), "indicator.unit"),
            source=_text(payload.get("source"), "indicator.source"),
            source_version=_text(payload.get("source_version"), "indicator.source_version"),
            uncertainty=_optional_number(payload.get("uncertainty"), "indicator.uncertainty"),
            uncertainty_kind=_optional_text(
                payload.get("uncertainty_kind"), "indicator.uncertainty_kind"
            ),
            applicability=_optional_text(payload.get("applicability"), "indicator.applicability"),
            status=cast(IndicatorStatus, payload.get("status", "ok")),
            trend=_text(payload.get("trend", "not_available"), "indicator.trend"),
            note=_optional_text(payload.get("note"), "indicator.note"),
        )


@dataclass(frozen=True)
class ConditionAlert:
    """One advisory alert on a report card.

    Alerts are always advisory.  A card cannot promote an alert into a treatment,
    constraint, or operational decision without a separate implementation.

    Parameters
    ----------
    code : str
        Stable alert code.
    severity : {"info", "watch", "warning"}
        Advisory severity.
    message : str
        Human-readable advisory message.
    indicator : str or None, optional
        Related indicator name.
    """

    code: str
    severity: AlertSeverity
    message: str
    indicator: str | None = None

    def __post_init__(self) -> None:
        """Validate the alert fields."""
        _text(self.code, "alert.code")
        _text(self.message, "alert.message")
        if self.severity not in ALERT_SEVERITIES:
            raise ValueError(f"alert.severity must be one of {sorted(ALERT_SEVERITIES)}")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation.

        Returns
        -------
        dict[str, object]
            Alert fields, with the advisory flag forced true.
        """
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "indicator": self.indicator,
            "advisory": True,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ConditionAlert:
        """Build and validate an alert from a mapping.

        Parameters
        ----------
        payload : Mapping[str, object]
            Decoded alert object.

        Returns
        -------
        ConditionAlert
            Validated alert.
        """
        if payload.get("advisory", True) is not True:
            raise ValueError("alert.advisory must be true; alerts are advisory only")
        return cls(
            code=_text(payload.get("code"), "alert.code"),
            severity=cast(AlertSeverity, payload.get("severity")),
            message=_text(payload.get("message"), "alert.message"),
            indicator=_optional_text(payload.get("indicator"), "alert.indicator"),
        )


@dataclass(frozen=True)
class ForestConditionReport:
    """One forest-condition report card.

    Parameters
    ----------
    report_id : str
        Stable report identifier.
    scenario_id : str
        WS4 scenario or run identifier.
    generated_utc : str
        ISO-8601 generation timestamp.
    period : str
        Reporting period.
    indicators : tuple of ConditionIndicator
        Indicator rows.
    review_status : {"draft", "provisional", "reviewed"}
        Review state of the card.
    alerts : tuple of ConditionAlert, optional
        Advisory alerts.
    provenance : mapping of str to str, optional
        Source and version metadata.
    schema_version : str, optional
        Report schema version.
    """

    report_id: str
    scenario_id: str
    generated_utc: str
    period: str
    indicators: tuple[ConditionIndicator, ...]
    review_status: ReviewStatus
    alerts: tuple[ConditionAlert, ...] = ()
    provenance: Mapping[str, str] | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate the report and its unique indicator names."""
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        _text(self.report_id, "report_id")
        _text(self.scenario_id, "scenario_id")
        _text(self.generated_utc, "generated_utc")
        _text(self.period, "period")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {sorted(REVIEW_STATUSES)}")
        names = [indicator.name for indicator in self.indicators]
        if len(names) != len(set(names)):
            raise ValueError("indicator names must be unique")
        for indicator in self.indicators:
            if not isinstance(indicator, ConditionIndicator):
                raise ValueError("indicators must contain ConditionIndicator values")
        for alert in self.alerts:
            if not isinstance(alert, ConditionAlert):
                raise ValueError("alerts must contain ConditionAlert values")
        if self.provenance is not None:
            for key, value in self.provenance.items():
                _text(key, "provenance key")
                _text(value, f"provenance.{key}")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation.

        Returns
        -------
        dict[str, object]
            Full report in JSON-compatible form.
        """
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "scenario_id": self.scenario_id,
            "generated_utc": self.generated_utc,
            "period": self.period,
            "review_status": self.review_status,
            "indicators": [indicator.to_dict() for indicator in self.indicators],
            "alerts": [alert.to_dict() for alert in self.alerts],
            "provenance": dict(self.provenance or {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ForestConditionReport:
        """Build and validate a report from a mapping.

        Parameters
        ----------
        payload : Mapping[str, object]
            Decoded report object.

        Returns
        -------
        ForestConditionReport
            Validated report.
        """
        raw_indicators = payload.get("indicators", [])
        if not isinstance(raw_indicators, list):
            raise ValueError("indicators must be a list")
        raw_alerts = payload.get("alerts", [])
        if not isinstance(raw_alerts, list):
            raise ValueError("alerts must be a list")
        raw_provenance = payload.get("provenance", {})
        provenance = _mapping(raw_provenance, "provenance")
        return cls(
            schema_version=_text(payload.get("schema_version"), "schema_version"),
            report_id=_text(payload.get("report_id"), "report_id"),
            scenario_id=_text(payload.get("scenario_id"), "scenario_id"),
            generated_utc=_text(payload.get("generated_utc"), "generated_utc"),
            period=_text(payload.get("period"), "period"),
            review_status=cast(ReviewStatus, payload.get("review_status")),
            indicators=tuple(
                ConditionIndicator.from_dict(_mapping(item, f"indicators[{index}]"))
                for index, item in enumerate(raw_indicators)
            ),
            alerts=tuple(
                ConditionAlert.from_dict(_mapping(item, f"alerts[{index}]"))
                for index, item in enumerate(raw_alerts)
            ),
            provenance={
                key: _text(value, f"provenance.{key}") for key, value in provenance.items()
            },
        )

    def to_json(self) -> str:
        """Return JSON with non-finite values forbidden.

        Returns
        -------
        str
            Indented JSON document.
        """
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> ForestConditionReport:
        """Parse and validate a report from JSON.

        Parameters
        ----------
        text : str
            JSON document.

        Returns
        -------
        ForestConditionReport
            Validated report.
        """
        payload = json.loads(text)
        return cls.from_dict(_mapping(payload, "report"))

    def to_markdown(self) -> str:
        """Render a one-page Markdown report card.

        Returns
        -------
        str
            Markdown document with the advisory and limit statements.
        """
        lines = [
            f"# Forest condition report: {self.report_id}",
            "",
            f"- **Scenario:** {self.scenario_id}",
            f"- **Period:** {self.period}",
            f"- **Generated:** {self.generated_utc}",
            f"- **Review status:** {self.review_status}",
            "- **Status:** report-only; alerts are advisory, not operational decisions.",
            "",
            "## Indicators",
            "",
        ]
        if self.indicators:
            lines.extend(
                [
                    "| Indicator | Value | Unit | Source | Status | Applicability |",
                    "| --- | ---: | --- | --- | --- | --- |",
                ]
            )
            for item in self.indicators:
                lines.append(
                    f"| {item.name} | {item.value:.6g} | {item.unit} | "
                    f"{item.source} ({item.source_version}) | {item.status} | "
                    f"{item.applicability or 'not stated'} |"
                )
        else:
            lines.append("No indicators were supplied.")
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(
                ["| Code | Severity | Indicator | Advisory message |", "| --- | --- | --- | --- |"]
            )
            for alert in self.alerts:
                lines.append(
                    f"| {alert.code} | {alert.severity} | {alert.indicator or '—'} | "
                    f"{alert.message} |"
                )
        else:
            lines.append("No alerts were supplied.")
        lines.extend(
            [
                "",
                "## Provenance",
                "",
            ]
        )
        if self.provenance:
            lines.extend(f"- **{key}:** {value}" for key, value in self.provenance.items())
        else:
            lines.append("No provenance metadata was supplied.")
        lines.extend(
            [
                "",
                "## Limits",
                "",
                "- This card is report-only and does not change objectives, constraints, "
                "growth, or the solver.",
                "- Alerts are advisory and must not be treated as operational decisions.",
                "- Indicator applicability and review status must be checked before use.",
                "",
            ]
        )
        return "\n".join(lines)


def build_report_from_accounts(
    values: pd.DataFrame,
    *,
    report_id: str,
    scenario_id: str,
    generated_utc: str,
    period: str,
    source_version: str = "unversioned",
    review_status: ReviewStatus = "draft",
    provenance: Mapping[str, str] | None = None,
) -> ForestConditionReport:
    """Build a review-required card from WS4 account values.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value`` columns.
    report_id : str
        Stable report identifier.
    scenario_id : str
        WS4 scenario or run identifier.
    generated_utc : str
        ISO-8601 generation timestamp.
    period : str
        Reporting period.
    source_version : str, optional
        Run or dataset version to record with every derived indicator.
    review_status : {"draft", "provisional", "reviewed"}, optional
        Review state of the card.
    provenance : mapping of str to str, optional
        Additional source metadata.

    Returns
    -------
    ForestConditionReport
        A card whose feature-account indicators are all ``review_required``.

    Raises
    ------
    ValueError
        If the table is empty, lacks required columns, has non-finite values, or
        contains no feature accounts.
    """
    required = {"offset", "account", "value"}
    missing = required.difference(values.columns)
    if missing:
        raise ValueError(f"account values are missing columns: {sorted(missing)}")
    if values.empty:
        raise ValueError("account values are empty")
    frame = values.copy()
    frame["offset"] = pd.to_numeric(frame["offset"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if frame["offset"].isna().any() or frame["value"].isna().any():
        raise ValueError("account values contain non-finite or non-numeric values")
    if not frame["value"].map(math.isfinite).all():
        raise ValueError("account values contain non-finite values")
    feature = frame[frame["account"].astype(str).str.startswith("feature.")]
    if feature.empty:
        raise ValueError("account values contain no feature.* accounts")
    indicators: list[ConditionIndicator] = []
    for account, group in feature.groupby("account", sort=True):
        ordered = group.sort_values("offset")
        first = float(ordered["value"].iloc[0])
        final = float(ordered["value"].iloc[-1])
        if math.isclose(final, first, rel_tol=1e-9, abs_tol=1e-9):
            trend = "stable"
        elif final > first:
            trend = "improving"
        else:
            trend = "declining"
        indicators.append(
            ConditionIndicator(
                name=str(account),
                value=final,
                unit="native",
                source="ws4.account_values",
                source_version=source_version,
                applicability="derived from run accounts; review required",
                status="review_required",
                trend=trend,
                note="Account-derived; not an independent condition indicator.",
            )
        )
    return ForestConditionReport(
        report_id=report_id,
        scenario_id=scenario_id,
        generated_utc=generated_utc,
        period=period,
        indicators=tuple(indicators),
        review_status=review_status,
        alerts=(),
        provenance=provenance,
    )


def load_report(path: str | Path) -> ForestConditionReport:
    """Load a report card from a JSON file.

    Parameters
    ----------
    path : str or pathlib.Path
        JSON report path.

    Returns
    -------
    ForestConditionReport
        Validated report.
    """
    return ForestConditionReport.from_json(Path(path).read_text(encoding="utf-8"))


def write_report(report: ForestConditionReport, path: str | Path) -> None:
    """Write a report card JSON file.

    Parameters
    ----------
    report : ForestConditionReport
        Report to write.
    path : str or pathlib.Path
        Destination path.
    """
    Path(path).write_text(report.to_json(), encoding="utf-8")
