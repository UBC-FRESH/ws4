"""Tests for building an initial schedule: the greedy for aggregate targets under a ceiling.

The instance in hand is uniform on purpose. Every block has the same area and age, so every block
is worth exactly the same product and costs exactly the same haul, and a floor stated in whole
blocks is met or missed by a whole number of them: the shortfall is a property of the search's move
set rather than a random draw.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target
from ws4.opt.operators import Candidates
from ws4.opt.seeding import greedy_schedule
from ws4.roads.accounts import load_route_config
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_BLOCKS = 60
_AREA_HA = 10.0
_AGE = 50
#: Blocks the floor needs, blocks the ceiling allows, and iterations the unseeded search is given.
#: Twenty cannot treat thirty: each operator changes at most one block, and three of the four never
#: add one, so the unseeded search's product is bounded by twenty blocks' worth.
_REQUIRED = 30
_ALLOWED = 35
_ITERATIONS = 20


def _dataset(tmp_path: Path) -> Path:
    """Compile the synthetic recipe over many blocks of one age and area."""
    fragments = tmp_path / "fragments.csv"
    rows = ["BLOCK,AREA_HA,F_AGE,AU,IFM"]
    rows.extend(f"{block},{_AREA_HA},{_AGE},1,unmanaged" for block in range(1, _BLOCKS + 1))
    fragments.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return build_canonical_dataset(_FIXTURE / "recipe.xml", fragments, tmp_path / "compiled")


def _route(tmp_path: Path) -> Path:
    """Write a one-segment route whose haul account is the whole cost, so the evaluator exists."""
    (tmp_path / "segments.csv").write_text(
        "SEGMENT,FNODE,TNODE,LENGTH,HAUL\n1,1,2,100.0,10.0\n", encoding="utf-8"
    )
    (tmp_path / "destinations.csv").write_text(
        "NODE,ACCOUNT\n2,destination.MILL1\n", encoding="utf-8"
    )
    (tmp_path / "linkages.csv").write_text(
        "BLOCK,NODE\n" + "".join(f"{block},1\n" for block in range(1, _BLOCKS + 1)),
        encoding="utf-8",
    )
    path = tmp_path / "route.yaml"
    path.write_text(
        "route:\n"
        "  segments: segments.csv\n"
        "  destinations: destinations.csv\n"
        "  linkages: linkages.csv\n"
        "route_accounts:\n"
        "  - {destination: destination.MILL1, kind: haul, account: route.Mill1.haul}\n",
        encoding="utf-8",
    )
    return path


def _one_block(dataset: Path, route: Path, tmp_path: Path) -> tuple[float, float]:
    """Return what one block is worth and what it costs, measured rather than assumed."""
    schedule = tmp_path / "one.csv"
    schedule.write_text("block_id,treatment,offset\n1,CC,0\n", encoding="utf-8")
    config = load_route_config(route)
    values = Simulator.from_dataset(dataset).run(
        schedule,
        years=1,
        out_dir=tmp_path / "one",
        route_model=config.model,
        route_accounts=config.route_accounts,
    )
    totals = values.groupby("account")["value"].sum()
    return float(totals["product.Volume"]), float(totals["route.Mill1.haul"])


def _config(
    tmp_path: Path,
    route: Path,
    floor: float,
    ceiling: float,
    greedy_seed: bool = False,
) -> OptimizeConfig:
    """A run whose floor needs more blocks than it takes, under a ceiling a few blocks wider."""
    targets = tmp_path / f"targets-{greedy_seed}.yaml"
    targets.write_text(
        "targets:\n"
        f"  - account: product.Volume\n    period: 1\n    minimum: {floor}\n"
        f"  - account: route.Mill1.haul\n    period: 1\n    maximum: {ceiling}\n",
        encoding="utf-8",
    )
    return OptimizeConfig(
        years=1,
        iterations=_ITERATIONS,
        seed=1,
        targets_path=str(targets),
        route_config_path=str(route),
        greedy_seed=greedy_seed,
    )


def _values(run: Path) -> dict[str, float]:
    """Return the value each target reached, from the run's own report."""
    frame = pd.read_csv(run / "report_targets.csv")
    return {
        str(account): float(value)
        for account, value in zip(frame["account"], frame["value"], strict=True)
    }


def _limits(tmp_path: Path) -> tuple[Path, Path, float, float]:
    """The dataset, the route, and the floor and ceiling a block count states."""
    dataset = _dataset(tmp_path)
    route = _route(tmp_path)
    product, cost = _one_block(dataset, route, tmp_path)
    return dataset, route, _REQUIRED * product, _ALLOWED * cost


class _GoalEvaluator:
    """A tiny reduction goal: one hazard maximum and one cost maximum."""

    def __init__(self, hazard: float = 12.0) -> None:
        self.targets = [
            Target("feature.Hazard", period=5, maximum=5.0),
            Target("product.Cost", period=5, maximum=5.0),
        ]
        self.optimizer = SimpleNamespace(cfg=SimpleNamespace(years=5))
        self.hazard = hazard
        self.totals: dict[tuple[int, str], float] = {}

    def reset(self, schedule: dict[int, tuple[tuple[str, int], ...]]) -> None:
        self.totals = {
            (4, "feature.Hazard"): self.hazard,
            (4, "product.Cost"): 0.0,
        }

    def contribution(
        self, block: int, chain: tuple[tuple[str, int], ...]
    ) -> dict[tuple[int, str], float]:
        values = {
            1: {(4, "feature.Hazard"): -6.0, (4, "product.Cost"): 2.0},
            2: {(4, "feature.Hazard"): -4.0, (4, "product.Cost"): 2.0},
            3: {(4, "feature.Hazard"): -10.0, (4, "product.Cost"): 10.0},
        }
        return values.get(block, {})


def test_a_goal_seed_reduces_the_named_maximum_under_its_cost_ceilings() -> None:
    """The hazard-shaped seed takes the best reduction per dollar until the target is met."""
    evaluator = _GoalEvaluator()
    candidates: Candidates = {
        1: [(("FB", 0),)],
        2: [(("FB", 0),)],
        3: [(("FB", 0),)],
    }
    schedule = greedy_schedule(
        cast(IncrementalObjective, evaluator), candidates, goal_account="feature.Hazard"
    )
    assert set(schedule) == {1, 2}
    hazard = 12.0 + sum(
        evaluator.contribution(block, chain)[(4, "feature.Hazard")]
        for block, chain in schedule.items()
    )
    cost = sum(
        evaluator.contribution(block, chain)[(4, "product.Cost")]
        for block, chain in schedule.items()
    )
    assert hazard == 2.0
    assert hazard <= 5.0
    assert cost == 4.0 <= 5.0


def test_a_goal_seed_is_empty_when_the_maximum_is_already_met() -> None:
    """A met reduction target needs no seed, rather than treating blocks for no reason."""
    evaluator = _GoalEvaluator(hazard=4.0)
    assert (
        greedy_schedule(
            cast(IncrementalObjective, evaluator),
            {1: [(("FB", 0),)]},
            goal_account="feature.Hazard",
        )
        == {}
    )


def test_a_goal_seed_names_an_account_it_can_reduce() -> None:
    """A misspelled or non-maximum goal account is refused with its name."""
    with pytest.raises(ValueError, match=r"feature\.Nope"):
        greedy_schedule(
            cast(IncrementalObjective, _GoalEvaluator()), {}, goal_account="feature.Nope"
        )


def test_the_unseeded_search_misses_the_floor_and_the_seeded_one_does_not(tmp_path: Path) -> None:
    """The measured need: an aggregate floor needs more moves than the search can make."""
    dataset, route, floor, ceiling = _limits(tmp_path)

    unseeded = tmp_path / "unseeded"
    Optimizer.from_dataset(dataset, _config(tmp_path, route, floor, ceiling)).run(unseeded)
    reached = _values(unseeded)["product.Volume"]
    # each operator changes at most one block, so twenty moves treat at most twenty of the thirty
    assert reached < floor
    assert reached <= _ITERATIONS * (floor / _REQUIRED)

    seeded = tmp_path / "seeded"
    Optimizer.from_dataset(dataset, _config(tmp_path, route, floor, ceiling, greedy_seed=True)).run(
        seeded
    )
    report = _values(seeded)
    assert report["product.Volume"] >= floor
    assert report["route.Mill1.haul"] <= ceiling
    assert set(pd.read_csv(seeded / "report_targets.csv")["status"]) == {"met"}


def test_the_greedy_takes_moves_until_the_ceiling_would_break(tmp_path: Path) -> None:
    """The builder itself: it meets the floor, and it stops before the ceiling it must respect."""
    dataset, route, floor, ceiling = _limits(tmp_path)
    optimizer = Optimizer.from_dataset(dataset, _config(tmp_path, route, floor, ceiling))
    schedule = optimizer.greedy_schedule()
    treated = sorted(block for block, chain in schedule.items() if chain)
    assert len(treated) >= _REQUIRED
    assert len(treated) <= _ALLOWED


def test_the_greedy_refuses_a_configuration_it_cannot_price(tmp_path: Path) -> None:
    """Duplicate accounts take the evaluator away, and a seed asked for anyway is refused."""
    dataset = _dataset(tmp_path)
    route = _route(tmp_path)
    text = (tmp_path / "route.yaml").read_text(encoding="utf-8")
    (tmp_path / "route.yaml").write_text(
        text + "duplicate_accounts:\n  - {master: route.Mill1.haul, target: route.Total.haul}\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset, _config(tmp_path, route, 1.0, 1.0, greedy_seed=True)
    )
    with pytest.raises(ValueError, match="needs the move-based objective evaluator"):
        optimizer.greedy_schedule()
