"""A block-level carbon ledger for the optimizer.

CBM is stand-level and area-additive. This ledger runs one block's treatment chain at a
time, caches the carbon accounts, and sums the blocks for a schedule. The optimizer can
then price a carbon target with exact CBM output and per-move deltas, rather than a
whole-schedule engine run on every candidate.

The cache is keyed by ``(block, chain)``. A chain is the block's sequence of
``(treatment, offset)`` events, as the optimizer's schedule represents it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

from .fertilization import (
    FertilizationConfig,
    fertilization_accounts,
    with_fertilization_curves,
    with_fertilization_disturbances,
    with_fertilization_recovery,
)
from .hwp import HwpConfig
from .libcbm import carbon_accounts, run_libcbm
from .package import CarbonPackage, filter_carbon_package
from .sit import build_sit_tables_from_tables

Cell = tuple[int, str]
Chain = tuple[tuple[str, int], ...]


class CarbonLedger:
    """Per-block CBM runs and their cached carbon accounts.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset directory.
    package : CarbonPackage
        The loaded FEMIC carbon package.
    years : int
        The annual horizon. A chain event at offset ``years - 1`` is the last one
        the ledger can price.
    fertilization : FertilizationConfig or None, optional
        When set, fertilizer events use the materialized curve transitions or the
        temporary growth multiplier, and the ledger includes the audited emissions
        accounts. Defaults to None.
    hwp : HwpConfig or None, optional
        When set, add the HWP lifecycle and whole-system carbon accounts. Defaults
        to None.
    """

    def __init__(
        self,
        dataset_dir: Path,
        package: CarbonPackage,
        years: int,
        *,
        fertilization: FertilizationConfig | None = None,
        hwp: HwpConfig | None = None,
    ) -> None:
        """Load the dataset tables and initialize the cache."""
        if years <= 0:
            raise ValueError("carbon ledger years must be positive")
        root = Path(dataset_dir)
        self.dataset_dir = root
        self.fertilization = fertilization
        self.hwp = hwp
        self.years = int(years)
        self.fragments = pd.read_parquet(root / "fragments.parquet")
        self.tracks = pd.read_parquet(root / "tracks.parquet")
        self.treatments = pd.read_parquet(root / "treatments.parquet")
        if fertilization is not None and fertilization.uses_curves:
            package, self.tracks, self.treatments = with_fertilization_curves(
                package,
                self.tracks,
                self.treatments,
                fertilization,
            )
        elif fertilization is not None:
            package = with_fertilization_disturbances(package, fertilization)
        self._cache: dict[tuple[int, Chain], dict[Cell, float]] = {}
        self._block_fragments = {
            int(str(block)): frame
            for block, frame in self.fragments.groupby("block_id", sort=False)
        }
        fragment_track_ids = set(
            pd.to_numeric(self.fragments["track_id"], errors="coerce").dropna().astype(int)
        )
        known_track_ids = set(
            pd.to_numeric(self.tracks["track_id"], errors="coerce").dropna().astype(int)
        )
        treatment_source = pd.to_numeric(self.treatments["track_id"], errors="coerce")
        treatment_target = (
            pd.to_numeric(self.treatments["new_track"], errors="coerce")
            if "new_track" in self.treatments.columns
            else pd.Series(index=self.treatments.index, dtype="float64")
        )
        selected_ids = fragment_track_ids & known_track_ids
        while True:
            reachable = treatment_source.isin(selected_ids)
            destinations = {
                int(value)
                for value in treatment_target.loc[reachable].dropna().tolist()
                if int(value) > 0
            }
            new_ids = (destinations & known_track_ids) - selected_ids
            if not new_ids:
                break
            selected_ids |= new_ids
        self._tracks = self.tracks.loc[
            pd.to_numeric(self.tracks["track_id"], errors="coerce").isin(selected_ids)
        ].copy()
        self._treatments = self.treatments.loc[treatment_source.isin(selected_ids)].copy()
        self.package = filter_carbon_package(
            package,
            set(self._tracks["name"].astype(str)),
        )
        self._context_cache: dict[int, tuple[CarbonPackage, pd.DataFrame, pd.DataFrame]] = {}

    @property
    def block_ids(self) -> tuple[int, ...]:
        """Return the ledger's block ids.

        Returns
        -------
        tuple of int
            The block ids, sorted.
        """
        return tuple(sorted(self._block_fragments))

    def empty(self, block: int) -> dict[Cell, float]:
        """Return one block's carbon accounts with no treatment.

        Parameters
        ----------
        block : int
            The block.

        Returns
        -------
        dict of (int, str) to float
            Carbon accounts by ``(offset, account)``.
        """
        return self._run(block, ())

    def contribution(self, block: int, chain: Chain) -> dict[Cell, float]:
        """Return a chain's carbon delta relative to the empty chain.

        Parameters
        ----------
        block : int
            The block.
        chain : tuple of (str, int)
            The treatment chain.

        Returns
        -------
        dict of (int, str) to float
            The non-zero account deltas.
        """
        after = self._run(block, chain)
        before = self.empty(block)
        return {
            cell: value - before.get(cell, 0.0)
            for cell, value in after.items()
            if value - before.get(cell, 0.0) != 0.0
        }

    def block_delta(
        self,
        block: int,
        chain: Chain,
        accounts: set[str] | None = None,
    ) -> dict[Cell, float]:
        """Return a chain's carbon delta, optionally filtered to accounts.

        Parameters
        ----------
        block : int
            The block.
        chain : tuple of (str, int)
            The treatment chain.
        accounts : set of str or None, optional
            Only return cells for these account names.

        Returns
        -------
        dict of (int, str) to float
            The filtered delta.
        """
        delta = self.contribution(block, chain)
        if accounts is None:
            return delta
        return {cell: value for cell, value in delta.items() if cell[1] in accounts}

    def base_values(self, accounts: set[str] | None = None) -> dict[Cell, float]:
        """Return the empty-schedule carbon totals across every block.

        Parameters
        ----------
        accounts : set of str or None, optional
            Only return cells for these account names.

        Returns
        -------
        dict of (int, str) to float
            The summed empty-schedule accounts.
        """
        totals: dict[Cell, float] = {}
        for block in self.block_ids:
            for cell, value in self.empty(block).items():
                if accounts is None or cell[1] in accounts:
                    totals[cell] = totals.get(cell, 0.0) + value
        return totals

    def schedule_values(
        self,
        schedule: Mapping[int, Sequence[tuple[str, int]]],
        accounts: set[str] | None = None,
    ) -> dict[Cell, float]:
        """Return the carbon totals for a schedule.

        Parameters
        ----------
        schedule : mapping of int to sequence of (str, int)
            The treatment chain per block.
        accounts : set of str or None, optional
            Only return cells for these account names.

        Returns
        -------
        dict of (int, str) to float
            The summed carbon accounts.
        """
        totals = self.base_values(accounts)
        for block, chain in schedule.items():
            for cell, value in self.block_delta(int(block), tuple(chain), accounts).items():
                totals[cell] = totals.get(cell, 0.0) + value
        return totals

    def _context(self, block: int) -> tuple[CarbonPackage, pd.DataFrame, pd.DataFrame]:
        """Return the package, tracks, and treatments reachable from one block.

        The package and treatment table are filtered once per block so the SIT
        builder does not rescan every package track for every block and chain.
        """
        cached = self._context_cache.get(int(block))
        if cached is not None:
            return cached
        fragments = self._block_fragments.get(int(block))
        if fragments is None:
            raise ValueError(f"carbon ledger has no block {block}")
        track_ids = set(pd.to_numeric(fragments["track_id"], errors="coerce").dropna().astype(int))
        track_ids &= set(
            pd.to_numeric(self._tracks["track_id"], errors="coerce").dropna().astype(int)
        )
        treatment_source = pd.to_numeric(self._treatments["track_id"], errors="coerce")
        treatment_target = (
            pd.to_numeric(self._treatments["new_track"], errors="coerce")
            if "new_track" in self._treatments.columns
            else pd.Series(index=self._treatments.index, dtype="float64")
        )
        selected = set(track_ids)
        known_ids = set(
            pd.to_numeric(self._tracks["track_id"], errors="coerce").dropna().astype(int)
        )
        while True:
            destinations = {
                int(value)
                for value in treatment_target.loc[treatment_source.isin(selected)].dropna().tolist()
                if int(value) > 0
            }
            new_ids = (destinations & known_ids) - selected
            if not new_ids:
                break
            selected |= new_ids
        tracks = self._tracks.loc[
            pd.to_numeric(self._tracks["track_id"], errors="coerce").isin(selected)
        ].copy()
        treatments = self._treatments.loc[treatment_source.isin(selected)].copy()
        package = filter_carbon_package(self.package, set(tracks["name"].astype(str)))
        result = (package, tracks, treatments)
        self._context_cache[int(block)] = result
        return result

    def _run(self, block: int, chain: Chain) -> dict[Cell, float]:
        """Run and cache one block/chain's carbon accounts."""
        key = (int(block), tuple(chain))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        fragments = self._block_fragments.get(int(block))
        if fragments is None:
            raise ValueError(f"carbon ledger has no block {block}")
        schedule = pd.DataFrame(
            {
                "block_id": [int(block)] * len(chain),
                "treatment": [treatment for treatment, _offset in chain],
                "offset": [offset for _treatment, offset in chain],
            }
        )
        if self.fertilization is not None and self.fertilization.uses_curves:
            schedule = with_fertilization_recovery(
                schedule,
                fragments,
                self._tracks,
                self.fertilization,
            )
        package, tracks, treatments = self._context(block)
        tables = build_sit_tables_from_tables(
            package,
            fragments,
            tracks,
            treatments,
            schedule,
        )
        run = run_libcbm(
            package,
            tables,
            n_steps=self.years,
            fertilization=(
                self.fertilization
                if self.fertilization is not None and not self.fertilization.uses_curves
                else None
            ),
        )
        accounts = carbon_accounts(run, hwp=self.hwp)
        if self.fertilization is not None:
            emissions = fertilization_accounts(
                schedule,
                fragments.loc[:, ["block_id", "area_ha"]],
                self.fertilization,
            )
            if not emissions.empty:
                accounts = pd.concat([accounts, emissions], ignore_index=True)
        result = {
            (int(str(row.offset)), str(row.account)): float(str(row.value))
            for row in accounts.itertuples(index=False)
        }
        self._cache[key] = result
        return result
