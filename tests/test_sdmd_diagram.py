"""Contract tests for SDMD diagrams, placement, envelopes, and AU reports."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from ws4.sdmd.compile import (
    SdmdReportError,
    Trajectory,
    assess_trajectory,
    build_au_report,
)
from ws4.sdmd.diagram import (
    DiagramReview,
    DiagramSource,
    SdmdDiagram,
    SdmdDiagramError,
    inside_envelope,
    interpolate_value,
    isopleth_y,
    load_diagram,
    observed_envelope,
    place_point,
    validate_diagram,
)

DIAGRAM_PATH = (
    Path(__file__).resolve().parents[1]
    / "ws4"
    / "sdmd"
    / "data"
    / "sdmd"
    / "idf-dk3-fdi-illustrative.json"
)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"
PILOT_DIAGRAM = (
    Path(__file__).resolve().parents[1]
    / "ws4"
    / "sdmd"
    / "data"
    / "sdmd"
    / "idf-dk3-fdi-natural.json"
)


def _diagram() -> SdmdDiagram:
    """Load the committed illustrative diagram.

    Returns
    -------
    SdmdDiagram
        The provisional fixture diagram.
    """
    return load_diagram(DIAGRAM_PATH)


def _reviewed(diagram: SdmdDiagram) -> SdmdDiagram:
    """Return a copy of the diagram with the maintainer review recorded.

    Parameters
    ----------
    diagram : SdmdDiagram
        The fixture diagram.

    Returns
    -------
    SdmdDiagram
        A reviewed copy, used to exercise the report path.
    """
    return replace(
        diagram,
        review=DiagramReview(
            status="reviewed",
            reviewer="G. Paradis",
            reviewed_utc="2026-11-02T00:00:00+00:00",
        ),
    )


def _points() -> pd.DataFrame:
    """Return the fixture SDMD points.

    Returns
    -------
    pandas.DataFrame
        Ten AU-level points across two AUs.
    """
    return pd.read_csv(FIXTURE / "sdmd_points.csv")


def test_load_diagram_reads_the_committed_fixture() -> None:
    """The shipped diagram is provisional, synthetic, and valid."""
    diagram = _diagram()
    assert diagram.diagram_id == "idf-dk3-fdi-illustrative"
    assert diagram.review.status == "provisional"
    assert diagram.source.kind == "synthetic"
    assert validate_diagram(diagram) == []


def test_load_diagram_rejects_a_bad_schema_version(tmp_path: Path) -> None:
    """The schema version is part of the file contract."""
    path = tmp_path / "diagram.json"
    path.write_text(json.dumps({"schema_version": "wrong"}), encoding="utf-8")
    with pytest.raises(SdmdDiagramError, match="schema_version"):
        load_diagram(path)


def test_load_diagram_rejects_invalid_json(tmp_path: Path) -> None:
    """Malformed JSON fails with a diagram error, not a decoder traceback."""
    path = tmp_path / "diagram.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SdmdDiagramError, match="not valid JSON"):
        load_diagram(path)


def test_load_diagram_rejects_a_missing_file(tmp_path: Path) -> None:
    """A missing file is a named error."""
    with pytest.raises(SdmdDiagramError, match="not found"):
        load_diagram(tmp_path / "missing.json")


def test_load_diagram_rejects_a_malformed_isopleth(tmp_path: Path) -> None:
    """An isopleth point must be a two-number list."""
    payload = json.loads(DIAGRAM_PATH.read_text(encoding="utf-8"))
    payload["isopleths"][0]["points"] = [[200.0, 0.5, 1.0]]
    path = tmp_path / "diagram.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SdmdDiagramError, match="points must be"):
        load_diagram(path)


def test_validate_diagram_requires_a_reviewer_when_reviewed() -> None:
    """A reviewed diagram without a reviewer is not reviewed."""
    diagram = replace(
        _diagram(),
        review=DiagramReview(status="reviewed", reviewer="", reviewed_utc=""),
    )
    codes = {problem.code for problem in validate_diagram(diagram)}
    assert "SDMD-DIAGRAM-REVIEW" in codes


def test_validate_diagram_rejects_an_unknown_review_status() -> None:
    """Review status is a closed set."""
    diagram = replace(
        _diagram(),
        review=DiagramReview(status="signed-off", reviewer="x", reviewed_utc="y"),
    )
    assert "SDMD-DIAGRAM-REVIEW" in {problem.code for problem in validate_diagram(diagram)}


def test_validate_diagram_rejects_an_unknown_source_kind() -> None:
    """A diagram must say whether it is published or illustrative."""
    diagram = replace(
        _diagram(),
        source=DiagramSource(citation="c", version="v", licence="l", kind="scan"),
    )
    assert "SDMD-DIAGRAM-SOURCE" in {problem.code for problem in validate_diagram(diagram)}


def test_validate_diagram_requires_two_interpolable_curves() -> None:
    """A single top-height isopleth cannot be interpolated."""
    diagram = _diagram()
    first = next(item for item in diagram.isopleths if item.kind == "top_height")
    others = tuple(item for item in diagram.isopleths if item.kind != "top_height")
    candidate = replace(diagram, isopleths=(*others, first))
    codes = {problem.code for problem in validate_diagram(candidate)}
    assert "SDMD-DIAGRAM-ISOPLETH" in codes


def test_validate_diagram_rejects_unordered_points() -> None:
    """Points must be ordered by strictly increasing density."""
    diagram = _diagram()
    first = diagram.isopleths[0]
    broken = replace(first, points=((500.0, 0.5), (200.0, 0.2)))
    candidate = replace(diagram, isopleths=(broken, *diagram.isopleths[1:]))
    messages = [problem.message for problem in validate_diagram(candidate)]
    assert any("strictly increasing" in message for message in messages)


def test_validate_diagram_rejects_a_non_positive_isopleth_value() -> None:
    """An isopleth value is a physical quantity and must be positive."""
    diagram = _diagram()
    broken = replace(diagram.isopleths[0], value=0.0)
    candidate = replace(diagram, isopleths=(broken, *diagram.isopleths[1:]))
    assert "SDMD-DIAGRAM-ISOPLETH" in {problem.code for problem in validate_diagram(candidate)}


def test_isopleth_y_interpolates_in_log_space() -> None:
    """The interpolated value stays between the two bracketing points."""
    isopleth = next(item for item in _diagram().isopleths if item.kind == "top_height")
    low = isopleth_y(isopleth, 200.0)
    middle = isopleth_y(isopleth, 300.0)
    high = isopleth_y(isopleth, 500.0)
    assert low is not None
    assert middle is not None
    assert high is not None
    assert high < middle < low


def test_isopleth_y_returns_none_outside_the_digitised_domain() -> None:
    """The diagram does not extrapolate a curve past its digitised points."""
    isopleth = next(item for item in _diagram().isopleths if item.kind == "top_height")
    assert isopleth_y(isopleth, 100.0) is None
    assert isopleth_y(isopleth, 4000.0) is None


def test_isopleth_y_rejects_a_non_positive_density() -> None:
    """A density of zero has no logarithm."""
    isopleth = _diagram().isopleths[0]
    with pytest.raises(SdmdDiagramError, match="tph must be positive"):
        isopleth_y(isopleth, 0.0)


def test_interpolate_value_reads_between_top_height_curves() -> None:
    """A point halfway between two height curves reads the midpoint height."""
    diagram = _diagram()
    curves = {item.value: item for item in diagram.isopleths if item.kind == "top_height"}
    y20 = isopleth_y(curves[20.0], 500.0)
    y25 = isopleth_y(curves[25.0], 500.0)
    assert y20 is not None
    assert y25 is not None
    result = interpolate_value(diagram, "top_height", 500.0, (y20 + y25) / 2.0)
    assert result == pytest.approx(22.5, abs=0.1)


def test_interpolate_value_returns_none_outside_the_family() -> None:
    """A mean tree volume above every curve cannot be read."""
    assert interpolate_value(_diagram(), "top_height", 500.0, 10.0) is None


def test_place_point_names_each_zone() -> None:
    """The boundaries separate understocked, managed, competition, and outside."""
    diagram = _diagram()
    assert place_point(diagram, 1000.0, 0.6).zone == "understocked"
    assert place_point(diagram, 1000.0, 1.2).zone == "density-management"
    assert place_point(diagram, 1000.0, 1.7).zone == "competition"
    assert place_point(diagram, 1000.0, 2.5).zone == "outside"


def test_place_point_flags_an_outside_axis_domain() -> None:
    """A density before the first digitised point is outside, not guessed."""
    placement = place_point(_diagram(), 100.0, 1.0)
    assert placement.zone == "outside"
    assert "outside-axis-domain" in placement.flags


def test_place_point_flags_an_isopleth_gap() -> None:
    """A point above the highest height curve cannot read a height."""
    placement = place_point(_diagram(), 1000.0, 1.7)
    assert placement.top_height_m is None
    assert "outside-isopleth-range" in placement.flags


def test_place_point_rejects_a_non_positive_coordinate() -> None:
    """Zero has no logarithm on either axis."""
    with pytest.raises(SdmdDiagramError, match="coordinates must be positive"):
        place_point(_diagram(), 0.0, 1.0)


def test_place_point_serializes() -> None:
    """The placement payload is JSON-serializable for the API."""
    payload = place_point(_diagram(), 1000.0, 1.2).to_dict()
    assert payload["zone"] == "density-management"
    assert isinstance(payload["flags"], list)


def test_observed_envelope_builds_a_hull() -> None:
    """The envelope has at least three vertices and contains an interior point."""
    points = list(zip(_points()["tph"], _points()["mean_tree_volume_m3"], strict=True))
    envelope = observed_envelope(points)
    assert len(envelope) >= 3
    assert inside_envelope((1500.0, 0.6), envelope)
    assert not inside_envelope((900.0, 1.5), envelope)


def test_observed_envelope_rejects_too_few_points() -> None:
    """Three points are the minimum for an area."""
    with pytest.raises(SdmdDiagramError, match="at least three"):
        observed_envelope(((1.0, 1.0), (2.0, 1.0)))


def test_observed_envelope_rejects_collinear_points() -> None:
    """A line does not span an envelope."""
    with pytest.raises(SdmdDiagramError, match="do not span an area"):
        observed_envelope(((1.0, 1.0), (2.0, 1.0), (3.0, 1.0)))


def test_observed_envelope_rejects_a_non_positive_point() -> None:
    """The logarithmic axes require positive coordinates."""
    with pytest.raises(SdmdDiagramError, match="positive"):
        observed_envelope(((0.0, 1.0), (2.0, 1.0), (3.0, 2.0)))


def test_inside_envelope_rejects_a_degenerate_hull() -> None:
    """A hull with fewer than three vertices contains nothing."""
    assert not inside_envelope((1.0, 1.0), ((1.0, 1.0), (2.0, 2.0)))


def test_assess_trajectory_inside() -> None:
    """A trajectory made of observed points is inside."""
    envelope = observed_envelope(
        ((980.0, 0.757), (2200.0, 0.128), (1700.0, 0.543), (1350.0, 0.793))
    )
    result = assess_trajectory(
        Trajectory(label="fvs", points=((1700.0, 0.543), (1350.0, 0.793))), envelope
    )
    assert result.status == "inside"
    assert result.first_outside is None
    assert result.point_count == 2


def test_assess_trajectory_reports_the_first_outside_point() -> None:
    """One outside point makes the whole trajectory an extrapolation."""
    envelope = observed_envelope(
        ((980.0, 0.757), (2200.0, 0.128), (1700.0, 0.543), (1350.0, 0.793))
    )
    result = assess_trajectory(
        Trajectory(label="fvs", points=((1700.0, 0.543), (900.0, 1.5))), envelope
    )
    assert result.status == "extrapolated"
    assert result.first_outside == (900.0, 1.5)


def test_assess_trajectory_refuses_a_density_and_volume_increase() -> None:
    """A path cannot gain trees and mean stem volume at the same time."""
    envelope = observed_envelope(
        ((980.0, 0.757), (2200.0, 0.128), (1700.0, 0.543), (1350.0, 0.793))
    )
    with pytest.raises(SdmdReportError, match="SDMD-TRAJECTORY-DENSITY"):
        assess_trajectory(
            Trajectory(label="impossible", points=((2400.0, 0.214), (3000.0, 5.0))),
            envelope,
        )


def test_assess_trajectory_rejects_an_empty_trajectory() -> None:
    """An empty trajectory has nothing to assess."""
    envelope = observed_envelope(
        ((980.0, 0.757), (2200.0, 0.128), (1700.0, 0.543), (1350.0, 0.793))
    )
    with pytest.raises(SdmdReportError, match="no points"):
        assess_trajectory(Trajectory(label="empty", points=()), envelope)


def test_build_au_report_refuses_an_unreviewed_diagram() -> None:
    """An unreviewed digitisation cannot enter a report."""
    with pytest.raises(SdmdReportError, match="needs a reviewed diagram"):
        build_au_report(au_id="AU-IDFdk3-FDI", diagram=_diagram(), observed=_points())


def test_build_au_report_is_supported_for_reviewed_evidence() -> None:
    """Reviewed evidence and an inside trajectory produce a supported report."""
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_reviewed(_diagram()),
        observed=_points(),
        trajectories=(Trajectory(label="fvs", points=((2400.0, 0.214), (1700.0, 0.543))),),
    )
    assert result.status == "supported"
    assert result.observed_count == 5
    assert result.observed_age_min == 40
    assert result.observed_age_max == 120
    assert result.trajectories[0].status == "inside"
    assert result.data_gaps == ()


def test_build_au_report_flags_an_extrapolated_trajectory() -> None:
    """A trajectory outside the envelope is named as extrapolation."""
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_reviewed(_diagram()),
        observed=_points(),
        trajectories=(Trajectory(label="kc-1173", points=((2400.0, 0.214), (900.0, 1.5))),),
    )
    assert result.status == "extrapolated"
    assert result.trajectories[0].status == "extrapolated"
    assert "trajectory kc-1173 leaves the observed envelope" in result.data_gaps


def test_build_au_report_rejects_an_initial_volume_over_the_limit() -> None:
    """The initial-volume gate rejects a value above the evidence limit."""
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_reviewed(_diagram()),
        observed=_points(),
        initial_volume_m3_ha=863.0,
        initial_volume_limit_m3_ha=800.0,
    )
    assert result.status == "rejected"
    assert any("initial volume exceeds" in gap for gap in result.data_gaps)


def test_build_au_report_accepts_an_initial_volume_at_the_limit() -> None:
    """The limit is inclusive."""
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_reviewed(_diagram()),
        observed=_points(),
        initial_volume_m3_ha=800.0,
        initial_volume_limit_m3_ha=800.0,
    )
    assert result.status == "supported"


def test_build_au_report_marks_an_au_without_points_unsupported() -> None:
    """No observed points means no envelope and an explicit gap."""
    empty = _points().iloc[0:0]
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_reviewed(_diagram()),
        observed=empty,
        allow_unreviewed=True,
    )
    assert result.status == "unsupported"
    assert result.observed_count == 0
    assert "fewer than three distinct observed points" in result.data_gaps


def test_build_au_report_marks_two_points_unsupported() -> None:
    """Two points cannot form an envelope."""
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_reviewed(_diagram()),
        observed=_points().iloc[:2],
    )
    assert result.status == "unsupported"
    assert result.observed_count == 2


def test_build_au_report_can_allow_a_provisional_diagram() -> None:
    """Method work can opt in to a provisional diagram and records the gap."""
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_diagram(),
        observed=_points(),
        allow_unreviewed=True,
    )
    assert result.review_status == "provisional"
    assert "diagram review status is provisional" in result.data_gaps


def test_build_au_report_serializes() -> None:
    """The report payload is JSON-serializable for the API."""
    result = build_au_report(
        au_id="AU-IDFdk3-FDI",
        diagram=_reviewed(_diagram()),
        observed=_points(),
        initial_volume_m3_ha=500.0,
        initial_volume_limit_m3_ha=800.0,
    )
    payload = result.to_dict()
    assert payload["status"] == "supported"
    assert isinstance(payload["envelope"], list)
    json.dumps(payload)


def test_build_au_report_rejects_bad_inputs() -> None:
    """An empty AU, a negative volume, and a non-positive limit fail."""
    with pytest.raises(SdmdReportError, match="au_id"):
        build_au_report(au_id=" ", diagram=_reviewed(_diagram()), observed=_points())
    with pytest.raises(SdmdReportError, match="negative"):
        build_au_report(
            au_id="AU-1",
            diagram=_reviewed(_diagram()),
            observed=_points(),
            initial_volume_m3_ha=-1.0,
        )
    with pytest.raises(SdmdReportError, match="positive"):
        build_au_report(
            au_id="AU-1",
            diagram=_reviewed(_diagram()),
            observed=_points(),
            initial_volume_limit_m3_ha=0.0,
        )


def test_build_au_report_requires_coordinate_columns() -> None:
    """The report cannot place a table that lacks the diagram coordinates."""
    with pytest.raises(SdmdReportError, match="missing column"):
        build_au_report(
            au_id="AU-1",
            diagram=_reviewed(_diagram()),
            observed=pd.DataFrame({"age": [10]}),
        )


def test_pilot_natural_diagram_is_a_valid_provisional_vector() -> None:
    """The digitised natural Interior Douglas-fir diagram is complete and provisional."""
    diagram = load_diagram(PILOT_DIAGRAM)
    assert validate_diagram(diagram) == []
    kinds: dict[str, int] = {}
    for isopleth in diagram.isopleths:
        kinds[isopleth.kind] = kinds.get(isopleth.kind, 0) + 1
    assert kinds == {
        "top_height": 10,
        "qmd": 10,
        "crown_closure": 1,
        "competition": 1,
        "self_thinning": 1,
    }
    assert diagram.review.status == "provisional"
    assert diagram.source.kind == "published"
    assert "BC-X-360" in diagram.source.citation
    assert len(diagram.source.citation) > 40


def test_pilot_natural_diagram_places_the_density_zones() -> None:
    """The digitised curves separate understocked, managed, competition, and outside."""
    diagram = load_diagram(PILOT_DIAGRAM)
    assert place_point(diagram, 1000.0, 0.01).zone == "understocked"
    assert place_point(diagram, 500.0, 0.05).zone == "density-management"
    assert place_point(diagram, 1000.0, 0.2).zone == "competition"
    assert place_point(diagram, 1000.0, 0.5).zone == "outside"


def test_pilot_natural_diagram_is_not_used_by_a_report_until_reviewed() -> None:
    """A provisional digitisation is still refused by the report path."""
    diagram = load_diagram(PILOT_DIAGRAM)
    with pytest.raises(SdmdReportError, match="needs a reviewed diagram"):
        build_au_report(au_id="AU-IDFdk3-FDI", diagram=diagram, observed=_points())
