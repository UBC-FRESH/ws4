"""Compact persisted Model II candidate/transition index.

The index stores block and treatment-event data as flat arrays.  It does not persist
per-block splice combinations; a block's options are reconstructed on load from the
transition index.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .operators import Candidates, Chain

_INDEX_VERSION = 1


@dataclass
class CandidateIndex:
    """Flat candidate-chain index keyed by block and option position."""

    blocks: np.ndarray
    chain_offsets: np.ndarray
    event_offsets: np.ndarray
    event_years: np.ndarray
    event_labels: np.ndarray
    labels: tuple[str, ...]

    @classmethod
    def build(cls, candidates: Candidates) -> CandidateIndex:
        """Build a compact index from a candidate mapping."""
        labels: dict[str, int] = {}
        blocks: list[int] = []
        chain_offsets: list[int] = [0]
        event_offsets: list[int] = [0]
        event_years: list[int] = []
        event_labels: list[int] = []
        for block in sorted(candidates):
            blocks.append(int(block))
            for chain in candidates[block]:
                for treatment, year in chain:
                    label_id = labels.setdefault(str(treatment), len(labels))
                    event_years.append(int(year))
                    event_labels.append(label_id)
                event_offsets.append(len(event_years))
            chain_offsets.append(len(event_offsets) - 1)
        inverse = {value: key for key, value in labels.items()}
        return cls(
            blocks=np.asarray(blocks, dtype=np.int64),
            chain_offsets=np.asarray(chain_offsets, dtype=np.int64),
            event_offsets=np.asarray(event_offsets, dtype=np.int64),
            event_years=np.asarray(event_years, dtype=np.int64),
            event_labels=np.asarray(event_labels, dtype=np.int64),
            labels=tuple(inverse[index] for index in range(len(inverse))),
        )

    def save(self, path: str | Path) -> Path:
        """Write the index to one compressed NumPy archive."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            destination,
            version=np.asarray([_INDEX_VERSION], dtype=np.int64),
            blocks=self.blocks,
            chain_offsets=self.chain_offsets,
            event_offsets=self.event_offsets,
            event_years=self.event_years,
            event_labels=self.event_labels,
            labels=np.asarray(self.labels),
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> CandidateIndex:
        """Load an index written by :meth:`save`."""
        with np.load(Path(path), allow_pickle=False) as payload:
            version = int(payload["version"][0])
            if version != _INDEX_VERSION:
                raise ValueError(f"unsupported candidate index version: {version}")
            return cls(
                blocks=payload["blocks"],
                chain_offsets=payload["chain_offsets"],
                event_offsets=payload["event_offsets"],
                event_years=payload["event_years"],
                event_labels=payload["event_labels"],
                labels=tuple(str(label) for label in payload["labels"].tolist()),
            )

    def chain(self, block: int, option: int) -> Chain:
        """Return one candidate chain by block and option index."""
        import bisect

        position = bisect.bisect_left(self.blocks.tolist(), int(block))
        if position >= len(self.blocks) or int(self.blocks[position]) != int(block):
            raise KeyError(block)
        chain_position = int(self.chain_offsets[position]) + int(option)
        if chain_position >= int(self.chain_offsets[position + 1]):
            raise IndexError(option)
        start = int(self.event_offsets[chain_position])
        stop = int(self.event_offsets[chain_position + 1])
        return tuple(
            (self.labels[int(self.event_labels[index])], int(self.event_years[index]))
            for index in range(start, stop)
        )

    def option_count(self, block: int) -> int:
        """Return the number of options for one block."""
        import bisect

        position = bisect.bisect_left(self.blocks.tolist(), int(block))
        if position >= len(self.blocks) or int(self.blocks[position]) != int(block):
            return 0
        return int(self.chain_offsets[position + 1] - self.chain_offsets[position])

    def to_candidates(self) -> Candidates:
        """Reconstruct the candidate lists from the flat arrays."""
        candidates: Candidates = {}
        years = self.event_years.tolist()
        labels = self.event_labels.tolist()
        event_offsets = self.event_offsets.tolist()
        chain_offsets = self.chain_offsets.tolist()
        for position, block in enumerate(self.blocks.tolist()):
            chains: list[Chain] = []
            for chain_position in range(chain_offsets[position], chain_offsets[position + 1]):
                start = event_offsets[chain_position]
                stop = event_offsets[chain_position + 1]
                chains.append(
                    tuple(
                        (self.labels[labels[index]], int(years[index]))
                        for index in range(start, stop)
                    )
                )
            candidates[int(block)] = chains
        return candidates
