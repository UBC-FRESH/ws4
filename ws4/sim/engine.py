"""Annual-step simulator over fragments, aggregated to blocks at runtime."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .curve import curve_value


class Simulator:
    """Annual-step simulator over fragments.

    Order per year:

    1. Apply the scheduled treatments for the year (reset the offset, switch track).
    2. Record the account values for the current state.
    3. Advance every fragment's offset age by one year.

    Product and feature attributes are aggregated to the block level on demand; the
    prototype records feature accounts only.
    """

    def __init__(self, dataset_dir: Path) -> None:
        """Load a compiled dataset and initialize each fragment's offset age."""
        self.dataset_dir = Path(dataset_dir)
        self.fragments = pd.read_parquet(self.dataset_dir / "fragments.parquet")
        self.tracks = pd.read_parquet(self.dataset_dir / "tracks.parquet")
        self.treatments = pd.read_parquet(self.dataset_dir / "treatments.parquet")
        self.curves = pd.read_parquet(self.dataset_dir / "curves.parquet")
        self.features = pd.read_parquet(self.dataset_dir / "features.parquet")
        self.fragments["offset"] = self.fragments["age"].astype(int)

    @classmethod
    def from_dataset(cls, dataset_dir: Path) -> Simulator:
        """Build a simulator that reads the given compiled dataset."""
        return cls(dataset_dir)

    def _apply_treatments(self, schedule: pd.DataFrame, year: int) -> None:
        """Apply the treatments scheduled for a year."""
        rows = schedule[schedule["period"] == year]
        for _, row in rows.iterrows():
            mask = self.fragments["block_id"] == row["block_id"]
            if not mask.any():
                continue
            match = self.treatments[self.treatments["treatment"] == row["treatment"]]
            if match.empty:
                continue
            self.fragments.loc[mask, "offset"] = int(match["offset"].iloc[0])
            self.fragments.loc[mask, "track_id"] = int(match["new_track"].iloc[0])

    def _account_values(self, year: int) -> list[dict[str, object]]:
        """Compute the feature account values for the current state.

        A label may appear on several tracks; the value is summed across them.
        """
        records: list[dict[str, object]] = []
        for label in sorted(set(self.features["label"])):
            total = 0.0
            for _, feature in self.features[self.features["label"] == label].iterrows():
                on_track = self.fragments["track_id"] == feature["track_id"]
                for _, fragment in self.fragments[on_track].iterrows():
                    value = curve_value(
                        self.curves, int(feature["curve_id"]), float(fragment["offset"])
                    )
                    total += float(fragment["area_ha"]) * value
            records.append({"year": year, "account": label, "value": total})
        return records

    def run(self, schedule_csv: Path, years: int, out_dir: Path) -> None:
        """Replay a schedule for the given horizon and write the account values."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        schedule = pd.read_csv(schedule_csv)
        if "period" not in schedule.columns:
            schedule = schedule.assign(period=0)

        records: list[dict[str, object]] = []
        for year in range(years):
            self._apply_treatments(schedule, year)
            records.extend(self._account_values(year))
            self.fragments["offset"] = self.fragments["offset"].astype(int) + 1

        pd.DataFrame(records, columns=["year", "account", "value"]).to_csv(
            out_dir / "account_values.csv", index=False
        )
