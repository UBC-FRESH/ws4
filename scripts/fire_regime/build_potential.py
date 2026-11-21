"""Build the P164.8 90-day potential-fire sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire.fwi import DailyWeather, FWIState, fwi_sequence  # noqa: E402
from ws4.fire.growth import GrowthConfig, SiteGrid, WeatherStep, grow_fire  # noqa: E402

ACTIVE_HOURS = 10.0
ACTIVE_DAYS_MAX = 7
ANTECEDENT_DAYS = 90
CELL_SIZE_M = 250.0
WEATHER_START = "2023-02-01"
WEATHER_END = "2023-09-30"


@dataclass(frozen=True)
class Tile:
    """One fixed calibration tile.

    Attributes
    ----------
    tile_id : str
        Tile identifier.
    minx, miny, maxx, maxy : float
        EPSG:3005 tile bounds.
    layers : str
        Layer NPZ filename.
    """

    tile_id: str
    minx: float
    miny: float
    maxx: float
    maxy: float
    layers: str


@dataclass(frozen=True)
class WeatherDay:
    """One cached daily weather record."""

    date: str
    temperature_c: float
    relative_humidity_percent: float
    wind_kmh: float
    wind_direction_deg: float
    precipitation_mm: float


def load_tiles(path: Path) -> tuple[dict[str, list[str]], tuple[Tile, ...]]:
    """Load the tile manifest and split.

    Parameters
    ----------
    path : Path
        Tile manifest JSON.

    Returns
    -------
    tuple
        Split mapping and ordered tiles.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("tile manifest must be a mapping")
    split = payload.get("split")
    raw_tiles = payload.get("tiles")
    if not isinstance(split, dict) or not isinstance(raw_tiles, list):
        raise ValueError("tile manifest needs split and tiles")
    tiles: list[Tile] = []
    for raw in raw_tiles:
        if not isinstance(raw, dict):
            raise ValueError("tile entries must be mappings")
        tiles.append(
            Tile(
                tile_id=str(raw["id"]),
                minx=float(raw["minx"]),
                miny=float(raw["miny"]),
                maxx=float(raw["maxx"]),
                maxy=float(raw["maxy"]),
                layers=str(raw["layers"]),
            )
        )
    train = [str(value) for value in split.get("train", [])]
    validation = [str(value) for value in split.get("validation", [])]
    if not train or not validation:
        raise ValueError("tile manifest needs non-empty train and validation splits")
    return {"train": train, "validation": validation}, tuple(tiles)


def _weather_path(directory: Path, tile: Tile) -> Path:
    """Return the cache path for one tile."""
    return directory / f"{tile.tile_id}.json"


def fetch_weather(
    tile: Tile, directory: Path
) -> tuple[tuple[DailyWeather, ...], tuple[float, ...]]:
    """Fetch and cache one tile's 2023 daily weather.

    Parameters
    ----------
    tile : Tile
        Tile definition.
    directory : Path
        Weather cache directory.

    Returns
    -------
    tuple
        Daily weather records and wind directions.
    """
    directory.mkdir(parents=True, exist_ok=True)
    target = _weather_path(directory, tile)
    if target.is_file():
        payload = json.loads(target.read_text(encoding="utf-8"))
        cached_days = tuple(DailyWeather(**entry) for entry in payload["days"])
        cached_directions = tuple(
            float(value) for value in payload.get("directions", [270.0] * len(cached_days))
        )
        return cached_days, cached_directions
    transformer = Transformer.from_crs(3005, 4326, always_xy=True)
    lon, lat = transformer.transform((tile.minx + tile.maxx) / 2, (tile.miny + tile.maxy) / 2)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": WEATHER_START,
        "end_date": WEATHER_END,
        "hourly": (
            "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation"
        ),
        "timezone": "America/Vancouver",
    }
    response = requests.get(
        "https://archive-api.open-meteo.com/v1/archive", params=params, timeout=180
    )
    response.raise_for_status()
    hourly = response.json()["hourly"]
    times = list(hourly["time"])
    temps = hourly["temperature_2m"]
    rh = hourly["relative_humidity_2m"]
    wind = hourly["wind_speed_10m"]
    direction = hourly["wind_direction_10m"]
    rain = hourly["precipitation"]
    grouped: dict[str, list[int]] = {}
    for index, stamp in enumerate(times):
        grouped.setdefault(str(stamp)[:10], []).append(index)
    days: list[DailyWeather] = []
    directions: list[float] = []
    for date, indices in sorted(grouped.items()):
        noon = next((index for index in indices if str(times[index])[11:13] == "13"), indices[0])
        if temps[noon] is None or rh[noon] is None or wind[noon] is None or direction[noon] is None:
            continue
        precipitation = sum(float(rain[index] or 0.0) for index in indices)
        directions.append(float(direction[noon] or 270.0))
        days.append(
            DailyWeather(
                year=int(date[:4]),
                month=int(date[5:7]),
                day=int(date[8:10]),
                temperature_c=float(temps[noon]),
                relative_humidity_percent=float(rh[noon]),
                wind_kmh=float(wind[noon]),
                precipitation_mm=precipitation,
                latitude_deg=lat,
            )
        )
    target.write_text(
        json.dumps(
            {
                "tile": tile.tile_id,
                "source": "Open-Meteo archive",
                "latitude": lat,
                "longitude": lon,
                "days": [day.__dict__ for day in days],
                "directions": directions,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return tuple(days), tuple(directions)


def select_start_indices(
    daily: list[DailyWeather],
    states: Sequence[FWIState],
    *,
    count: int,
    seed: int,
) -> list[int]:
    """Select fire-season start indices with fire-danger weighting.

    Parameters
    ----------
    daily : list of DailyWeather
        Daily weather.
    states : sequence
        FWI states aligned to ``daily``.
    count : int
        Number of starts.
    seed : int
        Deterministic seed.

    Returns
    -------
    list of int
        Selected start indices.
    """
    if len(daily) != len(states):
        raise ValueError("weather and FWI states must align")
    candidates = [
        index
        for index, day in enumerate(daily)
        if 5 <= day.month <= 9 and index + ACTIVE_DAYS_MAX < len(daily)
    ]
    if not candidates:
        raise ValueError("no eligible fire-season weather days")
    weights = [max(0.0, float(states[index].fwi) - 5.0) ** 2 for index in candidates]
    if not any(weights):
        weights = [1.0] * len(candidates)
    rng = random.Random(seed)
    return rng.choices(candidates, weights=weights, k=count)


def _layers(path: Path) -> dict[str, np.ndarray]:
    """Load a tile layer NPZ."""
    with np.load(path, allow_pickle=True) as payload:
        return {key: payload[key] for key in payload.files}


def build_case(
    tile: Tile,
    layers_dir: Path,
    daily: tuple[DailyWeather, ...],
    directions: tuple[float, ...],
    states: Sequence[FWIState],
    start_index: int,
    *,
    seed: int,
) -> dict[str, object]:
    """Build one potential-fire record.

    Parameters
    ----------
    tile : Tile
        Tile definition.
    layers_dir : Path
        Directory containing layer NPZ files.
    daily : tuple of DailyWeather
        Daily weather.
    start_index : int
        Selected start index.
    seed : int
        Deterministic seed.

    Returns
    -------
    dict
        Potential record and provenance.
    """
    arr = _layers(layers_dir / tile.layers)
    forest = np.asarray(arr["forest"], dtype=bool)
    rows, cols = forest.shape
    rng = random.Random(seed)
    ys, xs = np.nonzero(forest)
    index = rng.randrange(len(xs))
    ignition = (int(ys[index]), int(xs[index]))
    end = start_index
    for day_index in range(start_index, min(start_index + ACTIVE_DAYS_MAX, len(daily))):
        if daily[day_index].precipitation_mm >= 2.0:
            break
        end = day_index
    active_days = max(0.5, float(end - start_index + 1))
    steps = []
    for offset in range(10):
        day_index = min(start_index + offset, len(daily) - 1)
        day = daily[day_index]
        state = states[day_index]
        steps.append(
            WeatherStep(
                start_min=offset * 1440.0,
                wind_kmh=day.wind_kmh,
                wind_direction_deg=directions[day_index],
                ffmc=state.ffmc,
                bui=state.bui,
                relative_humidity_percent=day.relative_humidity_percent,
                precipitation_mm=day.precipitation_mm,
            )
        )
    grid = SiteGrid(
        fuel_type="C2",
        rows=rows,
        cols=cols,
        cell_size_m=CELL_SIZE_M,
        ffmc=steps[0].ffmc or 90.0,
        bui=steps[0].bui or 60.0,
        wind_kmh=steps[0].wind_kmh,
        wind_direction_deg=directions[start_index],
        slope_percent=0.0,
        aspect_deg=0.0,
        fuel_type_grid=arr["fuel"],
        burnable=forest,
        crown_closure_percent_grid=arr["crown"],
        conifer_percent_grid=arr["conifer"],
        dead_fir_percent_grid=np.zeros((rows, cols)),
        slope_percent_grid=arr["slope"],
        aspect_deg_grid=arr["aspect"],
        elevation_m_grid=arr["dem"],
    )
    depth = np.zeros((rows, cols))
    depth[np.asarray(arr["wet"], dtype=bool)] = 1.0
    config = GrowthConfig(
        ignition_cells=(ignition,),
        max_time_min=active_days * ACTIVE_HOURS * 60.0,
        snapshot_interval_min=240.0,
        weather_steps=tuple(steps),
        wet_depth_mm=depth,
        wet_start_min=0.0,
        wet_decay_min=1440.0,
        wet_required_mm=0.75,
        fire_stopping_precipitation_mm=2.0,
        fire_stopping_window_min=1440.0,
    )
    result = grow_fire(grid, config)
    return {
        "tile": tile.tile_id,
        "date": (
            f"{daily[start_index].year:04d}-"
            f"{daily[start_index].month:02d}-"
            f"{daily[start_index].day:02d}"
        ),
        "potential_ha": result.burned_area_ha,
        "active_days": active_days,
        "fwi": states[start_index].fwi,
        "bui": states[start_index].bui,
        "wind_kmh": daily[start_index].wind_kmh,
    }


def _hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Run the potential-sample builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tiles", type=Path, required=True)
    parser.add_argument("--layers-dir", type=Path, required=True)
    parser.add_argument("--weather-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    split, tiles = load_tiles(args.tiles)
    records: dict[str, list[dict[str, object]]] = {"train": [], "validation": []}
    for tile in tiles:
        daily, directions = fetch_weather(tile, args.weather_dir)
        states = fwi_sequence(list(daily))
        starts = select_start_indices(
            list(daily), states, count=args.count, seed=args.seed + int(tile.tile_id[1:])
        )
        for index, start in enumerate(starts):
            record = build_case(
                tile,
                args.layers_dir,
                daily,
                directions,
                states,
                start,
                seed=args.seed + int(tile.tile_id[1:]) * 1_000_003 + index,
            )
            group = "train" if tile.tile_id in split["train"] else "validation"
            records[group].append(record)
        print(f"{tile.tile_id}: {args.count} potential fires", flush=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for group, values in records.items():
        path = args.output_dir / f"{group}.json"
        path.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "protocol": "P164.8",
        "active_hours_per_day": ACTIVE_HOURS,
        "antecedent_days": ANTECEDENT_DAYS,
        "count_per_tile": args.count,
        "seed": args.seed,
        "split": split,
        "tiles": [tile.__dict__ for tile in tiles],
        "outputs": {
            group: {"path": f"{group}.json", "sha256": _hash(args.output_dir / f"{group}.json")}
            for group in records
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
