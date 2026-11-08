"""Tests for the eight SDMD validation gates."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
from ws4.sdmd.api import SdmdStore
from ws4.sdmd.validation import GATE_NAMES, ValidationReport, validate_au

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"
DIAGRAM = (
    Path(__file__).resolve().parents[1]
    / "ws4"
    / "sdmd"
    / "data"
    / "sdmd"
    / "idf-dk3-fdi-illustrative.json"
)
AU = "AU-IDFdk3-FDI"
REAL_AU = "AU-IDFdk3-TSA23-FDI"
REAL_PILOT = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "pilot-tsa23-idfdk3"
PLI_AU = "AU-IDFdk3-TSA23-PLI"
PLI_PILOT = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "pilot-tsa23-idfdk3-pli"


def _store_dir(tmp_path: Path, *, diagram: bool = True) -> Path:
    """Build a store directory from the fixture."""
    root = tmp_path / "sdmd"
    shutil.copytree(FIXTURE, root)
    if diagram:
        shutil.copy(DIAGRAM, root / "diagram.json")
    trajectory = root / "trajectories" / AU / "REG-A-CT60.json"
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(
        json.dumps({"points": [[2400.0, 0.214], [1700.0, 0.543]]}) + "\n",
        encoding="utf-8",
    )
    return root


def _statuses(report: ValidationReport) -> dict[str, str]:
    """Map gate names to statuses from a validation report."""
    return {gate.gate: gate.status for gate in report.gates}


def test_fixture_runs_all_eight_gates(tmp_path: Path) -> None:
    """The fixture is method-ready but warns about the provisional diagram."""
    report = validate_au(SdmdStore.from_directory(_store_dir(tmp_path)), AU)
    assert [gate.gate for gate in report.gates] == list(GATE_NAMES)
    assert report.status == "warn"
    statuses = _statuses(report)
    assert statuses["plot-support"] == "warn"
    assert statuses["density-plausibility"] == "pass"
    assert statuses["sdmd-fit"] == "warn"
    assert statuses["trajectory-plausibility"] == "pass"
    assert statuses["initial-volume"] == "warn"
    assert statuses["regime-completeness"] == "pass"
    assert statuses["solver-option-reduction"] == "pass"
    assert statuses["ui-payload-contract"] == "pass"


def test_initial_volume_rejects_863(tmp_path: Path) -> None:
    """The KC 863 m3/ha value is rejected against an 800 m3/ha limit."""
    report = validate_au(
        SdmdStore.from_directory(_store_dir(tmp_path)),
        AU,
        initial_volume_m3_ha=863.0,
        initial_volume_limit_m3_ha=800.0,
    )
    gate = next(item for item in report.gates if item.gate == "initial-volume")
    assert gate.status == "fail"
    assert "863" in gate.detail
    assert report.status == "fail"


def test_initial_volume_flags_1173(tmp_path: Path) -> None:
    """The 1,173 m3/ha value is flagged above the observed maximum."""
    report = validate_au(
        SdmdStore.from_directory(_store_dir(tmp_path)),
        AU,
        initial_volume_m3_ha=1173.0,
        initial_volume_limit_m3_ha=2000.0,
    )
    gate = next(item for item in report.gates if item.gate == "initial-volume")
    assert gate.status == "warn"
    assert "1173" in gate.detail


def test_initial_volume_within_evidence_passes(tmp_path: Path) -> None:
    """A value inside the observed range passes."""
    report = validate_au(
        SdmdStore.from_directory(_store_dir(tmp_path)),
        AU,
        initial_volume_m3_ha=500.0,
        initial_volume_limit_m3_ha=800.0,
    )
    assert next(item for item in report.gates if item.gate == "initial-volume").status == "pass"


def test_missing_diagram_fails_the_fit_gate(tmp_path: Path) -> None:
    """A store without a diagram cannot claim an SDMD fit."""
    report = validate_au(SdmdStore.from_directory(_store_dir(tmp_path, diagram=False)), AU)
    assert next(item for item in report.gates if item.gate == "sdmd-fit").status == "fail"


def test_impossible_trajectory_fails(tmp_path: Path) -> None:
    """A path that gains density and volume at once fails the trajectory gate."""
    root = _store_dir(tmp_path)
    (root / "trajectories" / AU / "REG-A-CT60.json").write_text(
        json.dumps({"points": [[2400.0, 0.214], [3000.0, 5.0]]}) + "\n",
        encoding="utf-8",
    )
    report = validate_au(SdmdStore.from_directory(root), AU)
    gate = next(item for item in report.gates if item.gate == "trajectory-plausibility")
    assert gate.status == "fail"
    assert "SDMD-TRAJECTORY-DENSITY" in gate.detail


def test_missing_constraint_fails_completeness(tmp_path: Path) -> None:
    """Every regime needs a constraint row."""
    root = _store_dir(tmp_path)
    frame = pd.read_csv(root / "au_constraints.csv")
    frame = frame.loc[frame["regime_id"] != "REG-A-CT60"]
    frame.to_csv(root / "au_constraints.csv", index=False)
    report = validate_au(SdmdStore.from_directory(root), AU)
    gate = next(item for item in report.gates if item.gate == "regime-completeness")
    assert gate.status == "fail"
    assert "REG-A-CT60" in gate.detail


def test_no_option_reduction_warns(tmp_path: Path) -> None:
    """A constraint set that removes nothing is a warning, not a pass."""
    root = _store_dir(tmp_path)
    frame = pd.read_csv(root / "au_constraints.csv")
    frame["required_sdmd_zone"] = ""
    frame.to_csv(root / "au_constraints.csv", index=False)
    report = validate_au(SdmdStore.from_directory(root), AU)
    gate = next(item for item in report.gates if item.gate == "solver-option-reduction")
    assert gate.status == "warn"


def test_report_serializes(tmp_path: Path) -> None:
    """The validation report is JSON-serializable for a run record."""
    report = validate_au(SdmdStore.from_directory(_store_dir(tmp_path)), AU)
    payload = report.to_dict()
    json.dumps(payload)
    assert payload["status"] == "warn"
    gates = payload["gates"]
    assert isinstance(gates, list)
    assert len(gates) == 8


def test_cli_validate_exit_codes(tmp_path: Path) -> None:
    """The CLI exits zero for warnings and one for a failed gate."""
    from typer.testing import CliRunner
    from ws4.cli import app

    root = _store_dir(tmp_path)
    runner = CliRunner()
    warned = runner.invoke(app, ["sdmd", "validate", "--sdmd-dir", str(root), "--au", AU])
    assert warned.exit_code == 0, warned.output
    assert "plot-support" in warned.output
    failed = runner.invoke(
        app,
        [
            "sdmd",
            "validate",
            "--sdmd-dir",
            str(root),
            "--au",
            AU,
            "--initial-volume",
            "863",
            "--initial-volume-limit",
            "800",
        ],
    )
    assert failed.exit_code == 1
    assert "863" in failed.output


def test_plot_support_flags_a_synthetic_point(tmp_path: Path) -> None:
    """A synthetic point is a named warning, not a silent pass."""
    report = validate_au(SdmdStore.from_directory(_store_dir(tmp_path)), AU)
    gate = next(item for item in report.gates if item.gate == "plot-support")
    assert gate.status == "warn"
    assert gate.evidence["synthetic_points"] == 1
    assert "synthetic" in gate.detail


def test_plot_support_fails_without_a_reviewed_psp_plot(tmp_path: Path) -> None:
    """A point that claims PSP but has no reviewed PSP plot fails the gate."""
    root = _store_dir(tmp_path)
    frame = pd.read_csv(root / "plots.csv")
    frame.loc[frame["plot_id"] == "PLOT-A02", "sources"] = "synthetic"
    frame.to_csv(root / "plots.csv", index=False)
    report = validate_au(SdmdStore.from_directory(root), AU)
    gate = next(item for item in report.gates if item.gate == "plot-support")
    assert gate.status == "fail"
    assert "no reviewed PSP plot at age 60" in gate.detail


def test_trajectory_gate_needs_three_psp_points(tmp_path: Path) -> None:
    """Synthetic points do not make an observed envelope."""
    root = _store_dir(tmp_path)
    frame = pd.read_csv(root / "sdmd_points.csv")
    frame.loc[frame["sdmd_id"].isin(["SDMD-A02", "SDMD-A03", "SDMD-A04"]), "source"] = "synthetic"
    frame.to_csv(root / "sdmd_points.csv", index=False)
    report = validate_au(SdmdStore.from_directory(root), AU)
    gate = next(item for item in report.gates if item.gate == "trajectory-plausibility")
    assert gate.status == "fail"
    assert "fewer than three PSP-backed" in gate.detail


def test_real_tsa23_pilot_passes_the_observed_gates() -> None:
    """The public TSA 23 IDFdk3 extract passes plot, density, and regime support."""
    report = validate_au(SdmdStore.from_directory(REAL_PILOT), REAL_AU)
    statuses = _statuses(report)
    assert statuses["plot-support"] == "pass"
    assert statuses["density-plausibility"] == "pass"
    assert statuses["regime-completeness"] == "pass"
    assert statuses["solver-option-reduction"] == "pass"
    gate = next(item for item in report.gates if item.gate == "plot-support")
    assert gate.evidence["psp_points"] == 11
    assert gate.evidence["synthetic_points"] == 0
    assert statuses["sdmd-fit"] == "pass"
    assert statuses["initial-volume"] == "pass"
    assert statuses["trajectory-plausibility"] == "warn"


def test_real_tsa23_pilot_has_two_stored_paths() -> None:
    """The real AU stores the untreated and CT60 FVS paths with source metadata."""
    store = SdmdStore.from_directory(REAL_PILOT)
    for regime in ("REG-A-UNTREATED", "REG-A-CT60"):
        payload = store.trajectory(REAL_AU, regime)
        assert payload["status"] in {"inside", "extrapolated"}
        assert payload["points"]
        assert "multi-cluster" in str(payload.get("source", ""))


def test_real_tsa23_pli_pilot_passes_the_observed_gates() -> None:
    """The public TSA 23 IDFdk3 lodgepole pine extract passes plot and density support."""
    store = SdmdStore.from_directory(PLI_PILOT)
    report = validate_au(store, PLI_AU)
    statuses = _statuses(report)
    assert statuses["plot-support"] == "pass"
    assert statuses["density-plausibility"] == "pass"
    assert statuses["initial-volume"] == "pass"
    assert statuses["regime-completeness"] == "pass"
    gate = next(item for item in report.gates if item.gate == "plot-support")
    assert gate.evidence["psp_points"] == 11
    assert gate.evidence["synthetic_points"] == 0
    assert store.diagram is not None
    assert store.diagram.diagram_id == "idf-dk3-pli-natural"
    assert store.diagram.species_group == "PLI"


def test_real_tsa23_pli_pilot_has_two_stored_paths() -> None:
    """The PLI AU stores the untreated and CT60 FVS paths."""
    store = SdmdStore.from_directory(PLI_PILOT)
    for regime in ("REG-A-UNTREATED", "REG-A-CT60"):
        payload = store.trajectory(PLI_AU, regime)
        assert payload["status"] in {"inside", "extrapolated"}
        assert payload["points"]
        assert "multi-cluster" in str(payload.get("source", ""))
