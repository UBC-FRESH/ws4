"""Tests for the mixed-integer bound."""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.mip import bound_for, relaxation_for
from ws4.opt.objective import Target, objective
from ws4.sim.engine import Simulator

pytest.importorskip("scipy")  # the MIP bound needs the optional 'opt' extra

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_EMPTY = pd.DataFrame([], columns=["block_id", "treatment", "offset"])


def _setup(tmp_path: Path) -> tuple[Path, list[Target]]:
    """Compile the synthetic fixture and return a target that CC improves."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    # The empty schedule gives 700; treating both blocks drops the value.
    return dataset, [Target("feature.Volume", period=1, maximum=500.0)]


def test_mip_bound_is_no_worse_than_the_empty_schedule(tmp_path: Path) -> None:
    """The bound is at or below the empty-schedule penalty."""
    dataset, targets = _setup(tmp_path)
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    result = bound_for(dataset, targets, candidates, 1)
    empty = objective(Simulator.from_dataset(dataset).simulate(_EMPTY, 1), targets)
    assert result.status == "optimal"
    assert result.objective <= empty


def test_mip_bound_is_achieved_by_its_schedule(tmp_path: Path) -> None:
    """The chosen schedule's real penalty equals the bound (a tight small problem)."""
    dataset, targets = _setup(tmp_path)
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    result = bound_for(dataset, targets, candidates, 1)
    schedule = pd.DataFrame(
        [
            {"block_id": block, "treatment": treatment, "offset": offset}
            for block, chain in result.schedule.items()
            for treatment, offset in chain
        ]
    )
    achieved = objective(Simulator.from_dataset(dataset).simulate(schedule, 1), targets)
    assert achieved == result.objective
    assert result.objective == 0.0  # both blocks can be treated


def test_mip_bound_is_a_lower_bound_for_random_schedules(tmp_path: Path) -> None:
    """No schedule has a penalty below the bound."""
    dataset, targets = _setup(tmp_path)
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    result = bound_for(dataset, targets, candidates, 1)
    rng = random.Random(0)
    for _ in range(8):
        schedule = {
            block: rng.choice(options)
            for block, options in candidates.items()
            if options and rng.random() < 0.5
        }
        frame = pd.DataFrame(
            [
                {"block_id": block, "treatment": treatment, "offset": offset}
                for block, chain in schedule.items()
                for treatment, offset in chain
            ],
            columns=["block_id", "treatment", "offset"],
        )
        values = Simulator.from_dataset(dataset).simulate(frame, 1)
        assert objective(values, targets) >= result.objective - 1e-6


def test_mip_bound_with_stand_centred_opening_constraints(tmp_path: Path) -> None:
    """The opening constraints tighten the bound and it stays a valid lower bound."""
    dataset, targets = _setup(tmp_path)
    topology = tmp_path / "topology.csv"
    topology.write_text("BLOCK1,BLOCK2,DISTANCE,LENGTH\n1,2,10,100\n", encoding="utf-8")
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    plain = bound_for(dataset, targets, candidates, 1)
    constrained = bound_for(
        dataset, targets, candidates, 1, topology_path=topology, max_opening_ha=4.0
    )
    assert constrained.status == "optimal"
    assert constrained.objective >= plain.objective - 1e-6
    schedule = pd.DataFrame(
        [
            {"block_id": block, "treatment": treatment, "offset": offset}
            for block, chain in constrained.schedule.items()
            for treatment, offset in chain
        ]
    )
    areas = {1: 3.0, 2: 2.0}
    harvested = {int(float(str(row.block_id))) for row in schedule.itertuples(index=False)}
    assert sum(areas.get(block, 0.0) for block in harvested) <= 4.0 + 1e-9
    achieved = objective(Simulator.from_dataset(dataset).simulate(schedule, 1), targets)
    assert achieved >= constrained.objective - 1e-6
    # a cap below a block's own area forbids harvesting that block (eq. 6, A_k+ < 0)
    tiny = bound_for(dataset, targets, candidates, 1, topology_path=topology, max_opening_ha=2.5)
    assert tiny.status == "optimal"
    assert 1 not in tiny.schedule
    assert tiny.objective >= plain.objective - 1e-6
    empty = objective(Simulator.from_dataset(dataset).simulate(_EMPTY, 1), targets)
    assert tiny.objective <= empty


def test_mip_bound_handles_periodic_targets(tmp_path: Path) -> None:
    """A period-width target constrains the account summed over the whole period."""
    dataset, _ = _setup(tmp_path)
    targets = [Target("feature.Volume", period=1, maximum=1400.0, period_width=2)]
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=2)).candidates()
    result = bound_for(dataset, targets, candidates, 2)
    assert result.status == "optimal"
    empty = objective(Simulator.from_dataset(dataset).simulate(_EMPTY, 2), targets)
    assert result.objective <= empty
    rng = random.Random(1)
    for _ in range(8):
        schedule = {
            block: rng.choice(options)
            for block, options in candidates.items()
            if options and rng.random() < 0.5
        }
        frame = pd.DataFrame(
            [
                {"block_id": block, "treatment": treatment, "offset": offset}
                for block, chain in schedule.items()
                for treatment, offset in chain
            ],
            columns=["block_id", "treatment", "offset"],
        )
        values = Simulator.from_dataset(dataset).simulate(frame, 2)
        assert objective(values, targets) >= result.objective - 1e-6


def test_lp_relaxation_is_a_lower_bound_with_a_binding_dual(tmp_path: Path) -> None:
    """The LP bound is no higher than the MIP, and an impossible floor has a positive dual."""
    dataset, _ = _setup(tmp_path)
    targets = [Target("feature.Volume", period=1, minimum=1000.0)]
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    mip = bound_for(dataset, targets, candidates, 1)
    lp = relaxation_for(dataset, targets, candidates, 1)
    assert lp.status == "optimal"
    assert lp.objective <= mip.objective + 1e-6
    assert len(lp.duals) == 1
    dual = lp.duals[0]
    assert dual.bound == "minimum"
    assert dual.binding is True
    assert dual.dual > 0.0
    assert len(lp.reduced_costs) == len(candidates)
    assert all(0.0 <= cost.value <= 1.0 for cost in lp.reduced_costs)


def test_lp_relaxation_records_a_non_binding_bound(tmp_path: Path) -> None:
    """A bound the schedule clears has zero dual and a positive slack."""
    dataset, _ = _setup(tmp_path)
    targets = [Target("feature.Volume", period=1, maximum=500.0)]
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    lp = relaxation_for(dataset, targets, candidates, 1)
    assert lp.status == "optimal"
    assert lp.duals[0].binding is False
    assert lp.duals[0].dual == 0.0
    assert lp.duals[0].slack > 0.0
