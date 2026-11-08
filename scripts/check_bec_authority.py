"""Check the packaged BEC authority tables and their source manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"
MANIFEST = DATA / "bec_sources.json"


def _digest(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_bec_authority(data: Path = DATA, manifest: Path = MANIFEST) -> list[str]:
    """Return contract failures for the BEC authority tables.

    Parameters
    ----------
    data : Path, optional
        Directory holding the packaged BEC CSVs. Defaults to the package data.
    manifest : Path, optional
        Source manifest with file digests and source metadata.

    Returns
    -------
    list of str
        Human-readable failures; empty when the tables and manifest agree.
    """
    failures: list[str] = []
    official = pd.read_csv(data / "bec_official.csv", dtype=str).fillna("")
    retired = pd.read_csv(data / "bec_retired.csv", dtype=str).fillna("")
    variants = pd.read_csv(data / "bec_variants.csv", dtype=str).fillna("")
    counts = pd.read_csv(data / "tsa_bec_counts.csv", dtype=str).fillna("")
    official_crosswalk = pd.read_csv(data / "bec_official_crosswalk.csv", dtype=str).fillna("")
    cciss = pd.read_csv(data / "bec_crosswalk_review.csv", dtype=str).fillna("")
    coverage = pd.read_csv(data / "bec_coverage.csv", dtype=str).fillna("")
    review_queue = pd.read_csv(data / "bec_review_queue.csv", dtype=str).fillna("")

    if len(official) != 219 or official["bec"].nunique() != 219:
        failures.append("bec_official.csv must have 219 unique current labels")
    if len(retired) != 107 or retired["bec"].nunique() != 107:
        failures.append("bec_retired.csv must have 107 unique retired labels")
    labels = (variants["zone"] + variants["subzone"] + variants["variant"]).astype(str)
    if len(variants) != 229 or labels.nunique() != 213:
        failures.append("bec_variants.csv must have 229 rows and 213 unique labels")
    if len(counts) != 304 or "ICHmw5" in set(counts["bec"]):
        failures.append("tsa_bec_counts.csv must have 304 normalized variant rows")
    if set(counts.get("bec_level", pd.Series(dtype=str))) != {"variant"}:
        failures.append("tsa_bec_counts.csv must contain only variant-level support")
    official_counts = official_crosswalk["relationship"].value_counts().to_dict()
    if official_counts != {
        "official_exact": 165,
        "retired": 48,
        "not_in_ws4": 51,
        "covered_by_finer": 3,
    }:
        failures.append(f"unexpected official crosswalk counts: {official_counts}")
    cciss_counts = cciss["relationship"].value_counts().to_dict()
    if cciss_counts != {
        "same": 183,
        "not_in_ws4": 19,
        "not_in_cciss": 19,
        "cciss_split": 9,
        "ws4_split": 7,
    }:
        failures.append(f"unexpected CCISS crosswalk counts: {cciss_counts}")
    if cciss.duplicated(["ws4_bec", "cciss_bec"]).any():
        failures.append("CCISS crosswalk has duplicate label pairs")
    coverage_counts = coverage["coverage_status"].value_counts().to_dict()
    if len(coverage) != 219 or coverage_counts != {
        "mixed_zone": 195,
        "no_diagram": 4,
        "reviewed_variant": 1,
        "reviewed_zone": 19,
    }:
        failures.append(f"unexpected BEC coverage counts: {coverage_counts}")
    gap_counts = (
        coverage[coverage["coverage_status"] == "no_diagram"]["gap_reason"].value_counts().to_dict()
    )
    if gap_counts != {"no_atlas_zone": 4}:
        failures.append(f"unexpected coverage gap counts: {gap_counts}")
    queued_labels: set[str] = set()
    for value in review_queue["bec_labels"]:
        queued_labels.update(item for item in str(value).split(";") if item)
    if len(review_queue) != 2 or len(queued_labels) != 196:
        failures.append("provisional review queue must name 2 diagrams and 196 BEC labels")

    if not manifest.is_file():
        failures.append(f"missing source manifest: {manifest}")
        return failures
    # json.loads returns Any; the manifest is a JSON object with a files mapping.
    payload: Any = json.loads(manifest.read_text(encoding="utf-8"))
    files = payload.get("files", {})
    for name, record in files.items():
        path = data / name
        if not path.is_file():
            failures.append(f"manifest names a missing file: {name}")
            continue
        expected = str(record.get("sha256", ""))
        if expected and _digest(path) != expected:
            failures.append(f"{name} digest changed")
    for name in (
        "bec_official.csv",
        "bec_retired.csv",
        "bec_variants.csv",
        "tsa_bec_counts.csv",
        "bec_official_crosswalk.csv",
        "bec_crosswalk_review.csv",
        "bec_coverage.csv",
        "bec_review_queue.csv",
    ):
        if name not in files:
            failures.append(f"manifest does not cover {name}")
    return failures


def main() -> int:
    """Run the BEC authority check and print failures.

    Returns
    -------
    int
        Zero when the tables and manifest agree, one otherwise.
    """
    failures = check_bec_authority()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("BEC authority tables and source manifest agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
