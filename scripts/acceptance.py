#!/usr/bin/env python3
"""Run the WS4 acceptance checks and print a report.

The checks verify the build against its acceptance criteria:

- ``prototype``: compile the synthetic fixture, simulate it, and check the account values.
- ``optimizer``: run a small search and check that it meets a target within tolerance.
- ``roads``: route a product over a small network.
- ``api``: build a model programmatically and via the file path and check they match.
- ``accounts``: with ``--accounts-report`` and ``--accounts-dataset``, replay the reference's own
  schedule in WS4 and compare the account values per year, which is what isolates the simulation.
- ``parity``: with ``--roads-sample``, compare WS4's least-haul-cost routes to the reference
  implementation's own ``cost_destination.*.csv`` tables, node by node.
- ``builder``: for each ``--case`` (a recipe, a fragment inventory, and a reference matrix
  directory), compile the recipe and compare the compiled matrix to the reference tables.
  No case is required; without one the check is skipped.

The reference matrix directory holds the established CSV table names: ``tracknames.csv``,
``strata.csv``, ``treatments.csv``, ``blocks.csv``, ``features.csv``, ``products.csv``, and
``protoaccounts.csv``. Only the files that are present are compared.

Command-line usage::

    python scripts/acceptance.py
    python scripts/acceptance.py --case recipe.xml fragments.shp reference/

The exit status is 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.model.api import Model
from ws4.model.schema import validate_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.roads.network import RouteNetwork, load_route_tables
from ws4.sim.engine import Simulator

Status = Literal["pass", "fail", "skip"]

DEFAULT_ROOT: Path = Path(__file__).resolve().parent.parent
FIXTURE: Path = DEFAULT_ROOT / "examples" / "synthetic"

# A reference table file name maps to the compiled table and the column that holds its label.
_REFERENCE_TABLES: tuple[tuple[str, str, str | None], ...] = (
    ("tracknames.csv", "tracks", None),
    ("strata.csv", "strata", None),
    ("treatments.csv", "treatments", None),
    ("blocks.csv", "blocks", None),
    ("features.csv", "features", "label"),
    ("products.csv", "products", "label"),
    ("protoaccounts.csv", "protoaccounts", "attribute"),
)


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one acceptance check.

    Attributes
    ----------
    name : str
        Short check identifier.
    status : {"pass", "fail", "skip"}
        The outcome.
    detail : str
        One line that says what was checked or what went wrong.
    """

    name: str
    status: Status
    detail: str


def compare_matrix(compiled_dir: Path, reference_dir: Path) -> list[str]:
    """Compare a compiled dataset to a reference matrix directory.

    Parameters
    ----------
    compiled_dir : Path
        The compiled dataset directory.
    reference_dir : Path
        A directory of reference CSV tables. Only the files that exist are compared.

    Returns
    -------
    list of str
        One message per difference. An empty list means the tables agree.
    """
    problems: list[str] = []
    for filename, table, label_column in _REFERENCE_TABLES:
        reference_path = reference_dir / filename
        if not reference_path.is_file():
            continue
        reference = pd.read_csv(reference_path)
        mine = pd.read_parquet(compiled_dir / f"{table}.parquet")
        if len(mine) != len(reference):
            problems.append(f"{table}: {len(mine)} rows, reference has {len(reference)}")
        if label_column is not None and label_column in mine.columns:
            column = "LABEL" if "LABEL" in reference.columns else label_column.upper()
            if column in reference.columns:
                missing = set(reference[column]) - set(mine[label_column])
                extra = set(mine[label_column]) - set(reference[column])
                if missing:
                    problems.append(f"{table}: {len(missing)} reference labels missing")
                if extra:
                    problems.append(f"{table}: {len(extra)} labels not in the reference")
    return problems


def check_builder(cases: Sequence[tuple[Path, Path, Path]], workdir: Path) -> CheckResult:
    """Compile each case and compare it to its reference matrix.

    Parameters
    ----------
    cases : sequence of tuple
        Each ``(recipe, fragments, reference)`` path triple.
    workdir : Path
        A scratch directory for the compiled datasets.

    Returns
    -------
    CheckResult
        ``skip`` when there are no cases, otherwise ``pass`` or ``fail``.
    """
    if not cases:
        return CheckResult("builder", "skip", "no --case given")
    problems: list[str] = []
    for index, (recipe, fragments, reference) in enumerate(cases):
        compiled = workdir / f"case-{index}"
        build_canonical_dataset(recipe, fragments, compiled)
        issues = validate_dataset(compiled)
        problems.extend(f"case {index}: {problem.message}" for problem in issues)
        problems.extend(
            f"case {index}: {message}" for message in compare_matrix(compiled, reference)
        )
    if problems:
        return CheckResult("builder", "fail", f"{len(problems)} difference(s): {problems[0]}")
    return CheckResult("builder", "pass", f"{len(cases)} case(s) match the reference")


def check_prototype(workdir: Path) -> CheckResult:
    """Compile the synthetic fixture and check the simulator's account values.

    Parameters
    ----------
    workdir : Path
        A scratch directory.

    Returns
    -------
    CheckResult
        ``pass`` when the compiled dataset validates and the simulator returns values.
    """
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", workdir / "dataset"
    )
    problems = [problem.message for problem in validate_dataset(dataset)]
    if problems:
        return CheckResult("prototype", "fail", problems[0])
    schedule = workdir / "schedule.csv"
    schedule.write_text("block_id,treatment,period\n", encoding="utf-8")
    values = Simulator.from_dataset(dataset).run(schedule, years=1, out_dir=workdir / "run")
    if values.empty:
        return CheckResult("prototype", "fail", "no account values")
    return CheckResult("prototype", "pass", f"{len(values)} account values over one year")


def check_optimizer(workdir: Path) -> CheckResult:
    """Run a small search on the fixture and check it meets a target.

    Parameters
    ----------
    workdir : Path
        A scratch directory.

    Returns
    -------
    CheckResult
        ``pass`` when the run's target report says the target is met.
    """
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", workdir / "dataset"
    )
    targets_path = workdir / "targets.yaml"
    targets_path.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    config = OptimizeConfig(years=1, iterations=200, seed=1, targets_path=str(targets_path))
    Optimizer.from_dataset(dataset, config).run(workdir / "run")
    report = pd.read_csv(workdir / "run" / "report_targets.csv")
    statuses = set(report["status"])
    if statuses == {"met"}:
        return CheckResult("optimizer", "pass", "the target is met")
    return CheckResult("optimizer", "fail", f"target status {sorted(statuses)}")


def check_roads(workdir: Path) -> CheckResult:
    """Build a small road network and route a product.

    Parameters
    ----------
    workdir : Path
        A scratch directory.

    Returns
    -------
    CheckResult
        ``pass`` when a destination is found and its route cost is finite.
    """
    segments = pd.DataFrame(
        {
            "from_vertex": [1, 2],
            "to_vertex": [2, 3],
            "length_m": [1000.0, 2000.0],
            "cost": [1.0, 2.0],
        }
    )
    destinations = pd.DataFrame({"dest_id": [3], "vertex_id": [3]})
    linkages = pd.DataFrame({"block_id": [1], "vertex_id": [1]})
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    nearest = network.nearest_destination(1)
    if nearest is None:
        return CheckResult("roads", "fail", "no destination found")
    destination, length = nearest
    cost = network.route_cost(1, destination)
    return CheckResult(
        "roads", "pass", f"block 1 to destination {destination}: {length:.0f} m, {cost:.1f}"
    )


def compare_route_costs(roads_dir: Path) -> tuple[list[str], int]:
    """Compare WS4's least-haul-cost routes to the reference's own per-node haul costs.

    The reference implementation ships ``cost_destination.<mill>.csv`` with ``NODE,SUM_HAUL``: the
    sum of the segment haul rates from that network node to that mill, and ``-1`` where it cannot
    reach it. WS4 computes the same quantity from the same tables, so this compares the **routing**
    rather than the data — a node the reference cannot reach must be one WS4 cannot reach either,
    and where both reach it the sums must agree. Nodes no block is linked to are not compared, since
    WS4 routes from blocks.

    Parameters
    ----------
    roads_dir : Path
        A directory with the network tables and the reference's ``cost_destination.*.csv`` files.

    Returns
    -------
    tuple of (list of str, int)
        One line per difference, at most ten, and the number of node-and-mill pairs compared.
    """
    _, segments, destinations, linkages = load_route_tables(roads_dir)
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    node_column = "NODE" if "NODE" in linkages.columns else "vertex_id"
    block_column = "BLOCK" if "BLOCK" in linkages.columns else "block_id"
    account_column = "ACCOUNT" if "ACCOUNT" in destinations.columns else "name"
    destination_node = "NODE" if "NODE" in destinations.columns else "vertex_id"
    nodes: dict[int, int] = dict(
        zip(linkages[block_column].astype(int), linkages[node_column].astype(int), strict=True)
    )
    accounts: dict[str, int] = dict(
        zip(
            destinations[account_column].astype(str),
            destinations[destination_node].astype(int),
            strict=True,
        )
    )

    differences: list[str] = []
    compared = 0
    for path in sorted(roads_dir.glob("cost_destination.*.csv")):
        label = path.name[len("cost_destination.") : -len(".csv")]
        account = next((name for name in accounts if name.rsplit(".", 1)[-1] == label), None)
        if account is None:
            differences.append(f"{path.name}: no destination account named for {label}")
            continue
        reference = pd.read_csv(path)
        value_column = "SUM_HAUL" if "SUM_HAUL" in reference.columns else reference.columns[1]
        expected = {
            int(node): float(value)
            for node, value in zip(reference.iloc[:, 0], reference[value_column], strict=True)
        }
        for block, node in nodes.items():
            want = expected.get(node)
            if want is None:
                continue
            route = network.route(block, account)
            compared += 1
            if want < 0.0:
                if route is not None:
                    differences.append(
                        f"{label}: node {node} is unreachable in the reference,"
                        f" reachable in WS4 at {route.haul_cost:.6f}"
                    )
            elif route is None:
                differences.append(
                    f"{label}: node {node} is reachable in the reference at {want:.6f},"
                    " unreachable in WS4"
                )
            elif abs(route.haul_cost - want) > 1e-6:
                differences.append(
                    f"{label}: node {node} haul {route.haul_cost:.6f}"
                    f" against the reference {want:.6f}"
                )
    return differences[:10], compared


def _first_present(frame: pd.DataFrame, *names: str) -> str | None:
    """Return the first of the given column names that the frame has, or None.

    Parameters
    ----------
    frame : pandas.DataFrame
        The frame to look in.
    *names : str
        Candidate column names.

    Returns
    -------
    str or None
        The column name, or None when none is present.
    """
    for name in names:
        if name in frame.columns:
            return name
    return None


def compare_account_values(dataset_dir: Path, report_dir: Path) -> tuple[list[str], int]:
    """Compare WS4's account values to a reference report for the same schedule.

    The reference's export is expected in ``report_dir`` as two files: ``schedule.csv`` with the
    block, treatment and year the reference ran, and ``account_values.csv`` with its realized
    account values per year. The schedule is replayed in WS4 exactly as given — which is the point:
    the two tools' optimizers choose different schedules, so comparing the *accounts* of one
    schedule isolates the simulation, and that is what the replacement claim rests on.

    Column names are taken as given where they are unambiguous: the schedule may use
    ``block_id``/``block``, ``treatment``, and ``period``/``year``; the values may use
    ``year``/``period``, ``account``, and ``value``.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset to replay the schedule over.
    report_dir : Path
        A directory with ``schedule.csv`` and ``account_values.csv``.

    Returns
    -------
    tuple of (list of str, int)
        One line per difference, at most ten, and the number of account-year cells compared.
    """
    schedule_frame = pd.read_csv(report_dir / "schedule.csv")
    block = _first_present(schedule_frame, "block_id", "block")
    treatment = _first_present(schedule_frame, "treatment")
    period = _first_present(schedule_frame, "period", "year")
    if block is None or treatment is None or period is None:
        return (["schedule.csv needs block_id, treatment and period columns"], 0)
    schedule = pd.DataFrame(
        {
            "block_id": schedule_frame[block].astype(int),
            "treatment": schedule_frame[treatment].astype(str),
            "period": schedule_frame[period].astype(int),
        }
    )

    reference = pd.read_csv(report_dir / "account_values.csv")
    reference_year = _first_present(reference, "year", "period")
    reference_account = _first_present(reference, "account", "ACCOUNT")
    reference_value = _first_present(reference, "value", "VALUE")
    if reference_year is None or reference_account is None or reference_value is None:
        missing = "account_values.csv needs year, account and value columns"
        return ([missing], 0)
    expected = {
        (int(year), str(account)): float(value)
        for year, account, value in zip(
            reference[reference_year],
            reference[reference_account],
            reference[reference_value],
            strict=True,
        )
    }

    years = int(schedule["period"].max()) + 1 if not schedule.empty else 1
    # The horizon to replay is the reference's own last reported year, which is what its account
    # values cover. Deriving it from the schedule alone under-simulates whenever the reference
    # reports years its last decision does not reach — and every such year is then reported as a
    # difference, which is a spurious failure rather than a finding. A schedule that decides beyond
    # the reported years is the opposite case, and is said out loud instead of silently truncated.
    reported_years = max((year for year, _ in expected), default=-1) + 1
    if reported_years > 0:
        years = reported_years
    values = Simulator.from_dataset(dataset_dir).simulate(schedule, years)
    produced = {
        (int(year), str(account)): float(value)
        for year, account, value in zip(
            values["year"], values["account"], values["value"], strict=True
        )
    }

    differences: list[str] = []
    if not schedule.empty and int(schedule["period"].max()) + 1 > years:
        differences.append(
            f"schedule.csv decides in period {int(schedule['period'].max())}, beyond the "
            f"reference's last reported year {years - 1}"
        )
    compared = 0
    tolerance = 1e-4
    for cell in sorted(set(expected) | set(produced)):
        want = expected.get(cell)
        got = produced.get(cell)
        if want is None or got is None:
            side = "the reference" if got is None else "WS4"
            differences.append(f"{cell[0]} {cell[1]}: only in {side}")
            continue
        compared += 1
        scale = max(abs(want), abs(got), 1.0)
        if abs(got - want) > tolerance * scale:
            differences.append(
                f"{cell[0]} {cell[1]}: WS4 {got:.6f} against the reference {want:.6f}"
            )
    return differences[:10], compared


def check_accounts(report_dir: Path | None, dataset_dir: Path | None) -> CheckResult:
    """Compare WS4's accounts to a reference report, when one has been provided.

    Parameters
    ----------
    report_dir : Path or None
        A directory with the reference's ``schedule.csv`` and ``account_values.csv``, or None.
    dataset_dir : Path or None
        The compiled dataset to replay that schedule over, or None.

    Returns
    -------
    CheckResult
        ``pass`` when every shared account-year agrees, ``fail`` on the first differences, and
        ``skip`` when either input is missing.
    """
    if report_dir is None or dataset_dir is None:
        return CheckResult("accounts", "skip", "needs --accounts-report and --accounts-dataset")
    if not report_dir.is_dir() or not dataset_dir.is_dir():
        return CheckResult("accounts", "fail", "report or dataset is not a directory")
    differences, compared = compare_account_values(dataset_dir, report_dir)
    if differences:
        return CheckResult(
            "accounts",
            "fail",
            f"{len(differences)} difference(s) in {compared} shared cells: {differences[0]}",
        )
    return CheckResult(
        "accounts", "pass", f"WS4 reproduces the reference's {compared} account-year values"
    )


def check_parity(roads_dir: Path | None) -> CheckResult:
    """Compare WS4's routing to the reference implementation's own per-node haul costs.

    Parameters
    ----------
    roads_dir : Path or None
        A sample's ``roads`` directory, or None to skip the comparison.

    Returns
    -------
    CheckResult
        ``pass`` when WS4 agrees with every reference value, ``fail`` on the first differences, and
        ``skip`` when no directory was given.
    """
    if roads_dir is None:
        return CheckResult("parity", "skip", "no --roads-sample given")
    if not roads_dir.is_dir():
        return CheckResult("parity", "fail", f"not a directory: {roads_dir}")
    differences, compared = compare_route_costs(roads_dir)
    if differences:
        return CheckResult(
            "parity",
            "fail",
            f"{len(differences)} difference(s) in {compared} comparisons: {differences[0]}",
        )
    return CheckResult(
        "parity",
        "pass",
        f"WS4 agrees with the reference on all {compared} routed node-and-mill pairs",
    )


def check_api(workdir: Path) -> CheckResult:
    """Build a model programmatically and via the file path and compare them.

    Parameters
    ----------
    workdir : Path
        A scratch directory.

    Returns
    -------
    CheckResult
        ``pass`` when both paths produce the same tables.
    """
    dataset = build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", workdir / "file"
    )
    loaded = Model.from_dataset(dataset)
    written = loaded.write(workdir / "roundtrip")
    for table in ("fragments", "blocks", "features", "products", "accounts"):
        before = pd.read_parquet(dataset / f"{table}.parquet")
        after = pd.read_parquet(written / f"{table}.parquet")
        if not before.reset_index(drop=True).equals(after.reset_index(drop=True)):
            return CheckResult("api", "fail", f"{table} differs after a round-trip")
    return CheckResult("api", "pass", "the programmatic and file models match")


def render(results: Sequence[CheckResult]) -> str:
    """Render the checks as a plain-text table with an overall verdict.

    Parameters
    ----------
    results : sequence of CheckResult
        The check results.

    Returns
    -------
    str
        One row per check, then the overall verdict.
    """
    rows = [f"{'CHECK':<12}{'STATUS':<6}DETAIL"]
    rows.extend(f"{r.name:<12}{r.status.upper():<6}{r.detail}" for r in results)
    failed = any(r.status == "fail" for r in results)
    rows.append("")
    rows.append(
        "OVERALL: FAIL. Investigate the failing checks."
        if failed
        else "OVERALL: PASS. Every check passed."
    )
    return "\n".join(rows)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the acceptance checks from the command line.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when every check passes, and ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description="Run the WS4 acceptance checks.")
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        default=[],
        metavar=("RECIPE", "FRAGMENTS", "REFERENCE"),
        help="a builder case: recipe, fragments, and a reference matrix directory",
    )
    parser.add_argument(
        "--accounts-report",
        type=Path,
        default=None,
        help="a reference export directory with schedule.csv and account_values.csv",
    )
    parser.add_argument(
        "--accounts-dataset",
        type=Path,
        default=None,
        help="the compiled dataset to replay the reference's schedule over",
    )
    parser.add_argument(
        "--roads-sample",
        type=Path,
        default=None,
        help="a sample's roads directory, to compare WS4's routing to the reference's haul costs",
    )
    args = parser.parse_args(argv)
    cases = [(Path(r), Path(f), Path(x)) for r, f, x in args.case]
    with tempfile.TemporaryDirectory() as scratch:
        workdir = Path(scratch)
        results = [
            check_builder(cases, workdir),
            check_prototype(workdir / "proto"),
            check_optimizer(workdir / "opt-run"),
            check_roads(workdir),
            check_api(workdir / "api"),
            check_parity(args.roads_sample),
            check_accounts(args.accounts_report, args.accounts_dataset),
        ]
    print(render(results))
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
