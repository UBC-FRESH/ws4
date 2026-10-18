"""Tests for the acceptance checks: the comparison helper, the renderer, and the skip path."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset

import acceptance as acc

FIXTURE: Path = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


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
    differences, compared, _skipped = acc.compare_route_costs(roads)
    assert differences == []
    assert compared == 2
    assert acc.check_parity(roads).status == "pass"


def test_the_parity_comparison_reports_a_difference(tmp_path: Path) -> None:
    """A reference haul cost that WS4 does not reproduce is a difference, and fails the check."""
    roads = _write_roads(tmp_path / "roads", "1,99.0\n2,2.0\n")
    differences, _, _ = acc.compare_route_costs(roads)
    assert differences
    assert "node 1" in differences[0]
    assert acc.check_parity(roads).status == "fail"


def test_the_parity_comparison_reports_a_reachability_disagreement(tmp_path: Path) -> None:
    """A node the reference calls unreachable but WS4 reaches is a difference."""
    roads = _write_roads(tmp_path / "roads", "1,3.0\n2,-1\n")
    differences, _, _ = acc.compare_route_costs(roads)
    assert differences
    assert "unreachable in the reference" in differences[0]


def test_the_parity_check_skips_and_rejects(tmp_path: Path) -> None:
    """No sample means skip; a path that is not a directory is a failure, not a crash."""
    assert acc.check_parity(None).status == "skip"
    assert acc.check_parity(tmp_path / "absent").status == "fail"


def _write_report(
    root: Path,
    dataset: Path,
    schedule: pd.DataFrame,
    factor: float = 1.0,
    horizon: int | None = None,
) -> Path:
    """Write a reference export produced from WS4 itself, optionally perturbed.

    Parameters
    ----------
    root : Path
        The report directory.
    dataset : Path
        The compiled dataset to replay.
    schedule : pandas.DataFrame
        The schedule to write and replay.
    factor : float
        A multiplier applied to every value, to make the comparison fail on purpose.
    horizon : int or None
        The number of years to report, when a reference reports years its last decision does not
        reach. Defaults to the year after the schedule's last period.

    Returns
    -------
    Path
        The report directory written.
    """
    from ws4.sim.engine import Simulator

    root.mkdir(parents=True, exist_ok=True)
    schedule.to_csv(root / "schedule.csv", index=False)
    years = horizon if horizon is not None else int(schedule["period"].max()) + 1
    values = Simulator.from_dataset(dataset).simulate(schedule, years)
    values = values.assign(value=values["value"] * factor)
    values.to_csv(root / "account_values.csv", index=False)
    return root


def test_the_accounts_comparison_agrees_with_itself(tmp_path: Path) -> None:
    """A report WS4 itself produced must reproduce, cell for cell."""
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    schedule = pd.DataFrame({"block_id": [1, 2], "treatment": ["CC", "CC"], "period": [0, 1]})
    report = _write_report(tmp_path / "report", dataset, schedule)

    differences, compared = acc.compare_account_values(dataset, report)
    assert differences == []
    assert compared > 0
    assert acc.check_accounts(report, dataset).status == "pass"


def test_the_accounts_comparison_reports_a_difference(tmp_path: Path) -> None:
    """A value that WS4 does not reproduce is a difference, and fails the check."""
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    schedule = pd.DataFrame({"block_id": [1], "treatment": ["CC"], "period": [0]})
    report = _write_report(tmp_path / "report", dataset, schedule, factor=2.0)

    differences, _ = acc.compare_account_values(dataset, report)
    assert differences
    assert acc.check_accounts(report, dataset).status == "fail"


def test_the_accounts_comparison_replays_the_reference_horizon(tmp_path: Path) -> None:
    """Years the reference reports but decides nothing in are replayed, not called differences."""
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    schedule = pd.DataFrame({"block_id": [1], "treatment": ["CC"], "period": [0]})
    report = _write_report(tmp_path / "report", dataset, schedule, horizon=3)

    differences, compared = acc.compare_account_values(dataset, report)
    assert differences == []
    assert compared > 0


def test_a_schedule_deciding_past_the_reported_years_is_a_difference(tmp_path: Path) -> None:
    """A decision in a year the reference never reported cannot be compared, and is said so."""
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    schedule = pd.DataFrame({"block_id": [1, 1], "treatment": ["CC", "CC"], "period": [0, 5]})
    report = _write_report(tmp_path / "report", dataset, schedule, horizon=2)

    differences, _ = acc.compare_account_values(dataset, report)
    assert any(
        "beyond the reference's last reported year" in difference for difference in differences
    )


def test_the_accounts_comparison_names_a_missing_column(tmp_path: Path) -> None:
    """A schedule without the columns the comparison needs is reported, not raised."""
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    report = tmp_path / "report"
    report.mkdir()
    pd.DataFrame({"nope": [1]}).to_csv(report / "schedule.csv", index=False)
    pd.DataFrame({"nope": [1]}).to_csv(report / "account_values.csv", index=False)

    differences, compared = acc.compare_account_values(dataset, report)
    assert differences
    assert compared == 0


def test_the_accounts_check_skips_without_inputs() -> None:
    """Either input missing means skip rather than a spurious failure."""
    assert acc.check_accounts(None, None).status == "skip"
    assert acc.check_accounts(Path("x"), None).status == "skip"


def _yield_fixture(
    root: Path, curves: dict[str, list[tuple[float, float]]], *, table: bool = False
) -> tuple[Path, Path]:
    """Write a reference yield XML and a compiled dataset holding the same curves.

    Parameters
    ----------
    root : Path
        A scratch directory.
    curves : dict of str to list of (float, float)
        The ``Y<n>.<species>`` curves to write, as ``(age, yield)`` points.

    Returns
    -------
    tuple of (Path, Path)
        The yield directory and the compiled dataset directory.
    """
    yields = root / "yield"
    yields.mkdir(parents=True, exist_ok=True)
    if table:
        # a 2025-era model states its yields as one table: an age column, then a column per curve
        ages = sorted({age for points in curves.values() for age, _ in points})
        by_name = {name: dict(points) for name, points in curves.items()}
        header = "Age," + ",".join(curves)
        text_rows = [
            f"{age:g}," + ",".join(f"{by_name[name].get(age, 0.0):g}" for name in curves)
            for age in ages
        ]
        body = '<curvetable split=",">' + "\n".join([header, *text_rows]) + "</curvetable>"
        (yields / "sample.xml").write_text(f"<model>{body}</model>")
    else:
        body = "".join(
            f'<curve id="{name}">'
            + "".join(f'<point x="{age:g}" y="{value:g}"/>' for age, value in points)
            + "</curve>"
            for name, points in curves.items()
        )
        (yields / "sample.xml").write_text(f"<model>{body}</model>")

    dataset = root / "compiled"
    dataset.mkdir(parents=True, exist_ok=True)
    rows = [
        {"curve_id": index, "x": age, "y": value}
        for index, points in enumerate(curves.values())
        for age, value in [(0.0, points[0][1]), *points]
    ]
    pd.DataFrame(rows).to_parquet(dataset / "curves.parquet", index=False)
    return yields, dataset


def test_the_yield_comparison_reproduces_the_reference_curves(tmp_path: Path) -> None:
    """Curves compiled from the reference's own points are reported as a match."""
    yields, dataset = _yield_fixture(
        tmp_path,
        {
            "Y1.Conif": [(2.0, 8.28), (7.0, 19.99), (12.0, 32.79)],
            "Y1.Decid": [(2.0, 0.0), (7.0, 0.051), (12.0, 0.17)],
        },
    )
    differences, compared, conflicts = acc.compare_yield_curves(yields, dataset)
    assert differences == []
    assert compared == 6
    assert conflicts == 0
    assert acc.check_growth(yields, dataset).status == "pass"


def test_the_yield_comparison_fails_on_a_changed_value(tmp_path: Path) -> None:
    """A compiled yield that does not match the reference's is a difference."""
    yields, dataset = _yield_fixture(tmp_path, {"Y1.Conif": [(2.0, 8.28), (7.0, 19.99)]})
    table = pd.read_parquet(dataset / "curves.parquet")
    table.loc[table["x"] == 7.0, "y"] = 25.0
    table.to_parquet(dataset / "curves.parquet", index=False)

    differences, _compared, _conflicts = acc.compare_yield_curves(yields, dataset)
    assert differences
    assert "age 7" in differences[0]
    assert acc.check_growth(yields, dataset).status == "fail"


def test_the_yield_comparison_fails_on_a_missing_age(tmp_path: Path) -> None:
    """An age the reference defines that the compiled curve lacks is a difference."""
    yields, dataset = _yield_fixture(tmp_path, {"Y1.Conif": [(2.0, 8.28), (7.0, 19.99)]})
    (yields / "sample.xml").write_text(
        '<model><curve id="Y1.Conif">'
        '<point x="2" y="8.28"/><point x="7" y="19.99"/><point x="40" y="80.0"/>'
        "</curve></model>"
    )
    differences, _compared, _conflicts = acc.compare_yield_curves(yields, dataset)
    assert any("not in curve" in difference for difference in differences)


def test_a_recorded_yield_conflict_is_reported_but_not_a_failure(tmp_path: Path) -> None:
    """The sample's own Decid disagreement at age 7 is named, not counted against WS4."""
    yields, dataset = _yield_fixture(tmp_path, {"Y1.Decid": [(7.0, 0.01), (12.0, 0.05)]})
    table = pd.read_parquet(dataset / "curves.parquet")
    table.loc[table["x"] == 7.0, "y"] = 0.001
    table.to_parquet(dataset / "curves.parquet", index=False)

    differences, _compared, conflicts = acc.compare_yield_curves(yields, dataset)
    assert differences == []
    assert conflicts == 1
    result = acc.check_growth(yields, dataset)
    assert result.status == "pass"
    assert "recorded upstream conflict" in result.detail


def test_a_yield_conflict_outside_the_recorded_one_is_a_failure(tmp_path: Path) -> None:
    """A different curve differing at the same age is not covered by the recorded conflict."""
    yields, dataset = _yield_fixture(tmp_path, {"Y1.Conif": [(7.0, 0.01), (12.0, 0.05)]})
    table = pd.read_parquet(dataset / "curves.parquet")
    table.loc[table["x"] == 7.0, "y"] = 0.001
    table.to_parquet(dataset / "curves.parquet", index=False)

    differences, _compared, _conflicts = acc.compare_yield_curves(yields, dataset)
    assert differences
    assert acc.check_growth(yields, dataset).status == "fail"


def test_the_growth_check_skips_without_inputs() -> None:
    """Either input missing means skip rather than a spurious failure."""
    assert acc.check_growth(None, None).status == "skip"
    assert acc.check_growth(Path("x"), None).status == "skip"
    assert acc.check_growth(None, Path("x")).status == "skip"


def _write_period_report(
    root: Path, dataset: Path, schedule: pd.DataFrame, *, aggregated: bool
) -> Path:
    """Write a reference export in the reference's own period format.

    Parameters
    ----------
    root : Path
        The report directory.
    dataset : Path
        The compiled dataset to simulate.
    schedule : pandas.DataFrame
        The schedule to write and replay.
    aggregated : bool
        Whether a product's period value is the period's total (the reference's convention) or the
        single year's value.

    Returns
    -------
    Path
        The report directory written.
    """
    from ws4.sim.engine import Simulator

    root.mkdir(parents=True, exist_ok=True)
    schedule.to_csv(root / "schedule.csv", index=False)
    values = Simulator.from_dataset(dataset).simulate(schedule, 21)
    series = {
        str(account): group.set_index("year")["value"]
        for account, group in values.groupby("account")
    }
    rows = []
    for account, annual in series.items():
        for period, year in ((0, 0), (1, 10), (2, 20)):
            if period == 0:
                current = float(annual.get(0, 0.0))
            elif aggregated and account.startswith("product."):
                window = annual.loc[year - 9 : year]
                current = float(window.sum())
            else:
                current = float(annual.get(year, 0.0))
            rows.append(
                {
                    "TARGET": account,
                    "PERIOD": period,
                    "YEAR": year,
                    "PERIODWIDTH": 10,
                    "CURRENT": current,
                }
            )
    pd.DataFrame(rows).to_csv(root / "account_values.csv", index=False)
    return root


def test_the_accounts_comparison_applies_the_reference_period_convention(tmp_path: Path) -> None:
    """A report in the reference's period format is compared under its own convention."""
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    schedule = pd.DataFrame({"block_id": [1, 2], "treatment": ["CC", "CC"], "period": [0, 1]})
    report = _write_period_report(tmp_path / "period", dataset, schedule, aggregated=True)

    differences, compared = acc.compare_account_values(dataset, report)
    assert differences == []
    assert compared >= 6
    assert acc.check_accounts(report, dataset).status == "pass"


def test_period_reports_of_annual_values_are_a_difference(tmp_path: Path) -> None:
    """A product reported per year rather than per period does not reproduce, and is reported."""
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    schedule = pd.DataFrame({"block_id": [1, 2], "treatment": ["CC", "CC"], "period": [0, 1]})
    report = _write_period_report(tmp_path / "period", dataset, schedule, aggregated=False)

    differences, _compared = acc.compare_account_values(dataset, report)
    assert differences
    assert acc.check_accounts(report, dataset).status == "fail"


def test_a_reference_table_for_a_destination_the_model_lacks_is_skipped(tmp_path: Path) -> None:
    """A cost table for a mill the model does not declare is named, not counted as a difference."""
    roads = _write_roads(tmp_path / "roads", "1,3.0\n2,2.0\n")
    (roads / "cost_destination.MILL3.csv").write_text("NODE,SUM_HAUL\n1,123.0\n", encoding="utf-8")
    differences, compared, skipped = acc.compare_route_costs(roads)
    assert differences == []
    assert compared > 0
    assert skipped == ["MILL3"]


def test_a_distance_table_is_compared_against_ws4s_shortest_distance(tmp_path: Path) -> None:
    """A table of distances asks a different question from a table of haul sums."""
    roads = _write_roads(tmp_path / "roads", "1,3.0\n2,2.0\n")
    # the fixture's network is 1,000 m then 2,000 m to the mill, and block 1 is linked to node 1
    (roads / "cost_destination.MILL1.csv").write_text(
        "NODE,SUM_LENGTH\n1,3000.0\n", encoding="utf-8"
    )
    differences, compared, _skipped = acc.compare_route_costs(roads)
    assert differences == []
    assert compared == 1


def test_a_distance_table_that_disagrees_is_reported(tmp_path: Path) -> None:
    """A distance the network does not have is a difference, not silently accepted."""
    roads = _write_roads(tmp_path / "roads", "1,3.0\n2,2.0\n")
    (roads / "cost_destination.MILL1.csv").write_text(
        "NODE,SUM_LENGTH\n1,2500.0\n", encoding="utf-8"
    )
    differences, compared, _skipped = acc.compare_route_costs(roads)
    assert compared == 1
    assert differences
    assert "m against the reference" in differences[0]


def test_a_yield_table_is_read_from_a_curvetable(tmp_path: Path) -> None:
    """A 2025-era model states its yields as one table of ages and curves."""
    yields, dataset = _yield_fixture(
        tmp_path,
        {"Y1.Conif": [(2.0, 8.28), (7.0, 19.99)], "Y1.Decid": [(2.0, 0.0), (7.0, 0.051)]},
        table=True,
    )
    differences, compared, conflicts = acc.compare_yield_curves(yields, dataset)
    assert differences == []
    assert compared == 4
    assert conflicts == 0


def test_a_curvetable_value_that_disagrees_is_a_difference(tmp_path: Path) -> None:
    """A table read for its values is compared like any other curve."""
    yields, dataset = _yield_fixture(
        tmp_path, {"Y1.Conif": [(2.0, 8.28), (7.0, 19.99)]}, table=True
    )
    (yields / "sample.xml").write_text(
        '<model><curvetable split=",">Age,Y1.Conif\n2,8.28\n7,99.0\n</curvetable></model>'
    )
    differences, _compared, _conflicts = acc.compare_yield_curves(yields, dataset)
    assert differences
    assert "Y1.Conif" in differences[0]


def test_exclusive_splits_are_read_from_the_reference_model(tmp_path: Path) -> None:
    """A master's destinations and its surplus account come from the reference's own declaration."""
    pin = tmp_path / "C5.pin"
    pin.write_text(
        'control.addExclusiveAccount("product.Yield.managed.Conif", '
        '"product.Mill1.Yield.Conif");\n'
        'control.duplicateAccount("product.Mill1.Yield.Conif", "destination.MILL1", 1);\n'
        'control.duplicateAccount("product.Mill1.Yield.Conif", "route.total.conifer", 1);\n'
        'control.addExclusiveAccount("product.Yield.managed.Conif", '
        '"product.Mill2.Yield.Conif");\n'
        'control.duplicateAccount("product.Mill2.Yield.Conif", "destination.MILL2", 1);\n'
        'control.addExclusiveAccount("product.Yield.managed.Decid", '
        '"product.Mill2.Yield.Decid");\n'
        'control.duplicateAccount("product.Mill2.Yield.Decid", "destination.MILL2", 1);\n'
        'control.addExclusiveAccount("product.Yield.managed.Decid", '
        '"product.unutilized.Decid");\n'
    )
    splits = acc.read_exclusive_splits(pin)
    assert [split.master for split in splits] == [
        "product.Yield.managed.Conif",
        "product.Yield.managed.Decid",
    ]
    conif, decid = splits
    assert conif.destinations == ("destination.MILL1", "destination.MILL2")
    assert conif.surplus == ""
    assert decid.destinations == ("destination.MILL2",)
    assert decid.surplus == "product.unutilized.Decid"


def test_a_reference_assignment_is_read_in_ws4_names(tmp_path: Path) -> None:
    """The exported choice names child accounts, which the split maps back to destinations."""
    table = tmp_path / "exclusive_product.Yield.managed.Decid.csv"
    pd.DataFrame(
        {
            "BLOCK": [1, 2],
            "PERIOD1": ["product.Mill2.Yield.Decid", "product.Mill2.Yield.Decid"],
            "PERIOD2": ["product.Mill2.Yield.Decid", "product.unutilized.Decid"],
        }
    ).to_csv(table, index=False)
    split = acc.ExclusiveSplit(
        master="product.Yield.managed.Decid",
        routed=(("destination.MILL2", "product.Mill2.Yield.Decid"),),
        surplus="product.unutilized.Decid",
    )
    assignment = acc.read_reference_assignment(table, split)
    assert assignment.to_dict("records") == [
        {"block": 1, "period": 1, "destination": "destination.MILL2"},
        {"block": 2, "period": 1, "destination": "destination.MILL2"},
        {"block": 1, "period": 2, "destination": "destination.MILL2"},
        {"block": 2, "period": 2, "destination": "product.unutilized.Decid"},
    ]


def test_an_export_is_found_through_its_own_layout(tmp_path: Path) -> None:
    """The scenario directory and the targets directory are one step from whichever is named."""
    scenario = tmp_path / "base" / "scenario"
    targets = tmp_path / "base" / "targets"
    scenario.mkdir(parents=True)
    targets.mkdir(parents=True)
    (scenario / "schedule.csv").write_text("BLOCK,DELTA,TREATMENT\n1,10,CC\n")
    (targets / "product_Mill1_Yield_Conif.csv").write_text(
        "PERIOD,YEAR,PERIODWIDTH,CURRENT\n1,10,10,5.0\n"
    )
    assert acc._reference_export_dirs(scenario) == (scenario, tmp_path / "base")
    found = acc._find_export_file(acc._reference_export_dirs(scenario), ("schedule.csv",))
    assert found == scenario / "schedule.csv"
    assert acc._reference_period_width(acc._reference_export_dirs(scenario)) == 10


def _destination_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Write a dataset, a sample and an export for the destination check.

    The split is the fixture's own product, so the allocation has something to partition, and
    the export carries the reference's own header and its own choice per block and period.
    """
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "dataset"
    )
    sample = tmp_path / "sample"
    roads = sample / "roads"
    roads.mkdir(parents=True)
    (roads / "vertices.csv").write_text("vertex_id\n1\n2\n3\n", encoding="utf-8")
    (roads / "segments.csv").write_text(
        "segment_id,from_vertex,to_vertex,length_m,haul_cost\n1,1,2,500,0.02\n2,1,3,900,0.03\n",
        encoding="utf-8",
    )
    (roads / "destinations.csv").write_text(
        "name,vertex_id\ndestination.MILL1,2\ndestination.MILL2,3\n", encoding="utf-8"
    )
    (roads / "linkages.csv").write_text("block_id,vertex_id\n1,1\n2,1\n", encoding="utf-8")
    analysis = sample / "analysis"
    analysis.mkdir()
    (analysis / "C5.pin").write_text(
        'control.addExclusiveAccount("product.Volume", "product.Mill1.Volume");\n'
        'control.duplicateAccount("product.Mill1.Volume", "destination.MILL1", 1);\n',
        encoding="utf-8",
    )
    report = tmp_path / "report"
    report.mkdir()
    (report / "schedule.csv").write_text(
        "BLOCK,DELTA,AGE,TYPE,TREATMENT\n1,1,41,MANAGED,CC\n", encoding="utf-8"
    )
    pd.DataFrame(
        {
            "BLOCK": [1],
            "PERIOD1": ["product.Mill1.Volume"],
            "PERIOD2": ["product.Mill1.Volume"],
        }
    ).to_csv(report / "exclusive_product.Volume.csv", index=False)
    return dataset, roads, report


def test_the_destination_check_reads_a_split_and_measures_a_forced_one(tmp_path: Path) -> None:
    """A split read from the model routes the product, and the forced one is checked."""
    dataset, roads, report = _destination_fixture(tmp_path)
    result = acc.check_destinations(roads, report, dataset, tmp_path / "work")
    assert result.status == "pass"
    assert "1 split(s)" in result.detail
    assert "admits one destination" in result.detail
    assert "no reference table" in result.detail


def test_a_forced_mill_product_that_disagrees_fails_the_check(tmp_path: Path) -> None:
    """Where the split leaves one destination the mill product is required, not merely measured."""
    dataset, roads, report = _destination_fixture(tmp_path)
    targets = report / "targets"
    targets.mkdir()
    (targets / "product_Mill1_Volume.csv").write_text(
        "PERIOD,YEAR,PERIODWIDTH,CURRENT\n1,1,1,0.0\n", encoding="utf-8"
    )
    result = acc.check_destinations(roads, report, dataset, tmp_path / "work")
    assert result.status == "fail"
    assert "forced mill product disagrees" in result.detail


def test_a_reference_choice_outside_its_own_split_fails_the_check(tmp_path: Path) -> None:
    """A decision the declared split does not name is reported, not silently mapped away."""
    dataset, roads, report = _destination_fixture(tmp_path)
    pd.DataFrame(
        {
            "BLOCK": [1],
            "PERIOD1": ["product.Mill3.Volume"],
            "PERIOD2": ["product.Mill1.Volume"],
        }
    ).to_csv(report / "exclusive_product.Volume.csv", index=False)
    result = acc.check_destinations(roads, report, dataset, tmp_path / "work")
    assert result.status == "fail"
    assert "outside the reference's own split" in result.detail


def test_the_destination_check_skips_without_its_inputs(tmp_path: Path) -> None:
    """Every input the comparison needs has a skip, so the tool runs where there is no sample."""
    assert acc.check_destinations(None, None, None, tmp_path).status == "skip"
    dataset, _roads, report = _destination_fixture(tmp_path)
    assert acc.check_destinations(None, report, dataset, tmp_path).status == "skip"


def test_an_undeclared_child_keeps_its_own_name(tmp_path: Path) -> None:
    """An assignment naming a child the split does not declare is kept as it came."""
    table = tmp_path / "exclusive.csv"
    pd.DataFrame({"BLOCK": [1], "PERIOD1": ["product.Unheard.Volume"]}).to_csv(table, index=False)
    split = acc.ExclusiveSplit(
        master="product.Volume",
        routed=(("destination.MILL1", "product.Mill1.Volume"),),
    )
    assignment = acc.read_reference_assignment(table, split)
    assert assignment.to_dict("records") == [
        {"block": 1, "period": 1, "destination": "product.Unheard.Volume"}
    ]
