"""Tests for the acceptance checks: the comparison helper, the renderer, and the skip path."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import acceptance as acc


def _write_compiled(root: Path, labels: list[str]) -> Path:
    """Write a minimal compiled dataset with a features table."""
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"track_id": [1] * len(labels), "label": labels, "curve_id": [1] * len(labels)}
    ).to_parquet(root / "features.parquet", index=False)
    return root


def _write_reference(root: Path, labels: list[str]) -> Path:
    """Write a minimal reference matrix directory with a features table."""
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"TRACK": [1] * len(labels), "LABEL": labels, "CURVE": [1] * len(labels)}).to_csv(
        root / "features.csv", index=False
    )
    return root


def test_compare_matrix_reports_a_match(tmp_path: Path) -> None:
    """Equal tables produce no differences."""
    compiled = _write_compiled(tmp_path / "compiled", ["feature.A", "feature.B"])
    reference = _write_reference(tmp_path / "ref", ["feature.A", "feature.B"])
    assert acc.compare_matrix(compiled, reference) == []


def test_compare_matrix_reports_a_count_difference(tmp_path: Path) -> None:
    """A row-count difference is reported."""
    compiled = _write_compiled(tmp_path / "compiled", ["feature.A"])
    reference = _write_reference(tmp_path / "ref", ["feature.A", "feature.B"])
    problems = acc.compare_matrix(compiled, reference)
    assert any("rows" in problem for problem in problems)


def test_compare_matrix_reports_a_missing_label(tmp_path: Path) -> None:
    """A label present only in the reference is reported."""
    compiled = _write_compiled(tmp_path / "compiled", ["feature.A", "feature.C"])
    reference = _write_reference(tmp_path / "ref", ["feature.A", "feature.B"])
    problems = acc.compare_matrix(compiled, reference)
    assert any("missing" in problem for problem in problems)
    assert any("not in the reference" in problem for problem in problems)


def test_check_builder_skips_without_cases(tmp_path: Path) -> None:
    """No case means the builder check is skipped."""
    result = acc.check_builder([], tmp_path)
    assert result.status == "skip"


def test_render_reports_fail_when_a_check_fails() -> None:
    """A failing check makes the overall verdict FAIL."""
    results = [
        acc.CheckResult("a", "pass", "ok"),
        acc.CheckResult("b", "fail", "bad"),
    ]
    assert "OVERALL: FAIL" in acc.render(results)


def test_render_reports_pass_when_every_check_passes() -> None:
    """An all-pass set makes the overall verdict PASS."""
    results = [acc.CheckResult("a", "pass", "ok")]
    assert "OVERALL: PASS" in acc.render(results)


def test_check_prototype_passes(tmp_path: Path) -> None:
    """The synthetic prototype check passes."""
    assert acc.check_prototype(tmp_path).status == "pass"


def test_check_optimizer_passes(tmp_path: Path) -> None:
    """The synthetic optimizer check meets its target."""
    assert acc.check_optimizer(tmp_path).status == "pass"


def test_check_roads_passes(tmp_path: Path) -> None:
    """The synthetic road check finds a destination."""
    assert acc.check_roads(tmp_path).status == "pass"


def test_check_api_passes(tmp_path: Path) -> None:
    """The programmatic and file models match."""
    assert acc.check_api(tmp_path).status == "pass"


def test_main_passes_without_cases() -> None:
    """The command returns 0 when every check passes and the builder is skipped."""
    assert acc.main([]) == 0


def test_main_fails_on_a_bad_case(tmp_path: Path) -> None:
    """A case that disagrees with its reference makes the command return 1."""
    reference = tmp_path / "ref"
    reference.mkdir()
    pd.DataFrame({"TRACK": [1], "LABEL": ["feature.Nope"], "CURVE": [1]}).to_csv(
        reference / "features.csv", index=False
    )
    code = acc.main(
        [
            "--case",
            str(acc.FIXTURE / "recipe.xml"),
            str(acc.FIXTURE / "fragments.csv"),
            str(reference),
        ]
    )
    assert code == 1
