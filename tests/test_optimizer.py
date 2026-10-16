"""Tests for the objective and the optimizer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target, load_targets, objective, penalty
from ws4.opt.telemetry import RunLogger, read_records

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_penalty_weights_shortfall_and_excess() -> None:
    """A value below the minimum or above the maximum is penalized."""
    target = Target(account="a", year=0, minimum=10.0, maximum=20.0, min_weight=2.0, max_weight=3.0)
    assert penalty(15.0, target) == 0.0
    assert penalty(7.0, target) == 2.0 * 3.0
    assert penalty(25.0, target) == 3.0 * 5.0


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
