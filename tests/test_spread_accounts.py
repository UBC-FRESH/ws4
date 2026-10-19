"""The synthetic oracle: a directed barrier that beats the patch-size account.

The bridge test's finding, in miniature. Seven-by-seven blocks; the treatment is either the
middle **row** or the middle **column**, at the same area and as one connected band. The wind is
from the south, so spread travels northward (bearing 0):

- the **row** band lies across the wind: every northward path crosses it, so it is a barrier;
- the **column** band lies along the wind: a fire runs up either side of it, so it is no barrier.

 Both are one connected band, so a patch-size account sees the **same** largest patch and cannot
tell them
apart. The connectivity account must prefer the row band on every measure.
"""

from __future__ import annotations

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


def _band(row_band: bool) -> dict[int, float]:
    """Return the criterion values of a band across the middle, by row or by column."""
    middle_row = _ROWS // 2
    middle_column = _COLUMNS // 2
    values: dict[int, float] = {}
    for block in _POINTS:
        row = (block - 1) // _COLUMNS
        column = (block - 1) % _COLUMNS
        in_band = row == middle_row if row_band else column == middle_column
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


def test_a_barrier_reduces_connectivity_while_the_patches_are_identical() -> None:
    """The oracle: the patch-size account cannot rank the patterns, and connectivity can."""
    barrier = _band(row_band=True)
    alongside = _band(row_band=False)

    # the treatment is the same area either way, and one connected band either way
    assert sum(barrier.values()) == sum(alongside.values())
    assert _largest_patch(barrier) == _largest_patch(alongside)

    across = _connectivity(barrier)
    along = _connectivity(alongside)

    # the barrier is strictly better on every connectivity measure
    assert across["spread.fire.largest_component"] < along["spread.fire.largest_component"]
    assert across["spread.fire.percolation_reach"] < along["spread.fire.percolation_reach"]
    assert across["spread.fire.edge_cut"] > along["spread.fire.edge_cut"]

    # The arithmetic, checkable by hand on the seven-by-seven lattice. A block below the row band
    # reaches only the three rows beneath it; the largest such reach is nine blocks (its column, the
    # two either side of it, and one row back), which is 90 ha. The column band leaves a fire free
    # to
    # run up the six-block half it starts in, reaching nineteen blocks, 190 ha.
    assert across["spread.fire.largest_component"] == 9 * _AREA
    assert along["spread.fire.largest_component"] == 19 * _AREA
    # of the 70 spread edges leaving untreated blocks, the row band stops the 14 that cross it, and
    # the column band stops only the 8 that run into it from the column in front
    assert across["spread.fire.edge_cut"] == pytest.approx(100.0 * 14 / 70)
    assert along["spread.fire.edge_cut"] == pytest.approx(100.0 * 8 / 64)


def test_the_direction_is_what_makes_a_band_a_barrier() -> None:
    """Turn the wind along the row band and the same band stops being one."""
    barrier = _band(row_band=True)
    northward = _connectivity(barrier, bearing=0.0)
    eastward = _connectivity(barrier, bearing=90.0)
    assert northward["spread.fire.largest_component"] < eastward["spread.fire.largest_component"]
    assert northward["spread.fire.edge_cut"] > eastward["spread.fire.edge_cut"]


def test_a_full_half_plane_cone_loses_the_direction_on_a_regular_lattice() -> None:
    """The reason the default is 60: at 90 every edge transmits, and the lattice is symmetric."""
    barrier = _band(row_band=True)
    alongside = _band(row_band=False)
    wide = {"tolerance": 90.0}
    # every edge transmits, so both bands separate the same number of blocks and the measure
    # can no longer tell them apart
    assert _connectivity(barrier, **wide)["spread.fire.largest_component"] == pytest.approx(
        _connectivity(alongside, **wide)["spread.fire.largest_component"]
    )
    assert _connectivity(barrier, **wide)["spread.fire.edge_cut"] == pytest.approx(
        _connectivity(alongside, **wide)["spread.fire.edge_cut"]
    )


def test_the_cone_and_the_hop_are_real_parameters() -> None:
    """A tolerance beyond 90 degrees is not a cone, and a short hop disconnects the lattice."""
    with pytest.raises(ValueError, match="at most 90 degrees"):
        SpreadAccount(name="spread.fire", criteria="feature.treated", tolerance=91.0)
    with pytest.raises(ValueError, match="finite number of degrees"):
        SpreadAccount(name="spread.fire", criteria="feature.treated", bearing=float("inf"))
    barrier = _band(row_band=True)
    short = _connectivity(barrier, search_distance=50.0)
    # no edge is that short, so nothing transmits and nothing is cut
    assert short["spread.fire.edge_cut"] == 0.0
    assert short["spread.fire.largest_component"] == _AREA


def test_an_empty_landscape_reports_nothing_rather_than_failing() -> None:
    """No untreated block and no transmitting edge are legitimate states, and both read zero."""
    everything_treated = dict.fromkeys(_POINTS, 1.0)
    cells = _connectivity(everything_treated)
    assert cells["spread.fire.largest_component"] == 0.0
    assert cells["spread.fire.percolation_reach"] == 0.0
    assert cells["spread.fire.TOTAL.blocks"] == 0.0
    assert cells["spread.fire.edge_cut"] == 0.0
