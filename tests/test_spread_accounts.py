"""The synthetic oracle: what fragments a fuel body, and what does not.

The bridge test's finding, in miniature. Seven-by-seven blocks at 10 ha, wind from the south (spread
bearing 0) in a 60-degree cone, so northward and diagonal edges are fast and east-west edges are
not.

Three patterns at the same treated area:

- the middle **row**, a band spanning the west-east width;
- the middle **column**, a band spanning the south-north height;
- a **partial** band: four blocks of the middle row, open at both ends.

The patch-size account sees the two full bands as the same largest patch and cannot rank them. The
connectivity account must see *both* full bands as cutting the fuel body in half — 210 ha against
490 ha untreated — and the partial band as leaving it whole. That is the honest claim: a span along
the wind fragments the fast graph just as much as one across it, because the traversal is
undirected. Direction lives in the cone (which edges are fast), not in the traversal; and a narrower
cone that drops the diagonals fragments the map into columns, which is why the default lets a fire
go around.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.patch.accounts import PatchAccount, patch_account_values
from ws4.spread.accounts import SpreadAccount, spread_account_values

_COLUMNS = 7
_ROWS = 7
_SPACING = 100.0
_AREA = 10.0
#: The block centroid of a lattice position, in metres: x east, y north.
_POINTS = {
    row * _COLUMNS + column + 1: (column * _SPACING, row * _SPACING)
    for row in range(_ROWS)
    for column in range(_COLUMNS)
}


def _lattice_edges() -> list[tuple[int, int, float]]:
    """Return the eight-neighbour lattice edges, so a fire can spread sideways as well as forward.

     A four-neighbour lattice is not enough to test a cone: at 60 degrees only the northward edges
    lie
    inside it, so every compartment degenerates into a one-block-wide corridor and the measure would
     reward a barrier for a reason that has nothing to do with the landscape. The diagonals are what
    let
    a fire go around something, which is the behaviour the account has to get right.
    """
    edges: list[tuple[int, int, float]] = []
    diagonal = _SPACING * 2.0**0.5
    for row in range(_ROWS):
        for column in range(_COLUMNS):
            block = row * _COLUMNS + column + 1
            if column + 1 < _COLUMNS:
                edges.append((block, block + 1, _SPACING))
            if row + 1 < _ROWS:
                edges.append((block, block + _COLUMNS, _SPACING))
                if column + 1 < _COLUMNS:
                    edges.append((block, block + _COLUMNS + 1, diagonal))
                if column > 0:
                    edges.append((block, block + _COLUMNS - 1, diagonal))
    return edges


def _band(row_band: bool, partial: bool = False) -> dict[int, float]:
    """Return the criterion values of a band through the middle, by row or by column.

    A partial band covers only the middle four columns of the middle row, leaving both ends open.
    """
    middle_row = _ROWS // 2
    middle_column = _COLUMNS // 2
    values: dict[int, float] = {}
    for block in _POINTS:
        row = (block - 1) // _COLUMNS
        column = (block - 1) % _COLUMNS
        if row_band:
            in_band = row == middle_row and (not partial or 1 <= column <= 4)
        else:
            in_band = column == middle_column
        values[block] = 1.0 if in_band else 0.0
    return values


def _areas() -> dict[int, float]:
    """Return every block's area."""
    return dict.fromkeys(_POINTS, _AREA)


def _largest_patch(values: dict[int, float]) -> float:
    """Return the largest treated patch, from the patch accounts the estate already reports."""
    account = PatchAccount(
        name="patch.treated", criteria="feature.treated", threshold=0.5, search_distance=None
    )
    edges = [(source, target, _SPACING) for source, target, _distance in _lattice_edges()]
    cells = patch_account_values(account, values, edges, _areas())
    return max(cells[key] for key in cells if key.endswith(".area") and key != "TOTAL.area")


def _connectivity(values: dict[int, float], **settings: object) -> dict[str, float]:
    """Return the spread-connectivity sub-accounts for a pattern, with the wind from the south."""
    fields: dict[str, object] = {
        "name": "spread.fire",
        "criteria": "feature.treated",
        "threshold": 0.5,
        "bearing": 0.0,
        "search_distance": None,
    }
    fields.update(settings)
    account = SpreadAccount(**fields)  # type: ignore[arg-type]
    return spread_account_values(account, values, _lattice_edges(), _POINTS, _areas())


def test_the_patch_account_cannot_tell_the_two_full_bands_apart() -> None:
    """The premise: same treated area, one connected band, and the same largest patch."""
    across = _band(row_band=True)
    along = _band(row_band=False)
    assert sum(across.values()) == sum(along.values())
    assert _largest_patch(across) == _largest_patch(along)


def test_a_full_span_fragments_the_fuel_body_and_a_partial_band_does_not() -> None:
    """The oracle: compartment size sees whether the band spans the landscape."""
    control = dict.fromkeys(_POINTS, 0.0)
    across = _connectivity(_band(row_band=True))
    along = _connectivity(_band(row_band=False))
    partial = _connectivity(_band(row_band=True, partial=True))

    # the untreated body is the whole lattice, 490 ha in 49 blocks
    assert _connectivity(control)["spread.fire.largest_component"] == _ROWS * _COLUMNS * _AREA
    assert _connectivity(control)["spread.fire.percolation_reach"] == _ROWS * _COLUMNS * _AREA

    # either full span cuts the 7-by-7 body into two halves of three rows or three columns
    assert across["spread.fire.largest_component"] == 3 * _ROWS * _AREA
    assert along["spread.fire.largest_component"] == 3 * _ROWS * _AREA
    assert across["spread.fire.percolation_reach"] == 3 * _ROWS * _AREA
    assert along["spread.fire.percolation_reach"] == 3 * _ROWS * _AREA
    assert across["spread.fire.TOTAL.blocks"] == 42.0
    assert along["spread.fire.TOTAL.blocks"] == 42.0

    # open both ends and the fire walks around it: 45 blocks left, all in one compartment
    assert partial["spread.fire.largest_component"] == 45 * _AREA
    assert partial["spread.fire.percolation_reach"] == 45 * _AREA
    assert partial["spread.fire.TOTAL.blocks"] == 45.0


def test_membership_lists_untreated_components_and_their_classes() -> None:
    """The membership names the blocks of each untreated component, largest first."""
    account = SpreadAccount(
        name="spread.fire", criteria="feature.treated", bearing=0.0, search_distance=None
    )
    rows: list[dict[str, object]] = []
    spread_account_values(
        account, _band(row_band=True), _lattice_edges(), _POINTS, _areas(), membership=rows
    )
    assert len(rows) == 42
    assert {row["account"] for row in rows} == {"spread.fire"}
    assert all(row["compartment_class"] == "150_9999999" for row in rows)
    assert min(int(str(row["compartment"])) for row in rows) == 0
    assert sum(float(str(row["area_ha"])) for row in rows) == pytest.approx(42 * _AREA)
    components = {int(str(row["compartment"])) for row in rows}
    assert len(components) == 2
    # the largest component is index 0
    largest = [row for row in rows if int(str(row["compartment"])) == 0]
    assert len(largest) == 21
    # a short hop isolates every block into a 10 ha component
    isolated: list[dict[str, object]] = []
    short = SpreadAccount(
        name="spread.fire", criteria="feature.treated", bearing=0.0, search_distance=50.0
    )
    cells = spread_account_values(
        short,
        dict.fromkeys(_POINTS, 0.0),
        _lattice_edges(),
        _POINTS,
        _areas(),
        membership=isolated,
    )
    assert cells["spread.fire.largest_component"] == _AREA
    assert len(isolated) == _ROWS * _COLUMNS
    assert all(row["compartment_class"] == "0_10" for row in isolated)


def test_a_narrow_cone_fragments_the_lattice_into_columns() -> None:
    """A twenty-degree cone keeps only the northward edges, so each column is its own body."""
    control = dict.fromkeys(_POINTS, 0.0)
    assert _connectivity(control, tolerance=20.0)["spread.fire.largest_component"] == (
        _ROWS * _AREA
    )
    # a row band still cuts every column, leaving three rows on each side
    assert _connectivity(_band(row_band=True), tolerance=20.0)["spread.fire.largest_component"] == (
        3 * _AREA
    )


def test_the_cone_and_the_hop_are_real_parameters() -> None:
    """A tolerance beyond 90 degrees is not a cone, and a short hop disconnects the lattice."""
    with pytest.raises(ValueError, match="at most 90 degrees"):
        SpreadAccount(name="spread.fire", criteria="feature.treated", tolerance=91.0)
    with pytest.raises(ValueError, match="finite number of degrees"):
        SpreadAccount(name="spread.fire", criteria="feature.treated", bearing=float("inf"))
    barrier = _band(row_band=True)
    short = _connectivity(barrier, search_distance=50.0)
    # no edge is that short, so every untreated block is its own compartment
    assert short["spread.fire.largest_component"] == _AREA
    assert short["spread.fire.TOTAL.blocks"] == 42.0


def test_an_empty_landscape_reports_nothing_rather_than_failing() -> None:
    """No untreated block and no transmitting edge are legitimate states, and both read zero."""
    everything_treated = dict.fromkeys(_POINTS, 1.0)
    cells = _connectivity(everything_treated)
    assert cells["spread.fire.largest_component"] == 0.0
    assert cells["spread.fire.percolation_reach"] == 0.0
    assert cells["spread.fire.TOTAL.blocks"] == 0.0
    assert cells["spread.fire.TOTAL.area"] == 0.0


# --- wiring: the account inside a run and the optimizer -------------------------------------------


def _run_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Write a small lattice dataset, topology, coordinates and a one-treatment schedule."""
    from ws4.build.compiler import build_canonical_dataset

    fragments = tmp_path / "fragments.csv"
    rows = ["BLOCK,AREA_HA,F_AGE,AU,IFM"]
    rows.extend(f"{block},{_AREA},{50 if block % 2 else 45},1,unmanaged" for block in range(1, 50))
    fragments.write_text("\n".join(rows) + "\n", encoding="utf-8")
    dataset = build_canonical_dataset(
        Path(__file__).resolve().parents[1] / "examples" / "synthetic" / "recipe.xml",
        fragments,
        tmp_path / "compiled",
    )
    topology = tmp_path / "topology.csv"
    links = [f"{source},{target},{distance}" for source, target, distance in _lattice_edges()]
    topology.write_text("src_block,dst_block,distance_m\n" + "\n".join(links) + "\n")
    coordinates = tmp_path / "coordinates.csv"
    coordinates.write_text(
        "block,x,y\n"
        + "\n".join(f"{block},{x},{y}" for block, (x, y) in sorted(_POINTS.items()))
        + "\n"
    )
    accounts = tmp_path / "spread.yaml"
    accounts.write_text(
        "accounts:\n"
        "  - name: spread.fire\n"
        "    criteria: product.Volume\n"
        "    threshold: 0.5\n"
        "    bearing: 0\n"
    )
    return dataset, topology, coordinates, accounts


def test_a_run_writes_the_spread_accounts_and_the_optimizer_can_target_them(tmp_path: Path) -> None:
    """The account reaches the run outputs per period, and a target on it is priced."""
    from ws4.opt.engine import OptimizeConfig, Optimizer
    from ws4.sim.engine import Simulator
    from ws4.spread.accounts import load_spread_accounts

    dataset, topology, coordinates, accounts = _run_fixture(tmp_path)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text("block_id,treatment,period\n1,CC,0\n", encoding="utf-8")
    out = tmp_path / "run"
    Simulator.from_dataset(dataset).run(
        schedule,
        years=2,
        out_dir=out,
        topology_csv=topology,
        spread_accounts=load_spread_accounts(accounts),
        block_coordinates=coordinates,
    )
    membership = pd.read_csv(out / "spread_membership.csv")
    assert not membership.empty
    assert {"year", "account", "compartment", "compartment_class", "block", "area_ha"}.issubset(
        membership.columns
    )
    assert sorted(membership["year"].unique().tolist()) == [0, 1]

    measured = pd.read_csv(out / "spread_metrics.csv")
    assert set(measured["account"]) == {
        "spread.fire.largest_component",
        "spread.fire.percolation_reach",
        "spread.fire.TOTAL.area",
        "spread.fire.TOTAL.blocks",
    }
    assert sorted(measured["year"].unique()) == [0, 1]
    values = pd.read_csv(out / "account_values.csv")
    assert (values["account"] == "spread.fire.largest_component").any()

    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: spread.fire.largest_component\n    year: 1\n    maximum: 0\n",
        encoding="utf-8",
    )
    config = OptimizeConfig(
        years=2,
        iterations=3,
        seed=1,
        targets_path=str(targets),
        topology_path=str(topology),
        spread_accounts_path=str(accounts),
        block_coordinates_path=str(coordinates),
    )
    optimizer = Optimizer.from_dataset(dataset, config)
    # a graph property of the landscape has no per-block delta, so the move-based path declines
    assert optimizer.delta_evaluator([]) is None
    summary = optimizer.run(tmp_path / "opt")
    assert summary["status"] == "ok"
    report = pd.read_csv(tmp_path / "opt" / "report_targets.csv")
    row = report[report["account"] == "spread.fire.largest_component"]
    assert not row.empty
    assert float(row["value"].iloc[0]) > 0.0  # year 1 treats nothing, so the lattice is untreated
