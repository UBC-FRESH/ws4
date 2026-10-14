"""Annual-step simulator over the compiled matrix dataset.

The simulator reads only the compiled dataset. Each year it applies the scheduled
treatments (only where the fragment's track offers the treatment, which is the
Model II operability rule), records the feature accounts, and advances every
fragment's offset age by one year. A schedule replays deterministically.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .curve import curve_value


def _as_int(value: object) -> int:
    """Convert a pandas scalar to an int."""
    return int(float(str(value)))


class Simulator:
    """Annual-step simulator over fragments and tracks.

    Parameters
    ----------
    dataset_dir : Path
        A compiled matrix dataset directory.
    """

    def __init__(self, dataset_dir: Path) -> None:
        """Load the compiled dataset and initialize each fragment's offset age."""
        self.dataset_dir = Path(dataset_dir)
        self.fragments = pd.read_parquet(self.dataset_dir / "fragments.parquet")
        self.tracks = pd.read_parquet(self.dataset_dir / "tracks.parquet")
        self.treatments = pd.read_parquet(self.dataset_dir / "treatments.parquet")
        self.curves = pd.read_parquet(self.dataset_dir / "curves.parquet")
        self.features = pd.read_parquet(self.dataset_dir / "features.parquet")
        self.accounts = pd.read_parquet(self.dataset_dir / "accounts.parquet")
        self.fragments["offset"] = self.fragments["age"].astype(int)

    @classmethod
    def from_dataset(cls, dataset_dir: Path) -> Simulator:
        """Build a simulator that reads the given compiled dataset."""
        return cls(dataset_dir)

    def _treatment(self, track_id: int, label: str) -> pd.Series | None:
        """Return the treatment row for a track and label, or None.

        A fragment is operable for a treatment only when its track offers it; this
        is the block-level intersection rule applied at the fragment.
        """
        match = self.treatments[
            (self.treatments["track_id"] == track_id) & (self.treatments["treatment"] == label)
        ]
        return match.iloc[0] if not match.empty else None

    def apply_treatments(self, schedule: pd.DataFrame, year: int) -> int:
        """Apply the treatments scheduled for a year.

        Parameters
        ----------
        schedule : pandas.DataFrame
            The schedule, with ``block_id``, ``treatment``, and ``period`` columns.
        year : int
            The year to apply.

        Returns
        -------
        int
            The number of fragments treated.
        """
        treated = 0
        for _, row in schedule[schedule["period"] == year].iterrows():
            mask = self.fragments["block_id"] == row["block_id"]
            for index in self.fragments.index[mask]:
                track_id = _as_int(self.fragments.at[index, "track_id"])
                treatment = self._treatment(track_id, str(row["treatment"]))
                if treatment is None:
                    continue
                self.fragments.at[index, "track_id"] = _as_int(treatment["new_track"])
                self.fragments.at[index, "offset"] = _as_int(treatment["offset"])
                treated += 1
        return treated

    def account_values(self, year: int) -> list[dict[str, object]]:
        """Compute the feature account values for the current state.

        A feature label may appear on several tracks; the value is summed across them.
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

    def run(self, schedule_csv: Path, years: int, out_dir: Path) -> pd.DataFrame:
        """Replay a schedule for the given horizon and write the account values.

        Parameters
        ----------
        schedule_csv : Path
            A CSV with ``block_id``, ``treatment``, and ``period`` columns.
        years : int
            The number of annual steps.
        out_dir : Path
            Directory to write ``account_values.csv`` into.

        Returns
        -------
        pandas.DataFrame
            The account values, with ``year``, ``account``, and ``value`` columns.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        schedule = pd.read_csv(schedule_csv)
        if "period" not in schedule.columns:
            schedule = schedule.assign(period=0)

        records: list[dict[str, object]] = []
        for year in range(years):
            self.apply_treatments(schedule, year)
            records.extend(self.account_values(year))
            self.fragments["offset"] = self.fragments["offset"].astype(int) + 1

        values = pd.DataFrame(records, columns=["year", "account", "value"])
        values.to_csv(out_dir / "account_values.csv", index=False)
        return values
