"""Build the provisional SDMD diagram review packet."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ws4.sdmd.diagram import Isopleth, SdmdDiagram

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"
REVIEW = Path(__file__).resolve().parents[1] / "notes" / "review"
PAGE_DIR = REVIEW / "p136-pages"
CURVE_DIR = REVIEW / "p136-curves"
CACHE = Path(
    os.environ.get(
        "WS4_SDMD_REVIEW_CACHE",
        str(Path(tempfile.gettempdir()) / "ws4-sdmd-review-cache"),
    )
)

ID_TO_JSON: dict[str, str] = {
    "fdcn": "cdf-cwh-fdc-natural.json",
    "fdcp": "cdf-cwh-fdc-planted.json",
    "ssn": "cdf-cwh-ss-natural.json",
    "ssp": "cdf-cwh-ss-planted.json",
    "hwn": "cwh-hw-natural.json",
    "hwp": "cwh-hw-planted.json",
    "cwn": "cwh-cw-natural.json",
    "cwp": "cwh-cw-planted.json",
    "swn": "sbs-sw-natural.json",
    "swp": "sbs-sw-planted.json",
}


def _sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _download(url: str, sha256: str, cache: Path = CACHE) -> Path:
    """Download a source PDF and verify its catalogue hash.

    Parameters
    ----------
    url : str
        Source PDF URL.
    sha256 : str
        Expected SHA-256 digest.
    cache : Path, optional
        Local cache directory.

    Returns
    -------
    Path
        The verified PDF.

    Raises
    ------
    ValueError
        If the downloaded file does not match the catalogue hash.
    """
    cache.mkdir(parents=True, exist_ok=True)
    name = url.rsplit("/", 1)[-1]
    target = cache / name
    if not target.is_file() or _sha256(target) != sha256:
        request = urllib.request.Request(url, headers={"User-Agent": "WS4-SDMD-review/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            target.write_bytes(response.read())
    actual = _sha256(target)
    if actual != sha256:
        raise ValueError(f"{name}: expected {sha256}, got {actual}")
    return target


def curve_summary(diagram: SdmdDiagram) -> dict[str, str]:
    """Return a compact inventory of one diagram's curve families.

    Parameters
    ----------
    diagram : SdmdDiagram
        The loaded diagram.

    Returns
    -------
    dict of str to str
        Human-readable counts and value ranges.
    """
    groups: dict[str, list[Isopleth]] = {}
    for curve in diagram.isopleths:
        groups.setdefault(curve.kind, []).append(curve)
    summary: dict[str, str] = {}
    for kind, curves in sorted(groups.items()):
        values = sorted({round(curve.value, 3) for curve in curves})
        summary[kind] = f"{len(curves)} curves; values {values[0]}..{values[-1]}"
    return summary


def review_rows() -> list[dict[str, object]]:
    """Return one validated review row per provisional diagram.

    Returns
    -------
    list of dict
        Queue row, diagram path, curve summary, and validation findings.
    """
    from ws4.sdmd.diagram import load_diagram, validate_diagram

    queue = pd.read_csv(DATA / "bec_review_queue.csv", dtype=str).fillna("")
    rows: list[dict[str, object]] = []
    for row in queue.itertuples(index=False):
        diagram_id = str(row.diagram_id)
        path = DATA / ID_TO_JSON[diagram_id]
        diagram = load_diagram(path)
        findings = validate_diagram(diagram)
        rows.append(
            {
                "diagram_id": diagram_id,
                "json": path.name,
                "species": diagram.species_group,
                "bec": f"{diagram.bec_zone}{diagram.bec_subzone}{diagram.bec_variant or ''}",
                "review": diagram.review.status,
                "curves": curve_summary(diagram),
                "findings": [f"{item.code}: {item.message}" for item in findings],
                "pdf_url": str(row.pdf_url),
                "labels": int(str(row.label_count)),
            }
        )
    return rows


def _plot_curves(diagram_id: str, diagram: SdmdDiagram, output: Path) -> None:
    """Write a log-axis plot of a stored diagram's isopleths."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(8, 6))
    for curve in diagram.isopleths:
        x = [point[0] for point in curve.points]
        y = [point[1] for point in curve.points]
        axis.plot(x, y, linewidth=1.1, label=f"{curve.kind} {curve.value:g}")
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("trees per hectare")
    axis.set_ylabel("mean tree volume (m3)")
    axis.set_title(f"{diagram_id}: stored isopleths")
    axis.grid(True, which="both", alpha=0.2)
    axis.legend(fontsize=6, ncol=2, loc="best")
    figure.tight_layout()
    figure.savefig(output, dpi=140)
    plt.close(figure)


def build_packet(*, download: bool = True) -> Path:
    """Build the review packet and figures.

    Parameters
    ----------
    download : bool, optional
        Download and hash-check source PDFs. Defaults to True.

    Returns
    -------
    Path
        The Markdown packet.
    """
    from ws4.sdmd.diagram import load_diagram

    rows = review_rows()
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    CURVE_DIR.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((DATA / "source_catalog.json").read_text(encoding="utf-8"))
    by_id = {str(item["diagram_id"]): item for item in catalog.get("diagrams", [])}
    lines = [
        "# P136 provisional SDMD diagram review packet",
        "",
        "Status: all 10 diagrams remain **provisional**. This packet prepares the",
        "maintainer's review; it does not approve any diagram.",
        "",
        "The source page and stored-curve plot are side-by-side evidence. They are not",
        "axis-registered overlays because the original digitisation specs are not in the",
        "repository. The review still requires comparing curve identity and placement.",
        "",
        "## Diagrams",
        "",
        "| Diagram | Species | BEC reference | Labels | Curves | Validation | Figures |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in rows:
        diagram_id = str(row["diagram_id"])
        diagram = load_diagram(DATA / str(row["json"]))
        page = PAGE_DIR / f"{diagram_id}.png"
        curve_path = CURVE_DIR / f"{diagram_id}.png"
        _plot_curves(diagram_id, diagram, curve_path)
        findings = row["findings"]
        assert isinstance(findings, list)
        status = "pass" if not findings else "; ".join(str(item) for item in findings)
        if download:
            meta = by_id[diagram_id]
            pdf = _download(str(meta["url"]), str(meta["sha256"]))
            from ws4.sdmd.review import render_pdf_page

            existing = next(PAGE_DIR.glob(f"{pdf.stem}*.png"), None)
            if existing is not None and existing != page:
                existing.replace(page)
            elif not page.is_file():
                render_pdf_page(pdf, PAGE_DIR, dpi=150)
                rendered = next(PAGE_DIR.glob(f"{pdf.stem}*.png"), None)
                if rendered is not None and rendered != page:
                    rendered.replace(page)
        curves = row["curves"]
        assert isinstance(curves, dict)
        curve_text = "<br>".join(f"{key}: {value}" for key, value in curves.items())
        lines.append(
            f"| `{diagram_id}` | {row['species']} | {row['bec']} | {row['labels']} | "
            f"{curve_text} | {status} | [page](p136-pages/{diagram_id}.png) · "
            f"[curves](p136-curves/{diagram_id}.png) |"
        )
    lines += [
        "",
        "## Review checklist",
        "",
        "Mark each line accepted or name the curve to correct. Do not mark a diagram",
        "reviewed without the maintainer's name and UTC time.",
        "",
    ]
    for row in rows:
        lines.append(
            f"- [ ] `{row['diagram_id']}` curve identity, labels, boundaries, and crown closure"
        )
    lines += [
        "",
        "## No-diagram labels",
        "",
        "`BAFAun`, `CMAun`, `CMAwh`, and `IMAun` have no diagram in the 14-public",
        "Atlas. For each, choose one: acquire/digitize a public source, or record a",
        "permanent refusal. Do not substitute an unrelated diagram.",
        "",
        "## Known limits",
        "",
        "- No axis-registered overlay is available; the original specs are not tracked.",
        "- The source pages are rendered for review, not copied into the data layer.",
        "- A validated diagram is structurally valid, not necessarily correct.",
        "- The maintainer remains reviewer of record.",
        "",
    ]
    packet = REVIEW / "p136-provisional-review.md"
    packet.write_text("\n".join(lines), encoding="utf-8")
    return packet


def main() -> int:
    """Build the packet with source PDFs.

    Returns
    -------
    int
        Zero after the packet and figures are written.
    """
    packet = build_packet(download=True)
    print(f"wrote {packet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
