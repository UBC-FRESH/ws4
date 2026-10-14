"""Annual-step simulator over fragments, aggregated to blocks at runtime."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class Simulator:
    """Annual-step simulator over fragments; aggregates to blocks at runtime.

    Order per year:
      1) Growth (curves → feature/product states per fragment by offset age)
      2) Succession (breakup/renew rules; switch tracks; reset offset when needed)
      3) Treatments (apply scheduled ops; net operability at block = ∩ over fragments)
      4) Products & routes (compute yields and route to destinations)
      5) Patch metrics (computed over *blocks* using aggregated states)
      6) Accounts (summary/ratio/patch/route)
    """

    def __init__(self, dataset_dir: Path) -> None:
        """Load a compiled dataset and initialize each fragment's offset age."""
        self.dataset_dir = Path(dataset_dir)
        self.fragments = pd.read_parquet(self.dataset_dir / "fragments.parquet")
        self.tracks = pd.read_parquet(self.dataset_dir / "tracks.parquet")
        self.treatments = pd.read_parquet(self.dataset_dir / "treatments.parquet")
        # Curves/products/destinations available if needed
        self.curves = pd.read_parquet(self.dataset_dir / "curves.parquet")
        self.products = pd.read_parquet(self.dataset_dir / "products.parquet")
        self.destinations = pd.read_parquet(self.dataset_dir / "destinations.parquet")
        # Offset age starts as current age
        self.fragments["offset"] = self.fragments["age"].astype(int)

    @classmethod
    def from_dataset(cls, dataset_dir: Path) -> Simulator:
        """Build a simulator that reads the given compiled dataset."""
        return cls(dataset_dir)

    def run(self, schedule_csv: Path, years: int, out_dir: Path) -> None:
        """Replay a schedule for the given horizon and write the run directory."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        schedule = pd.read_csv(schedule_csv)  # block_id,treatment,period
        # Pre-index schedule by period for fast lookup
        sch_index = {int(p): df.drop(columns=["period"]) for p, df in schedule.groupby("period")}

        # Simple annual loop (placeholder logic)
        for t in range(years):
            # Apply scheduled block-level treatments at year t by mapping to fragments
            if t in sch_index:
                to_apply = sch_index[t]
                # For each block, compute net operability = intersection across fragments
                by_block = to_apply.groupby("block_id")
                for block_id, _rows in by_block:
                    # Find fragments in this block
                    mask = self.fragments["block_id"] == block_id
                    frag_ids = self.fragments.index[mask]
                    if len(frag_ids) == 0:
                        continue
                    # Simplified operability gate: if any fragment is inoperable,
                    # skip the block. The real gate evaluates fragment-level
                    # expressions against attributes and offsets.

                    can_apply = True
                    if not can_apply:
                        continue
                    # Apply: reset offset, maybe switch track (new_track_id if defined)
                    self.fragments.loc[mask, "offset"] = 0

            # Growth (placeholder): +1 offset per year
            self.fragments["offset"] = self.fragments["offset"].astype(int) + 1

        # Write a tiny report stub
        blocks = (
            self.fragments.groupby("block_id")
            .agg(area_ha=("area_ha", "sum"), mean_offset=("offset", "mean"))
            .reset_index()
        )
        blocks.to_parquet(out_dir / "blocks_summary.parquet", index=False)
