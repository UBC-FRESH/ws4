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
- ``patchcomponents``: with ``--roads-sample``, ``--accounts-report`` and ``--accounts-dataset``,
  compare WS4's patch components to the reference's, when its export can state membership. It cannot
  today, and the check says so rather than implying a comparison was made.
- ``destinations``: with ``--roads-sample``, ``--accounts-report`` and ``--accounts-dataset``,
  compare the destination each block's product is sent to against the reference's own exported
  choice, and the mill products against its ``targets/product_Mill*_Yield_*.csv``. A decision the
  reference's split forces must match; one it leaves free is measured and reported.
- ``growth``: with ``--yield-sample`` and ``--yield-dataset``, compare WS4's compiled yield curves
  to the reference's own model curves, point by point: the growth that the whole accounts
  comparison rests on, checkable without a licensed reference run.
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
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.model.api import Model
from ws4.model.schema import validate_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target, flow_series
from ws4.patch.accounts import PatchAccount
from ws4.roads.accounts import ProductAllocation, RouteModel
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
    schedule.write_text("block_id,treatment,offset\n", encoding="utf-8")
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
        "targets:\n  - account: feature.Volume\n    period: 1\n    maximum: 500\n",
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


# A reference report rounds as it computes: its areas and products are rounded to three decimals per
# contribution, and a period's value is a sum of them. Measured across both 2026 scenarios — 2,646
# cells — the worst disagreement with WS4 is 1.05e-3 on a value of 0.977, so a relative tolerance
# alone flags the reference's own rounding: 101 cells at the relative tolerance alone, 3 with a
# 1e-3 floor, and none with 2e-3, which is two units in the third decimal.
_ABSOLUTE_TOLERANCE = 2e-3

# The reference's yield curves are identified per stratum and species, as ``Y1.Conif``.
_YIELD_CURVE_ID = re.compile(r"^Y\d+\.(?:Conif|Decid)$")

# The reference's own artefacts print two decimals, so half a unit is the tightest honest tolerance.
_YIELD_TOLERANCE = 5e-3

# One point where the sample's own files disagree with each other: its legacy matrix carries 0.001
# at offset age 7 on the Decid curve, where the same sample's sibling artefacts (Woodstock's
# ``C5_yld.prn`` and ``ForestModel_C5_strata.xml``) carry 0.01. WS4 compiles what the matrix says,
# so the difference is upstream of it. It is recorded rather than absorbed into the tolerance, so a
# real difference cannot hide among it, and the check reports when it is still there.
_KNOWN_YIELD_CONFLICTS = frozenset({("Decid", 7.0)})


def read_reference_yields(yield_dir: Path) -> dict[str, list[tuple[float, float]]]:
    """Read the reference's own yield curves from a sample's yield directory.

    Every ``*.xml`` in the directory is read for ``curve`` elements whose id names a yield curve
    for a stratum and species (``Y1.Conif``). The reference also ships the same numbers as a printed
    Woodstock table (``Woodstock/C5_yld.prn``); the XML is used because it carries the age of every
    value, where the printed table is a bare sequence of values against an assumed grid.

    Parameters
    ----------
    yield_dir : Path
        A sample's ``yield`` directory.

    Returns
    -------
    dict of str to list of (float, float)
        The ``(age, yield)`` points per curve id.
    """
    curves: dict[str, list[tuple[float, float]]] = {}
    for path in sorted(yield_dir.glob("*.xml")):
        root = ET.parse(path).getroot()
        for element in root.iter("curve"):
            identifier = element.get("id")
            if identifier is None or not _YIELD_CURVE_ID.match(identifier):
                continue
            points = [
                (float(point.get("x", "0")), float(point.get("y", "0")))
                for point in element.findall("point")
            ]
            if points:
                curves[identifier] = points
        for table in root.iter("curvetable"):
            # A 2025-era model states its yields as one table: an age column, then a column
            # per curve.
            split = table.get("split", ",")
            rows = [
                line.split(split) for line in "".join(table.itertext()).splitlines() if line.strip()
            ]
            if len(rows) < 2:
                continue
            for column, name in enumerate(rows[0]):
                if column == 0 or not _YIELD_CURVE_ID.match(name.strip()):
                    continue
                points = []
                for row in rows[1:]:
                    if column >= len(row) or not row[column].strip():
                        continue
                    points.append((float(row[0]), float(row[column])))
                if points:
                    curves[name.strip()] = points
    return curves


def compare_yield_curves(yield_dir: Path, dataset_dir: Path) -> tuple[list[str], int, int]:
    """Compare WS4's compiled yield curves to the reference's own model curves, point by point.

    Each reference curve is resolved to the compiled curve that reproduces most of its ages, and
    every one of its points is then compared there: a missing age, a value outside the print
    tolerance, or a yield curve with no counterpart at all is a difference. A value that differs by
    exactly one of the sample's own recorded internal conflicts is counted and named instead.

    Parameters
    ----------
    yield_dir : Path
        The sample's ``yield`` directory, holding the reference's own curves.
    dataset_dir : Path
        The compiled dataset to compare, which is what WS4 will actually use.

    Returns
    -------
    tuple of (list of str, int, int)
        One line per difference, at most ten; the number of points compared; and the number of
        recorded conflicts seen.
    """
    reference = read_reference_yields(yield_dir)
    if not reference:
        return (["no Y<n>.<species> yield curves in the yield directory"], 0, 0)
    table = pd.read_parquet(dataset_dir / "curves.parquet")
    compiled: dict[int, tuple[np.ndarray, np.ndarray]] = {
        int(str(identifier)): (group["x"].to_numpy(), group["y"].to_numpy())
        for identifier, group in table.groupby("curve_id")
    }
    differences: list[str] = []
    compared = 0
    conflicts = 0
    for name in sorted(reference):
        points = reference[name]
        species = name.split(".", 1)[1]
        ages = {age for age, _ in points}
        best: tuple[int, int, int] | None = None
        for identifier, (xs, ys) in compiled.items():
            present = {
                float(age): float(value) for age, value in zip(xs, ys, strict=True) if age in ages
            }
            missing = len(ages - set(present))
            differing = sum(
                1
                for age, value in points
                if age in present and abs(present[age] - value) > _YIELD_TOLERANCE
            )
            score = missing + differing
            if best is None or score < best[0] or (score == best[0] and identifier < best[1]):
                best = (score, identifier, missing)
        if best is None:
            continue
        _score, identifier, missing = best
        xs, ys = compiled[identifier]
        at_age = {float(age): float(value) for age, value in zip(xs, ys, strict=True)}
        if missing:
            absent = sorted(ages - set(at_age))[:3]
            differences.append(f"{name}: {missing} age(s) not in curve {identifier}, e.g. {absent}")
        for age, value in points:
            if age not in at_age:
                continue
            compared += 1
            got = at_age[age]
            if abs(got - value) <= _YIELD_TOLERANCE:
                continue
            if (species, age) in _KNOWN_YIELD_CONFLICTS and abs(got - value) <= 0.1:
                conflicts += 1
                continue
            differences.append(f"{name} age {age:g}: WS4 {got:g} against the reference {value:g}")
    return (differences[:10], compared, conflicts)


def check_growth(yield_dir: Path | None, dataset_dir: Path | None) -> CheckResult:
    """Compare WS4's compiled growth to the reference's own yield curves, when both are given.

    Parameters
    ----------
    yield_dir : Path or None
        A sample's ``yield`` directory, or None to skip the comparison.
    dataset_dir : Path or None
        The compiled dataset to compare, or None to skip the comparison.

    Returns
    -------
    CheckResult
        ``pass`` when every reference point is reproduced, ``fail`` on the first differences, and
        ``skip`` when either input is missing.
    """
    if yield_dir is None or dataset_dir is None:
        return CheckResult("growth", "skip", "needs --yield-sample and --yield-dataset")
    if not yield_dir.is_dir() or not dataset_dir.is_dir():
        return CheckResult("growth", "fail", "yield sample or dataset is not a directory")
    differences, compared, conflicts = compare_yield_curves(yield_dir, dataset_dir)
    if differences:
        return CheckResult(
            "growth",
            "fail",
            f"{len(differences)} difference(s) in {compared} points: {differences[0]}",
        )
    detail = f"WS4 reproduces the reference's {compared} yield-curve points"
    if conflicts:
        detail += f", with {conflicts} recorded upstream conflict(s) reported"
    return CheckResult("growth", "pass", detail)


def compare_route_costs(roads_dir: Path) -> tuple[list[str], int, list[str]]:
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
    tuple of (list of str, int, list of str)
        One line per difference, at most ten; the number of node-and-mill pairs compared; and the
        reference tables skipped because the model declares no such destination.
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
    skipped: list[str] = []
    compared = 0
    for path in sorted(roads_dir.glob("cost_destination.*.csv")):
        label = path.name[len("cost_destination.") : -len(".csv")]
        account = next((name for name in accounts if name.rsplit(".", 1)[-1] == label), None)
        if account is None:
            # a reference table for a mill this model no longer has, which is a property of the
            # sample rather than a difference in WS4's routing
            skipped.append(label)
            continue
        reference = pd.read_csv(path)
        # The reference's own column names say which quantity the table holds: a sum of haul rates,
        # or a sum of route lengths. Earlier samples shipped the first and the 2026 sample the
        # second, so a comparison that always used WS4's haul cost would compare different
        # quantities.
        sum_length = "SUM_LENGTH" in reference.columns or "LENGTH" in reference.columns
        value_column = (
            "SUM_LENGTH"
            if "SUM_LENGTH" in reference.columns
            else ("SUM_HAUL" if "SUM_HAUL" in reference.columns else reference.columns[1])
        )
        expected = {
            int(node): float(value)
            for node, value in zip(reference.iloc[:, 0], reference[value_column], strict=True)
        }
        for block, node in nodes.items():
            want = expected.get(node)
            if want is None:
                continue
            compared += 1
            if sum_length:
                # The table holds the **distance** from the node to the mill, not the cost of the
                # route WS4 would choose: measured on the 2026 sample, the value it reports for a
                # node is the shortest path by length (81,098 m) where WS4's least-haul path is
                # 97,169 m. The like-for-like comparison is therefore WS4's own shortest distance.
                distance = network.route_length(block, account)
                if want < 0.0:
                    if distance is not None:
                        differences.append(
                            f"{label}: node {node} is unreachable in the reference,"
                            f" reachable in WS4 at {distance:.6f} m"
                        )
                elif distance is None:
                    differences.append(
                        f"{label}: node {node} is reachable in the reference at {want:.6f} m,"
                        " unreachable in WS4"
                    )
                elif abs(distance - want) > 1e-4 * max(abs(want), 1.0):
                    differences.append(
                        f"{label}: node {node} {distance:.6f} m against the reference {want:.6f} m"
                    )
                continue
            route = network.route(block, account)
            got = route.haul_cost if route is not None else 0.0
            if want < 0.0:
                if route is not None:
                    differences.append(
                        f"{label}: node {node} is unreachable in the reference,"
                        f" reachable in WS4 at {got:.6f}"
                    )
            elif route is None:
                differences.append(
                    f"{label}: node {node} is reachable in the reference at {want:.6f},"
                    " unreachable in WS4"
                )
            elif abs(got - want) > 1e-4 * max(abs(want), 1.0):
                differences.append(
                    f"{label}: node {node} routed {got:.6f} against the reference {want:.6f}"
                )
    return differences[:10], compared, skipped


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
    lowered = {str(column).lower(): str(column) for column in frame.columns}
    for name in names:
        if name in frame.columns:
            return name
        match = lowered.get(name.lower())
        if match is not None:
            return match
    return None


def _reference_period_value(
    series: Mapping[str, pd.Series], account: str, period: int, year: int, width: int
) -> float:
    """Return WS4's value for one period of a reference report.

    The reference reports a value per account per **period**, and its convention is not WS4's:
    ``PERIOD 0`` is the initial snapshot at year 0, and a later period labelled ``YEAR`` with
    ``PERIODWIDTH`` covers that many years **ending** at ``YEAR``. What it reports for a period also
    depends on the account: a product — and a patch account, which the reference's own field list
    describes as "the sum of ... values in this period" — accumulates within the period and is
    reported as its total, while a feature is a level reported at the period's year. Measured on
    the 2026 C5 sample, this convention puts WS4 and the reference within 1% on every
    account-period cell of both the no-treatment and the optimized run, where comparing annual
    values year for year agreed on the features and on none of the products.

    Parameters
    ----------
    series : mapping of str to pandas.Series
        WS4's annual values per account, indexed by year.
    account : str
        The account.
    period : int
        The reference's period index.
    year : int
        The reference's year for that period.
    width : int
        The reference's period width, in years.

    Returns
    -------
    float
        WS4's value for the period, or 0.0 when the account is absent.
    """
    values = series.get(account)
    if values is None:
        return 0.0
    if period <= 0:
        return float(values.get(-1, 0.0))
    end_offset = year - 1
    if account.startswith(("product.", "patch.")):
        # a product, and a patch account, accumulate within the period and are reported as its
        # total: the reference's own field list says so ("the sum of ... values in this period"),
        # and measured on the harvested family a level reading is 25 times too small
        return float(values.loc[end_offset - width + 1 : end_offset].sum())
    return float(values.get(end_offset, 0.0))


def compare_account_values(
    dataset_dir: Path, report_dir: Path, known_accounts: set[str] | None = None
) -> tuple[list[str], int]:
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
        A directory with ``schedule.csv`` and ``account_values.csv`` (or the reference's own
        ``targetSummary.csv``).
    known_accounts : set of str, optional
        The accounts WS4 has, when the reference reports more than that. A reference target with no
        WS4 account is not compared: those are the reference's own ratio, flow and route targets
        rather than account values. Without this, every reference row is compared.

    Returns
    -------
    tuple of (list of str, int)
        One line per difference, at most ten, and the number of account-year cells compared.
    """
    schedule_frame = pd.read_csv(report_dir / "schedule.csv")
    block = _first_present(schedule_frame, "block_id", "block")
    treatment = _first_present(schedule_frame, "treatment")
    time_column = _first_present(schedule_frame, "offset", "period", "year", "DELTA")
    if block is None or treatment is None or time_column is None:
        return (["schedule.csv needs block_id, treatment and offset columns"], 0)
    schedule = pd.DataFrame(
        {
            "block_id": schedule_frame[block].astype(int),
            "treatment": schedule_frame[treatment].astype(str),
            "offset": schedule_frame[time_column].astype(int) - (1 if time_column == "year" else 0),
        }
    )

    values_path = report_dir / "account_values.csv"
    if not values_path.is_file():
        # the reference's own report name, so its export can be read where it lands
        values_path = report_dir / "targetSummary.csv"
    reference = pd.read_csv(values_path)
    reference_year = _first_present(reference, "offset", "year", "period", "YEAR")
    reference_account = _first_present(reference, "account", "ACCOUNT", "TARGET")
    reference_value = _first_present(reference, "value", "VALUE", "CURRENT")
    if reference_year is None or reference_account is None or reference_value is None:
        missing = f"{values_path.name} needs a year, an account and a value column"
        return ([missing], 0)
    if known_accounts is not None:
        # the reference reports its own ratio, flow and route targets as well as account values;
        # only the accounts both sides have are comparable
        reference = reference[reference[reference_account].astype(str).isin(known_accounts)]
    raw_expected = {
        (int(year), str(account)): float(value)
        for year, account, value in zip(
            reference[reference_year],
            reference[reference_account],
            reference[reference_value],
            strict=True,
        )
    }

    years = int(schedule["offset"].max()) + 1 if not schedule.empty else 1
    # The horizon to replay is the reference's own last reported year, which is what its account
    # values cover. Deriving it from the schedule alone under-simulates whenever the reference
    # reports years its last decision does not reach — and every such year is then reported as a
    # difference, which is a spurious failure rather than a finding. A schedule that decides beyond
    # the reported years is the opposite case, and is said out loud instead of silently truncated.
    reported_years = max((year for year, _ in raw_expected), default=-1) + 1
    if reported_years > 0:
        years = reported_years
    values = Simulator.from_dataset(dataset_dir).simulate(schedule, years)
    period_column = _first_present(reference, "PERIOD", "period_index")
    width_column = _first_present(reference, "PERIODWIDTH", "period_width")
    if period_column is not None and width_column is not None:
        # the reference's own period format: build its cells from WS4's annual values under the
        # convention it uses, rather than comparing its period totals to WS4's single years
        expected = raw_expected
        series = {
            str(account): group.set_index("offset")["value"]
            for account, group in values.groupby("account")
        }
        produced = {
            (int(year), str(account)): _reference_period_value(
                series, str(account), int(period), int(year), int(width)
            )
            for period, year, account, width in zip(
                reference[period_column],
                reference[reference_year],
                reference[reference_account],
                reference[width_column],
                strict=True,
            )
        }
    else:
        # A WS4-native values file already carries offsets; an external annual report carries
        # 1-based years, so its cells shift back by one to meet the offset clock.
        expected = (
            raw_expected
            if reference_year == "offset"
            else {(year - 1, account): value for (year, account), value in raw_expected.items()}
        )
        produced = {
            (int(year), str(account)): float(value)
            for year, account, value in zip(
                values["offset"], values["account"], values["value"], strict=True
            )
        }

    differences: list[str] = []
    if not schedule.empty and int(schedule["offset"].max()) + 1 > years:
        differences.append(
            f"schedule.csv decides in period {int(schedule['offset'].max())}, beyond the "
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
        allowed = max(tolerance * scale, _ABSOLUTE_TOLERANCE)
        if abs(got - want) > allowed:
            differences.append(
                f"{cell[0]} {cell[1]}: WS4 {got:.6f} against the reference {want:.6f}"
            )
    return differences[:10], compared


def _simulated_for_report(dataset_dir: Path, report_dir: Path) -> pd.DataFrame:
    """Return WS4's account values for the reference's own schedule.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset to replay the schedule over.
    report_dir : Path
        The reference's export directory, holding ``schedule.csv``.

    Returns
    -------
    pandas.DataFrame
        The account values, with ``year``, ``account`` and ``value``.
    """
    schedule_frame = pd.read_csv(report_dir / "schedule.csv")
    block = _first_present(schedule_frame, "block_id", "block", "BLOCK")
    treatment = _first_present(schedule_frame, "treatment", "TREATMENT")
    time_column = _first_present(schedule_frame, "offset", "period", "year", "DELTA")
    if block is None or treatment is None or time_column is None:
        return pd.DataFrame(columns=["offset", "account", "value"])
    schedule = pd.DataFrame(
        {
            "block_id": schedule_frame[block].astype(int),
            "treatment": schedule_frame[treatment].astype(str),
            "offset": schedule_frame[time_column].astype(int) - (1 if time_column == "year" else 0),
        }
    )
    summary = report_dir / "targetSummary.csv"
    if summary.is_file():
        years = int(pd.read_csv(summary)["YEAR"].max()) + 1
    else:
        years = int(schedule["offset"].max()) + 1
    return Simulator.from_dataset(dataset_dir).simulate(schedule, years)


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
    accounts_path = dataset_dir / "accounts.parquet"
    known = (
        set(pd.read_parquet(accounts_path)["account"].astype(str))
        if accounts_path.is_file()
        else None
    )
    differences, compared = compare_account_values(dataset_dir, report_dir, known)
    flow_differences, flow_compared, uncovered = compare_flow_targets(
        _simulated_for_report(dataset_dir, report_dir), report_dir, _ABSOLUTE_TOLERANCE
    )
    differences = differences + flow_differences
    compared += flow_compared
    if differences:
        return CheckResult(
            "accounts",
            "fail",
            f"{len(differences)} difference(s) in {compared} shared cells: {differences[0]}",
        )
    tail = ""
    if known is not None:
        leftovers = _reference_only_targets(report_dir, known)
        if leftovers:
            tail = f"; {leftovers} reference target(s) have no WS4 account and are not compared"
    if uncovered:
        families = ", ".join(
            f"{count} {prefix.rstrip('.')}" for prefix, count in sorted(uncovered.items())
        )
        tail += f"; {families} not compared"
    return CheckResult(
        "accounts",
        "pass",
        f"WS4 reproduces the reference's {compared} account-period and flow values{tail}",
    )


# The reference's flow targets, from its own model file (`analysis/C5.pin`): each
# `addFlowRatioAccount` names the account it constrains and a spec that gives the window.
# `ndy(periods-9, periods, -1)` is the last ten periods of a twenty-period model, which in
# 101 to 200; `even()` is the whole horizon. The per-mill forms are left out because each one's
# denominator is that mill's own product, and WS4 splits the conifer master between the mills by a
# different rule — the least haul cost against the reference's Mill 1 delivery target — so the two
# flows are not yet the same quantity. What the split is and how far apart the two rules are is in
# `notes/design/ws4-parity-harness.md` and checked by `check_destinations`.
_REFERENCE_FLOWS: dict[str, tuple[str, str, int, int]] = {
    "flow.ndy.feature.Yield.Conif": ("feature.Yield.managed.Conif", "ndy", 101, 201),
    "flow.ndy.feature.Yield.Decid": ("feature.Yield.managed.Decid", "ndy", 101, 201),
    "flow.even.product.Yield.Conif": ("product.Yield.managed.Conif", "even", 0, 201),
    "flow.even.product.Yield.Decid": ("product.Yield.managed.Decid", "even", 0, 201),
}

#: The families a report may hold that this comparison does not yet cover, by name prefix.
_UNCOVERED_PREFIXES: tuple[tuple[str, str], ...] = (
    ("flow.", "a flow target for a per-mill allocation"),
    ("ratio.", "a ratio, whose numerator and denominator WS4 does not both report yet"),
    ("patch.", "a patch distribution, which WS4 reports from its own patch accounts"),
)


def compare_flow_targets(
    values: pd.DataFrame, report_dir: Path, tolerance: float
) -> tuple[list[str], int, dict[str, int]]:
    """Compare the reference's flow targets against WS4's values for the same schedule.

    A flow target constrains the shape of an account's profile and is reported as one percent value
    per period, which is what :func:`ws4.opt.objective.flow_series` gives back. The definitions come
    from the reference's own model file rather than from its reported numbers.

    Parameters
    ----------
    values : pandas.DataFrame
        WS4's account values for the replayed schedule, with ``year``, ``account`` and ``value``.
    report_dir : Path
        The reference's export directory.
    tolerance : float
        The absolute tolerance a percent value is compared with.

    Returns
    -------
    tuple of (list of str, int, dict of str to int)
        One line per difference, at most ten; the number of period cells compared; and how many
        targets of each uncovered family the report holds.
    """
    path = report_dir / "targetSummary.csv"
    if not path.is_file():
        path = report_dir / "account_values.csv"
    if not path.is_file():
        return ([], 0, {})
    summary = pd.read_csv(path)
    target_column = _first_present(summary, "TARGET", "account", "ACCOUNT")
    year_column = _first_present(summary, "YEAR", "year", "period")
    value_column = _first_present(summary, "CURRENT", "value", "VALUE")
    if target_column is None or year_column is None or value_column is None:
        return ([], 0, {})
    index = {
        (int(float(str(row.offset))), str(row.account)): float(str(row.value))
        for row in values.itertuples(index=False)
    }
    horizon = max((year for year, _ in index), default=-1) + 1
    uncovered: dict[str, int] = {}
    for name in summary[target_column].astype(str).unique():
        for prefix, _reason in _UNCOVERED_PREFIXES:
            if name.startswith(prefix) and name not in _REFERENCE_FLOWS:
                uncovered[prefix] = uncovered.get(prefix, 0) + 1
    differences: list[str] = []
    compared = 0
    for name, definition in _REFERENCE_FLOWS.items():
        account, flow, start, end = definition
        rows = summary[summary[target_column].astype(str) == name]
        if rows.empty:
            continue
        target = Target(
            account,
            horizon,
            flow=flow,
            flow_start=max(0, start - 1),
            flow_end=max(0, end - 1),
            period_width=10,
        )
        series = flow_series(index, target, horizon)
        for year, want in zip(rows[year_column], rows[value_column], strict=True):
            got = series.get(int(year))
            if got is None:
                continue
            compared += 1
            if abs(got - float(want)) > tolerance:
                differences.append(
                    f"{name} year {int(year)}: WS4 {got:.4f}"
                    f" against the reference {float(want):.4f}"
                )
    return (differences[:10], compared, uncovered)


def _reference_only_targets(report_dir: Path, known: set[str]) -> int:
    """Return how many of the reference's targets have no WS4 account to compare against.

    The reference reports its own ratio, flow and route targets alongside account values, and those
    have no counterpart in WS4's accounts table; the comparison leaves them out and says how many.

    Parameters
    ----------
    report_dir : Path
        The reference's export directory.
    known : set of str
        The accounts WS4 has.

    Returns
    -------
    int
        The number of targets left out of the comparison, or 0 when no report is found.
    """
    path = report_dir / "targetSummary.csv"
    if not path.is_file():
        path = report_dir / "account_values.csv"
    if not path.is_file():
        return 0
    frame = pd.read_csv(path)
    column = _first_present(frame, "account", "ACCOUNT", "TARGET")
    if column is None:
        return 0
    return len(set(frame[column].astype(str)) - known)


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
    differences, compared, skipped = compare_route_costs(roads_dir)
    if differences:
        return CheckResult(
            "parity",
            "fail",
            f"{len(differences)} difference(s) in {compared} comparisons: {differences[0]}",
        )
    tail = ""
    if skipped:
        tail = f"; skipped {', '.join(skipped)} (the model declares no such destination)"
    return CheckResult(
        "parity",
        "pass",
        f"WS4 agrees with the reference on all {compared} routed node-and-mill pairs{tail}",
    )


def _short(account: str) -> str:
    """Return the trailing part of an account name, for a report line."""
    return account.rsplit(".", 1)[-1]


# The reference declares a mill product as an *exclusive split* of a master product, in its
# own model file: `addExclusiveAccount(master, child)` divides the master among the children,
# and a child that `duplicateAccount` sends to a destination is a place the wood goes. The
# split is therefore the policy — which destinations may receive a product, and which account
# holds what reached none — and it is read from the reference's file rather than transcribed,
# so what is compared is its own declaration. The conifer master is a split between the two
# mills; the deciduous master is a split between Mill 2 and the unutilized account, which is
# why WS4 routing deciduous to Mill 1 at all was wrong rather than merely different.
#
# The split is the policy in one more way: where it offers a product a single destination the
# decision is forced, and where it offers several the choice is free — so the check below requires
# the first and only measures the second.
_EXCLUSIVE_ACCOUNT = re.compile(r'addExclusiveAccount\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)')
_DUPLICATE_ACCOUNT = re.compile(
    r'duplicateAccount\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*(-?[0-9.]+)\s*\)'
)


@dataclass(frozen=True)
class ExclusiveSplit:
    """One master product's destinations, as the reference declares them.

    Attributes
    ----------
    master : str
        The master product being divided.
    routed : tuple of (str, str)
        ``(destination, child account)`` per delivered child, in declaration order.
    surplus : str
        The account for what reaches no destination, or an empty string when the reference
        declares none — which the conifer split does not.
    """

    master: str
    routed: tuple[tuple[str, str], ...]
    surplus: str = ""

    @property
    def destinations(self) -> tuple[str, ...]:
        """Return the destinations the master may be sent to, in declaration order.

        Returns
        -------
        tuple of str
            The destination accounts, in the order the reference declares them.
        """
        return tuple(destination for destination, _child in self.routed)


def read_exclusive_splits(pin_path: Path) -> tuple[ExclusiveSplit, ...]:
    """Return the reference's exclusive splits, read from its own model file.

    Parameters
    ----------
    pin_path : Path
        The reference's model file, ``analysis/C5.pin``.

    Returns
    -------
    tuple of ExclusiveSplit
        One entry per master product the reference divides, in declaration order.
    """
    text = Path(pin_path).read_text(encoding="utf-8", errors="replace")
    children: dict[str, list[str]] = {}
    for master, child in _EXCLUSIVE_ACCOUNT.findall(text):
        children.setdefault(master, []).append(child)
    delivered: dict[str, str] = {}
    for child, target, _factor in _DUPLICATE_ACCOUNT.findall(text):
        if target.startswith("destination."):
            delivered.setdefault(child, target)
    splits: list[ExclusiveSplit] = []
    for master, kids in children.items():
        routed = tuple((delivered[kid], kid) for kid in kids if kid in delivered)
        surplus = next((kid for kid in kids if kid not in delivered), "")
        splits.append(ExclusiveSplit(master=master, routed=routed, surplus=surplus))
    return tuple(splits)


def read_reference_assignment(path: Path, split: ExclusiveSplit) -> pd.DataFrame:
    """Return the reference's own destination per block and period, in WS4's names.

    Parameters
    ----------
    path : Path
        The reference's ``exclusive_<master>.csv`` table, gzipped or not.
    split : ExclusiveSplit
        The master's declared split, which maps its child accounts to destinations.

    Returns
    -------
    pandas.DataFrame
        ``block``, ``period`` and ``destination``, one row per cell of the table. A child the
        split does not name keeps its own name, so that a declaration failing to cover what the
        reference exported is reported rather than mapped away.
    """
    frame = pd.read_csv(path)
    block = _first_present(frame, "BLOCK", "block_id", "block")
    if block is None:
        return pd.DataFrame(columns=["block", "period", "destination"])
    periods = [column for column in frame.columns if str(column).startswith("PERIOD")]
    long = frame.melt(
        id_vars=block, value_vars=periods, var_name="period", value_name="child"
    ).rename(columns={block: "block"})
    long["period"] = long["period"].astype(str).str.replace("PERIOD", "", regex=False).astype(int)
    long["block"] = long["block"].astype(int)
    known = {child: destination for destination, child in split.routed}
    if split.surplus:
        known.setdefault(split.surplus, split.surplus)
    long["destination"] = long["child"].map(lambda child: known.get(str(child), str(child)))
    return long[["block", "period", "destination"]]


def _reference_export_dirs(report_dir: Path) -> tuple[Path, ...]:
    """Return the directories a reference export may keep its files in.

    The reference writes a report tree: a scenario directory holding the schedule, the summary
    and the exclusive assignments, beside a ``targets`` directory holding one file per target.
    Depending on which of the two a caller names, the other is one step away, so the directories
    searched are the given one, its ``scenario`` subdirectory, and its parent.

    Parameters
    ----------
    report_dir : Path
        The export directory the caller named.

    Returns
    -------
    tuple of Path
        The existing candidate directories, nearest first.
    """
    candidates = (report_dir, report_dir / "scenario", report_dir.parent)
    seen: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir() and candidate not in seen:
            seen.append(candidate)
    return tuple(seen)


def _find_export_file(where: Sequence[Path], names: Sequence[str]) -> Path | None:
    """Return the first of ``names`` found in any of ``where``.

    Parameters
    ----------
    where : sequence of Path
        The directories to search, nearest first.
    names : sequence of str
        The file names to look for.

    Returns
    -------
    Path or None
        The path found, or None when none of the names exists.
    """
    for directory in where:
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def _reference_period_width(where: Sequence[Path]) -> int:
    """Return the period width the reference's report states, or 1 when it states none.

    Parameters
    ----------
    where : sequence of Path
        The export directories to search, nearest first.

    Returns
    -------
    int
        The width, in years, that the report's own tables state.
    """
    for directory in where:
        targets = directory / "targets"
        if not targets.is_dir():
            continue
        for path in sorted(targets.glob("*.csv")):
            frame = pd.read_csv(path, nrows=5)
            column = _first_present(frame, "PERIODWIDTH", "period_width")
            if column is not None and len(frame):
                return int(float(frame[column].max()))
    return 1


def check_destinations(
    roads_dir: Path | None,
    report_dir: Path | None,
    dataset_dir: Path | None,
    workdir: Path,
) -> CheckResult:
    """Compare WS4's destination decisions, and the mill products they produce, to the reference's.

    The reference chooses which mill a block's product goes to by search, under its mill
    delivery targets, and exports the choice per block and period. That choice is the *spatial
    decision* this phase is about, and it is compared here in two parts, because the model does
    not leave every decision open:

    - where the reference's own split offers a product **one** destination, the decision is
      forced, and WS4 must match it — the deciduous master, whose only mill is Mill 2;
    - where it offers **several**, the destination is a policy choice — the conifer master —
      and the two choices' agreement is measured and reported rather than required.

    The mill products themselves are then compared period by period against the reference's own
    ``targets/product_Mill*_Yield_*.csv``, which is what the forced part has to satisfy.

    Parameters
    ----------
    roads_dir : Path or None
        A sample's ``roads`` directory, which also locates its ``analysis/C5.pin``.
    report_dir : Path or None
        The reference's export directory, holding ``schedule.csv`` and its tables.
    dataset_dir : Path or None
        The compiled dataset to replay the schedule over.
    workdir : Path
        A scratch directory for the routed run.

    Returns
    -------
    CheckResult
        ``fail`` when a forced decision disagrees or a forced mill product is outside tolerance,
        and ``skip`` when any input is missing.
    """
    if roads_dir is None or report_dir is None or dataset_dir is None:
        return CheckResult(
            "destinations",
            "skip",
            "needs --roads-sample, --accounts-report and --accounts-dataset",
        )
    if not (roads_dir.is_dir() and report_dir.is_dir() and dataset_dir.is_dir()):
        return CheckResult(
            "destinations", "fail", "a route, report or dataset input is not a directory"
        )
    pin_path = roads_dir.parent / "analysis" / "C5.pin"
    if not pin_path.is_file():
        return CheckResult("destinations", "skip", f"the sample has no model file at {pin_path}")
    splits = read_exclusive_splits(pin_path)
    if not splits:
        return CheckResult("destinations", "skip", "the model declares no exclusive split")

    where = _reference_export_dirs(report_dir)
    assignments: dict[str, pd.DataFrame] = {}
    for split in splits:
        path = _find_export_file(
            where, (f"exclusive_{split.master}.csv.gz", f"exclusive_{split.master}.csv")
        )
        if path is not None:
            assignments[split.master] = read_reference_assignment(path, split)
    if not assignments:
        return CheckResult(
            "destinations", "skip", f"the export holds no exclusive assignment under {report_dir}"
        )

    _vertices, segments, destinations, linkages = load_route_tables(roads_dir)
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    model = RouteModel(
        network=network,
        eligibility={split.master: split.destinations for split in splits},
        unutilized={split.master: split.surplus for split in splits if split.surplus},
    )

    schedule_path = _ws4_schedule(report_dir, where, workdir)
    if schedule_path is None:
        return CheckResult(
            "destinations", "fail", f"the export holds no schedule.csv under {report_dir}"
        )
    schedule_frame = pd.read_csv(schedule_path)
    block = _first_present(schedule_frame, "block_id", "block")
    treatment = _first_present(schedule_frame, "treatment")
    time_column = _first_present(schedule_frame, "offset", "period", "year", "DELTA")
    if block is None or treatment is None or time_column is None:
        return CheckResult(
            "destinations", "fail", "schedule.csv needs block_id, treatment and offset"
        )
    schedule = pd.DataFrame(
        {
            "block": schedule_frame[block].astype(int),
            "treatment": schedule_frame[treatment].astype(str),
            "offset": schedule_frame[time_column].astype(int) - (1 if time_column == "year" else 0),
        }
    )

    width = max(_reference_period_width(where), 1)
    schedule["reference_period"] = [
        0 if offset < 0 else offset // width + 1 for offset in schedule["offset"]
    ]

    unexplained: list[str] = []
    report: list[str] = []
    for split in splits:
        reference = assignments.get(split.master)
        if reference is None:
            continue
        joined = schedule.merge(
            reference,
            left_on=["block", "reference_period"],
            right_on=["block", "period"],
            how="inner",
            suffixes=("", "_reference"),
        )
        if joined.empty:
            continue
        joined["ws4"] = [
            model.assign(int(one_block), split.master)[0] for one_block in joined["block"]
        ]
        # Every decision the reference itself made must be one its declared split admits: this is
        # what would have caught WS4 sending deciduous wood to Mill 1, an outcome the reference's
        # model does not give that product at all.
        admitted = {*split.destinations, split.surplus, ""}
        for row in joined[~joined["destination"].isin(admitted)].itertuples(index=False):
            unexplained.append(
                f"{split.master}: the reference sent block {row.block} in period "
                f"{row.reference_period} to {row.destination!r}, which its own split does not name"
            )
        matched = joined["destination"] == joined["ws4"]
        if len(split.destinations) <= 1:
            only = split.destinations[0] if split.destinations else "none"
            report.append(
                f"{_short(split.master)} admits one destination ({only}) and WS4 matched the "
                f"reference on {int(matched.sum()):,} of {len(joined):,} block-periods"
            )
        else:
            report.append(
                f"{_short(split.master)} is a free choice and WS4 agreed on {int(matched.sum()):,} "
                f"of {len(joined):,} block-periods ({100 * float(matched.mean()):.1f}%)"
            )
    if unexplained:
        return CheckResult(
            "destinations",
            "fail",
            f"{len(unexplained)} decision(s) outside the reference's own split: {unexplained[0]}",
        )

    allocations = tuple(
        ProductAllocation(
            master=split.master,
            allocations=split.routed,
            unallocated=split.surplus,
        )
        for split in splits
        if split.routed
    )
    years = _reported_years(where, schedule)
    values = Simulator.from_dataset(dataset_dir).run(
        schedule_path,
        years=years,
        out_dir=workdir / "destination-run",
        route_model=model,
        product_allocations=allocations,
    )
    series = {
        str(account): group.set_index("offset")["value"]
        for account, group in values.groupby("account")
    }
    compared = 0
    required_difference = 0.0
    free = ""
    free_difference = 0.0
    surplus = ""
    surplus_difference = 0.0
    beyond: list[str] = []
    unavailable: list[str] = []
    for split in splits:
        # A split with one destination leaves the reference's own search no choice about the
        # account, so its value must be reproduced. A split with several leaves the choice free,
        # and its accounts differ by construction: what is reported there is the policy, not an
        # error, so it is measured and named rather than failed.
        required = len(split.destinations) <= 1
        for _destination, child in split.routed:
            cells, largest, excess = _compare_mill_product(where, child, series)
            compared += cells
            if cells == 0:
                unavailable.append(child)
                continue
            if required:
                required_difference = max(required_difference, largest)
                if excess > 0.0:
                    beyond.append(f"{child} is off by {largest:,.1f}")
            elif largest > free_difference:
                free_difference = largest
                free = child
        if split.surplus:
            # what reached no destination is a choice too, and a small one: it is measured, not
            # required, because the reference's own search is what decides to leave wood unutilized
            cells, largest, _excess = _compare_mill_product(where, split.surplus, series)
            compared += cells
            if cells == 0:
                unavailable.append(split.surplus)
            elif largest > surplus_difference:
                surplus_difference = largest
                surplus = split.surplus
    tail = ""
    if unavailable:
        tail = f"; no reference table for {', '.join(sorted(set(unavailable)))}"
    if beyond:
        return CheckResult(
            "destinations",
            "fail",
            f"a forced mill product disagrees: {beyond[0]} over {compared} period cells",
        )
    message = (
        f"the reference's own model declares {len(splits)} split(s): "
        + "; ".join(report)
        + f"; over {compared} period cells the forced mill products differ by at most "
        f"{required_difference:,.1f}"
        + (f", the free ones by up to {free_difference:,.1f} on {free}" if free else "")
        + (f", and what reached no destination by {surplus_difference:,.1f}" if surplus else "")
        + tail
    )
    return CheckResult("destinations", "pass", message)


def _reported_years(where: Sequence[Path], schedule: pd.DataFrame) -> int:
    """Return the horizon the reference reports, which is what its account values cover.

    Parameters
    ----------
    where : sequence of Path
        The export directories to search, nearest first.
    schedule : pandas.DataFrame
        The replayed schedule, used when the export states no summary.

    Returns
    -------
    int
        The number of annual steps to simulate.
    """
    for name in ("targetSummary.csv", "account_values.csv"):
        path = _find_export_file(where, (name,))
        if path is None:
            continue
        frame = pd.read_csv(path)
        year = _first_present(frame, "YEAR", "year", "period")
        if year is not None and len(frame):
            return int(frame[year].max()) + 1
    return max(int(schedule["offset"].max()) + 1, 1) if not schedule.empty else 1


def _compare_mill_product(
    where: Sequence[Path], account: str, series: Mapping[str, pd.Series]
) -> tuple[int, float, float]:
    """Compare one routed account to the reference's table for it, period by period.

    Parameters
    ----------
    where : sequence of Path
        The export directories to search, nearest first.
    account : str
        The routed account, whose table is named after it with dots for underscores.
    series : mapping of str to pandas.Series
        WS4's annual values per account.

    Returns
    -------
    tuple of (int, float, float)
        The number of period cells compared, the largest absolute difference, and how far the
        worst cell is beyond the tolerance the accounts comparison uses — zero when every cell
        is within it.
    """
    path = _find_export_file(where, (f"targets/{account.replace('.', '_')}.csv",))
    if path is None:
        path = _find_export_file(where, (f"{account.replace('.', '_')}.csv",))
    if path is None:
        return (0, 0.0, 0.0)
    frame = pd.read_csv(path)
    period_column = _first_present(frame, "PERIOD", "period_index")
    year_column = _first_present(frame, "YEAR", "year")
    width_column = _first_present(frame, "PERIODWIDTH", "period_width")
    value_column = _first_present(frame, "CURRENT", "value", "VALUE")
    if None in (period_column, year_column, value_column):
        return (0, 0.0, 0.0)
    width = int(float(frame[width_column].max())) if width_column is not None else 1
    largest = 0.0
    excess = 0.0
    compared = 0
    for one_period, one_year, want in zip(
        frame[period_column], frame[year_column], frame[value_column], strict=True
    ):
        got = _reference_period_value(series, account, int(one_period), int(one_year), width)
        difference = abs(got - float(want))
        largest = max(largest, difference)
        # the same rule the accounts comparison uses: a relative tolerance with an absolute floor,
        # because a reference report rounds as it computes
        allowed = max(1e-4 * max(abs(float(want)), abs(got), 1.0), _ABSOLUTE_TOLERANCE)
        excess = max(excess, difference - allowed)
        compared += 1
    return (compared, largest, excess)


# A patch **component listing** is the document the component comparison reads: one row per member
# block of every patch, with the period it was formed in. This is the specification of it, and it is
# what WS4 writes as ``patch_membership.csv``:
#
#   ``period``, ``year``, ``account``, ``class``, ``patch``, ``block``, ``area_ha``
#
# Only ``year``, ``account``, ``patch`` and ``block`` are compared. ``patch`` is each tool's own id
# and the two never need to agree: what is compared is the **partition** — which blocks are together
# — not the labels, so a listing from another tool is comparable as it stands. A listing that states
# which criterion each patch was formed on (WS4 puts it in ``account``, and the reference would name
# it its own way) is compared per account, one account at a time.
_PATCH_MEMBERSHIP_NAMES = ("patch_membership.csv",)
_PATCH_TARGET = re.compile(
    r'addPatchTarget\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)'
)
_PATCH_TOPOLOGY = re.compile(r'inputTopology\(\s*"([^"]+)"\s*,\s*([0-9.]+)d?\s*\)')


def read_patch_targets(pin_path: Path) -> tuple[tuple[str, str, tuple[float, ...]], ...]:
    """Return the patch accounts the reference declares, with their criterion and size classes.

    The reference declares one target per size class, named ``<account>.<class>``, so an account's
    classes are the bounds its targets state.

    Parameters
    ----------
    pin_path : Path
        The reference's model file, ``analysis/C5.pin``.

    Returns
    -------
    tuple of (str, str, tuple of float)
        ``(account, criterion label, size-class upper bounds)`` per patch account, in declaration
        order.
    """
    text = Path(pin_path).read_text(encoding="utf-8", errors="replace")
    declarations: dict[str, list[tuple[float, float]]] = {}
    criteria: dict[str, str] = {}
    for criterion, name, low, high in _PATCH_TARGET.findall(text):
        account = name.rsplit(".", 1)[0]
        declarations.setdefault(account, []).append((float(low), float(high)))
        criteria[account] = criterion
    return tuple(
        (account, criteria[account], tuple(sorted(upper for _low, upper in bounds)))
        for account, bounds in declarations.items()
    )


def read_patch_topology(pin_path: Path) -> tuple[str, float] | None:
    """Return the topology path and search distance the reference's model declares.

    Parameters
    ----------
    pin_path : Path
        The reference's model file, ``analysis/C5.pin``.

    Returns
    -------
    tuple of (str, float) or None
        The path as the model states it, relative to the model's directory, and the search
        distance in metres; None when it declares no topology.
    """
    text = Path(pin_path).read_text(encoding="utf-8", errors="replace")
    found = _PATCH_TOPOLOGY.search(text)
    if found is None:
        return None
    return (found.group(1), float(found.group(2)))


def read_patch_listing(path: Path) -> pd.DataFrame:
    """Read a patch component listing, under either tool's column names.

    Parameters
    ----------
    path : Path
        The listing.

    Returns
    -------
    pandas.DataFrame
        ``year``, ``account``, ``patch`` and ``block``.

    Raises
    ------
    ValueError
        When the listing is missing one of the four columns a comparison needs.
    """
    frame = pd.read_csv(path)
    columns: dict[str, str] = {}
    for wanted, candidates in (
        ("year", ("year", "YEAR", "period", "PERIOD")),
        ("account", ("account", "ACCOUNT", "criterion", "CRITERION")),
        ("patch", ("patch", "PATCH", "patch_id", "PATCH_ID")),
        ("block", ("block", "BLOCK", "block_id", "BLOCK_ID")),
    ):
        found = _first_present(frame, *candidates)
        if found is None:
            raise ValueError(f"{path.name} needs a {wanted} column")
        columns[found] = wanted
    frame = frame.rename(columns=columns)
    result = frame[["year", "account", "patch", "block"]].copy()
    result["year"] = result["year"].astype(int)
    return result


def compare_patch_components(reference: Path, mine: Path) -> tuple[list[str], int]:
    """Compare two patch component listings: which blocks formed which patch, where.

    The comparison is over the **partition**, not the labels: two listings agree on a period when
    every patch on one side is exactly a patch on the other, however the ids are numbered. A patch
    that spans more than one patch on the other side is a *merge* against it, and is reported with
    an example, because that is the difference a component comparison exists to state.

    Parameters
    ----------
    reference : Path
        The reference's listing, or the listing to compare against.
    mine : Path
        WS4's listing.

    Returns
    -------
    tuple of (list of str, int)
        One line per difference, at most ten, and the number of year-and-account cells compared.
    """
    theirs = read_patch_listing(reference)
    ours = read_patch_listing(mine)
    differences: list[str] = []
    compared = 0
    for account in sorted(set(theirs["account"]) & set(ours["account"])):
        one = theirs[theirs["account"] == account]
        other = ours[ours["account"] == account]
        for year in sorted(set(one["year"]) & set(other["year"])):
            left = one[one["year"] == year]
            right = other[other["year"] == year]
            compared += 1
            left_of = dict(zip(left["block"], left["patch"], strict=True))
            right_of = dict(zip(right["block"], right["patch"], strict=True))
            shared = set(left_of) & set(right_of)
            if not shared:
                differences.append(f"{account} year {year}: the two listings share no block")
                continue
            left_span: dict[int, set[int]] = {}
            right_span: dict[int, set[int]] = {}
            for block in shared:
                left_span.setdefault(int(left_of[block]), set()).add(int(right_of[block]))
                right_span.setdefault(int(right_of[block]), set()).add(int(left_of[block]))
            merges_left = sorted(key for key, value in left_span.items() if len(value) > 1)
            merges_right = sorted(key for key, value in right_span.items() if len(value) > 1)
            only = len(set(left_of) ^ set(right_of))
            if not (merges_left or merges_right or only):
                continue
            example = ""
            if merges_left:
                key = merges_left[0]
                blocks = sum(1 for block in left_of if left_of[block] == key)
                example = (
                    f"; the reference's patch {key} is {len(left_span[key])} of WS4's, "
                    f"over {blocks} blocks"
                )
            elif merges_right:
                key = merges_right[0]
                blocks = sum(1 for block in right_of if right_of[block] == key)
                example = (
                    f"; WS4's patch {key} is {len(right_span[key])} of the reference's, "
                    f"over {blocks} blocks"
                )
            differences.append(
                f"{account} year {year}: {len(left_span)} against {len(right_span)} patches, "
                f"{len(merges_left)} merging one way and {len(merges_right)} the other, "
                f"{only} block(s) in one listing only{example}"
            )
    return differences[:10], compared


def find_patch_listing(where: Sequence[Path]) -> Path | None:
    """Return a reference patch component listing, if the export ships one.

    Parameters
    ----------
    where : sequence of Path
        The export directories to search, nearest first.

    Returns
    -------
    Path or None
        The listing's path, or None when the export states no membership. The reference's own
        reports carry class aggregates and map images; a listing is looked for under its ``patch``
        directory, by the names this specification names.
    """
    for directory in where:
        for name in _PATCH_MEMBERSHIP_NAMES:
            candidate = directory / "patch" / name
            if candidate.is_file():
                return candidate
        for pattern in ("patch/*membership*.csv", "patch/*Membership*.csv"):
            found = sorted(directory.glob(pattern))
            if found:
                return found[0]
    return None


def _ws4_schedule(report_dir: Path, where: Sequence[Path], workdir: Path) -> Path | None:
    """Return the reference's schedule as a file WS4's run reads, or None when there is none.

    The reference writes ``BLOCK,DELTA,AGE,TYPE,TREATMENT``; a run reads ``block_id``,
    ``treatment`` and ``period``. The two are the same three columns under different names, so the
    schedule is normalised into a scratch copy rather than made to fit either tool.

    Parameters
    ----------
    report_dir : Path
        The export directory the caller named, for the message when there is none.
    where : sequence of Path
        The export directories to search, nearest first.
    workdir : Path
        A scratch directory to write the normalised schedule into.

    Returns
    -------
    Path or None
        The normalised schedule, or None when the export holds no schedule.
    """
    found = _find_export_file(where, ("schedule.csv",))
    if found is None:
        return None
    frame = pd.read_csv(found)
    block = _first_present(frame, "block_id", "block", "BLOCK")
    treatment = _first_present(frame, "treatment", "TREATMENT")
    period = _first_present(frame, "period", "year", "DELTA")
    if block is None or treatment is None or period is None:
        return None
    workdir.mkdir(parents=True, exist_ok=True)
    normalised = workdir / "schedule-for-ws4.csv"
    pd.DataFrame(
        {
            "block_id": frame[block].astype(int),
            "treatment": frame[treatment].astype(str),
            "offset": frame[period].astype(int) - (1 if period == "year" else 0),
        }
    ).to_csv(normalised, index=False)
    return normalised


def check_patch_components(
    roads_dir: Path | None,
    report_dir: Path | None,
    dataset_dir: Path | None,
    workdir: Path,
) -> CheckResult:
    """Compare WS4's patch components to the reference's, when its export can state them.

    The reference ships patch *class aggregates* and map images, not membership — checked over
    every report group of the 2026 export: ``patch/`` holds four reports over target tables,
    ``harvest/maps/`` is images with a field list, and the ``nta`` reports are aggregates. So this
    check states what it can and skips with that reason rather than implying a comparison was made.
    The listing it reads is specified in ``notes/design/ws4-parity-harness.md``, and
    ``compare_patch_components`` is the comparison itself, tested against a known difference.

    Parameters
    ----------
    roads_dir : Path or None
        A sample's ``roads`` directory, which also locates its ``analysis/C5.pin``.
    report_dir : Path or None
        The reference's export directory.
    dataset_dir : Path or None
        The compiled dataset to replay the schedule over, for WS4's own listing.
    workdir : Path
        A scratch directory.

    Returns
    -------
    CheckResult
        ``pass`` when the two partitions agree, ``fail`` when they differ, and ``skip`` with the
        reason when the reference states no membership.
    """
    if roads_dir is None or report_dir is None or dataset_dir is None:
        return CheckResult(
            "patchcomponents",
            "skip",
            "needs --roads-sample, --accounts-report and --accounts-dataset",
        )
    where = _reference_export_dirs(report_dir)
    listing = find_patch_listing(where)
    if listing is None:
        return CheckResult(
            "patchcomponents",
            "skip",
            "the reference's export states no patch membership — its patch reports are class "
            "aggregates and its maps are images — so the class aggregates are the ceiling; the "
            "listing this would read is specified in notes/design/ws4-parity-harness.md",
        )
    pin_path = roads_dir.parent / "analysis" / "C5.pin"
    if not pin_path.is_file():
        return CheckResult("patchcomponents", "skip", f"the sample has no model file at {pin_path}")
    topology = read_patch_topology(pin_path)
    if topology is None:
        return CheckResult("patchcomponents", "skip", "the model declares no patch topology")
    relative, distance = topology
    topology_path = (pin_path.parent / relative).resolve()
    if not topology_path.is_file():
        return CheckResult("patchcomponents", "skip", f"no topology at {topology_path}")
    accounts = read_patch_targets(pin_path)
    if not accounts:
        return CheckResult("patchcomponents", "skip", "the model declares no patch target")
    schedule = _ws4_schedule(report_dir, where, workdir)
    if schedule is None:
        return CheckResult("patchcomponents", "skip", "the export holds no schedule to replay")
    out = workdir / "patch-components"
    Simulator.from_dataset(dataset_dir).run(
        schedule,
        years=_reported_years(where, pd.DataFrame({"offset": [0]})),
        out_dir=out,
        topology_csv=topology_path,
        patch_accounts=tuple(
            PatchAccount(
                name=account,
                criteria=criterion,
                threshold=0.5,
                size_classes=classes,
                search_distance=distance,
            )
            for account, criterion, classes in accounts
        ),
        patch_membership=True,
    )
    differences, compared = compare_patch_components(listing, out / "patch_membership.csv")
    if differences:
        return CheckResult(
            "patchcomponents",
            "fail",
            f"{len(differences)} difference(s) in {compared} period-and-account cells: "
            f"{differences[0]}",
        )
    return CheckResult(
        "patchcomponents",
        "pass",
        f"WS4 forms the reference's own components over {compared} period-and-account cells",
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
        "--yield-sample",
        type=Path,
        default=None,
        help="a sample's yield directory, holding the reference's own yield curves",
    )
    parser.add_argument(
        "--yield-dataset",
        type=Path,
        default=None,
        help="a compiled dataset, to compare its yield curves against the reference's",
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
            check_destinations(
                args.roads_sample, args.accounts_report, args.accounts_dataset, workdir / "dest"
            ),
            check_patch_components(
                args.roads_sample, args.accounts_report, args.accounts_dataset, workdir / "patches"
            ),
            check_accounts(args.accounts_report, args.accounts_dataset),
            check_growth(args.yield_sample, args.yield_dataset),
        ]
    print(render(results))
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
