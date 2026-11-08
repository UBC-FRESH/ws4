"""The eight validation gates for one AU.

These gates are the evidence layer for the SDMD phase. They do not add capability;
they refuse to call an AU supported when the plots, the density, the diagram, the
trajectory, the initial volume, the regimes, the option reduction, or the UI payload
do not hold together.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from .api import SdmdStore
from .compile import Trajectory, assess_trajectory
from .constraints import check_regime
from .diagram import observed_envelope, place_point
from .equations import basal_area_m2_ha
from .regimes import get_regime
from .schema import Problem

GateStatus = Literal["pass", "warn", "fail"]

GATE_NAMES: tuple[str, ...] = (
    "plot-support",
    "density-plausibility",
    "sdmd-fit",
    "trajectory-plausibility",
    "initial-volume",
    "regime-completeness",
    "solver-option-reduction",
    "ui-payload-contract",
)


@dataclass(frozen=True)
class GateResult:
    """One gate outcome.

    Attributes
    ----------
    gate : str
        The gate name.
    status : {"pass", "warn", "fail"}
        The outcome.
    detail : str
        One sentence that states what the gate saw.
    evidence : dict
        The values the finding rests on.
    """

    gate: str
    status: GateStatus
    detail: str
    evidence: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _PspCheck:
    """The PSP provenance and support behind an AU's observed points.

    Attributes
    ----------
    coordinates : tuple of tuple of float
        The PSP-backed ``(tph, mean_tree_volume_m3)`` points.
    psp_points : int
        Number of points whose source is PSP.
    synthetic_points : int
        Number of points whose source is not PSP.
    psp_plots : int
        Number of distinct reviewed PSP plots.
    findings : tuple of str
        Missing plots, missing tree lists, or unreviewed points.
    """

    coordinates: tuple[tuple[float, float], ...]
    psp_points: int
    synthetic_points: int
    psp_plots: int
    findings: tuple[str, ...]


@dataclass(frozen=True)
class ValidationReport:
    """The eight gate outcomes for one AU.

    Attributes
    ----------
    au_id : str
        The analysis unit.
    gates : tuple of GateResult
        One result per gate, in :data:`GATE_NAMES` order.
    """

    au_id: str
    gates: tuple[GateResult, ...]

    @property
    def status(self) -> GateStatus:
        """Return the overall status.

        Returns
        -------
        {"pass", "warn", "fail"}
            ``fail`` if any gate failed, ``warn`` if any warned, otherwise ``pass``.
        """
        if any(item.status == "fail" for item in self.gates):
            return "fail"
        if any(item.status == "warn" for item in self.gates):
            return "warn"
        return "pass"

    def to_dict(self) -> dict[str, object]:
        """Return the report as a JSON-serializable mapping.

        Returns
        -------
        dict
            The AU, the overall status, and each gate.
        """
        return {
            "au_id": self.au_id,
            "status": self.status,
            "gates": [
                {
                    "gate": item.gate,
                    "status": item.status,
                    "detail": item.detail,
                    "evidence": item.evidence,
                }
                for item in self.gates
            ],
        }


def validate_au(
    store: SdmdStore,
    au_id: str,
    *,
    initial_volume_m3_ha: float | None = None,
    initial_volume_limit_m3_ha: float | None = None,
) -> ValidationReport:
    """Run the eight gates for one AU.

    Parameters
    ----------
    store : SdmdStore
        The loaded SDMD store.
    au_id : str
        The analysis unit.
    initial_volume_m3_ha : float, optional
        The AU's initial volume, when the caller has one.
    initial_volume_limit_m3_ha : float, optional
        The highest initial volume the evidence supports.

    Returns
    -------
    ValidationReport
        The eight outcomes.
    """
    store.require_au(au_id)
    volume = initial_volume_m3_ha
    limit = initial_volume_limit_m3_ha
    source = ""
    if store.initial_volume is not None and str(store.initial_volume.get("au_id")) == au_id:
        if volume is None:
            volume = float(str(store.initial_volume["initial_volume_m3_ha"]))
        if limit is None:
            limit = float(str(store.initial_volume["limit_m3_ha"]))
        source = str(store.initial_volume.get("source", ""))
    detail = store.au(au_id)
    yields = store.yield_curve(au_id)
    points = store.sdmd(au_id)
    regimes = store.regimes_for(au_id)
    preview = store.preview(au_id)
    gates = (
        _plot_support(store, au_id, detail),
        _density_plausibility(yields),
        _sdmd_fit(store, detail, points),
        _trajectory_plausibility(store, au_id, points),
        _initial_volume(volume, limit, yields, source),
        _regime_completeness(store, au_id, regimes),
        _solver_reduction(preview),
        _ui_payload(detail, yields, points, regimes, preview),
    )
    return ValidationReport(au_id=au_id, gates=gates)


def _psp_observed(store: SdmdStore, au_id: str) -> _PspCheck:
    """Check that each PSP point has a reviewed PSP plot and a tree list.

    Parameters
    ----------
    store : SdmdStore
        The loaded store.
    au_id : str
        The analysis unit.

    Returns
    -------
    _PspCheck
        The supported coordinates and the provenance findings.
    """
    points = store.sdmd(au_id).get("points", [])
    plots = store.plots_for(au_id)
    tree_plots = set(store.trees["plot_id"].astype(str)) if not store.trees.empty else set()
    psp_plots: dict[int, list[str]] = {}
    for plot in plots:
        sources = str(plot.get("sources", "")).lower()
        review = str(plot.get("review_status", ""))
        if "psp" not in sources or review != "reviewed":
            continue
        age = int(float(str(plot.get("stand_age", 0))))
        psp_plots.setdefault(age, []).append(str(plot.get("plot_id", "")))
    supported: list[tuple[float, float]] = []
    findings: list[str] = []
    psp_points = 0
    synthetic = 0
    if not isinstance(points, list):
        return _PspCheck((), 0, 0, 0, ("the SDMD point payload is not a list",))
    for row in points:
        if not isinstance(row, dict):
            continue
        label = str(row.get("sdmd_id", "point"))
        if str(row.get("source", "")).lower() != "psp":
            synthetic += 1
            continue
        psp_points += 1
        if str(row.get("review_status", "")) != "reviewed":
            findings.append(f"{label} is not reviewed")
            continue
        age = int(float(str(row.get("age", 0))))
        candidates = psp_plots.get(age, [])
        if not candidates:
            findings.append(f"{label} has no reviewed PSP plot at age {age}")
            continue
        if not any(plot_id in tree_plots for plot_id in candidates):
            findings.append(f"{label} has no PSP tree list at age {age}")
            continue
        supported.append(
            (
                float(str(row.get("tph", 0.0))),
                float(str(row.get("mean_tree_volume_m3", 0.0))),
            )
        )
    return _PspCheck(
        coordinates=tuple(supported),
        psp_points=psp_points,
        synthetic_points=synthetic,
        psp_plots=len({plot_id for ids in psp_plots.values() for plot_id in ids}),
        findings=tuple(findings),
    )


def _plot_support(store: SdmdStore, au_id: str, detail: dict[str, object]) -> GateResult:
    """Gate 1: enough observed plots, PSP provenance, and age support."""
    count = int(str(detail.get("plot_count", 0)))
    ages = f"{detail.get('age_min', 'n/a')}-{detail.get('age_max', 'n/a')}"
    check = _psp_observed(store, au_id)
    evidence: dict[str, object] = {
        "plot_count": count,
        "age_range": ages,
        "psp_points": check.psp_points,
        "synthetic_points": check.synthetic_points,
        "psp_plots": check.psp_plots,
        "findings": list(check.findings),
    }
    if count < 3:
        return GateResult(
            "plot-support",
            "fail",
            f"{count} plots is below the three-plot minimum",
            evidence,
        )
    if check.findings:
        return GateResult(
            "plot-support",
            "fail",
            "; ".join(check.findings[:3]),
            evidence,
        )
    if check.psp_points < 3:
        return GateResult(
            "plot-support",
            "fail",
            f"{check.psp_points} PSP-backed points is below the three-point minimum",
            evidence,
        )
    if check.synthetic_points:
        return GateResult(
            "plot-support",
            "warn",
            f"{count} plots; {check.psp_points} PSP-backed and "
            f"{check.synthetic_points} synthetic point(s)",
            evidence,
        )
    return GateResult(
        "plot-support",
        "pass",
        f"{count} plots and {check.psp_points} PSP-backed points; ages {ages}",
        evidence,
    )


def _density_plausibility(yields: list[dict[str, object]]) -> GateResult:
    """Gate 2: reported basal area agrees with TPH and QMD."""
    if not yields:
        return GateResult("density-plausibility", "fail", "no stand summaries")
    worst = 0.0
    for row in yields:
        tph = float(str(row.get("tph", 0.0)))
        qmd = float(str(row.get("qmd_cm", 0.0)))
        reported = float(str(row.get("ba_m2_ha", 0.0)))
        if tph <= 0 or qmd <= 0 or reported <= 0:
            return GateResult(
                "density-plausibility",
                "fail",
                "a stand summary has a non-positive TPH, QMD, or basal area",
                {"tph": tph, "qmd_cm": qmd, "ba_m2_ha": reported},
            )
        calculated = basal_area_m2_ha(tph, qmd)
        error = abs(calculated - reported) / reported
        worst = max(worst, error)
    if worst > 0.25:
        return GateResult(
            "density-plausibility",
            "fail",
            f"basal area disagrees with TPH and QMD by {worst:.1%}",
            {"worst_error": worst},
        )
    if worst > 0.15:
        return GateResult(
            "density-plausibility",
            "warn",
            f"basal area disagrees with TPH and QMD by {worst:.1%}",
            {"worst_error": worst},
        )
    return GateResult(
        "density-plausibility",
        "pass",
        f"basal area agrees with TPH and QMD within {worst:.1%}",
        {"worst_error": worst},
    )


def _sdmd_fit(
    store: SdmdStore,
    detail: dict[str, object],
    points: dict[str, object],
) -> GateResult:
    """Gate 3: the diagram exists, is reviewed, and the points are inside it."""
    if store.diagram is None:
        return GateResult("sdmd-fit", "fail", "no diagram is loaded")
    rows = points.get("points", [])
    if not isinstance(rows, list) or len(rows) < 3:
        return GateResult("sdmd-fit", "fail", "fewer than three SDMD points")
    zones: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            placement = place_point(
                store.diagram,
                float(str(row.get("tph", 0.0))),
                float(str(row.get("mean_tree_volume_m3", 0.0))),
            )
        except ValueError:
            return GateResult("sdmd-fit", "fail", "a point is outside the diagram domain")
        zones[placement.zone] = zones.get(placement.zone, 0) + 1
    review = store.diagram.review.status
    if review != "reviewed":
        return GateResult(
            "sdmd-fit",
            "warn",
            f"the diagram is {review}; the fit is method-only",
            {"diagram_id": store.diagram.diagram_id, "zones": zones},
        )
    if zones.get("outside", 0):
        return GateResult(
            "sdmd-fit",
            "warn",
            f"{zones['outside']} point(s) fall outside the diagram",
            {"diagram_id": store.diagram.diagram_id, "zones": zones},
        )
    return GateResult(
        "sdmd-fit",
        "pass",
        "the reviewed diagram contains every point",
        {"diagram_id": store.diagram.diagram_id, "zones": zones},
    )


def _trajectory_plausibility(
    store: SdmdStore,
    au_id: str,
    points: dict[str, object],
) -> GateResult:
    """Gate 4: every stored trajectory is physical and assessed."""
    check = _psp_observed(store, au_id)
    if check.findings:
        return GateResult(
            "trajectory-plausibility",
            "fail",
            "; ".join(check.findings[:3]),
            {"findings": list(check.findings)},
        )
    envelope = observed_envelope(check.coordinates) if len(check.coordinates) >= 3 else ()
    directory = store.root / "trajectories" / au_id
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    if not files:
        return GateResult(
            "trajectory-plausibility",
            "warn",
            "no stored trajectory for this AU",
            {"files": 0},
        )
    statuses: dict[str, str] = {}
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw_points = raw.get("points") if isinstance(raw, dict) else None
        if not isinstance(raw_points, list):
            return GateResult(
                "trajectory-plausibility",
                "fail",
                f"{path.name} has no points list",
                {"files": len(files)},
            )
        trajectory = Trajectory(
            label=path.stem,
            points=tuple(
                (float(str(point[0])), float(str(point[1])))
                for point in raw_points
                if isinstance(point, list) and len(point) == 2
            ),
        )
        try:
            if not envelope:
                return GateResult(
                    "trajectory-plausibility",
                    "fail",
                    "fewer than three PSP-backed observed points for an envelope",
                    {"files": len(files), "psp_points": check.psp_points},
                )
            assessment = assess_trajectory(trajectory, envelope)
        except ValueError as error:
            return GateResult(
                "trajectory-plausibility",
                "fail",
                f"{path.stem}: {error}",
                {"files": len(files)},
            )
        statuses[path.stem] = assessment.status
    if any(status == "extrapolated" for status in statuses.values()):
        return GateResult(
            "trajectory-plausibility",
            "warn",
            "at least one trajectory leaves the observed envelope",
            {"trajectories": statuses},
        )
    return GateResult(
        "trajectory-plausibility",
        "pass",
        "every stored trajectory stays inside the observed envelope",
        {"trajectories": statuses},
    )


def _initial_volume(
    volume: float | None,
    limit: float | None,
    yields: list[dict[str, object]],
    source: str = "",
) -> GateResult:
    """Gate 5: the initial volume is supplied and plausible."""
    if volume is None:
        return GateResult(
            "initial-volume",
            "warn",
            "no initial volume supplied",
            {"observed_max_m3_ha": _observed_max(yields)},
        )
    observed_max = _observed_max(yields)
    if limit is not None and volume > limit:
        return GateResult(
            "initial-volume",
            "fail",
            f"{volume:g} m³/ha exceeds the evidence limit {limit:g}",
            {"volume_m3_ha": volume, "limit_m3_ha": limit},
        )
    if observed_max is not None and volume > observed_max:
        return GateResult(
            "initial-volume",
            "warn",
            f"{volume:g} m³/ha is above the observed maximum {observed_max:g}",
            {"volume_m3_ha": volume, "observed_max_m3_ha": observed_max, "source": source},
        )
    return GateResult(
        "initial-volume",
        "pass",
        f"{volume:g} m³/ha is within the observed evidence",
        {"volume_m3_ha": volume, "observed_max_m3_ha": observed_max, "source": source},
    )


def _observed_max(yields: list[dict[str, object]]) -> float | None:
    """Return the maximum stand-summary volume, when any stands exist."""
    values = [
        float(str(row.get("volume_m3_ha", 0.0)))
        for row in yields
        if row.get("volume_m3_ha") is not None
    ]
    return max(values) if values else None


def _regime_completeness(
    store: SdmdStore,
    au_id: str,
    regimes: list[dict[str, object]],
) -> GateResult:
    """Gate 6: every regime has a constraint and no forbidden flag."""
    constraints = {item.regime_id: item for item in store.constraints_for(au_id)}
    missing: list[str] = []
    findings: list[Problem] = []
    for regime in regimes:
        regime_id = str(regime.get("regime_id", ""))
        constraint = constraints.get(regime_id)
        if constraint is None:
            missing.append(regime_id)
            continue
        findings.extend(
            item
            for item in check_regime(constraint, get_regime(store.regimes, regime_id))
            if item.code not in {"SDMD-CONSTRAINT-DENIED", "SDMD-REGIME-OUTSIDE-SDMD"}
        )
    if missing:
        return GateResult(
            "regime-completeness",
            "fail",
            f"{len(missing)} regime(s) have no constraint: " + ", ".join(missing[:5]),
            {"missing": missing},
        )
    if findings:
        return GateResult(
            "regime-completeness",
            "fail",
            "; ".join(f"{item.code}: {item.message}" for item in findings),
            {"findings": len(findings)},
        )
    return GateResult(
        "regime-completeness",
        "pass",
        f"{len(regimes)} regimes have passing constraints",
        {"regimes": len(regimes)},
    )


def _solver_reduction(preview: dict[str, object]) -> GateResult:
    """Gate 7: the constraints reduce the option space without emptying it."""
    counts = preview.get("counts", {})
    if not isinstance(counts, dict):
        return GateResult("solver-option-reduction", "fail", "no option counts")
    before = int(str(counts.get("regimes_before", 0)))
    after = int(str(counts.get("regimes_after", 0)))
    entries_before = int(str(counts.get("entries_before", 0)))
    entries_after = int(str(counts.get("entries_after", 0)))
    if after == 0:
        return GateResult(
            "solver-option-reduction",
            "fail",
            "the constraints remove every regime",
            dict(counts),
        )
    if after >= before and entries_after >= entries_before:
        return GateResult(
            "solver-option-reduction",
            "warn",
            "the constraints do not reduce the option space",
            dict(counts),
        )
    return GateResult(
        "solver-option-reduction",
        "pass",
        f"{before} → {after} regimes and {entries_before} → {entries_after} entries",
        dict(counts),
    )


def _ui_payload(
    detail: dict[str, object],
    yields: list[dict[str, object]],
    points: dict[str, object],
    regimes: list[dict[str, object]],
    preview: dict[str, object],
) -> GateResult:
    """Gate 8: every AU Explorer payload has the keys the tab reads."""
    required = {
        "detail": ("au_id", "plot_count", "data_gaps", "diagram"),
        "yield": (),
        "points": ("points", "envelope", "diagram"),
        "regimes": ("regime_id", "allowed", "findings", "constraint"),
        "preview": ("counts", "dropped"),
    }
    missing: list[str] = []
    for key in required["detail"]:
        if key not in detail:
            missing.append(f"detail.{key}")
    if not yields:
        missing.append("yield")
    for key in required["points"]:
        if key not in points:
            missing.append(f"sdmd.{key}")
    for row in regimes:
        for key in required["regimes"]:
            if key not in row:
                missing.append(f"regimes.{key}")
                break
    for key in required["preview"]:
        if key not in preview:
            missing.append(f"preview.{key}")
    if missing:
        return GateResult(
            "ui-payload-contract",
            "fail",
            "missing payload keys: " + ", ".join(missing[:8]),
            {"missing": missing},
        )
    return GateResult(
        "ui-payload-contract",
        "pass",
        "detail, yield, SDMD, regime, and preview payloads are complete",
        {"regimes": len(regimes)},
    )
