"""Print a ten-day Canadian FWI sequence.

The sequence is a demo, not a calibrated weather record. It shows the moisture codes that
feed the FBP surface-fire model.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire import DailyWeather, fwi_sequence, initial_fwi_state  # noqa: E402

WEATHER = [
    DailyWeather(2026, 7, 1, 20, 40, 10, 0, 55),
    DailyWeather(2026, 7, 2, 22, 35, 12, 0, 55),
    DailyWeather(2026, 7, 3, 18, 50, 8, 2, 55),
    DailyWeather(2026, 7, 4, 25, 30, 15, 0, 55),
    DailyWeather(2026, 7, 5, 27, 25, 20, 0, 55),
    DailyWeather(2026, 7, 6, 21, 45, 9, 0, 55),
    DailyWeather(2026, 7, 7, 19, 60, 5, 5, 55),
    DailyWeather(2026, 7, 8, 23, 38, 11, 0, 55),
    DailyWeather(2026, 7, 9, 26, 28, 18, 0, 55),
    DailyWeather(2026, 7, 10, 24, 33, 14, 0, 55),
]


def main() -> None:
    """Print the daily FWI sequence."""
    states = fwi_sequence(WEATHER, initial_fwi_state(85, 6, 15))
    print("day  FFMC    DMC     DC     ISI    BUI    FWI    DSR")
    for day, state in zip(WEATHER, states, strict=True):
        print(
            f"{day.day:>3}  {state.ffmc:6.2f}  {state.dmc:6.2f}  {state.dc:6.2f}  "
            f"{state.isi:5.2f}  {state.bui:5.2f}  {state.fwi:5.2f}  {state.dsr:5.3f}"
        )


if __name__ == "__main__":
    main()
