"""Contract tests for the public BC SDMD source catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict, cast

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"
CATALOG = DATA / "source_catalog.json"
VARIANTS = DATA / "bec_variants.csv"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class _Diagram(TypedDict):
    """One diagram entry in the catalog."""

    diagram_id: str
    species_code: str
    file_name: str
    url: str
    origin: str
    pages: int
    size_bytes: int
    sha256: str
    bec_main: list[str]
    bec_basis: str
    page_label: str
    pdf_title: str
    aliases: list[str]


class _Report(TypedDict):
    """The methods report entry."""

    report_id: str
    pages: int
    sha256: str
    url: str


class _Catalog(TypedDict):
    """The decoded source catalog."""

    schema_version: str
    diagram_count: int
    species_count: int
    diagrams: list[_Diagram]
    guides: list[dict[str, object]]
    report: _Report
    digitizations: list[dict[str, object]]


def _catalog() -> _Catalog:
    """Load the source catalog.

    Returns
    -------
    _Catalog
        The decoded catalog.
    """
    # json.loads returns Any; the test asserts the shape below.
    return cast(_Catalog, json.loads(CATALOG.read_text(encoding="utf-8")))


def _variants() -> pd.DataFrame:
    """Load the BEC variant table with text identifiers.

    Returns
    -------
    pandas.DataFrame
        The 229 BEC rows.
    """
    return pd.read_csv(VARIANTS, dtype={"zone": str, "subzone": str, "variant": str})


def test_catalog_covers_the_public_bc_set() -> None:
    """The BC set is seven species in natural and planted versions."""
    catalog = _catalog()
    diagrams = catalog["diagrams"]
    assert catalog["schema_version"] == "ws4.sdmd.sources.v1"
    assert catalog["diagram_count"] == 14
    assert catalog["species_count"] == 7
    assert len(diagrams) == 14
    assert {item["species_code"] for item in diagrams} == {
        "Fdc",
        "Fdi",
        "Pl",
        "Ss",
        "Hw",
        "Cw",
        "Sw",
    }


def test_every_diagram_has_provenance() -> None:
    """Each diagram records its URL, version, size, and checksum."""
    for item in _catalog()["diagrams"]:
        assert item["diagram_id"] == item["file_name"].removesuffix(".pdf")
        assert item["url"].startswith("https://www2.gov.bc.ca/")
        assert item["origin"] in {"natural", "planted"}
        assert item["pages"] == 1
        assert item["size_bytes"] > 0
        assert SHA256.match(item["sha256"])
        assert item["bec_main"]
        assert item["bec_basis"]


def test_every_diagram_id_is_unique() -> None:
    """Two diagrams cannot share an id."""
    ids = [item["diagram_id"] for item in _catalog()["diagrams"]]
    assert len(ids) == len(set(ids))


def test_guides_and_report_are_recorded() -> None:
    """The instructional guides and the Farnden report carry provenance too."""
    catalog = _catalog()
    assert len(catalog["guides"]) == 5
    report = catalog["report"]
    assert report["report_id"] == "farnden-1996-bc-x-360"
    assert report["pages"] == 41
    assert SHA256.match(report["sha256"])
    assert report["url"].startswith("https://resources.sipexchangebc.com/")


def test_variant_table_covers_every_bec_row() -> None:
    """The variant table has the full BEC export and consistent diagram ids."""
    variants = _variants()
    diagram_ids = {item["diagram_id"] for item in _catalog()["diagrams"]}
    assert len(variants) == 229
    assert {"zone", "subzone", "variant", "bec_name", "sdmd_main", "sdmd_rare"} <= set(
        variants.columns
    )
    for column in ("sdmd_main", "sdmd_rare"):
        for value in variants[column].dropna():
            for diagram_id in str(value).split(";"):
                if diagram_id:
                    assert diagram_id in diagram_ids


def test_pilot_variant_resolves_to_interior_douglas_fir() -> None:
    """IDFdk3 has the natural and planted Interior Douglas-fir diagrams."""
    variants = _variants()
    row = variants.loc[
        (variants["zone"] == "IDF") & (variants["subzone"] == "dk") & (variants["variant"] == "3")
    ].iloc[0]
    main = set(str(row["sdmd_main"]).split(";"))
    assert {"fdin", "fdip"} <= main
    assert row["bec_name"] == "Interior Douglas-fir"


def test_alpine_rows_have_no_diagram() -> None:
    """An alpine variant is not silently given a forest diagram."""
    variants = _variants()
    alpine = variants.loc[variants["zone"] == "BAFA"]
    assert not alpine.empty
    assert alpine["sdmd_main"].fillna("").str.strip().eq("").all()


def test_page_labels_cover_all_fourteen_diagrams() -> None:
    """The catalog mirrors every label on the BC index page."""
    diagrams = _catalog()["diagrams"]
    labels = {item["page_label"] for item in diagrams}
    assert len(labels) == 14
    assert "White pine (natural)" in labels
    assert "White pine (planted)" in labels
    mislabelled = [item for item in diagrams if "White pine" in item["aliases"]]
    assert {item["diagram_id"] for item in mislabelled} == {"swn", "swp"}
    assert all(item["pdf_title"] == "White spruce" for item in mislabelled)


def test_digitised_diagrams_are_catalogued() -> None:
    """The pilot digitizations name their source PDF and the reviewer of record."""
    catalog = _catalog()
    entries = catalog["digitizations"]
    assert len(entries) == 14
    assert sum(entry["review_status"] == "reviewed" for entry in entries) == 4
    for entry in entries:
        assert entry["review_status"] in {"reviewed", "provisional"}
        if entry["review_status"] == "reviewed":
            assert entry["reviewer"]
        source = next(
            item for item in catalog["diagrams"] if item["diagram_id"] == entry["source_diagram_id"]
        )
        assert entry["source_sha256"] == source["sha256"]
        assert (DATA / str(entry["file"])).is_file()
