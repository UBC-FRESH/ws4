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
from ..patch.constraints import (
    core_area_violations,
    green_up_violations,
    opening_violations,
    schedule_years,
)
from ..patch.edge import EdgeElement, edge_values
from ..patch.metrics import patch_metrics
from ..roads.accounts import (
    DuplicateAccount,
    RouteAccount,
    RouteCostLedger,
    RouteModel,
    resolve_account_values,
)
from ..roads.network import RouteNetwork
from .curve import CurveTable


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
        self._initial_track = self.fragments["track_id"].to_numpy(copy=True)
        self._initial_offset = self.fragments["offset"].to_numpy(copy=True)
        self._product_values: list[dict[str, object]] = []
        self._route_values: list[dict[str, object]] = []
        self._edge_values: list[dict[str, object]] = []
        # An integer-age table for gather-based evaluation (see :class:`CurveTable`).
        self._curve_table = CurveTable.from_curves(self.curves)
        # Index the treatments, products, and fragments once, so a year's treatments do not
        # index the frames row by row.
        self._treatment_by_key: dict[tuple[int, str], tuple[int, int]] = {
            (_as_int(row.track_id), str(row.treatment)): (
                _as_int(row.new_track),
                _as_int(row.offset),
            )
            for row in self.treatments.itertuples(index=False)
        }
        self._products_by_key: dict[tuple[int, str], list[tuple[int, str]]] = {}
        for product in self.products.itertuples(index=False):
            key = (_as_int(product.track_id), str(product.treatment))
            self._products_by_key.setdefault(key, []).append(
                (_as_int(product.curve_id), str(product.label))
            )
        self._track_features: dict[int, list[tuple[int, str]]] = {}
        for feature in self.features.itertuples(index=False):
            self._track_features.setdefault(_as_int(feature.track_id), []).append(
                (_as_int(feature.curve_id), str(feature.label))
            )
        # The fragment-position index is rebuilt lazily (the caller may replace the frame).
        self._fragments_index_id = -1
        self._fragments_by_block: dict[int, list[int]] = {}
        # The fragment-to-feature join is precomputed as arrays and rebuilt only when a
        # treatment changes a fragment's track (or the frame is replaced).
        self._join_dirty = True
        self._join_frame_id = -1
        self._pair_frag = np.empty(0, dtype=np.int64)
        self._pair_label = np.empty(0, dtype=np.int64)
        self._pair_row = np.empty(0, dtype=np.int64)
        self._labels: list[str] = []
        # Precompute the feature side of the join once (the features table never changes):
        # the feature rows sorted by track code, with each curve's table row and the label
        # code resolved, so a rebuild is only a searchsorted and a vectorized expansion.
        self._track_ids = np.unique(self.tracks["track_id"].to_numpy(dtype=np.int64))
        feature_track = self.features["track_id"].to_numpy(dtype=np.int64)
        feature_curve = self.features["curve_id"].to_numpy(dtype=np.int64)
        feature_label = self.features["label"].astype(str).to_numpy()
        label_names, feature_label_code = np.unique(feature_label, return_inverse=True)
        self._labels = [str(name) for name in label_names]
        feature_codes = np.searchsorted(self._track_ids, feature_track)
        self._feature_order = np.argsort(feature_codes, kind="stable")
        self._feature_per_code = np.bincount(feature_codes, minlength=self._track_ids.size)
        self._feature_starts = np.zeros(self._track_ids.size, dtype=np.int64)
        if self._track_ids.size:
            self._feature_starts[1:] = np.cumsum(self._feature_per_code)[:-1]
        sorted_curve = feature_curve[self._feature_order]
        self._sorted_label_code = feature_label_code[self._feature_order]
        unique_curve, curve_inverse = np.unique(sorted_curve, return_inverse=True)
        row_lookup = np.zeros(unique_curve.size, dtype=np.int64)
        for index, curve_id in enumerate(unique_curve):
            curve_row = self._curve_table.row(int(curve_id))
            if curve_row is not None:
                row_lookup[index] = curve_row
        self._sorted_row = row_lookup[curve_inverse]
        # Per-label joins for the patch/edge criteria, rebuilt when the frame changes.
        self._criteria_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._criteria_frame_id = -1

    def _rebuild_join(self) -> None:
        """Precompute the fragment-to-feature join as flat arrays.

        The join is ``(fragment position, curve row, label code)`` per feature of the
        fragment's track, so a year's account values are a vectorized gather. The feature
        side is precomputed once; only the fragment tracks change between rebuilds.
        """
        fragment_track = self.fragments["track_id"].to_numpy(dtype=np.int64)
        fragment_count = fragment_track.size
        if fragment_count == 0 or self._feature_order.size == 0:
            self._pair_frag = np.empty(0, dtype=np.int64)
            self._pair_label = np.empty(0, dtype=np.int64)
            self._pair_row = np.empty(0, dtype=np.int64)
            self._join_dirty = False
            self._join_frame_id = id(self.fragments)
            return
        fragment_codes = np.searchsorted(self._track_ids, fragment_track)
        per_fragment = self._feature_per_code[fragment_codes]
        pair_frag = np.repeat(np.arange(fragment_count, dtype=np.int64), per_fragment)
        cumulative = np.cumsum(per_fragment)
        block_start = cumulative - per_fragment
        within = np.arange(pair_frag.size, dtype=np.int64) - np.repeat(block_start, per_fragment)
        feature_rows = self._feature_starts[np.repeat(fragment_codes, per_fragment)] + within
        self._pair_frag = pair_frag
        self._pair_row = self._sorted_row[feature_rows]
        self._pair_label = self._sorted_label_code[feature_rows]
        self._join_dirty = False
        self._join_frame_id = id(self.fragments)

    def _block_index(self) -> dict[int, list[int]]:
        """Return the fragment positions per block, rebuilt when the frame is replaced."""
        if self._fragments_index_id != id(self.fragments):
            by_block: dict[int, list[int]] = {}
            for index, block in enumerate(self.fragments["block_id"].to_numpy()):
                by_block.setdefault(int(block), []).append(index)
            self._fragments_by_block = by_block
            self._fragments_index_id = id(self.fragments)
        return self._fragments_by_block

    def _curve_value(self, curve_id: int, x: float) -> float:
        """Evaluate a curve at one point: exact for integer ages, linear between them."""
        return self._curve_table.value(curve_id, x)

    @classmethod
    def from_dataset(cls, dataset_dir: Path) -> Simulator:
        """Build a simulator that reads the given compiled dataset."""
        return cls(dataset_dir)

    def reset(self) -> None:
        """Restore the mutable state (tracks and offsets) to the construction state.

        The static caches (curves, feature joins, treatment and product indexes) are kept,
        so a search can reuse one simulator across evaluations instead of reloading the
        dataset each time. The join is only invalidated when the tracks actually changed.
        """
        if not np.array_equal(self.fragments["track_id"].to_numpy(), self._initial_track):
            self.fragments["track_id"] = self._initial_track
            self._join_dirty = True
        self.fragments["offset"] = self._initial_offset
        self._criteria_frame_id = -1

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
        tracks = self.fragments["track_id"].to_numpy(copy=True)
        offsets = self.fragments["offset"].to_numpy(copy=True)
        areas = self.fragments["area_ha"].to_numpy(copy=True)
        by_block = self._block_index()
        changed = False
        for row in schedule[schedule["period"] == year].itertuples(index=False):
            block_id = _as_int(row.block_id)
            label = str(row.treatment)
            for index in by_block.get(block_id, []):
                key = (int(tracks[index]), label)
                treatment = self._treatment_by_key.get(key)
                if treatment is None:
                    continue
                offset = int(offsets[index])
                area = float(areas[index])
                for curve_id, product_label in self._products_by_key.get(key, []):
                    value = area * self._curve_value(curve_id, offset)
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
                tracks[index] = treatment[0]
                offsets[index] = treatment[1]
                changed = True
                disturbed.add(block_id)
        if changed:
            self.fragments["track_id"] = tracks
            self.fragments["offset"] = offsets
            self._join_dirty = True
        return disturbed

    def account_values(self, year: int) -> list[dict[str, object]]:
        """Compute the feature account values for the current state.

        A feature label may appear on several tracks; the value is the sum of the area
        times the feature curve at the fragment's offset, over the precomputed join. The
        curves are evaluated with a single integer-age table gather.
        """
        if self._join_dirty or self._join_frame_id != id(self.fragments):
            self._rebuild_join()
        if self._pair_frag.size == 0:
            return []
        offsets = self.fragments["offset"].to_numpy(dtype=float)
        areas = self.fragments["area_ha"].to_numpy(dtype=float)
        yields = self._curve_table.gather(self._pair_row, offsets[self._pair_frag])
        values = areas[self._pair_frag] * yields
        totals = np.bincount(self._pair_label, weights=values, minlength=len(self._labels))
        return [
            {"year": year, "account": self._labels[index], "value": float(total)}
            for index, total in enumerate(totals)
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
        pair_frag, pair_row = self._criteria_join(label)
        if pair_frag.size == 0:
            return {}
        offsets = self.fragments["offset"].to_numpy(dtype=float)
        areas = self.fragments["area_ha"].to_numpy(dtype=float)
        yields = self._curve_table.gather(pair_row, offsets[pair_frag])
        frag_area = areas[pair_frag]
        weighted = frag_area * yields
        blocks = self.fragments["block_id"].to_numpy(dtype=np.int64)[pair_frag]
        unique, inverse = np.unique(blocks, return_inverse=True)
        numerator = np.bincount(inverse, weights=weighted, minlength=unique.size)
        denominator = np.bincount(inverse, weights=frag_area, minlength=unique.size)
        return {
            int(block): float(numerator[index] / denominator[index])
            if denominator[index] > 0.0
            else 0.0
            for index, block in enumerate(unique)
        }

    def block_trajectory(
        self, block_id: int, treatment: str | None, year: int, years: int
    ) -> dict[tuple[int, str], float]:
        """Return one block's feature account values over a horizon.

        The block's fragments are simulated in isolation: if ``treatment`` is given, it is
        applied in ``year`` (a no-op where the fragment's track does not offer it), and
        every fragment's offset advances one year per step. The result is
        ``(year, label) -> value``, so a schedule's account values are the empty-schedule
        base plus a per-block delta. Feature account values are additive over blocks.

        Parameters
        ----------
        block_id : int
            The block.
        treatment : str or None
            The treatment to apply, or None for no treatment.
        year : int
            The year to apply the treatment.
        years : int
            The horizon, in years.

        Returns
        -------
        dict of (int, str) to float
            The account value per year and label (non-zero entries only). Feature labels
            and the product labels produced by the treatment are both included, so the
            result is addable to the empty-schedule base for every simulated account.
        """
        positions = self._block_index().get(int(block_id), [])
        if not positions:
            return {}
        tracks = self.fragments["track_id"].to_numpy()[positions].astype(np.int64)
        offsets = self.fragments["offset"].to_numpy()[positions].astype(np.int64)
        areas = self.fragments["area_ha"].to_numpy()[positions].astype(float)
        totals: dict[tuple[int, str], float] = {}
        for step in range(years):
            if treatment is not None and step == year:
                for index in range(len(positions)):
                    current = int(tracks[index])
                    transition = self._treatment_by_key.get((current, str(treatment)))
                    if transition is not None:
                        area = float(areas[index])
                        offset = int(offsets[index])
                        for curve_id, product_label in self._products_by_key.get(
                            (current, str(treatment)), []
                        ):
                            value = area * self._curve_value(curve_id, offset)
                            key = (step, product_label)
                            totals[key] = totals.get(key, 0.0) + value
                        tracks[index] = transition[0]
                        offsets[index] = transition[1]
            for index in range(len(positions)):
                area = float(areas[index])
                offset = int(offsets[index])
                for curve_id, label in self._track_features.get(int(tracks[index]), ()):
                    value = area * self._curve_value(curve_id, offset)
                    key = (step, label)
                    totals[key] = totals.get(key, 0.0) + value
            offsets += 1
        return totals

    def block_products(self, block_id: int, treatment: str, year: int) -> dict[str, float]:
        """Return the product values a treatment makes on a block.

        The value is the fragment area times the product curve at the pre-treatment
        offset **at the treatment year** (the fragment ages ``year`` steps before the
        treatment), summed over the block's fragments. This is the product part of
        :meth:`block_trajectory` without stepping the horizon, so it costs O(fragments)
        rather than O(fragments x years).

        Parameters
        ----------
        block_id : int
            The block.
        treatment : str
            The treatment to apply.
        year : int
            The year the treatment is applied.

        Returns
        -------
        dict of str to float
            The product value per product label (non-zero entries only).
        """
        positions = self._block_index().get(int(block_id), [])
        if not positions:
            return {}
        tracks = self.fragments["track_id"].to_numpy()
        offsets = self.fragments["offset"].to_numpy()
        areas = self.fragments["area_ha"].to_numpy(dtype=float)
        totals: dict[str, float] = {}
        for index in positions:
            key = (int(tracks[index]), str(treatment))
            if key not in self._treatment_by_key:
                continue
            offset = int(offsets[index]) + int(year)
            area = float(areas[index])
            for curve_id, product_label in self._products_by_key.get(key, []):
                value = area * self._curve_value(curve_id, offset)
                totals[product_label] = totals.get(product_label, 0.0) + value
        return totals

    def block_route_accounts(
        self,
        block_id: int,
        treatment: str | None,
        year: int,
        years: int,
        route_model: RouteModel,
        route_accounts: Sequence[RouteAccount],
    ) -> dict[tuple[int, str], float]:
        """Return one block's route-account values over a horizon.

        The block's fragments are simulated in isolation (like :meth:`block_trajectory`),
        but its produced products are routed with ``route_model`` and recorded into a fresh
        summary ledger; the ledger's account values are returned as
        ``(year, account) -> value``. Route haul, maintenance, and volume are additive over
        blocks; build cost is not (it is charged once per segment across the whole
        schedule), so the objective excludes ``build`` accounts from the incremental path.

        Parameters
        ----------
        block_id : int
            The block.
        treatment : str or None
            The treatment to apply, or None.
        year : int
            The year to apply the treatment.
        years : int
            The horizon, in years.
        route_model : RouteModel
            The route model (destinations, eligibility, surplus).
        route_accounts : sequence of RouteAccount
            The route accounts to resolve.

        Returns
        -------
        dict of (int, str) to float
            The route account value per year and account (non-zero entries only).
        """
        positions = self._block_index().get(int(block_id), [])
        if not positions or not route_accounts:
            return {}
        tracks = self.fragments["track_id"].to_numpy()[positions].astype(np.int64)
        offsets = self.fragments["offset"].to_numpy()[positions].astype(np.int64)
        areas = self.fragments["area_ha"].to_numpy()[positions].astype(float)
        ledger = RouteCostLedger(route_model.network, collect=False)
        for step in range(years):
            if treatment is not None and step == year:
                for index in range(len(positions)):
                    key = (int(tracks[index]), str(treatment))
                    transition = self._treatment_by_key.get(key)
                    if transition is None:
                        continue
                    offset = int(offsets[index])
                    area = float(areas[index])
                    for curve_id, product_label in self._products_by_key.get(key, []):
                        value = area * self._curve_value(curve_id, offset)
                        destination, route = route_model.assign(int(block_id), product_label)
                        ledger.record(step, int(block_id), product_label, value, destination, route)
                    tracks[index] = transition[0]
                    offsets[index] = transition[1]
            offsets += 1
        frame = ledger.account_values(route_accounts)
        return {
            (int(str(row.year)), str(row.account)): float(str(row.value))
            for row in frame.itertuples(index=False)
        }

    def _criteria_join(self, label: str) -> tuple[np.ndarray, np.ndarray]:
        """Return the fragment positions and curve-table rows for a feature label."""
        if self._criteria_frame_id != id(self.fragments):
            self._criteria_cache = {}
            self._criteria_frame_id = id(self.fragments)
        cached = self._criteria_cache.get(label)
        if cached is not None:
            return cached
        feature = self.features[self.features["label"] == label]
        by_track: dict[int, list[int]] = {}
        for track, curve in zip(
            feature["track_id"].to_numpy(), feature["curve_id"].to_numpy(), strict=True
        ):
            by_track.setdefault(int(track), []).append(self._curve_table.row(int(curve)) or 0)
        pair_frag: list[int] = []
        pair_row: list[int] = []
        for position, track in enumerate(self.fragments["track_id"].to_numpy()):
            for row in by_track.get(int(track), ()):
                pair_frag.append(position)
                pair_row.append(row)
        result = (
            np.asarray(pair_frag, dtype=np.int64),
            np.asarray(pair_row, dtype=np.int64),
        )
        self._criteria_cache[label] = result
        return result

    def simulate(
        self,
        schedule: pd.DataFrame,
        years: int,
        network: RouteNetwork | None = None,
        route_model: RouteModel | None = None,
        ledger: RouteCostLedger | None = None,
        edge_elements: Sequence[EdgeElement] = (),
        edges: Sequence[tuple[int, int, float]] = (),
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
        edge_elements : sequence of EdgeElement, optional
            Edge contrast elements. When given with ``edges``, an edge contrast account
            value per element per year is added to the account values.
        edges : sequence of (int, int, float), optional
            The adjacency edges ``(src, dst, shared_length)`` for the edge contrast.

        Returns
        -------
        pandas.DataFrame
            The account values, with ``year``, ``account``, and ``value`` columns. Feature
            and product accounts are both included: a treatment's products are recorded as
            account values in the year they are produced, so every simulated account is
            scoreable.
        """
        model = route_model
        if model is None and network is not None:
            model = RouteModel(network)
        records: list[dict[str, object]] = []
        self._product_values = []
        self._route_values = []
        self._edge_values = []
        criteria_labels = sorted(
            {element.attribute1 for element in edge_elements}
            | {element.attribute2 for element in edge_elements}
        )
        for year in range(years):
            products_before = len(self._product_values)
            self.apply_treatments(schedule, year, model, ledger)
            records.extend(self.account_values(year))
            produced: dict[str, float] = {}
            for record in self._product_values[products_before:]:
                account = str(record["account"])
                produced[account] = produced.get(account, 0.0) + float(str(record["value"]))
            records.extend(
                {"year": year, "account": account, "value": value}
                for account, value in produced.items()
            )
            if edge_elements:
                criteria = {label: self.block_criteria(label) for label in criteria_labels}
                for row in edge_values(edge_elements, list(edges), criteria):
                    record = {"year": year, "account": row["account"], "value": row["value"]}
                    records.append(record)
                    self._edge_values.append(dict(record))
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
        edge_elements: Sequence[EdgeElement] = (),
        core_buffer_m: float | None = None,
        min_core_area_ha: float | None = None,
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
        edge_elements : sequence of EdgeElement, optional
            Edge contrast elements. When given with a topology, an edge contrast account
            value per element per year is added to the account values and written to
            ``edge_metrics.csv``.
        core_buffer_m : float or None, optional
            The core-area buffer width, in metres. When given with ``min_core_area_ha``,
            ``spatial_violations.csv`` reports patches whose core area is below it.
        min_core_area_ha : float or None, optional
            The minimum core area, in hectares.

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
        graph = load_patch_edges(topology_csv) if topology_csv is not None else []

        values = self.simulate(
            schedule,
            years,
            route_model=model,
            ledger=ledger,
            edge_elements=edge_elements,
            edges=graph,
        )
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
        if edge_elements:
            pd.DataFrame(self._edge_values, columns=["year", "account", "value"]).to_csv(
                out_dir / "edge_metrics.csv", index=False
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
                core_buffer_m=core_buffer_m,
                min_core_area_ha=min_core_area_ha,
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
        core_buffer_m: float | None = None,
        min_core_area_ha: float | None = None,
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
        if (
            max_opening_ha is not None
            or min_green_up_years is not None
            or min_core_area_ha is not None
        ):
            selected_by_year, harvest_year = schedule_years(schedule_pairs)
            violations: list[dict[str, object]] = []
            if max_opening_ha is not None:
                violations.extend(
                    opening_violations(selected_by_year, edges, block_area, max_opening_ha)
                )
            if min_green_up_years is not None:
                violations.extend(green_up_violations(harvest_year, edges, min_green_up_years))
            if min_core_area_ha is not None and core_buffer_m is not None:
                violations.extend(
                    core_area_violations(
                        selected_by_year, graph, block_area, core_buffer_m, min_core_area_ha
                    )
                )
            pd.DataFrame(
                violations,
                columns=["kind", "year", "area_ha", "limit", "block_a", "block_b", "years"],
            ).to_csv(out_dir / "spatial_violations.csv", index=False)
