"""Build a small CFSDS fixture with hourly Open-Meteo reanalysis weather."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds

STANDARD_FUELS: Final[dict[int, str | None]] = {
    0: None,
    1: "C-1",
    2: "C-2",
    3: "C-3",
    4: "C-4",
    5: "C-5",
    6: "C-6",
    7: "C-7",
    11: "D-1",
    12: "D-2",
    13: "D-1/D-2",
    21: "S-1",
    22: "S-2",
    23: "S-3",
    31: "O-1A",
    32: "O-1B",
    33: "O-1A",
    40: "M-1",
    50: "M-2",
    60: "M-1/M-2",
    70: "M-3",
    80: "M-4",
    90: "M-3/M-4",
    101: None,
    102: None,
    103: None,
    104: "D-1/D-2",
    105: "M-1/M-2 (25 PC)",
    106: "D-1/D-2",
}
MISSING: Final[int] = 4294967295


def _fuel_label(code: int) -> str | None:
    """Return a supported FBP label for one FireSTARR fuel code."""
    if code in STANDARD_FUELS:
        return STANDARD_FUELS[code]
    if 400 <= code < 500:
        return f"M-1 ({code % 100:02d} PC)"
    if 500 <= code < 600:
        return f"M-2 ({code % 100:02d} PC)"
    if 600 <= code < 700:
        return f"M-1 ({code % 100:02d} PC)"
    raise ValueError(f"unsupported FireSTARR fuel code: {code}")


def _write_ascii(
    path: Path,
    values: np.ndarray,
    *,
    xll: float,
    yll: float,
    cell: float,
    nodata: float,
) -> None:
    """Write an ESRI ASCII grid."""
    nrows, ncols = values.shape
    header = (
        f"ncols {ncols}\n"
        f"nrows {nrows}\n"
        f"xllcorner {xll:.1f}\n"
        f"yllcorner {yll:.1f}\n"
        f"cellsize {cell:.1f}\n"
        f"NODATA_value {nodata:.1f}\n"
    )
    body = "\n".join(" ".join(str(value) for value in row) for row in values)
    path.write_text(header + body + "\n", encoding="utf-8")


def _rings(
    mask: np.ndarray, transform: rasterio.Affine, to_lonlat: Transformer
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Return exterior rings in longitude/latitude from a mask."""
    result: list[tuple[tuple[float, float], ...]] = []
    for geometry, value in shapes(
        mask.astype(np.uint8), mask=mask.astype(bool), transform=transform
    ):
        if value != 1:
            continue
        coordinates = geometry["coordinates"]
        polygons = coordinates if geometry["type"] == "MultiPolygon" else [coordinates]
        for polygon in polygons:
            ring = [(float(x), float(y)) for x, y in polygon[0]]
            result.append(tuple(to_lonlat.transform(x, y) for x, y in ring))
    if not result:
        raise ValueError("mask has no polygons")
    return tuple(result)


def _write_kml(path: Path, rings: tuple[tuple[tuple[float, float], ...], ...]) -> None:
    """Write one KML document with exterior rings."""
    placemarks = []
    for ring in rings:
        coords = " ".join(f"{lon:.8f},{lat:.8f},0" for lon, lat in ring)
        placemarks.append(
            f"<Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates>"
            "</LinearRing></outerBoundaryIs></Polygon></Placemark>"
        )
    path.write_text(
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        + "".join(placemarks)
        + "</Document></kml>\n",
        encoding="utf-8",
    )


def _write_point(path: Path, lon: float, lat: float) -> None:
    """Write one KML point."""
    path.write_text(
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><Point>'
        f"<coordinates>{lon:.8f},{lat:.8f},0</coordinates>"
        "</Point></Placemark></Document></kml>\n",
        encoding="utf-8",
    )


def _fetch_weather(  # pragma: no cover - network access
    lat: float, lon: float, start: str, end: str
) -> pd.DataFrame:
    """Fetch hourly historical weather from Open-Meteo."""
    query = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "start_date": start,
            "end_date": end,
            "hourly": (
                "temperature_2m,relative_humidity_2m,wind_speed_10m,"
                "wind_direction_10m,precipitation"
            ),
            "timezone": "America/Edmonton",
        }
    )
    url = f"https://archive-api.open-meteo.com/v1/archive?{query}"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    hourly = payload["hourly"]
    return pd.DataFrame(
        {
            "local_time": pd.to_datetime(hourly["time"]),
            "temperature_c": hourly["temperature_2m"],
            "relative_humidity_percent": hourly["relative_humidity_2m"],
            "wind_speed_kmh": hourly["wind_speed_10m"],
            "wind_direction_deg": hourly["wind_direction_10m"],
            "precipitation_mm": hourly["precipitation"],
        }
    )


def main() -> None:  # pragma: no cover - builds fixture from external data
    """Build the fixture directory and metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--case", default="2003_526")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--padding-cells", type=int, default=20)
    parser.add_argument("--cell-size", type=float, default=100.0)
    args = parser.parse_args()
    case = str(args.case)
    year = int(case.split("_")[0])
    root = args.data_root
    summary = root / f"Firegrowth_groups_v1_1_{year}.csv"
    raster_zip = root / f"{year}_fireDOYrasters.zip"
    frame = pd.read_csv(summary)
    rows = frame[frame["ID"] == case].sort_values("fireday")
    if rows.empty:
        raise SystemExit(f"case {case} not found")
    start_doy = int(rows["DOB"].iloc[0])
    days = int(rows["fireday"].max())
    end_doy = start_doy + days - 1
    ffmc = float(rows["ffmc"].iloc[0])
    dmc = float(rows["dmc"].iloc[0])
    dc = float(rows["dc"].iloc[0])
    bui = float(rows["bui"].iloc[0])
    start_date = datetime(year, 1, 1) + timedelta(days=start_doy - 1)
    end_date = datetime(year, 1, 1) + timedelta(days=end_doy - 1)
    event_start = start_date.replace(hour=13)
    event_end = end_date.replace(hour=23)
    source_path = f"/vsizip/{raster_zip.resolve()}/{case}_krig.tif"
    with rasterio.open(source_path) as source:
        values = source.read(1)
        valid = (values > 0) & (values != MISSING)
        start_mask = values == start_doy
        final_mask = valid
        left, bottom, right, top = transform_bounds(source.crs, "EPSG:26911", *source.bounds)
        transform = source.transform
        source_crs = source.crs
    cell = args.cell_size
    pad = args.padding_cells * cell
    xmin = np.floor(left / cell) * cell - pad
    xmax = np.ceil(right / cell) * cell + pad
    ymin = np.floor(bottom / cell) * cell - pad
    ymax = np.ceil(top / cell) * cell + pad
    ncols = round((xmax - xmin) / cell)
    nrows = round((ymax - ymin) / cell)
    target = from_origin(float(xmin), float(ymax), cell, cell)
    start_raster = np.zeros((nrows, ncols), dtype=np.uint8)
    final_raster = np.zeros_like(start_raster)
    reproject(
        start_mask.astype(np.uint8),
        start_raster,
        src_transform=transform,
        src_crs=source_crs,
        dst_transform=target,
        dst_crs="EPSG:26911",
        resampling=Resampling.nearest,
    )
    reproject(
        final_mask.astype(np.uint8),
        final_raster,
        src_transform=transform,
        src_crs=source_crs,
        dst_transform=target,
        dst_crs="EPSG:26911",
        resampling=Resampling.nearest,
    )
    fuel_path = root / "fuel_11_0.tif"
    dem_path = root / "dem_11_0.tif"
    with rasterio.open(fuel_path) as source:
        window = from_bounds(float(xmin), float(ymin), float(xmax), float(ymax), source.transform)
        fuel = source.read(
            1, window=window, out_shape=(nrows, ncols), resampling=Resampling.nearest
        )
    with rasterio.open(dem_path) as source:
        window = from_bounds(float(xmin), float(ymin), float(xmax), float(ymax), source.transform)
        elevation = source.read(
            1, window=window, out_shape=(nrows, ncols), resampling=Resampling.nearest
        )
    lookup = {int(code): _fuel_label(int(code)) for code in np.unique(fuel)}
    lookup[0] = None
    lookup[101] = None
    lookup[102] = None
    to_lonlat = Transformer.from_crs("EPSG:26911", "EPSG:4326", always_xy=True)
    start_rings = _rings(start_raster, target, to_lonlat)
    final_rings = _rings(final_raster, target, to_lonlat)
    start_rows, start_cols = np.where(start_raster > 0)
    if len(start_rows) == 0:
        raise SystemExit("start perimeter is empty")
    ignition_x = float(xmin) + (start_cols.mean() + 0.5) * cell
    ignition_y = float(ymax) - (start_rows.mean() + 0.5) * cell
    ignition_lon, ignition_lat = to_lonlat.transform(ignition_x, ignition_y)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    _write_ascii(
        output / "fbp_fuel_type.asc", fuel, xll=float(xmin), yll=float(ymin), cell=cell, nodata=0
    )
    _write_ascii(
        output / "elevation.asc",
        elevation,
        xll=float(xmin),
        yll=float(ymin),
        cell=cell,
        nodata=-9999,
    )
    pd.DataFrame(
        [
            {"grid_value": code, "fuel_type": "Non-fuel" if label is None else label}
            for code, label in sorted(lookup.items())
        ]
    ).to_csv(output / "fbp_lookup_table.csv", index=False)
    _write_kml(output / f"perimeter_{event_start.strftime('%Y%m%d_%H%M')}.kml", start_rings)
    _write_kml(output / f"perimeter_{event_end.strftime('%Y%m%d_%H%M')}.kml", final_rings)
    _write_point(output / "ignition.kml", float(ignition_lon), float(ignition_lat))
    weather = _fetch_weather(
        float(ignition_lat),
        float(ignition_lon),
        start_date.date().isoformat(),
        end_date.date().isoformat(),
    )
    weather = weather[
        (weather["local_time"] >= pd.Timestamp(event_start))
        & (weather["local_time"] <= pd.Timestamp(event_end))
    ].reset_index(drop=True)
    weather_rows = pd.DataFrame(
        {
            "HOURLY": weather["local_time"].dt.strftime("%d/%m/%Y"),
            "HOUR": weather["local_time"].dt.hour,
            "TEMP": weather["temperature_c"],
            "RH": weather["relative_humidity_percent"],
            "WD": weather["wind_direction_deg"],
            "WS": weather["wind_speed_kmh"],
            "PRECIP": weather["precipitation_mm"],
        }
    )
    weather_rows.to_csv(output / "weather.csv", index=False)
    metadata = {
        "case_id": case,
        "name": f"CFSDS {case}",
        "event_start": event_start.isoformat(),
        "event_end": event_end.isoformat(),
        "duration_min": (event_end - event_start).total_seconds() / 60.0,
        "ffmc": ffmc,
        "dmc": dmc,
        "dc": dc,
        "bui": bui,
        "daily_cumuarea_ha": [float(value) for value in rows["cumuarea"].tolist()],
        "daily_cfsds": {
            name: [float(value) for value in rows[name].tolist()]
            for name in ("ffmc", "dmc", "dc", "bui", "isi", "ws", "rh", "prec", "tmax")
        },
        "source": f"CFSDS {year} daily raster; FireSTARR fuel/DEM; Open-Meteo hourly reanalysis",
        "licence": "CFSDS public OSF f48ry; FireSTARR public fuel index; Open-Meteo CC-BY 4.0",
        "weather_mode": "hourly reanalysis (Open-Meteo), not an on-site station",
        "ignition_mode": "centroid of the first-day burned cells; reconstructed",
        "provenance": {
            "cfsds": "https://osf.io/f48ry/",
            "weather": "https://archive-api.open-meteo.com/",
            "fuel": "FireSTARR Fuel 2023 V1.0 tile 11_0",
        },
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output / "SOURCE.md").write_text(
        f"# {case} hourly reanalysis case\n\n"
        f"- Event window: {event_start.isoformat()} to {event_end.isoformat()} local.\n"
        f"- Final scar: CFSDS `{case}_krig.tif`.\n"
        "- Fuel and elevation: FireSTARR tile 11_0.\n"
        "- Weather: Open-Meteo hourly reanalysis, not an on-site station.\n"
        "- Ignition: first-day burned-cell centroid, reconstructed.\n"
        f"- Final area: {final_raster.sum() * cell * cell / 10_000.0:.1f} ha.\n"
        "- This is a derived fixture, not a raw archive.\n",
        encoding="utf-8",
    )
    print(f"wrote {output} with {final_raster.sum()} final cells, {nrows}x{ncols} grid")


if __name__ == "__main__":
    main()
