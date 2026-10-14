"""Annual-step simulator over the compiled matrix dataset.

The simulator reads only the compiled dataset. Each year it applies the scheduled
treatments (only where the fragment's track offers the treatment, which is the
Model II operability rule), records the feature accounts, and advances every
fragment's offset age by one year. A schedule replays deterministically.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from ..model.schema import dataset_reference
from ..patch.metrics import load_topology, patch_metrics
from ..roads.network import RouteNetwork
from .curve import curve_value


def _as_int(value: object) -> int:
    """Convert a pandas scalar to an int."""
    return int(float(str(value)))


def _as_float(value: object) -> float:
    """Convert a pandas scalar to a float."""
    return float(str(value))


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
        self.products = pd.read_parquet(self.dataset_dir / "products.parquet")
        self.accounts = pd.read_parquet(self.dataset_dir / "accounts.parquet")
        self.fragments["offset"] = self.fragments["age"].astype(int)
        self._product_values: list[dict[str, object]] = []
        self._route_values: list[dict[str, object]] = []
        # Cache each curve's sorted x/y arrays for vectorized interpolation.
        self._curves: dict[int, tuple[np.ndarray, np.ndarray]] = {
            _as_int(curve_id): (
                group.sort_values("x")["x"].to_numpy(dtype=float),
                group.sort_values("x")["y"].to_numpy(dtype=float),
            )
            for curve_id, group in self.curves.groupby("curve_id")
        }

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

    def apply_treatments(
        self, schedule: pd.DataFrame, year: int, network: RouteNetwork | None = None
    ) -> set[int]:
        """Apply the treatments scheduled for a year and record their products.

        A product is produced when its treatment is applied to a fragment on the
        product's track; the yield is the fragment's area times the product curve at
        the pre-treatment offset. When a road network is given, each product is routed
        to the block's nearest destination (exclusive routing) and the haul cost is
        recorded.

        Parameters
        ----------
        schedule : pandas.DataFrame
            The schedule, with ``block_id``, ``treatment``, and ``period`` columns.
        year : int
            The year to apply.
        network : RouteNetwork or None, optional
            The road network for routing products to destinations.

        Returns
        -------
        set of int
            The blocks that had at least one fragment treated.
        """
        disturbed: set[int] = set()
        for _, row in schedule[schedule["period"] == year].iterrows():
            mask = self.fragments["block_id"] == row["block_id"]
            for index in self.fragments.index[mask]:
                track_id = _as_int(self.fragments.at[index, "track_id"])
                label = str(row["treatment"])
                treatment = self._treatment(track_id, label)
                if treatment is None:
                    continue
                offset = _as_int(self.fragments.at[index, "offset"])
                area = _as_float(self.fragments.at[index, "area_ha"])
                produced = self.products[
                    (self.products["track_id"] == track_id) & (self.products["treatment"] == label)
                ]
                block_id = int(row["block_id"])
                for _, product in produced.iterrows():
                    value = area * curve_value(self.curves, int(product["curve_id"]), offset)
                    self._product_values.append(
                        {"year": year, "account": str(product["label"]), "value": value}
                    )
                    if network is not None:
                        nearest = network.nearest_destination(block_id)
                        if nearest is not None:
                            destination, length = nearest
                            self._route_values.append(
                                {
                                    "year": year,
                                    "block_id": block_id,
                                    "dest_id": destination,
                                    "product": str(product["label"]),
                                    "volume": value,
                                    "length_m": length,
                                    "cost": network.route_cost(block_id, destination),
                                }
                            )
                self.fragments.at[index, "track_id"] = _as_int(treatment["new_track"])
                self.fragments.at[index, "offset"] = _as_int(treatment["offset"])
                disturbed.add(int(row["block_id"]))
        return disturbed

    def account_values(self, year: int) -> list[dict[str, object]]:
        """Compute the feature account values for the current state.

        A feature label may appear on several tracks; the value is summed across them.
        The curves are evaluated vectorized per curve, then multiplied by area and
        summed per account label.
        """
        merged = self.fragments[["track_id", "area_ha", "offset"]].merge(
            self.features[["track_id", "label", "curve_id"]], on="track_id", how="inner"
        )
        if merged.empty:
            return []
        merged["yield"] = 0.0
        for curve_id, group in merged.groupby("curve_id"):
            arrays = self._curves.get(_as_int(curve_id))
            if arrays is None:
                continue
            xs, ys = arrays
            merged.loc[group.index, "yield"] = np.interp(
                group["offset"].to_numpy(dtype=float), xs, ys
            )
        merged["value"] = merged["area_ha"].astype(float) * merged["yield"]
        totals = merged.groupby("label")["value"].sum()
        return [
            {"year": year, "account": str(label), "value": float(value)}
            for label, value in totals.items()
        ]

    def simulate(
        self, schedule: pd.DataFrame, years: int, network: RouteNetwork | None = None
    ) -> pd.DataFrame:
        """Replay a schedule and return the account values, without writing files.

        Parameters
        ----------
        schedule : pandas.DataFrame
            The schedule, with ``block_id``, ``treatment``, and ``period`` columns.
        years : int
            The number of annual steps.
        network : RouteNetwork or None, optional
            The road network for routing products to destinations.

        Returns
        -------
        pandas.DataFrame
            The account values, with ``year``, ``account``, and ``value`` columns.
        """
        records: list[dict[str, object]] = []
        self._product_values = []
        self._route_values = []
        for year in range(years):
            self.apply_treatments(schedule, year, network)
            records.extend(self.account_values(year))
            self.fragments["offset"] = self.fragments["offset"].astype(int) + 1
        return pd.DataFrame(records, columns=["year", "account", "value"])

    def run(
        self,
        schedule_csv: Path,
        years: int,
        out_dir: Path,
        topology_csv: Path | None = None,
        patch_breaks: Sequence[float] = (5.0, 10.0, 50.0),
        network: RouteNetwork | None = None,
    ) -> pd.DataFrame:
        """Replay a schedule for the given horizon and write the run outputs.

        Parameters
        ----------
        schedule_csv : Path
            A CSV with ``block_id``, ``treatment``, and ``period`` columns.
        years : int
            The number of annual steps.
        out_dir : Path
            Directory to write the run outputs into.
        topology_csv : Path or None, optional
            A block topology edge list. When given, per-year patch metrics are written
            to ``patch_metrics.csv``.
        patch_breaks : sequence of float, optional
            The patch size-class upper bounds, in hectares.
        network : RouteNetwork or None, optional
            The road network for routing products. When given, ``route_values.csv`` is
            written.

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

        values = self.simulate(schedule, years, network)
        values.to_csv(out_dir / "account_values.csv", index=False)
        pd.DataFrame(self._product_values, columns=["year", "account", "value"]).to_csv(
            out_dir / "product_values.csv", index=False
        )
        if network is not None:
            pd.DataFrame(
                self._route_values,
                columns=["year", "block_id", "dest_id", "product", "volume", "length_m", "cost"],
            ).to_csv(out_dir / "route_values.csv", index=False)
        if topology_csv is not None:
            # A fresh simulator: ``simulate`` above already advanced this one's state.
            Simulator.from_dataset(self.dataset_dir).write_patch_metrics(
                schedule, years, topology_csv, patch_breaks, out_dir
            )
        (out_dir / "dataset.json").write_text(
            json.dumps(dataset_reference(self.dataset_dir), indent=2) + "\n", encoding="utf-8"
        )
        return values

    def write_patch_metrics(
        self,
        schedule: pd.DataFrame,
        years: int,
        topology_csv: Path,
        patch_breaks: Sequence[float],
        out_dir: Path,
    ) -> None:
        """Replay a schedule and write per-year patch metrics for the disturbed blocks."""
        topology = load_topology(topology_csv)
        edges = list(
            zip(topology["src_block"].tolist(), topology["dst_block"].tolist(), strict=True)
        )
        block_area = {
            _as_int(block): _as_float(area)
            for block, area in self.fragments.groupby("block_id")["area_ha"].sum().items()
        }
        patch_records: list[dict[str, object]] = []
        self.fragments["offset"] = self.fragments["age"].astype(int)
        for year in range(years):
            disturbed = self.apply_treatments(schedule, year)
            if disturbed:
                patch_records.append(
                    {"year": year, **patch_metrics(disturbed, edges, block_area, patch_breaks)}
                )
            self.fragments["offset"] = self.fragments["offset"].astype(int) + 1
        pd.DataFrame(patch_records).to_csv(out_dir / "patch_metrics.csv", index=False)
