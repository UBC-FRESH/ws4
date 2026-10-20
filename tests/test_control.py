"""The run control file: a polled pause/stop that leaves a clean summary."""

from __future__ import annotations

import json
from pathlib import Path

from ws4.opt.control import RunControl
from ws4.opt.solvers import _stopped


def test_a_missing_or_invalid_file_means_run(tmp_path: Path) -> None:
    """A run without a readable control file is not paused or stopped."""
    control = RunControl(tmp_path / "control.json")
    assert control.action() == "run"
    control.path.write_text("not json", encoding="utf-8")
    assert control.action() == "run"
    control.path.write_text(json.dumps({"action": "explode"}), encoding="utf-8")
    assert control.action() == "run"


def test_stop_is_seen_at_the_poll_interval(tmp_path: Path) -> None:
    """The solver checks every sixty-fourth iteration and honours a stop."""
    control = RunControl(tmp_path / "control.json")
    control.path.write_text('{"action": "stop"}', encoding="utf-8")
    assert _stopped(control, 0) is True
    assert _stopped(control, 1) is False  # not a poll iteration
    control.path.write_text('{"action": "run"}', encoding="utf-8")
    assert _stopped(control, 64) is False
