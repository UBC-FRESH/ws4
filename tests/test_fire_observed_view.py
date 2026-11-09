"""Tests for the observed-versus-simulated SVG view."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.fire.comparison import DogribCase, run_dogrib_case
from ws4.fire.observed import ObservedFire, load_dogrib
from ws4.fire.observed_view import render_comparison_svg, write_comparison_svg

FIXTURE = Path(__file__).parent / "fixtures" / "fire" / "dogrib"


@pytest.fixture(scope="module")
def fire() -> ObservedFire:
    """Load the pinned Dogrib observed fire once."""
    return load_dogrib(FIXTURE)


@pytest.fixture(scope="module")
def case(fire: ObservedFire) -> DogribCase:
    """Run a short base case once for rendering tests."""
    return run_dogrib_case(fire, scenario="view-test", duration_min=30.0)


def test_render_comparison_svg_contains_both_perimeters_and_metrics(
    fire: ObservedFire, case: DogribCase
) -> None:
    svg = render_comparison_svg(fire, case)

    assert svg.startswith("<svg")
    assert "Dogrib observed vs simulated perimeter" in svg
    assert 'fill="#ff7a33"' in svg
    assert 'stroke="#2d6cdf"' in svg
    assert 'stroke="#111111"' in svg
    assert "Dogrib comparison" in svg
    assert "16 Oct 2001 13:00" in svg
    assert "17 Oct 2001 11:52" in svg
    assert "RWF085" in svg
    assert "Prometheus Dogrib sample" in svg
    assert "Simulated" in svg
    assert "Run 30 min" in svg
    assert "Target 17 Oct 11:52" in svg
    assert "Weather constant" in svg
    assert "No spotting" in svg
    assert svg.count("<path") >= 4
    assert len(svg) > 10_000


def test_write_comparison_svg_writes_a_file(
    tmp_path: Path, fire: ObservedFire, case: DogribCase
) -> None:
    destination = write_comparison_svg(fire, case, tmp_path / "view.svg")

    assert destination.is_file()
    assert destination.read_text(encoding="utf-8").startswith("<svg")


def test_render_rejects_a_tiny_canvas(fire: ObservedFire, case: DogribCase) -> None:
    with pytest.raises(ValueError, match="too small"):
        render_comparison_svg(fire, case, width=320, height=240)
