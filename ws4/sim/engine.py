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
from ..patch.accounts import PatchAccount, PatchLedger, load_patch_edges
from ..patch.constraints import green_up_violations, opening_violations, schedule_years
from ..patch.metrics import patch_metrics
from ..roads.accounts import (
    DuplicateAccount,
    RouteAccount,
    RouteCostLedger,
    RouteModel,
    resolve_account_values,
)
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
        self,
        schedule: pd.DataFrame,
        year: int,
        route_model: RouteModel | None = None,
        ledger: RouteCostLedger | None = None,
    ) -> set[int]:
        """Apply the treatments scheduled for a year and record their products.

        A product is produced when its treatment is applied to a fragment on the
        product's track; the yield is the fragment's area times the product curve at
        the pre-treatment offset. When a route model is given, each product is sent to an
        eligible destination (exclusive per product per block) and the route cost is
        recorded.

        Parameters
        ----------
        schedule : pandas.DataFrame
            The schedule, with ``block_id``, ``treatment``, and ``period`` columns.
        year : int
            The year to apply.
        route_model : RouteModel or None, optional
            The route model (destinations, eligibility, surplus) for routing products.
        ledger : RouteCostLedger or None, optional
            The route cost ledger to record the routed products into.

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
                    product_label = str(product["label"])
                    self._product_values.append(
                        {"year": year, "account": product_label, "value": value}
                    )
                    if route_model is not None:
                        destination, route = route_model.assign(block_id, product_label)
                        if ledger is not None:
                            ledger.record(year, block_id, product_label, value, destination, route)
                        self._route_values.append(
                            {
                                "year": year,
                                "block_id": block_id,
                                "destination": destination,
                                "product": product_label,
                                "volume": value,
                                "length_m": route.length_m if route is not None else 0.0,
                                "haul_cost": route.haul_cost if route is not None else 0.0,
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
        merged = (
            self.fragments[["track_id", "area_ha", "offset"]]
            .merge(self.features[["track_id", "label", "curve_id"]], on="track_id", how="inner")
            .reset_index(drop=True)
        )
        if merged.empty:
            return []
        # Assign into a positional array rather than ``.loc`` per curve: a big model has tens
        # of thousands of curves, and a per-group ``.loc`` setitem dominates the run.
        yields = np.zeros(len(merged), dtype=float)
        for curve_id, group in merged.groupby("curve_id"):
            arrays = self._curves.get(_as_int(curve_id))
            if arrays is None:
                continue
            xs, ys = arrays
            yields[group.index.to_numpy()] = np.interp(
                group["offset"].to_numpy(dtype=float), xs, ys
            )
        merged["yield"] = yields
        merged["value"] = merged["area_ha"].astype(float) * merged["yield"]
        totals = merged.groupby("label")["value"].sum()
        return [
            {"year": year, "account": str(label), "value": float(value)}
            for label, value in totals.items()
        ]

    def block_criteria(self, label: str) -> dict[int, float]:
        """Return the per-block value of a feature label, area-weighted.

        The value is the area-weighted mean of the feature curve over the block's
        fragments, so a half disturbed block has a criterion value of 0.5. This is the
        patch membership criterion of the patch accounts (see ``ws4.patch.accounts``).

        Parameters
        ----------
        label : str
            The feature label (for example ``feature.Seral.young``).

        Returns
        -------
        dict of int to float
            The criterion value per block.
        """
        features = self.features[self.features["label"] == label]
        merged = self.fragments[["block_id", "track_id", "area_ha", "offset"]].merge(
            features[["track_id", "curve_id"]], on="track_id", how="inner"
        )
        if merged.empty:
            return {}
        values = np.zeros(len(merged), dtype=float)
        for curve_id, group in merged.groupby("curve_id"):
            arrays = self._curves.get(_as_int(curve_id))
            if arrays is None:
                continue
            xs, ys = arrays
            values[group.index.to_numpy()] = np.interp(
                group["offset"].to_numpy(dtype=float), xs, ys
            )
        merged = merged.assign(weighted=values * merged["area_ha"].astype(float))
        grouped = merged.groupby("block_id").agg(
            weighted=("weighted", "sum"), area=("area_ha", "sum")
        )
        return {
            _as_int(block): float(row.weighted / row.area) if row.area > 0.0 else 0.0
            for block, row in grouped.iterrows()
        }

    def simulate(
        self,
        schedule: pd.DataFrame,
        years: int,
        network: RouteNetwork | None = None,
        route_model: RouteModel | None = None,
        ledger: RouteCostLedger | None = None,
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
        route_model : RouteModel or None, optional
            The route model. When omitted but ``network`` is given, a default model over
            that network is used.
        ledger : RouteCostLedger or None, optional
            The route cost ledger to record routed products into.

        Returns
        -------
        pandas.DataFrame
            The account values, with ``year``, ``account``, and ``value`` columns.
        """
        model = route_model
        if model is None and network is not None:
            model = RouteModel(network)
        records: list[dict[str, object]] = []
        self._product_values = []
        self._route_values = []
        for year in range(years):
            self.apply_treatments(schedule, year, model, ledger)
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
        route_model: RouteModel | None = None,
        route_accounts: Sequence[RouteAccount] = (),
        duplicate_accounts: Sequence[DuplicateAccount] = (),
        max_opening_ha: float | None = None,
        min_green_up_years: int | None = None,
        patch_accounts: Sequence[PatchAccount] = (),
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
            The road network for routing products.
        route_model : RouteModel or None, optional
            The route model (destinations, eligibility, surplus). When omitted but
            ``network`` is given, a default model over that network is used.
        route_accounts : sequence of RouteAccount, optional
            The route accounts to resolve into the account values.
        duplicate_accounts : sequence of DuplicateAccount, optional
            The duplicate accounts to apply to the account values.
        max_opening_ha : float or None, optional
            The maximum opening size. When given, ``spatial_violations.csv`` reports the
            patches over it.
        min_green_up_years : int or None, optional
            The green-up interval. When given, ``spatial_violations.csv`` reports the
            adjacent pairs disturbed within it.
        patch_accounts : sequence of PatchAccount, optional
            Patch account definitions. When given with a topology, ``patch_accounts.csv``
            is written.

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

        model = route_model
        if model is None and network is not None:
            model = RouteModel(network)
        ledger = RouteCostLedger(model.network) if model is not None else None

        values = self.simulate(schedule, years, route_model=model, ledger=ledger)
        if ledger is not None and route_accounts:
            values = resolve_account_values(
                values, ledger.account_values(route_accounts), duplicate_accounts
            )
        elif duplicate_accounts:
            values = resolve_account_values(values, None, duplicate_accounts)
        values.to_csv(out_dir / "account_values.csv", index=False)
        pd.DataFrame(self._product_values, columns=["year", "account", "value"]).to_csv(
            out_dir / "product_values.csv", index=False
        )
        if ledger is not None:
            ledger.write(out_dir)
        elif self._route_values:
            pd.DataFrame(
                self._route_values,
                columns=[
                    "year",
                    "block_id",
                    "destination",
                    "product",
                    "volume",
                    "length_m",
                    "haul_cost",
                ],
            ).to_csv(out_dir / "route_values.csv", index=False)
        if topology_csv is not None:
            # A fresh simulator: ``simulate`` above already advanced this one's state.
            Simulator.from_dataset(self.dataset_dir).write_patch_metrics(
                schedule,
                years,
                topology_csv,
                patch_breaks,
                out_dir,
                max_opening_ha=max_opening_ha,
                min_green_up_years=min_green_up_years,
                patch_accounts=patch_accounts,
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
        max_opening_ha: float | None = None,
        min_green_up_years: int | None = None,
        patch_accounts: Sequence[PatchAccount] = (),
    ) -> None:
        """Replay a schedule and write per-year patch metrics and patch accounts."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        graph = load_patch_edges(topology_csv)
        edges = [(source, target) for source, target, _ in graph]
        block_area = {
            _as_int(block): _as_float(area)
            for block, area in self.fragments.groupby("block_id")["area_ha"].sum().items()
        }
        ledger = PatchLedger(patch_accounts, graph, block_area) if patch_accounts else None
        criteria_labels = sorted({account.criteria for account in patch_accounts})
        patch_records: list[dict[str, object]] = []
        schedule_pairs: list[tuple[int, int]] = []
        self.fragments["offset"] = self.fragments["age"].astype(int)
        for year in range(years):
            disturbed = self.apply_treatments(schedule, year)
            if ledger is not None:
                criteria = {label: self.block_criteria(label) for label in criteria_labels}
                ledger.record(year, criteria)
            if disturbed:
                schedule_pairs.extend((int(block), year) for block in disturbed)
                patch_records.append(
                    {"year": year, **patch_metrics(disturbed, edges, block_area, patch_breaks)}
                )
            self.fragments["offset"] = self.fragments["offset"].astype(int) + 1
        pd.DataFrame(patch_records).to_csv(out_dir / "patch_metrics.csv", index=False)
        if ledger is not None:
            ledger.write(out_dir)
        if max_opening_ha is not None or min_green_up_years is not None:
            selected_by_year, harvest_year = schedule_years(schedule_pairs)
            violations: list[dict[str, object]] = []
            if max_opening_ha is not None:
                violations.extend(
                    opening_violations(selected_by_year, edges, block_area, max_opening_ha)
                )
            if min_green_up_years is not None:
                violations.extend(green_up_violations(harvest_year, edges, min_green_up_years))
            pd.DataFrame(
                violations,
                columns=["kind", "year", "area_ha", "limit", "block_a", "block_b", "years"],
            ).to_csv(out_dir / "spatial_violations.csv", index=False)
