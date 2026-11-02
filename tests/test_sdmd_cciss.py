"""Contract tests for the derived CCISS species and BEC extracts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"


def _read(name: str) -> pd.DataFrame:
    """Read one derived CCISS extract.

    Parameters
    ----------
    name : str
        File name in the SDMD data directory.

    Returns
    -------
    pandas.DataFrame
        The table.
    """
    return pd.read_csv(DATA / name)


def test_tree_species_catalog_is_attributed_and_complete() -> None:
    """The catalog carries the seven SDMD species and an explicit licence."""
    frame = _read("tree_species.csv")
    assert len(frame) == 37
    assert set(frame["tree_code"]) >= {"Fd", "Pl", "Sw", "Hw", "Cw", "Ss"}
    assert frame["tree_code"].is_unique
    assert frame["source"].str.contains("ccissr").all()
    assert frame["licence"].str.contains("Apache").all()


def test_sdmd_species_traits_cover_the_six_diagram_species() -> None:
    """The trait subset covers the six species in the public SDMD set."""
    frame = _read("species_traits.csv")
    assert set(frame["tree_code"]) == {"Cw", "Fd", "Hw", "Pl", "Ss", "Sw"}
    lodgepole = frame.loc[frame["tree_code"] == "Pl"].iloc[0]
    assert lodgepole["low_light_tolerance"] == "L"
    assert lodgepole["water_deficit_tolerance"] == "H"
    assert lodgepole["fire_risk"] == "H"


def test_idfdk3_stocking_prefers_lodgepole_pine() -> None:
    """Lodgepole pine is preferred in eight of nine IDFdk3 site series."""
    frame = _read("idfdk3_stocking.csv")
    assert len(frame) == 9
    preferred = (
        frame["preferred_species"].fillna("").str.split(";").apply(lambda values: "Pl" in values)
    )
    acceptable = (
        frame["acceptable_species"].fillna("").str.split(";").apply(lambda values: "Pl" in values)
    )
    assert int(preferred.sum()) == 8
    assert int(acceptable.sum()) == 1
    assert frame["target_stems_ha"].min() == 800
    assert frame["target_stems_ha"].max() == 1200
    assert frame["edatopic"].notna().all()
    assert set(frame["stocking_delay_years"]) == {4.0, 7.0}


def test_bec_crosswalk_names_the_version_differences() -> None:
    """The crosswalk keeps the SDMD-only and CCISS-only BEC rows visible."""
    frame = _read("bec_crosswalk.csv")
    counts = frame["note"].value_counts().to_dict()
    assert counts == {"both": 183, "cciss-only": 34, "sdmd-only": 30}
    assert frame.loc[frame["bec"] == "IDFdk3", "note"].item() == "both"


def test_idfdk3_suitability_rates_lodgepole_pine() -> None:
    """CCISS feasibility gives lodgepole pine a rating on every IDFdk3 site series."""
    frame = _read("idfdk3_suitability.csv")
    pine = frame.loc[(frame["species_code"] == "Pli") & (frame["site_series"] != "Ro")]
    assert len(pine) == 9
    assert pine["feasible_rating"].between(1, 4).all()
    assert set(pine["site_series"]) == {f"{number:02d}" for number in range(1, 10)}


def test_idfdk3_sibec_gives_species_site_index() -> None:
    """SIBEC supplies site index for the species used in the IDFdk3 pilot."""
    frame = _read("idfdk3_sibec.csv")
    assert set(frame["species_code"]) >= {"Fd", "Pl", "Sx"}
    assert frame["mean_site_index_m"].between(13, 23).all()
    assert len(frame) == 32
