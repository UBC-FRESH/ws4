"""Contract tests for SDMD PSP, VRI, and LiDAR ingestion."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.sdmd.ingest import (
    AuMatchResult,
    SdmdIngestError,
    label_synthetic,
    leading_species,
    match_plots_to_aus,
    read_lidar_evidence,
    read_psp_plots,
    read_psp_trees,
    read_vri_aus,
)
from ws4.sdmd.schema import SDMD_TABLE_NAMES, coerce_to_schema, table_schema, validate_dataset

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"


def _raw(name: str) -> pd.DataFrame:
    """Read one raw fixture table.

    Parameters
    ----------
    name : str
        Table name without the suffix.

    Returns
    -------
    pandas.DataFrame
        The raw table.
    """
    return pd.read_csv(FIXTURE / f"{name}.csv")


def _aus() -> pd.DataFrame:
    """Return the two-AU VRI assignment used by the matching tests.

    Returns
    -------
    pandas.DataFrame
        One row per AU with a BEC/TSA key, a species group, and windows.
    """
    return pd.DataFrame(
        {
            "au_id": ["AU-IDFdk3-FDI", "AU-IDFdk3-PLI"],
            "region": ["Interior", "Interior"],
            "bec_zone": ["IDF", "IDF"],
            "bec_subzone": ["dk", "dk"],
            "bec_variant": ["3", "3"],
            "tsa": ["TSA-24", "TSA-24"],
            "species_group": ["FDI", "PLI"],
            "min_age": [30, 30],
            "max_age": [140, 140],
            "min_site_index": [10.0, 10.0],
            "max_site_index": [30.0, 30.0],
        }
    )


def _leading() -> pd.DataFrame:
    """Return the fixture's leading species per plot.

    Returns
    -------
    pandas.DataFrame
        ``plot_id`` and ``species_group``.
    """
    return leading_species(_raw("trees"))


def _without_au(plots: pd.DataFrame) -> pd.DataFrame:
    """Return the plot table with its AU column blanked.

    Parameters
    ----------
    plots : pandas.DataFrame
        The plot table.

    Returns
    -------
    pandas.DataFrame
        A copy whose ``au_id`` is empty, to exercise matching.
    """
    result = plots.copy()
    result["au_id"] = ""
    return result


def test_read_psp_plots_normalizes_aliases() -> None:
    """Short column aliases produce the canonical plot contract."""
    raw = _raw("plots").rename(
        columns={
            "plot_id": "plot",
            "visit_year": "year",
            "stand_age": "age",
            "site_index": "si",
            "au_id": "au",
            "bec_zone": "zone",
            "bec_subzone": "subzone",
            "bec_variant": "variant",
        }
    )
    result = read_psp_plots(raw)
    assert {"plot_id", "visit_year", "au_id", "bec_variant"} <= set(result.columns)
    assert str(result.loc[0, "plot_id"]) == "PLOT-A01"
    coerce_to_schema(result, table_schema("plots"))


def test_read_psp_plots_rejects_a_missing_column() -> None:
    """A plot table without its BEC identity cannot be ingested."""
    with pytest.raises(SdmdIngestError, match="missing required column"):
        read_psp_plots(_raw("plots").drop(columns=["region"]))


def test_read_psp_plots_rejects_a_schema_problem() -> None:
    """Schema findings surface as one ingest error with the stable code."""
    raw = _raw("plots")
    raw.loc[0, "stand_age"] = -1
    with pytest.raises(SdmdIngestError, match="SDMD-RANGE"):
        read_psp_plots(raw)


def test_read_psp_plots_rejects_unlabelled_nemora() -> None:
    """A gap-fill row cannot enter as an observation without a synthetic label."""
    raw = _raw("plots")
    raw.loc[0, "sources"] = "nemora"
    raw.loc[0, "review_status"] = "provisional"
    with pytest.raises(SdmdIngestError, match="unlabelled nemora"):
        read_psp_plots(raw)


def test_label_synthetic_marks_the_source_and_review_status() -> None:
    """Labelling turns a gap-fill row into an admissible synthetic row."""
    raw = _raw("plots").iloc[[0]].copy()
    raw.loc[:, "sources"] = "nemora"
    raw.loc[:, "review_status"] = "reviewed"
    labelled = label_synthetic(raw)
    assert labelled.loc[0, "sources"] == "synthetic:nemora"
    assert labelled.loc[0, "review_status"] == "provisional"
    assert len(read_psp_plots(labelled)) == 1


def test_read_psp_trees_normalizes_aliases() -> None:
    """A tree list with short aliases is accepted against its plots."""
    raw = _raw("trees").rename(
        columns={
            "tree_id": "tree",
            "dbh_cm": "dbh",
            "height_m": "height",
            "crown_ratio": "crown",
            "tph": "expansion",
        }
    )
    result = read_psp_trees(raw, plots=_raw("plots"))
    assert str(result.loc[0, "tree_id"]) == "T01"
    assert result.loc[0, "dbh_cm"] == 14.7


def test_read_psp_trees_rejects_an_unknown_plot() -> None:
    """A tree list may only name plots in the plot table."""
    raw = _raw("trees")
    raw.loc[0, "plot_id"] = "PLOT-MISSING"
    with pytest.raises(SdmdIngestError, match="PLOT-MISSING"):
        read_psp_trees(raw, plots=_raw("plots"))


def test_read_vri_aus_types_and_windows() -> None:
    """AU bounds are numeric and the text fields are trimmed."""
    result = read_vri_aus(_aus())
    assert str(result.loc[0, "au_id"]) == "AU-IDFdk3-FDI"
    assert result.loc[0, "max_age"] == 140.0
    assert result["min_age"].dtype == "Float64"


def test_read_vri_aus_rejects_a_duplicate_au() -> None:
    """Two AU rows with one id would make matching ambiguous by construction."""
    raw = pd.concat([_aus(), _aus().iloc[[0]]], ignore_index=True)
    with pytest.raises(SdmdIngestError, match="repeat au_id"):
        read_vri_aus(raw)


def test_read_vri_aus_rejects_an_inverted_window() -> None:
    """A minimum age above the maximum is contradictory."""
    raw = _aus()
    raw.loc[0, "min_age"] = 200
    with pytest.raises(SdmdIngestError, match="min_age"):
        read_vri_aus(raw)


def test_read_vri_aus_rejects_blank_identity() -> None:
    """An AU without a TSA cannot be matched to a plot."""
    raw = _aus()
    raw.loc[0, "tsa"] = "  "
    with pytest.raises(SdmdIngestError, match="blank tsa"):
        read_vri_aus(raw)


def test_leading_species_uses_total_tph() -> None:
    """The leading group is the species with the most expanded TPH."""
    trees = pd.DataFrame(
        {
            "plot_id": ["P1", "P1", "P2"],
            "species": ["FDI", "PLI", "FDI"],
            "tph": [10.0, 90.0, 5.0],
        }
    )
    result = leading_species(trees)
    assert result.set_index("plot_id").loc["P1", "species_group"] == "PLI"


def test_leading_species_breaks_a_tie_deterministically() -> None:
    """Equal TPH chooses the species code in ascending order."""
    trees = pd.DataFrame(
        {
            "plot_id": ["P1", "P1"],
            "species": ["PLI", "FDI"],
            "tph": [50.0, 50.0],
        }
    )
    result = leading_species(trees)
    assert result.loc[0, "species_group"] == "FDI"


def test_match_plots_to_aus_assigns_each_plot() -> None:
    """A unique BEC/TSA/species/age/site match fills the AU."""
    result = match_plots_to_aus(_without_au(_raw("plots")), _aus(), leading_species=_leading())
    assert isinstance(result, AuMatchResult)
    assert len(result.matched) == 10
    assert result.unmatched.empty
    assert set(result.matched["au_id"]) == {"AU-IDFdk3-FDI", "AU-IDFdk3-PLI"}


def test_match_plots_to_aus_keeps_a_preassigned_au() -> None:
    """An AU that exists in the VRI table is not re-matched."""
    result = match_plots_to_aus(_raw("plots"), _aus(), leading_species=_leading())
    assert len(result.matched) == 10
    assert result.unmatched.empty


def test_match_plots_to_aus_reports_an_unknown_preassigned_au() -> None:
    """A preassigned AU that the VRI table does not contain is reported."""
    plots = _raw("plots")
    plots.loc[0, "au_id"] = "AU-MISSING"
    result = match_plots_to_aus(plots, _aus(), leading_species=_leading())
    assert len(result.matched) == 9
    assert "preassigned AU not in VRI table" in str(result.unmatched.iloc[0]["match_reason"])


def test_match_plots_to_aus_reports_no_match() -> None:
    """No candidate is reported, not guessed."""
    aus = _aus()
    aus["tsa"] = "TSA-99"
    result = match_plots_to_aus(_without_au(_raw("plots")), aus, leading_species=_leading())
    assert result.matched.empty
    assert len(result.unmatched) == 10
    assert "no AU matched" in str(result.unmatched.iloc[0]["match_reason"])


def test_match_plots_to_aus_reports_ambiguity() -> None:
    """Two equal rules are ambiguous and are not resolved by row order."""
    aus = pd.concat([_aus().iloc[[0]], _aus().iloc[[0]].assign(au_id="AU-OTHER")])
    result = match_plots_to_aus(_without_au(_raw("plots")), aus, leading_species=_leading())
    reasons = set(result.unmatched["match_reason"].astype(str))
    assert any(reason.startswith("ambiguous match") for reason in reasons)


def test_match_plots_to_aus_uses_the_age_window() -> None:
    """A plot outside the AU age window is reported."""
    aus = _aus().iloc[[0]].copy()
    aus["max_age"] = 50
    result = match_plots_to_aus(_without_au(_raw("plots")), aus, leading_species=_leading())
    assert len(result.matched) == 1
    assert len(result.unmatched) == 9


def test_match_plots_to_aus_uses_the_species_group() -> None:
    """A plot whose leading species differs from the AU is reported."""
    aus = _aus().iloc[[0]].copy()
    result = match_plots_to_aus(_without_au(_raw("plots")), aus, leading_species=_leading())
    assert len(result.matched) == 5
    assert len(result.unmatched) == 5


def test_match_plots_to_aus_without_species_uses_the_other_keys() -> None:
    """Species is optional; the BEC/TSA/age/site key still has to be unique."""
    aus = _aus().iloc[[0]].copy()
    result = match_plots_to_aus(_without_au(_raw("plots")), aus)
    assert len(result.matched) == 10


def test_read_lidar_evidence_accepts_total_tph() -> None:
    """A total basis may carry a TPH."""
    frame = pd.DataFrame(
        {
            "au_id": ["AU-1"],
            "piece_size_m3": [0.8],
            "clump_fraction": [0.35],
            "canopy_cover_pct": [55.0],
            "tph": [1200.0],
            "tph_basis": ["total"],
            "source": ["lidar"],
            "review_status": ["reviewed"],
        }
    )
    result = read_lidar_evidence(frame)
    assert result.loc[0, "tph"] == 1200.0


def test_read_lidar_evidence_accepts_canopy_structure_without_tph() -> None:
    """Canopy-only evidence may describe structure but not density."""
    frame = pd.DataFrame(
        {
            "au_id": ["AU-1"],
            "piece_size_m3": [0.4],
            "clump_fraction": [0.6],
            "canopy_cover_pct": [70.0],
            "tph_basis": ["canopy_only"],
            "source": ["lidar"],
            "review_status": ["provisional"],
        }
    )
    result = read_lidar_evidence(frame)
    assert result["tph"].isna().iloc[0]


def test_read_lidar_evidence_refuses_canopy_only_tph() -> None:
    """Canopy-derived density is not total stand density."""
    frame = pd.DataFrame(
        {
            "au_id": ["AU-1"],
            "tph": [900.0],
            "tph_basis": ["canopy_only"],
            "source": ["lidar"],
            "review_status": ["reviewed"],
        }
    )
    with pytest.raises(SdmdIngestError, match="canopy-only LiDAR TPH"):
        read_lidar_evidence(frame)


def test_read_lidar_evidence_refuses_an_unknown_basis() -> None:
    """The basis is a closed set so the total/canopy distinction is never vague."""
    frame = pd.DataFrame(
        {
            "au_id": ["AU-1"],
            "piece_size_m3": [0.4],
            "tph_basis": ["unknown"],
            "source": ["lidar"],
            "review_status": ["reviewed"],
        }
    )
    with pytest.raises(SdmdIngestError, match="unknown tph_basis"):
        read_lidar_evidence(frame)


def test_read_lidar_evidence_refuses_a_non_positive_piece_size() -> None:
    """A zero piece size is not evidence."""
    frame = pd.DataFrame(
        {
            "au_id": ["AU-1"],
            "piece_size_m3": [0.0],
            "tph_basis": ["total"],
            "source": ["lidar"],
            "review_status": ["reviewed"],
        }
    )
    with pytest.raises(SdmdIngestError, match="piece_size_m3"):
        read_lidar_evidence(frame)


def test_read_lidar_evidence_refuses_an_out_of_range_fraction() -> None:
    """A clump fraction is a fraction."""
    frame = pd.DataFrame(
        {
            "au_id": ["AU-1"],
            "clump_fraction": [1.5],
            "tph_basis": ["total"],
            "source": ["lidar"],
            "review_status": ["reviewed"],
        }
    )
    with pytest.raises(SdmdIngestError, match="clump_fraction"):
        read_lidar_evidence(frame)


def test_read_lidar_evidence_refuses_an_empty_row() -> None:
    """Evidence must carry at least one metric."""
    frame = pd.DataFrame(
        {
            "au_id": ["AU-1"],
            "tph_basis": ["total"],
            "source": ["lidar"],
            "review_status": ["reviewed"],
        }
    )
    with pytest.raises(SdmdIngestError, match="no piece size"):
        read_lidar_evidence(frame)


def test_read_lidar_evidence_normalizes_aliases() -> None:
    """Short aliases are accepted for the structural metrics."""
    frame = pd.DataFrame(
        {
            "au": ["AU-1"],
            "piece_size": [0.5],
            "clump": [0.4],
            "cover": [50.0],
            "basis": ["canopy_only"],
            "source": ["lidar"],
            "review_status": ["provisional"],
        }
    )
    result = read_lidar_evidence(frame)
    assert result.loc[0, "piece_size_m3"] == 0.5


def test_ingested_tables_validate_with_the_fixture() -> None:
    """Adapter output drops into the six-table contract unchanged."""
    frames = {name: coerce_to_schema(_raw(name), table_schema(name)) for name in SDMD_TABLE_NAMES}
    frames["plots"] = read_psp_plots(_raw("plots"))
    frames["trees"] = read_psp_trees(_raw("trees"), plots=frames["plots"])
    assert validate_dataset(frames, required=SDMD_TABLE_NAMES) == []
