"""Tests for the provisional diagram review packet builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _builder() -> Any:  # noqa: ANN401 - test-only dynamic module loader
    """Load the packet builder without making ``scripts`` a package."""
    spec = importlib.util.spec_from_file_location(
        "build_diagram_review_packet_test",
        ROOT / "scripts" / "build_diagram_review_packet.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_review_rows_validate_all_six_provisional_diagrams() -> None:
    """Every queue diagram loads, validates, and names its curve families."""
    rows = _builder().review_rows()
    assert len(rows) == 6
    assert {row["diagram_id"] for row in rows} == {
        "cwn",
        "cwp",
        "hwn",
        "hwp",
        "swn",
        "swp",
    }
    for row in rows:
        assert row["review"] == "provisional"
        assert row["findings"] == []
        curves = row["curves"]
        assert isinstance(curves, dict)
        assert {"top_height", "qmd", "competition", "self_thinning", "crown_closure"} <= set(curves)


def test_packet_writes_ten_curve_plots_and_a_checklist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The packet builder writes figures and a maintainer checklist."""
    builder = _builder()
    monkeypatch.setattr(builder, "REVIEW", tmp_path)
    monkeypatch.setattr(builder, "PAGE_DIR", tmp_path / "pages")
    monkeypatch.setattr(builder, "CURVE_DIR", tmp_path / "curves")
    packet = builder.build_packet(download=False)
    text = packet.read_text(encoding="utf-8")
    assert "all 6 diagrams remain **provisional**" in text
    assert text.count("- [ ]") == 6
    assert len(list((tmp_path / "curves").glob("*.svg"))) == 6
    assert 'fill="#c9ced6"' in (tmp_path / "curves" / "hwn.svg").read_text(encoding="utf-8")
