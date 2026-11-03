"""Figure rendering, overlays, and review manifests for SDMD digitisation.

This module is the WS4 side of the figrecover integration. It renders the source
PDF page, draws the stored isopleths over the rendered page, and writes a
figrecover review manifest. Curve extraction stays in :mod:`ws4.sdmd.digitise`.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from .diagram import load_diagram
from .digitise import calibrate_axes, load_spec

__all__ = ["overlay_diagram", "render_pdf_page", "write_review_manifest"]

_COLORS = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
)


def render_pdf_page(pdf_path: str | Path, output_dir: str | Path, *, dpi: int = 300) -> Path:
    """Render the first page of a PDF with figrecover.

    Parameters
    ----------
    pdf_path : str or Path
        The source PDF.
    output_dir : str or Path
        Directory for the rendered image.
    dpi : int
        Render resolution. Defaults to 300.

    Returns
    -------
    Path
        The rendered page image.
    """
    from figrecover import render_pdf_pages

    pages = render_pdf_pages(Path(pdf_path), Path(output_dir), pages="1", dpi=dpi)
    return Path(pages[0].image_path)


def overlay_diagram(
    diagram_path: str | Path,
    spec_path: str | Path,
    page_image: str | Path,
    output_path: str | Path,
    *,
    dpi: int = 300,
) -> Path:
    """Draw a stored diagram over a rendered page with figrecover QA.

    Parameters
    ----------
    diagram_path : str or Path
        The stored diagram JSON.
    spec_path : str or Path
        The digitisation spec with the PDF-axis calibration.
    page_image : str or Path
        The rendered page image.
    output_path : str or Path
        Destination overlay image.
    dpi : int
        Render resolution used for the page image. Defaults to 300.

    Returns
    -------
    Path
        The overlay image path.
    """
    from figrecover import (
        Calibration,
        DataPoint,
        DigitizeResult,
        DigitizeSpec,
        SeriesResult,
        SeriesSpec,
    )
    from figrecover.qa import render_overlay
    from PIL import Image

    spec = load_spec(spec_path)
    calibration = calibrate_axes(spec.x_ticks, spec.y_ticks)
    diagram = load_diagram(diagram_path)
    page = Path(page_image)
    with Image.open(page) as image:
        width, height = image.size
    scale = dpi / 72.0
    series: list[SeriesResult] = []
    series_specs: list[SeriesSpec] = []
    for index, isopleth in enumerate(diagram.isopleths):
        color = _COLORS[index % len(_COLORS)]
        name = f"{isopleth.kind}-{isopleth.value:g}"
        series_specs.append(SeriesSpec(name=name, color=color, mode="line"))
        points = [
            DataPoint(
                series=name,
                x=tph,
                y=volume,
                x_pixel=calibration.x_for_tph(tph) * scale,
                y_pixel=calibration.y_for_volume(volume) * scale,
            )
            for tph, volume in isopleth.points
        ]
        series.append(
            SeriesResult(spec=SeriesSpec(name=name, color=color, mode="line"), points=points)
        )
    result = DigitizeResult(
        spec=DigitizeSpec(
            calibration=Calibration.from_plot_bounds(
                plot_left=0,
                plot_right=width,
                plot_top=0,
                plot_bottom=height,
                x_min=0,
                x_max=width,
                y_min=0,
                y_max=height,
            ),
            series=series_specs,
            image_id=diagram.diagram_id,
            source_pdf=spec.pdf_path,
            source_page=1,
            extraction_tool="ws4.sdmd.digitise",
        ),
        image_path=page,
        width=width,
        height=height,
        series=series,
    )
    artifact = render_overlay(result, Path(output_path), source_image_path=page)
    return Path(artifact.path)


def write_review_manifest(
    diagram_path: str | Path,
    overlay_path: str | Path,
    output_path: str | Path,
    *,
    status: str = "needs_review",
    reviewer: str = "",
    notes: str = "",
) -> Path:
    """Write a figrecover review manifest for one diagram.

    Parameters
    ----------
    diagram_path : str or Path
        The diagram JSON.
    overlay_path : str or Path
        The overlay image used for review.
    output_path : str or Path
        Destination JSONL manifest.
    status : str
        A figrecover review status. Defaults to ``needs_review``.
    reviewer : str
        The reviewer name or role.
    notes : str
        Optional review notes.

    Returns
    -------
    Path
        The manifest path.
    """
    from figrecover.review import ReviewEntry, ReviewManifest, ReviewStatus

    allowed = {
        "accepted",
        "rejected",
        "manually_corrected",
        "needs_recrop",
        "needs_recalibration",
        "needs_review",
    }
    if status not in allowed:
        raise ValueError(f"unknown review status {status!r}")
    diagram = load_diagram(diagram_path)
    entry = ReviewEntry(
        review_id=f"{diagram.diagram_id}-review",
        figure_id=diagram.diagram_id,
        image_path=None,
        overlay_path=Path(overlay_path),
        table_path=Path(diagram_path),
        status=cast(ReviewStatus, status),  # checked against the literal set above
        reviewer=reviewer or None,
        notes=notes or None,
    )
    manifest = ReviewManifest.from_entries([entry])
    return Path(manifest.write_jsonl(Path(output_path)))
