"""Build the BC-wide SDMD coverage registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"

#: Zone-level diagrams from the public SDMD atlas. These are provisional unless
#: a reviewed diagram overrides them for a specific variant.
ZONE_DIAGRAMS: dict[str, tuple[str, ...]] = {
    "CDF": ("fdcn", "fdcp", "ssn", "ssp"),
    "CWH": ("fdcn", "fdcp", "ssn", "ssp", "cwn", "cwp", "hwn", "hwp"),
    "MH": ("ssn", "ssp", "hwn", "hwp"),
    "SBS": ("swn", "swp"),
}

#: Variant-specific diagrams that are reviewed and safe to name exactly.
VARIANT_DIAGRAMS: dict[str, tuple[str, ...]] = {
    "IDFdk3": ("fdin", "fdip", "pln", "plp"),
}

DIAGRAM_META: dict[str, tuple[str, str, str]] = {
    "fdcn": ("FDC", "natural", "fdcn"),
    "fdcp": ("FDC", "planted", "fdcp"),
    "fdin": ("FDI", "natural", "fdin"),
    "fdip": ("FDI", "planted", "fdip"),
    "pln": ("PLI", "natural", "pln"),
    "plp": ("PLI", "planted", "plp"),
    "ssn": ("SS", "natural", "ssn"),
    "ssp": ("SS", "planted", "ssp"),
    "hwn": ("HW", "natural", "hwn"),
    "hwp": ("HW", "planted", "hwp"),
    "cwn": ("CW", "natural", "cwn"),
    "cwp": ("CW", "planted", "cwp"),
    "swn": ("SW", "natural", "swn"),
    "swp": ("SW", "planted", "swp"),
}

AU_EVIDENCE: dict[str, tuple[str, ...]] = {"IDFdk3": ("AU-IDFdk3-TSA23-FDI", "AU-IDFdk3-TSA23-PLI")}


def _diagram_reviews() -> dict[str, str]:
    """Read the review status for each Atlas diagram."""
    reviews: dict[str, str] = {}
    for path in sorted(DATA.glob("*.json")):
        try:
            diagram: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(diagram, dict):
            continue
        if not str(diagram.get("schema_version", "")).startswith("ws4.sdmd.diagram"):
            continue
        species = str(diagram.get("species_group", ""))
        origin = "planted" if path.stem.endswith("-planted") else "natural"
        if "illustrative" in path.stem:
            continue
        for diagram_id, (expected_species, expected_origin, _) in DIAGRAM_META.items():
            if species == expected_species and origin == expected_origin:
                reviews[diagram_id] = str(diagram.get("review", {}).get("status", "unreviewed"))
    return reviews


def build_coverage() -> pd.DataFrame:
    """Return one row per current BEC label with diagram and evidence status.

    Returns
    -------
    pandas.DataFrame
        The 219-row coverage registry.
    """
    official = pd.read_csv(DATA / "bec_official.csv", dtype=str).fillna("")
    reviews = _diagram_reviews()
    rows: list[dict[str, object]] = []
    for row in official.sort_values("bec").itertuples(index=False):
        bec = str(row.bec)
        diagrams = list(VARIANT_DIAGRAMS.get(bec, ()))
        match_level = "variant" if diagrams else ""
        if not diagrams:
            diagrams = list(ZONE_DIAGRAMS.get(str(row.zone), ()))
            match_level = "zone" if diagrams else ""
        species = sorted({DIAGRAM_META[item][0] for item in diagrams})
        origins = sorted({DIAGRAM_META[item][1] for item in diagrams})
        statuses = [reviews.get(item, "unreviewed") for item in diagrams]
        reviewed = sum(1 for status in statuses if status == "reviewed")
        provisional = sum(1 for status in statuses if status == "provisional")
        if reviewed:
            status = "reviewed"
            note = "Reviewed variant-specific diagrams."
        elif provisional:
            status = "provisional"
            note = "Zone-level provisional diagrams; verify BEC variant, species, and origin."
        else:
            status = "no-diagram"
            note = "No digitized SDMD diagram covers this BEC label."
        au_ids = AU_EVIDENCE.get(bec, ())
        rows.append(
            {
                "bec": bec,
                "zone": str(row.zone),
                "subzone": str(row.subzone),
                "variant": str(row.variant),
                "zone_name": str(row.zone_name),
                "subzone_name": str(row.subzone_name),
                "variant_name": str(row.variant_name),
                "coverage_status": status,
                "match_level": match_level,
                "diagram_ids": ";".join(diagrams),
                "species": ";".join(species),
                "origins": ";".join(origins),
                "reviewed_count": reviewed,
                "provisional_count": provisional,
                "au_ids": ";".join(au_ids),
                "evidence_status": "pilot" if au_ids else "none",
                "note": note,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    """Write the coverage CSV and print a summary.

    Returns
    -------
    int
        Zero after the registry is written.
    """
    frame = build_coverage()
    output = DATA / "bec_coverage.csv"
    frame.to_csv(output, index=False)
    counts = frame["coverage_status"].value_counts().to_dict()
    print(f"wrote {len(frame)} rows to {output}")
    print(f"status counts: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
