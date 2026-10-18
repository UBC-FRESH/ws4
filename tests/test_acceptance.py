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


def _write_roads(root: Path, reference: str) -> Path:
    """Write a three-node network whose reference cost table holds ``reference``.

    Parameters
    ----------
    root : Path
        The directory to write into.
    reference : str
        The body of ``cost_destination.MILL1.csv``, below its header row.

    Returns
    -------
    Path
        The directory written.
    """
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "SEGMENT": [1, 2],
            "FNODE": [1, 2],
            "TNODE": [2, 3],
            "LENGTH": [1000.0, 2000.0],
            "HAUL": [1.0, 2.0],
            "BUILD": [0.0, 0.0],
            "MAINTAIN": [0.0, 0.0],
        }
    ).to_csv(root / "segments.csv", index=False)
    pd.DataFrame({"NODE": [3], "ACCOUNT": ["destination.MILL1"]}).to_csv(
        root / "destinations.csv", index=False
    )
    pd.DataFrame({"BLOCK": [1, 2], "NODE": [1, 2]}).to_csv(root / "linkages.csv", index=False)
    pd.DataFrame({"NODE": [1, 2, 3], "X": [0.0, 1.0, 2.0], "Y": [0.0, 1.0, 2.0]}).to_csv(
        root / "vertices.csv", index=False
    )
    (root / "cost_destination.MILL1.csv").write_text("NODE,SUM_HAUL\n" + reference)
    return root


def test_the_parity_comparison_agrees_when_the_reference_agrees(tmp_path: Path) -> None:
    """A node the reference cannot reach is one WS4 cannot reach, and the sums match otherwise."""
    roads = _write_roads(tmp_path / "roads", "1,3.0\n2,2.0\n")
    differences, compared = acc.compare_route_costs(roads)
    assert differences == []
    assert compared == 2
    assert acc.check_parity(roads).status == "pass"


def test_the_parity_comparison_reports_a_difference(tmp_path: Path) -> None:
    """A reference haul cost that WS4 does not reproduce is a difference, and fails the check."""
    roads = _write_roads(tmp_path / "roads", "1,99.0\n2,2.0\n")
    differences, _ = acc.compare_route_costs(roads)
    assert differences
    assert "node 1" in differences[0]
    assert acc.check_parity(roads).status == "fail"


def test_the_parity_comparison_reports_a_reachability_disagreement(tmp_path: Path) -> None:
    """A node the reference calls unreachable but WS4 reaches is a difference."""
    roads = _write_roads(tmp_path / "roads", "1,3.0\n2,-1\n")
    differences, _ = acc.compare_route_costs(roads)
    assert differences
    assert "unreachable in the reference" in differences[0]


def test_the_parity_check_skips_and_rejects(tmp_path: Path) -> None:
    """No sample means skip; a path that is not a directory is a failure, not a crash."""
    assert acc.check_parity(None).status == "skip"
    assert acc.check_parity(tmp_path / "absent").status == "fail"
