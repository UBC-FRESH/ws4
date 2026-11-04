"""Consistency checks for phase closeout reports."""

from __future__ import annotations

from pathlib import Path

REPORTS = Path(__file__).resolve().parents[1] / "notes" / "reports"


def test_merged_closeout_reports_do_not_say_not_merged() -> None:
    """A report whose status says merged cannot also say the PR is queued."""
    for path in sorted(REPORTS.glob("*-closeout.md")):
        text = path.read_text(encoding="utf-8")
        if "Status: merged" not in text:
            continue
        lowered = text.lower()
        assert "not merged" not in lowered, path
        assert "pr queued, not merged" not in lowered, path
