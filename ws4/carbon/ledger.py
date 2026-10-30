"""An area-weighted carbon ledger for the optimizer.

CBM is aspatial and linear in area. This ledger prices a **stand state** once,
keyed by ``(track_id, age, chain)``, and turns a block into the area-weighted sum of
its fragments' stand states. A chain is the sequence of ``(treatment, offset)`` events
the optimizer represents for a block.

This is the important decomposition: blocks are spatial containers, but they are not
carbon states. Running libcbm once per block would repeat the same stand calculation for
every block that shares a track and age, then add the pieces back together. The ledger
does the opposite: one stand-state calculation, shared by every block that contains it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
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
    """Area-weighted carbon ledger with a batch path and a stand-state cache.

    The initial schedule and final replay are evaluated in one libcbm model. Search
    moves use the stand-state cache so a move prices only the blocks it touches.

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
    base_workers : int, optional
        Fork-based worker processes for the empty-schedule base. Defaults to one
        (serial). Use more than one only in a serial optimizer process; the
        optimizer disables it when islands or process-parallel starts are active.
    """

    def __init__(
        self,
        dataset_dir: Path,
        package: CarbonPackage,
        years: int,
        *,
        fertilization: FertilizationConfig | None = None,
        hwp: HwpConfig | None = None,
        base_workers: int = 1,
    ) -> None:
        """Load the dataset tables and initialize the cache."""
        if years <= 0:
            raise ValueError("carbon ledger years must be positive")
        if base_workers <= 0:
            raise ValueError("carbon ledger base_workers must be positive")
        self.base_workers = int(base_workers)
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
        self._unit_cache: dict[tuple[int, int, Chain], dict[Cell, float]] = {}
        self._track_context_cache: dict[int, tuple[CarbonPackage, pd.DataFrame, pd.DataFrame]] = {}

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
        return self.schedule_values({}, accounts)

    def _batch_values(
        self,
        schedule: Mapping[int, Sequence[tuple[str, int]]],
        accounts: set[str] | None = None,
    ) -> dict[Cell, float]:
        """Run one libcbm model for every block and return the summed accounts.

        This is the exact whole-schedule path. It avoids one model initialisation per
        stand state: the inventory is all fragments, and only scheduled blocks carry
        events. The result is the same area-weighted total the per-state ledger builds,
        but the fixed model cost is paid once instead of once per state.
        """
        rows: list[dict[str, object]] = []
        for block, chain in schedule.items():
            if int(block) not in self._block_fragments:
                raise ValueError(f"carbon ledger has no block {block}")
            for treatment, offset in chain:
                rows.append(
                    {
                        "block_id": int(block),
                        "treatment": str(treatment),
                        "offset": int(offset),
                    }
                )
        schedule_frame = pd.DataFrame(rows, columns=["block_id", "treatment", "offset"])
        if self.fertilization is not None and self.fertilization.uses_curves:
            schedule_frame = with_fertilization_recovery(
                schedule_frame,
                self.fragments,
                self._tracks,
                self.fertilization,
            )
        tables = build_sit_tables_from_tables(
            self.package,
            self.fragments,
            self._tracks,
            self._treatments,
            schedule_frame,
        )
        run = run_libcbm(
            self.package,
            tables,
            n_steps=self.years,
            fertilization=(
                self.fertilization
                if self.fertilization is not None and not self.fertilization.uses_curves
                else None
            ),
        )
        values = carbon_accounts(run, hwp=self.hwp)
        if self.fertilization is not None:
            emissions = fertilization_accounts(
                schedule_frame,
                self.fragments.loc[:, ["block_id", "area_ha"]],
                self.fertilization,
            )
            if not emissions.empty:
                values = pd.concat([values, emissions], ignore_index=True)
        totals: dict[Cell, float] = {}
        for row in values.itertuples(index=False):
            cell = (int(str(row.offset)), str(row.account))
            if accounts is None or cell[1] in accounts:
                totals[cell] = totals.get(cell, 0.0) + float(str(row.value))
        return totals

    def prepare(
        self,
        chains_by_block: Mapping[int, Sequence[Chain]],
        *,
        candidate_limit: int | None = None,
    ) -> None:
        """Price every stand state a seed will score, once.

        Parameters
        ----------
        chains_by_block : mapping of int to sequence of Chain
            Candidate chains per block.
        candidate_limit : int or None, optional
            The same per-block cap the seed will use. None scores every chain.
        """
        if candidate_limit is not None and candidate_limit < 1:
            raise ValueError("carbon seed candidate_limit must be positive")
        keys: set[tuple[int, int, Chain]] = set()
        for block, options in chains_by_block.items():
            fragments = self._block_fragments.get(int(block))
            if fragments is None:
                continue
            limited = options[:candidate_limit] if candidate_limit is not None else options
            for row in fragments.itertuples(index=False):
                track = int(str(row.track_id))
                age = int(str(row.age))
                keys.add((track, age, ()))
                for chain in limited:
                    keys.add((track, age, tuple(chain)))
        self._prepare_units(keys)

    def _prepare_units(self, keys: set[tuple[int, int, Chain]]) -> None:
        """Price missing stand-state keys once, optionally in fork workers."""
        missing = [key for key in sorted(keys) if key not in self._unit_cache]
        if not missing:
            return
        if self.base_workers <= 1 or len(missing) <= 1:
            for track, age, chain in missing:
                self._unit_accounts(track, age, chain)
            return
        try:
            context = get_context("fork")
        except ValueError:
            for track, age, chain in missing:
                self._unit_accounts(track, age, chain)
            return
        global _BASE_WORKER_LEDGER
        _BASE_WORKER_LEDGER = self
        try:
            workers = min(self.base_workers, len(missing))
            chunksize = max(1, len(missing) // (workers * 4))
            with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
                results = list(pool.map(_unit_worker, missing, chunksize=chunksize))
            for key, values in zip(missing, results, strict=True):
                self._unit_cache[key] = values
        finally:
            _BASE_WORKER_LEDGER = None

    def schedule_values(
        self,
        schedule: Mapping[int, Sequence[tuple[str, int]]],
        accounts: set[str] | None = None,
    ) -> dict[Cell, float]:
        """Return the carbon totals for a schedule in one whole-schedule run.

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
        return self._batch_values(schedule, accounts)

    def _track_context(self, track_id: int) -> tuple[CarbonPackage, pd.DataFrame, pd.DataFrame]:
        """Return the package, tracks, and treatments reachable from one track."""
        cached = self._track_context_cache.get(int(track_id))
        if cached is not None:
            return cached
        known_ids = set(
            pd.to_numeric(self._tracks["track_id"], errors="coerce").dropna().astype(int)
        )
        treatment_source = pd.to_numeric(self._treatments["track_id"], errors="coerce")
        treatment_target = (
            pd.to_numeric(self._treatments["new_track"], errors="coerce")
            if "new_track" in self._treatments.columns
            else pd.Series(index=self._treatments.index, dtype="float64")
        )
        selected = {int(track_id)} & known_ids
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
        self._track_context_cache[int(track_id)] = result
        return result

    def _unit_accounts(self, track_id: int, age: int, chain: Chain) -> dict[Cell, float]:
        """Return one hectare of one stand state and treatment chain."""
        key = (int(track_id), int(age), tuple(chain))
        cached = self._unit_cache.get(key)
        if cached is not None:
            return cached
        fragments = pd.DataFrame(
            {
                "fragment_id": [1],
                "block_id": [1],
                "track_id": [int(track_id)],
                "area_ha": [1.0],
                "age": [int(age)],
            }
        )
        schedule = pd.DataFrame(
            {
                "block_id": [1] * len(chain),
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
        package, tracks, treatments = self._track_context(track_id)
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
        self._unit_cache[key] = result
        return result

    def _run(self, block: int, chain: Chain) -> dict[Cell, float]:
        """Return one block's carbon accounts as an area-weighted stand-state sum."""
        key = (int(block), tuple(chain))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        fragments = self._block_fragments.get(int(block))
        if fragments is None:
            raise ValueError(f"carbon ledger has no block {block}")
        result: dict[Cell, float] = {}
        for row in fragments.itertuples(index=False):
            track = int(str(row.track_id))
            age = int(str(row.age))
            area = float(str(row.area_ha))
            for cell, value in self._unit_accounts(track, age, tuple(chain)).items():
                result[cell] = result.get(cell, 0.0) + area * value
        self._cache[key] = result
        return result


_BASE_WORKER_LEDGER: CarbonLedger | None = None


def _unit_worker(key: tuple[int, int, Chain]) -> dict[Cell, float]:
    """Return one stand state's per-hectare accounts in a fork worker."""
    if _BASE_WORKER_LEDGER is None:
        raise RuntimeError("carbon base worker has no ledger")
    track, age, chain = key
    return _BASE_WORKER_LEDGER._unit_accounts(track, age, chain)
