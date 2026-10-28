"""Contract test for the checked-in c5 base scenario."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "examples" / "c5_base" / "targets.yaml"
INITIAL_GROWING_STOCK = 26_556_411.752642564


def test_c5_base_scenario_has_twenty_decades_and_a_ninety_percent_floor() -> None:
    """The base scenario covers periods 1-20 and floors final growing stock at 90%."""
    document = yaml.safe_load(SCENARIO.read_text(encoding="utf-8"))
    rows = document["targets"]
    periods = sorted({int(row["period"]) for row in rows if row.get("period") is not None})
    assert periods == list(range(1, 21))
    assert all(row.get("period_width") == 10 for row in rows if row.get("period"))
    flow = [row for row in rows if row.get("flow") == "even"]
    assert len(flow) == 1
    assert flow[0]["flow_end_period"] == 20
    floor = [row for row in rows if row["account"] == "feature.total.Yield" and row["period"] == 20]
    assert len(floor) == 1
    assert floor[0]["minimum"] == round(INITIAL_GROWING_STOCK * 0.9, 2)
