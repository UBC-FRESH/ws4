"""Tests for the objective and the optimizer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner
from ws4.build.compiler import build_canonical_dataset
from ws4.cli import app
from ws4.opt.core import Problem
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target, load_targets, objective, objective_terms, penalty
from ws4.opt.operators import OperatorRegistry, Schedule, ToggleOperator
from ws4.opt.solvers import patience_reached, solve_sa
from ws4.opt.telemetry import RunLogger, read_records
from ws4.patch.constraints import core_area_penalty, schedule_years, spatial_penalty

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_patience_is_a_stability_stop_only_when_enabled() -> None:
    """The stability stop fires after the configured run of unimproved iterations."""
    assert patience_reached(0, 0, 0) is False
    assert patience_reached(10, 10, 0) is False
    assert patience_reached(9, 0, 10) is False
    assert patience_reached(10, 0, 10) is True
    assert patience_reached(20, 10, 10) is True
    with pytest.raises(ValueError, match="patience"):
        OptimizeConfig(patience=-1)


def test_the_solver_stops_after_patience_without_an_improvement() -> None:
    """The stability stop bounds a start that cannot improve, not only the helper."""
    import random

    steps: list[int] = []
    problem = Problem(
        evaluate=lambda schedule: 0.0,
        candidates={},
        registry=OperatorRegistry([ToggleOperator()]),
    )
    best, objective = solve_sa(
        problem,
        random.Random(1),
        iterations=100,
        temperature=1.0,
        cooling=1.0,
        patience=5,
        on_step=lambda iteration, value: steps.append(iteration),
    )
    assert best == {}
    assert objective == 0.0
    assert steps == [0, 1, 2, 3, 4]


def test_penalty_weights_shortfall_and_excess() -> None:
    """A value below the minimum or above the maximum is penalized."""
    target = Target(account="a", year=0, minimum=10.0, maximum=20.0, min_weight=2.0, max_weight=3.0)
    assert penalty(15.0, target) == 0.0
    assert penalty(7.0, target) == 2.0 * 3.0
    assert penalty(25.0, target) == 3.0 * 5.0


def test_a_target_period_must_be_at_least_one_year() -> None:
    """The account period is a whole number of years, never shorter."""
    with pytest.raises(ValueError, match="period_width"):
        Target("a", 0, minimum=1.0, period_width=0)
    # a period ends at its year, which is the reference implementation's convention
    assert Target("a", 0, minimum=1.0, period_width=7).cell_years() == range(-6, 1)
    assert Target("a", 10, minimum=1.0, period_width=10).cell_years() == range(1, 11)


def test_inactive_targets_are_kept_and_not_priced(tmp_path: Path) -> None:
    """An inactive target round-trips from YAML but contributes no objective term."""
    path = tmp_path / "targets.yaml"
    path.write_text(
        "targets:\n  - account: a\n    year: 0\n    minimum: 10\n    active: false\n",
        encoding="utf-8",
    )
    targets = load_targets(path)
    assert targets[0].active is False
    values = pd.DataFrame({"year": [0], "account": ["a"], "value": [0.0]})
    assert objective(values, targets) == 0.0
    assert objective_terms(values, targets) == [0.0]


def test_the_incremental_evaluator_skips_inactive_targets(tmp_path: Path) -> None:
    """The move evaluator does not watch or price a target the file marks inactive."""
    dataset, targets_path = _compile(tmp_path)
    optimizer = Optimizer.from_dataset(
        dataset, OptimizeConfig(targets_path=targets_path, years=1, iterations=5)
    )
    evaluator = IncrementalObjective(
        optimizer, [Target("feature.Volume", 0, minimum=500.0, active=False)]
    )
    assert evaluator.targets == []
    assert evaluator.objective == 0.0


def test_penalty_non_linear_squares_the_deviation() -> None:
    """A non-linear target adds the weight times the squared deviation."""
    target = Target("a", 0, minimum=10.0, min_weight=3.0, shape="non_linear")
    assert penalty(7.0, target) == 3.0 * 3.0 * 3.0
    with pytest.raises(ValueError, match="penalty shape"):
        Target("a", 0, minimum=1.0, shape="cubic")


def test_objective_sums_targets() -> None:
    """The objective sums the penalties over the targets."""
    values = pd.DataFrame({"year": [0, 0], "account": ["a", "b"], "value": [5.0, 100.0]})
    targets = [Target("a", 0, minimum=10.0), Target("b", 0, maximum=50.0)]
    assert objective(values, targets) == 5.0 + 50.0


def test_the_optimizer_resolves_route_accounts(tmp_path: Path) -> None:
    """With a route config, the run resolves route accounts and writes the route tables."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    (tmp_path / "segments.csv").write_text(
        "SEGMENT,FNODE,TNODE,LENGTH,HAUL\n1,1,2,100.0,10.0\n", encoding="utf-8"
    )
    (tmp_path / "destinations.csv").write_text(
        "NODE,ACCOUNT\n2,destination.MILL1\n", encoding="utf-8"
    )
    (tmp_path / "linkages.csv").write_text("BLOCK,NODE\n1,1\n2,1\n", encoding="utf-8")
    (tmp_path / "route.yaml").write_text(
        "route:\n"
        "  segments: segments.csv\n"
        "  destinations: destinations.csv\n"
        "  linkages: linkages.csv\n"
        "route_accounts:\n"
        "  - {destination: destination.MILL1, kind: haul, account: route.Mill1.haul}\n"
        "duplicate_accounts:\n"
        "  - {master: route.Mill1.haul, target: route.Total.haul}\n",
        encoding="utf-8",
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: route.Total.haul\n    year: 0\n    minimum: 0\n", encoding="utf-8"
    )
    cfg = OptimizeConfig(
        years=1,
        iterations=2,
        seed=1,
        warm_start=True,
        targets_path=str(targets),
        route_config_path=str(tmp_path / "route.yaml"),
    )
    result = Optimizer.from_dataset(dataset, cfg).run(tmp_path / "opt")
    assert result["status"] == "ok"
    assert (tmp_path / "opt" / "route_cost_report.csv").is_file()
    values = pd.read_csv(tmp_path / "opt" / "account_values.csv")
    assert (values["account"] == "route.Mill1.haul").any()
    assert (values["account"] == "route.Total.haul").any()


def test_incremental_route_accounts_match_the_full_simulation(tmp_path: Path) -> None:
    """A per-block delta agrees with a full simulation, for the accounts that are per-block sums.

    The configuration also prices the maintenance, which is charged once per segment per period and
    so is not a per-block sum: that account is what makes the incremental path defer to the full
    simulation, and this is the check that the deferral agrees with it.
    """
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    (tmp_path / "segments.csv").write_text(
        "SEGMENT,FNODE,TNODE,LENGTH,HAUL,BUILD,MAINTAIN\n1,1,2,100.0,10.0,0.0,1.0\n",
        encoding="utf-8",
    )
    (tmp_path / "destinations.csv").write_text(
        "NODE,ACCOUNT\n2,destination.MILL1\n", encoding="utf-8"
    )
    (tmp_path / "linkages.csv").write_text("BLOCK,NODE\n1,1\n2,1\n", encoding="utf-8")
    (tmp_path / "route.yaml").write_text(
        "route:\n"
        "  segments: segments.csv\n"
        "  destinations: destinations.csv\n"
        "  linkages: linkages.csv\n"
        "route_accounts:\n"
        "  - {destination: destination.MILL1, kind: volume, account: route.vol}\n"
        "  - {destination: destination.MILL1, kind: haul, account: route.haul}\n"
        "  - {destination: destination.MILL1, kind: maintain, account: route.maint}\n"
        "duplicate_accounts:\n"
        "  - {master: route.haul, target: route.total.haul}\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=3, iterations=1, seed=1, route_config_path=str(tmp_path / "route.yaml")
        ),
    )
    model, route_accounts, duplicate_accounts = optimizer.route()
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 0),)}
    incremental = optimizer._incremental_values(schedule, duplicate_accounts, route_accounts)
    full = optimizer._full_values(schedule, model, route_accounts, duplicate_accounts)
    joined = (
        incremental.set_index(["year", "account"])["value"]
        .to_frame("incremental")
        .join(full.set_index(["year", "account"])["value"].to_frame("full"), how="outer")
        .fillna(0.0)
    )
    assert (joined["incremental"] - joined["full"]).abs().max() == pytest.approx(0.0, abs=1e-6)
    # The route accounts are present, not just the feature accounts.
    assert {"route.vol", "route.haul", "route.maint", "route.total.haul"} <= set(
        incremental["account"]
    )


def test_load_targets(tmp_path: Path) -> None:
    """Targets load from a YAML file."""
    path = tmp_path / "targets.yaml"
    path.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    loaded = load_targets(path)
    assert loaded == [Target("feature.Volume", 0, maximum=500.0)]


@pytest.mark.parametrize("metaheuristic", ["sa", "tabu", "ils"])
def test_metaheuristics_improve_the_objective(tmp_path: Path, metaheuristic: str) -> None:
    """Each metaheuristic finds a schedule that lowers the penalty."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    # The empty schedule gives feature.Volume = 700 at year 0; CC on block 1 lowers it.
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            targets_path=str(targets),
            seed=1,
            years=1,
            iterations=60,
            metaheuristic=metaheuristic,
        ),
    )
    summary = optimizer.run(tmp_path / "run")
    assert summary["incumbent_objective"] < 200.0
    assert summary["metaheuristic"] == metaheuristic
    assert (tmp_path / "run" / "schedule.csv").is_file()


def test_run_logger_writes_a_header_and_steps(tmp_path: Path) -> None:
    """The telemetry logger writes a run header and one record per step."""
    path = tmp_path / "telemetry.jsonl"
    with RunLogger(path, "run-1", {"seed": 7}) as logger:
        logger.step(0, 10.0)
        logger.step(1, 8.0)
    records = read_records(path)
    assert records[0] == {"type": "run", "run_id": "run-1", "config": {"seed": 7}}
    assert records[1] == {"type": "step", "iteration": 0, "objective": 10.0}
    assert records[2]["objective"] == 8.0


def test_optimizer_writes_telemetry(tmp_path: Path) -> None:
    """An optimizer run writes its telemetry beside its outputs."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    Optimizer.from_dataset(
        dataset, OptimizeConfig(targets_path=str(targets), seed=1, years=1, iterations=5)
    ).run(tmp_path / "run")
    records = read_records(tmp_path / "run" / "telemetry.jsonl")
    assert records[0]["type"] == "run"
    assert sum(1 for record in records if record["type"] == "step") == 5


def test_lns_operator_is_registered(tmp_path: Path) -> None:
    """The destroy-repair operator is part of the default registry."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig())
    assert "lns" in optimizer.registry.names()


def test_warm_start_runs(tmp_path: Path) -> None:
    """A warm-started run produces a valid incumbent."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    summary = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(targets_path=str(targets), seed=1, years=1, iterations=30, warm_start=True),
    ).run(tmp_path / "run")
    assert summary["incumbent_objective"] < 200.0


def test_mip_bound_is_recorded_with_a_non_negative_gap(tmp_path: Path) -> None:
    """A run with the MIP bound records the bound and a non-negative gap."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    summary = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(targets_path=str(targets), seed=1, years=1, iterations=40, mip_bound=True),
    ).run(tmp_path / "run")
    assert summary["bound_status"] == "optimal"
    assert summary["gap"] >= 0.0
    assert summary["bound"] <= summary["incumbent_objective"]


def _compile(tmp_path: Path) -> tuple[Path, str]:
    """Compile the fixture and write a target that a treatment can meet."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    return dataset, str(targets)


def test_parallel_multi_start_matches_the_serial_result(tmp_path: Path) -> None:
    """A parallel multi-start run produces the same result as the serial run."""
    dataset, targets = _compile(tmp_path)

    def run(name: str, workers: int) -> dict[str, object]:
        return Optimizer.from_dataset(
            dataset,
            OptimizeConfig(
                targets_path=targets, seed=1, years=1, iterations=30, starts=3, workers=workers
            ),
        ).run(tmp_path / name)

    serial = run("serial", 1)
    parallel = run("parallel", 3)
    assert serial["incumbent_objective"] == parallel["incumbent_objective"]
    assert (tmp_path / "serial" / "schedule.csv").read_text() == (
        tmp_path / "parallel" / "schedule.csv"
    ).read_text()


def test_parallel_starts_write_tagged_telemetry(tmp_path: Path) -> None:
    """A process-pool search forwards every start's steps to the run's single telemetry file."""
    dataset, targets = _compile(tmp_path)
    summary = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(targets_path=targets, seed=1, years=1, iterations=8, starts=2, workers=2),
    ).run(tmp_path / "telemetry")
    assert summary["starts"] == 2
    records = read_records(tmp_path / "telemetry" / "telemetry.jsonl")
    steps = [record for record in records if record["type"] == "step"]
    assert {record.get("island") for record in steps} == {"start-0", "start-1"}
    assert sum(1 for record in steps if record.get("island") == "start-0") == 8
    assert sum(1 for record in steps if record.get("island") == "start-1") == 8


def test_parallel_workers_share_the_caller_time_limit(tmp_path: Path) -> None:
    """The worker processes see the parent's deadline, not an unbounded per-start budget."""
    dataset, targets = _compile(tmp_path)
    summary = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            targets_path=targets,
            seed=1,
            years=1,
            iterations=1_000_000,
            starts=2,
            workers=2,
            time_limit="00:00:01",
        ),
    ).run(tmp_path / "limited")
    # a million iterations per worker would take hours; the shared deadline is what stops it
    assert summary["time_limit_reached"] is True


def test_same_seed_reproduces_the_same_result(tmp_path: Path) -> None:
    """The same seed reproduces the same objective and the same schedule."""
    dataset, targets = _compile(tmp_path)

    def run(name: str) -> dict[str, object]:
        return Optimizer.from_dataset(
            dataset, OptimizeConfig(targets_path=targets, seed=5, years=1, iterations=40)
        ).run(tmp_path / name)

    first = run("a")
    second = run("b")
    assert first["incumbent_objective"] == second["incumbent_objective"]
    assert (tmp_path / "a" / "schedule.csv").read_text() == (
        tmp_path / "b" / "schedule.csv"
    ).read_text()


def test_warm_start_is_deterministic(tmp_path: Path) -> None:
    """A warm-started run reproduces itself for the same seed."""
    dataset, targets = _compile(tmp_path)

    def run(name: str) -> dict[str, object]:
        return Optimizer.from_dataset(
            dataset,
            OptimizeConfig(targets_path=targets, seed=5, years=1, iterations=30, warm_start=True),
        ).run(tmp_path / name)

    assert run("a")["incumbent_objective"] == run("b")["incumbent_objective"]


def test_run_records_the_dataset_reference(tmp_path: Path) -> None:
    """A run summary identifies the dataset that produced it."""
    dataset, targets = _compile(tmp_path)
    summary = Optimizer.from_dataset(
        dataset, OptimizeConfig(targets_path=targets, seed=1, years=1, iterations=5)
    ).run(tmp_path / "run")
    reference = summary["dataset"]
    assert isinstance(reference, dict)
    assert reference["schema_version"] == "0.1"
    assert len(str(reference["manifest_sha256"])) == 64


def test_the_scoped_spatial_penalty_matches_the_full_edge_computation(tmp_path: Path) -> None:
    """Scanning only incident edges gives the same penalty as scanning every edge."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    (tmp_path / "topology.csv").write_text(
        "src_block,dst_block,length_m\n1,2,100.0\n3,4,100.0\n", encoding="utf-8"
    )
    max_opening, green_up, min_core, core_buffer = 3.0, 3, 2.0, 50.0
    config = OptimizeConfig(
        years=2,
        iterations=1,
        topology_path=str(tmp_path / "topology.csv"),
        max_opening_ha=max_opening,
        min_green_up_years=green_up,
        min_core_area_ha=min_core,
        core_buffer_m=core_buffer,
    )
    optimizer = Optimizer.from_dataset(dataset, config)
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 1),)}
    frame = optimizer._schedule_frame(schedule)
    scoped = optimizer._spatial_penalty(frame)

    graph = optimizer._graph()
    block_area = optimizer._block_area()
    pairs = [
        (int(float(str(row.block_id))), int(float(str(row.period))))
        for row in frame.itertuples(index=False)
    ]
    selected_by_year, disturbance_years = schedule_years(pairs)
    full = spatial_penalty(
        selected_by_year,
        disturbance_years,
        [(source, target) for source, target, _ in graph],
        block_area,
        max_opening,
        green_up,
    ) + core_area_penalty(selected_by_year, graph, block_area, core_buffer, min_core)
    assert scoped == pytest.approx(config.spatial_weight * full)


def test_optimizer_avoids_a_maximum_opening_violation(tmp_path: Path) -> None:
    """With enforcement, the optimizer does not open adjacent blocks past the cap."""
    dataset, targets = _compile(tmp_path)
    topology = tmp_path / "topology.csv"
    pd.DataFrame({"src_block": [1], "dst_block": [2], "distance_m": [10.0]}).to_csv(
        topology, index=False
    )
    Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            targets_path=targets,
            seed=1,
            years=1,
            iterations=80,
            topology_path=str(topology),
            max_opening_ha=4.0,
            spatial_weight=1000.0,
        ),
    ).run(tmp_path / "run")
    schedule = pd.read_csv(tmp_path / "run" / "schedule.csv")
    # Treating both adjacent blocks in the only year opens 5 ha, over the 4 ha cap.
    assert not ({1, 2} <= set(schedule["block_id"]))


def test_spatial_override_disables_the_penalty(tmp_path: Path) -> None:
    """The explicit override turns the spatial penalty off."""
    dataset, _ = _compile(tmp_path)
    topology = tmp_path / "topology.csv"
    pd.DataFrame({"src_block": [1], "dst_block": [2], "distance_m": [10.0]}).to_csv(
        topology, index=False
    )
    frame = pd.DataFrame(
        [
            {"block_id": 1, "treatment": "CC", "period": 0},
            {"block_id": 2, "treatment": "CC", "period": 0},
        ]
    )
    enforced = Optimizer.from_dataset(
        dataset, OptimizeConfig(topology_path=str(topology), max_opening_ha=4.0)
    )
    override = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            topology_path=str(topology), max_opening_ha=4.0, allow_spatial_override=True
        ),
    )
    assert enforced._spatial_penalty(frame) == 1.0  # 5 ha over a 4 ha cap
    assert override._spatial_penalty(frame) == 0.0


def test_multi_start_is_no_worse_than_single_start(tmp_path: Path) -> None:
    """More starts cannot raise the incumbent objective."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )

    def config(starts: int) -> OptimizeConfig:
        return OptimizeConfig(
            targets_path=str(targets), seed=1, years=1, iterations=40, starts=starts
        )

    single = Optimizer.from_dataset(dataset, config(1)).run(tmp_path / "s1")
    multi = Optimizer.from_dataset(dataset, config(4)).run(tmp_path / "s4")
    assert multi["incumbent_objective"] <= single["incumbent_objective"]


def test_incremental_evaluation_matches_a_full_simulation(tmp_path: Path) -> None:
    """The base-plus-delta objective equals a full re-simulation, cell for cell."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=3, iterations=1, seed=1))
    targets = [Target("feature.Volume", 0, maximum=1000.0)]
    options = optimizer.candidates()
    schedule = {block: choices[0] for block, choices in options.items() if choices}
    assert schedule  # the fixture offers at least one treatment

    incremental = optimizer._incremental_values(schedule, ())
    full = optimizer._full_values(schedule, None, (), ())
    joined = (
        incremental.set_index(["year", "account"])["value"]
        .to_frame("incremental")
        .join(full.set_index(["year", "account"])["value"].to_frame("full"), how="outer")
        .fillna(0.0)
    )
    assert (joined["incremental"] - joined["full"]).abs().max() == pytest.approx(0.0, abs=1e-6)
    assert optimizer._evaluate(schedule, targets) == pytest.approx(
        objective(optimizer._full_values(schedule, None, (), ()), targets)
    )


def test_incremental_evaluation_matches_for_the_empty_schedule(tmp_path: Path) -> None:
    """The empty schedule's incremental objective equals a full simulation."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=3, iterations=1, seed=1))
    targets = [Target("feature.Volume", 0, minimum=0.0)]
    assert optimizer._evaluate({}, targets) == pytest.approx(
        objective(optimizer._full_values({}, None, (), ()), targets)
    )


def test_objective_scores_a_product_account_target(tmp_path: Path) -> None:
    """A target on a raw product account is scored against the produced volume."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=1, iterations=1, seed=1))
    schedule: Schedule = {1: (("CC", 0),)}
    # Block 1 produces 360; a minimum above it shows the exact shortfall, not a zero value.
    shortfall = optimizer._evaluate(schedule, [Target("product.Volume", 0, minimum=1000.0)])
    assert shortfall == pytest.approx(640.0)
    met = optimizer._evaluate(schedule, [Target("product.Volume", 0, minimum=100.0)])
    assert met == pytest.approx(0.0)


def test_island_search_is_deterministic_and_no_worse_than_a_single_start(tmp_path: Path) -> None:
    """The island model reproduces its result and does not raise the objective."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )

    def island_config() -> OptimizeConfig:
        return OptimizeConfig(
            targets_path=str(targets),
            seed=1,
            years=1,
            iterations=30,
            islands=2,
            episodes=2,
            workers=2,
        )

    first = Optimizer.from_dataset(dataset, island_config()).run(tmp_path / "i1")
    second = Optimizer.from_dataset(dataset, island_config()).run(tmp_path / "i2")
    assert first["incumbent_objective"] == second["incumbent_objective"]

    single = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(targets_path=str(targets), seed=1, years=1, iterations=30),
    ).run(tmp_path / "s")
    assert first["incumbent_objective"] <= single["incumbent_objective"] + 1e-9


def test_optimize_command_records_a_mip_bound(tmp_path: Path) -> None:
    """The optimize command records a mixed-integer bound when asked."""
    pytest.importorskip("scipy")
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n", encoding="utf-8"
    )
    weights = tmp_path / "weights.yaml"
    weights.write_text("weights: {}\n", encoding="utf-8")
    out = tmp_path / "opt"
    result = CliRunner().invoke(
        app,
        [
            "optimize",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets),
            "--weights",
            str(weights),
            "--out",
            str(out),
            "--years",
            "1",
            "--time-limit",
            "00:00:10",
            "--threads",
            "1",
            "--mip-bound",
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["bound_status"] == "optimal"
    assert summary["gap"] >= 0.0


def test_the_thread_setting_pins_the_process_it_runs_in(tmp_path: Path) -> None:
    """``threads`` limits the BLAS pools and the environment, not only the configuration.

    A forked worker inherits its parent's already-initialised BLAS, so the environment alone cannot
    reach it; the pools loaded in this process are retuned as well.
    """
    optimizer = Optimizer.from_dataset(
        tmp_path / "unused", OptimizeConfig(years=1, iterations=0, threads=2)
    )

    assert optimizer.cfg.threads == 2
    assert os.environ["OMP_NUM_THREADS"] == "2"
    assert os.environ["OPENBLAS_NUM_THREADS"] == "2"
    assert os.environ["MKL_NUM_THREADS"] == "2"

    threadpoolctl = pytest.importorskip("threadpoolctl")
    pools = [pool for pool in threadpoolctl.threadpool_info() if "num_threads" in pool]
    assert pools, "expected at least one discoverable thread pool in this environment"
    assert all(pool["num_threads"] == 2 for pool in pools)


def test_the_default_thread_setting_is_one_per_process(tmp_path: Path) -> None:
    """One BLAS thread per process is the default, so a pool of workers does not oversubscribe."""
    Optimizer.from_dataset(tmp_path / "unused", OptimizeConfig(years=1, iterations=0))

    assert os.environ["OMP_NUM_THREADS"] == "1"


def test_a_run_leaves_the_incumbent_values_readable(tmp_path: Path) -> None:
    """``last_account_values`` holds the incumbent's values after a run, not an empty frame."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n- account: feature.Volume\n  year: 0\n  minimum: 1\n  period_width: 1\n"
    )
    optimizer = Optimizer.from_dataset(
        dataset, OptimizeConfig(years=3, iterations=20, seed=1, targets_path=str(targets))
    )

    assert optimizer.last_account_values().empty, "nothing has been evaluated yet"

    optimizer.run(tmp_path / "run")

    values = optimizer.last_account_values()
    assert not values.empty
    assert {"year", "account", "value"} <= set(values.columns)
    assert "feature.Volume" in set(values["account"])


def test_the_incremental_route_path_prices_the_additive_accounts(tmp_path: Path) -> None:
    """With only per-block sums configured, the delta is the path taken and it agrees."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    (tmp_path / "segments.csv").write_text(
        "SEGMENT,FNODE,TNODE,LENGTH,HAUL,BUILD,MAINTAIN\n1,1,2,100.0,10.0,0.0,1.0\n",
        encoding="utf-8",
    )
    (tmp_path / "destinations.csv").write_text(
        "NODE,ACCOUNT\n2,destination.MILL1\n", encoding="utf-8"
    )
    (tmp_path / "linkages.csv").write_text("BLOCK,NODE\n1,1\n2,1\n", encoding="utf-8")
    (tmp_path / "route.yaml").write_text(
        "route:\n"
        "  segments: segments.csv\n"
        "  destinations: destinations.csv\n"
        "  linkages: linkages.csv\n"
        "route_accounts:\n"
        "  - {destination: destination.MILL1, kind: volume, account: route.vol}\n"
        "  - {destination: destination.MILL1, kind: haul, account: route.haul}\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=3, iterations=1, seed=1, route_config_path=str(tmp_path / "route.yaml")
        ),
    )
    model, route_accounts, duplicate_accounts = optimizer.route()
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 0),)}
    incremental = optimizer._incremental_values(schedule, duplicate_accounts, route_accounts)
    full = optimizer._full_values(schedule, model, route_accounts, duplicate_accounts)
    joined = (
        incremental.set_index(["year", "account"])["value"]
        .to_frame("incremental")
        .join(full.set_index(["year", "account"])["value"].to_frame("full"), how="outer")
        .fillna(0.0)
    )
    assert (joined["incremental"] - joined["full"]).abs().max() == pytest.approx(0.0, abs=1e-6)
    assert (joined["incremental"] > 0.0).any()
