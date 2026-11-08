"""Contract tests for the pilot FVS-BC trajectories."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from ws4.sdmd.compile import Trajectory, assess_trajectory, validate_trajectory
from ws4.sdmd.diagram import observed_envelope

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "trajectories"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"


def _files() -> list[Path]:
    """Return the four stored pilot trajectories."""
    return sorted(DATA.glob("AU-*/*.json"))


def _envelope() -> tuple[tuple[float, float], ...]:
    """Build the observed envelope from the SDMD fixture."""
    frame = pd.read_csv(FIXTURE / "sdmd_points.csv")
    return observed_envelope(
        list(
            zip(
                frame["tph"].astype(float),
                frame["mean_tree_volume_m3"].astype(float),
                strict=True,
            )
        )
    )


def _trajectory(path: Path) -> Trajectory:
    """Load one stored trajectory as a ``Trajectory``."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Trajectory(
        label=payload["regime_id"],
        points=tuple((float(point[0]), float(point[1])) for point in payload["points"]),
    )


def test_four_pilot_trajectories_are_stored() -> None:
    """There is a no-cut and a CT60 path for each pilot AU."""
    files = _files()
    assert len(files) == 4
    assert {path.parent.name for path in files} == {"AU-IDFdk3-FDI", "AU-IDFdk3-PLI"}
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "ws4.sdmd.trajectory.v1"
        assert payload["regime_id"] == path.stem
        assert payload["au_id"] == path.parent.name
        assert payload["review_status"] == "provisional"
        assert "fresh-fvsbc" in payload["source"]
        assert len(payload["points"]) >= 5


def test_every_trajectory_is_physical() -> None:
    """No stored path gains trees and stem volume at the same time."""
    for path in _files():
        assert validate_trajectory(_trajectory(path)) == []


def test_trajectories_are_assessed_against_the_envelope() -> None:
    """The inside and extrapolated statuses are both exercised."""
    envelope = _envelope()
    statuses = {
        path.stem: assess_trajectory(_trajectory(path), envelope).status for path in _files()
    }
    assert statuses["REG-B-UNTREATED"] == "inside"
    assert statuses["REG-A-CT60"] == "extrapolated"
    assert set(statuses.values()) <= {"inside", "extrapolated"}


def test_trajectory_points_are_positive() -> None:
    """FVS output converts to a positive density and mean tree volume."""
    for path in _files():
        for tph, volume in _trajectory(path).points:
            assert tph > 0
            assert volume > 0
