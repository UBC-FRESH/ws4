"""Render an observed-versus-simulated perimeter comparison as SVG.

The view is a read-only report artifact. It draws the simulated burned mask, the observed
start and final perimeters, and the P157.2 metrics on one shared grid. It is intentionally
simple: no browser, no GIS stack, and no hidden layer order.
"""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np

from .comparison import DogribCase
from .observed import ObservedFire

_SIMULATED_COLOR = "#ff7a33"
_OBSERVED_START_COLOR = "#2d6cdf"
_OBSERVED_FINAL_COLOR = "#111111"
_BACKGROUND = "#ffffff"
_TEXT = "#17201b"
_MUTED = "#52645a"


def render_comparison_svg(
    fire: ObservedFire,
    case: DogribCase,
    *,
    width: int = 1000,
    height: int = 720,
) -> str:
    """Render the Dogrib comparison as a standalone SVG.

    Parameters
    ----------
    fire : ObservedFire
        Observed fire with projected perimeters and grid geometry.
    case : DogribCase
        The simulated case and metrics.
    width, height : int, optional
        SVG canvas size in pixels.

    Returns
    -------
    str
        A standalone SVG document.

    Raises
    ------
    ValueError
        If the canvas is too small or the grid is empty.
    """
    if width < 400 or height < 300:
        raise ValueError("SVG canvas is too small")
    grid = fire.grid
    padding = 52
    panel_width = 236
    map_top = 78
    map_bottom = 90
    span_x = grid.ncols * grid.cell_size_m
    span_y = grid.nrows * grid.cell_size_m
    available_width = width - padding - panel_width - 24
    available_height = height - map_top - map_bottom
    scale = min(available_width / span_x, available_height / span_y)
    map_width = span_x * scale
    map_height = span_y * scale
    offset_x = padding + (available_width - map_width) / 2.0
    offset_y = map_top + (available_height - map_height) / 2.0
    panel_x = width - panel_width + 4
    metric_x = panel_x + 12

    def px(x: float) -> float:
        return offset_x + (x - grid.xll) * scale

    def py(y: float) -> float:
        return offset_y + (grid.yll + grid.nrows * grid.cell_size_m - y) * scale

    mask = case.growth.ignition_time_min.copy()
    if case.initial_burned_mask is not None:
        mask[case.initial_burned_mask] = 0.0
    rows, cols = mask.shape
    paths: list[str] = []
    for row in range(rows):
        col = 0
        while col < cols:
            if not bool(np.isfinite(mask[row, col])):
                col += 1
                continue
            start = col
            while col < cols and bool(np.isfinite(mask[row, col])):
                col += 1
            x1 = px(grid.xll + start * grid.cell_size_m)
            x2 = px(grid.xll + col * grid.cell_size_m)
            y1 = py(grid.yll + (row + 1) * grid.cell_size_m)
            y2 = py(grid.yll + row * grid.cell_size_m)
            paths.append(f"M{x1:.2f},{y1:.2f} h{x2 - x1:.2f} v{y2 - y1:.2f} h{-(x2 - x1):.2f} Z")
    simulated_path = " ".join(paths)

    def ring_path(rings: tuple[tuple[tuple[float, float], ...], ...]) -> str:
        commands: list[str] = []
        for ring in rings:
            if not ring:
                continue
            first = ring[0]
            commands.append(f"M{px(first[0]):.2f},{py(first[1]):.2f}")
            for x, y in ring[1:]:
                commands.append(f"L{px(x):.2f},{py(y):.2f}")
            commands.append("Z")
        return " ".join(commands)

    start_path = ring_path(fire.perimeters[0].rings_projected)
    final_path = ring_path(fire.perimeters[-1].rings_projected)
    metrics = case.metrics
    metric_lines = [
        f"Simulated {metrics.area_sim_ha:,.0f} ha",
        f"Observed {metrics.area_obs_ha:,.0f} ha",
        f"Area bias {metrics.area_bias * 100:+.1f}%",
        f"Perimeter bias {metrics.perimeter_bias * 100:+.1f}%",
        f"Centroid {metrics.centroid_distance_m / 1000.0:.2f} km",
        f"IoU {metrics.iou:.3f}   Sorensen {metrics.sorensen:.3f}",
        f"Orientation {metrics.orientation_error_deg:.1f}°",
    ]
    metric_text = "".join(
        f'<text x="{metric_x}" y="{112 + index * 19}" class="metric">{html.escape(line)}</text>'
        for index, line in enumerate(metric_lines)
    )
    note_lines = [
        f"Run {case.duration_min:.0f} min",
        f"Target {fire.event_end:%d %b %H:%M}",
        f"Fuel {case.fuel_mode}",
        f"FFMC {case.ffmc:.1f} · BUI {case.bui:.0f}",
        f"Weather {case.weather_mode}",
        f"Wind {case.wind_kmh:.0f} km/h",
        "No spotting",
    ]
    note_text = "".join(
        f'<text x="{metric_x}" y="{112 + len(metric_lines) * 19 + 18 + index * 17}" '
        f'class="legend">{html.escape(line)}</text>'
        for index, line in enumerate(note_lines)
    )
    scale_bar = 10_000.0 * scale
    scale_text = f"{10:.0f} km"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
  viewBox="0 0 {width} {height}" role="img"
  aria-label="Dogrib observed versus simulated fire perimeter">
  <rect width="{width}" height="{height}" fill="{_BACKGROUND}"/>
  <style>
    .title {{ font: 700 20px system-ui, sans-serif; fill: {_TEXT}; }}
    .subtitle {{ font: 13px system-ui, sans-serif; fill: {_MUTED}; }}
    .metric {{ font: 12px ui-monospace, monospace; fill: {_TEXT}; }}
    .legend {{ font: 12px system-ui, sans-serif; fill: {_MUTED}; }}
    .scale {{ font: 11px system-ui, sans-serif; fill: {_MUTED}; }}
  </style>
  <text x="{padding}" y="28" class="title">Dogrib observed vs simulated perimeter</text>
  <text x="{padding}" y="46" class="subtitle">Observed start {fire.perimeters[0].area_ha:,.0f} ha
    · observed final {metrics.area_obs_ha:,.0f} ha · simulated {metrics.area_sim_ha:,.0f} ha</text>
  <text x="{padding}" y="62" class="subtitle">{fire.event_start:%d %b %Y %H:%M} →
    {fire.event_end:%d %b %Y %H:%M} local · {html.escape(fire.fire_id)} ·
    Prometheus Dogrib sample</text>
  <rect x="{panel_x}" y="64" width="{panel_width - 12}" height="{height - 128}"
    rx="8" fill="#f5f7f5" stroke="#d9e1da"/>
  <text x="{metric_x}" y="88" class="subtitle">Dogrib comparison</text>
  <path d="{simulated_path}" fill="{_SIMULATED_COLOR}" fill-opacity="0.32"
    stroke="{_SIMULATED_COLOR}" stroke-width="1.1"/>
  <path d="{start_path}" fill="none" stroke="{_OBSERVED_START_COLOR}"
    stroke-width="1.6" stroke-dasharray="6 4"/>
  <path d="{final_path}" fill="none" stroke="{_OBSERVED_FINAL_COLOR}" stroke-width="1.7"/>
  <rect x="{padding}" y="{height - 36}" width="46" height="4"
    fill="{_SIMULATED_COLOR}" fill-opacity="0.32" stroke="{_SIMULATED_COLOR}"/>
  <text x="{padding + 54}" y="{height - 30}" class="legend">simulated</text>
  <line x1="{padding + 150}" y1="{height - 34}" x2="{padding + 190}"
    y2="{height - 34}" stroke="{_OBSERVED_START_COLOR}" stroke-width="1.6"
    stroke-dasharray="6 4"/>
  <text x="{padding + 198}" y="{height - 30}" class="legend">observed start</text>
  <line x1="{padding + 330}" y1="{height - 34}" x2="{padding + 370}"
    y2="{height - 34}" stroke="{_OBSERVED_FINAL_COLOR}" stroke-width="1.7"/>
  <text x="{padding + 378}" y="{height - 30}" class="legend">observed final</text>
  <line x1="{padding}" y1="{height - 70}" x2="{padding + scale_bar:.1f}"
    y2="{height - 70}" stroke="{_TEXT}" stroke-width="2"/>
  <text x="{padding}" y="{height - 78}" class="scale">{scale_text}</text>
  <g transform="translate({width - panel_width - 48},88)">
    <path d="M0,0 L-7,18 L0,14 L7,18 Z" fill="{_TEXT}"/>
    <text x="-4" y="30" class="scale">N</text>
  </g>
  {metric_text}
  {note_text}
</svg>
'''


def write_comparison_svg(
    fire: ObservedFire,
    case: DogribCase,
    path: str | Path,
    *,
    width: int = 1000,
    height: int = 720,
) -> Path:
    """Write the comparison SVG to a file.

    Parameters
    ----------
    fire : ObservedFire
        Observed fire.
    case : DogribCase
        Simulated case.
    path : str or Path
        Destination path.
    width, height : int, optional
        Canvas size.

    Returns
    -------
    pathlib.Path
        The written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_comparison_svg(fire, case, width=width, height=height),
        encoding="utf-8",
    )
    return destination
