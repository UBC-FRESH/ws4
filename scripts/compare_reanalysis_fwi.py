"""Compare Open-Meteo-derived daily FWI with CFSDS daily FWI."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _summary(rows: list[dict[str, Any]]) -> dict[str, object]:
    """Summarize FWI deltas."""
    ffmc = [abs(float(row["ffmc_delta"])) for row in rows]
    bui = [abs(float(row["bui_delta"])) for row in rows]
    isi = [abs(float(row["isi_delta"])) for row in rows]
    return {
        "day_count": len(rows),
        "median_abs_ffmc_delta": statistics.median(ffmc),
        "max_abs_ffmc_delta": max(ffmc),
        "median_abs_bui_delta": statistics.median(bui),
        "max_abs_bui_delta": max(bui),
        "median_abs_isi_delta": statistics.median(isi),
        "max_abs_isi_delta": max(isi),
        "days_reanalysis_isi_higher": sum(float(row["isi_delta"]) > 0 for row in rows),
        "major_mismatch": statistics.median(isi) > 2.0 or max(isi) > 5.0,
    }


def main() -> None:
    """Run the FWI consistency diagnostic."""
    import pandas as pd
    from ws4.fire.fwi import DailyWeather, fwi_sequence, initial_fwi_state
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p170-fwi-consistency.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p170-fwi-consistency.csv",
    )
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    for fixture in args.fixtures:
        metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
        fire = load_cfsds_reanalysis_case(fixture)
        weather = fire.weather.copy()
        weather["date"] = weather["local_time"].dt.date
        daily: list[DailyWeather] = []
        dates: list[str] = []
        open_ws: list[float] = []
        open_rh: list[float] = []
        open_prec: list[float] = []
        for date, group in weather.groupby("date", sort=True):
            noon = group[group["local_time"].dt.hour == 13]
            if noon.empty:
                continue
            row = noon.iloc[0]
            previous = weather[
                (weather["local_time"] > row["local_time"] - pd.Timedelta(hours=24))
                & (weather["local_time"] <= row["local_time"])
            ]
            daily.append(
                DailyWeather(
                    year=int(row["local_time"].year),
                    month=int(row["local_time"].month),
                    day=int(row["local_time"].day),
                    temperature_c=float(row["temperature_c"]),
                    relative_humidity_percent=float(row["relative_humidity_percent"]),
                    wind_kmh=float(row["wind_speed_kmh"]),
                    precipitation_mm=float(previous["precipitation_mm"].sum()),
                    latitude_deg=float(fire.ignition_lonlat[1]),
                )
            )
            dates.append(str(date))
            open_ws.append(float(row["wind_speed_kmh"]))
            open_rh.append(float(row["relative_humidity_percent"]))
            open_prec.append(float(previous["precipitation_mm"].sum()))
        initial = initial_fwi_state(
            ffmc=float(metadata["ffmc"]),
            dmc=float(metadata["dmc"]),
            dc=float(metadata["dc"]),
        )
        states = fwi_sequence(daily, initial=initial)
        cfsds = metadata["daily_cfsds"]
        count = min(len(states), len(cfsds["ffmc"]))
        for index in range(count):
            rows.append(
                {
                    "case": fire.fire_id,
                    "day": index + 1,
                    "date": dates[index],
                    "cfsds_ffmc": float(cfsds["ffmc"][index]),
                    "calc_ffmc": states[index].ffmc,
                    "ffmc_delta": states[index].ffmc - float(cfsds["ffmc"][index]),
                    "cfsds_bui": float(cfsds["bui"][index]),
                    "calc_bui": states[index].bui,
                    "bui_delta": states[index].bui - float(cfsds["bui"][index]),
                    "cfsds_isi": float(cfsds["isi"][index]),
                    "calc_isi": states[index].isi,
                    "isi_delta": states[index].isi - float(cfsds["isi"][index]),
                    "cfsds_ws": float(cfsds["ws"][index]),
                    "open_ws": open_ws[index],
                    "cfsds_rh": float(cfsds["rh"][index]),
                    "open_rh": open_rh[index],
                    "cfsds_prec": float(cfsds["prec"][index]),
                    "open_prec": open_prec[index],
                }
            )
    payload = {
        "protocol": "Open-Meteo hourly reanalysis aggregated to 13:00 daily; CFSDS initial DMC/DC",
        "model_skill": False,
        "summary": _summary(rows),
        "rows": rows,
        "limitations": (
            "CFSDS FWI values are daily summary fields; the diagnostic uses a fixed 13:00 "
            "sample and previous-24h precipitation. It does not prove the model weather is wrong."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(args.csv, index=False)
    print(
        pd.DataFrame(rows)[
            [
                "case",
                "day",
                "cfsds_ffmc",
                "calc_ffmc",
                "cfsds_bui",
                "calc_bui",
                "cfsds_isi",
                "calc_isi",
            ]
        ].to_string(index=False)
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
