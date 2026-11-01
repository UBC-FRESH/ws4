"""Persist the bounded candidate-chain map used by the population search.

Candidate generation walks the treatment graph for every block.  On the full TSA23 model
it takes about 33 s on top of the simulator load; the resulting map is independent of the
objective targets and of the search seed, so it can be reused across population runs.

The cache is deliberately explicit.  It records the dataset fingerprint, the candidate
horizon and the candidate-limit constants.  A changed dataset or horizon invalidates the
cache rather than silently mixing candidate maps from different models.

The pickled cache is a local trusted artifact; do not load a cache from an untrusted
source.
"""

from __future__ import annotations

import hashlib
import pickle
from array import array
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .engine import (
    _CHAIN_STEP,
    _FRONTIER_CAP,
    _MAX_CHAINS,
    _MAX_ROTATIONS,
    _ROTATION_SEEDS,
)

if TYPE_CHECKING:
    from ..sim.engine import Simulator
    from .engine import Optimizer
    from .operators import Candidates

CANDIDATE_CACHE_VERSION = 1
SIMULATOR_CACHE_VERSION = 1


class CandidateCacheError(RuntimeError):
    """Raised when a candidate cache is absent, corrupt, or does not match the model."""


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_fingerprint(dataset_dir: Path) -> str:
    """Return a content-based fingerprint of a compiled dataset.

    Parameters
    ----------
    dataset_dir : pathlib.Path
        The compiled dataset directory.

    Returns
    -------
    str
        The SHA-256 digest over the manifest and every table named by it.

    Raises
    ------
    CandidateCacheError
        When the manifest or a named table is missing.
    """
    manifest = dataset_dir / "manifest.json"
    if not manifest.is_file():
        raise CandidateCacheError(f"compiled dataset has no manifest: {manifest}")
    digest = hashlib.sha256(manifest.read_bytes())
    import json

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    tables = payload.get("tables", {})
    if not isinstance(tables, dict):
        raise CandidateCacheError(f"manifest tables are not a mapping: {manifest}")
    for name in sorted(tables):
        table = dataset_dir / str(tables[name])
        if not table.is_file():
            raise CandidateCacheError(f"compiled dataset is missing table {table}")
        digest.update(str(name).encode("utf-8"))
        digest.update(_sha256_file(table).encode("ascii"))
    return digest.hexdigest()


def cache_metadata(optimizer: Optimizer) -> dict[str, Any]:
    """Return the identity a candidate cache must match.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer that would generate the candidates.

    Returns
    -------
    dict
        The version, dataset fingerprint, horizon, and candidate-limit constants.
    """
    return {
        "version": CANDIDATE_CACHE_VERSION,
        "dataset": str(optimizer.dataset_dir.resolve()),
        "dataset_fingerprint": dataset_fingerprint(optimizer.dataset_dir),
        "years": int(optimizer.cfg.years),
        "max_rotations": _MAX_ROTATIONS,
        "max_chains": _MAX_CHAINS,
        "chain_step": _CHAIN_STEP,
        "frontier_cap": _FRONTIER_CAP,
        "rotation_seeds": _ROTATION_SEEDS,
    }


def simulator_metadata(optimizer: Optimizer) -> dict[str, Any]:
    """Return the identity a simulator cache must match.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer whose simulator is cached.

    Returns
    -------
    dict
        The version, dataset path, and dataset fingerprint.
    """
    return {
        "version": SIMULATOR_CACHE_VERSION,
        "dataset": str(optimizer.dataset_dir.resolve()),
        "dataset_fingerprint": dataset_fingerprint(optimizer.dataset_dir),
    }


def save_simulator_cache(path: str | Path, simulator: Simulator, metadata: dict[str, Any]) -> Path:
    """Write a loaded simulator and its identity to a pickle cache.

    Parameters
    ----------
    path : str or pathlib.Path
        Destination file.
    simulator : Simulator
        The already-loaded simulator.
    metadata : dict
        The result of :func:`simulator_metadata`.

    Returns
    -------
    pathlib.Path
        The written archive.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("wb") as handle:
        pickle.dump(
            {
                "metadata": metadata,
                "simulator": simulator,
            },
            handle,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    temporary.replace(destination)
    return destination


def load_simulator_cache(path: str | Path, expected_metadata: dict[str, Any]) -> Simulator:
    """Load and validate a simulator cache.

    Parameters
    ----------
    path : str or pathlib.Path
        Cache written by :func:`save_simulator_cache`.
    expected_metadata : dict
        The identity returned by :func:`simulator_metadata`.

    Returns
    -------
    Simulator
        The loaded simulator.

    Raises
    ------
    CandidateCacheError
        When the file is missing, corrupt, or belongs to another dataset.
    """
    source = Path(path)
    if not source.is_file():
        raise CandidateCacheError(f"simulator cache does not exist: {source}")
    try:
        with source.open("rb") as handle:
            payload = pickle.load(handle)
    except (OSError, pickle.UnpicklingError, EOFError) as exc:
        raise CandidateCacheError(f"cannot read simulator cache {source}: {exc}") from exc
    if not isinstance(payload, dict) or "metadata" not in payload or "simulator" not in payload:
        raise CandidateCacheError(f"simulator cache has an unexpected shape: {source}")
    if payload["metadata"] != expected_metadata:
        raise CandidateCacheError(
            f"simulator cache does not match the current dataset; rebuild it explicitly: {source}"
        )
    simulator = payload["simulator"]
    from ..sim.engine import Simulator

    if not isinstance(simulator, Simulator):
        raise CandidateCacheError(f"simulator cache does not contain a simulator: {source}")
    return simulator


def load_or_build_simulator(
    optimizer: Optimizer,
    path: str | Path,
    *,
    rebuild: bool = False,
) -> Simulator:
    """Load the simulator cache into the optimizer, or build and persist it.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer that will own the simulator.
    path : str or pathlib.Path
        Cache file.
    rebuild : bool, optional
        Rebuild the simulator and replace the cache even when it matches.  Defaults to
        False.

    Returns
    -------
    Simulator
        The simulator now attached to the optimizer.
    """
    metadata = simulator_metadata(optimizer)
    if not rebuild and Path(path).is_file():
        simulator = load_simulator_cache(path, metadata)
        optimizer._simulator_cache = simulator
        optimizer._simulator_base_cache = None
        optimizer._base_cache = None
        return simulator
    simulator = optimizer.simulator()
    save_simulator_cache(path, simulator, metadata)
    return simulator


def save_candidates_cache(
    path: str | Path, candidates: Candidates, metadata: dict[str, Any]
) -> Path:
    """Write a candidate map and its identity to a pickle cache.

    Parameters
    ----------
    path : str or pathlib.Path
        Destination file.
    candidates : mapping of int to sequence of tuple
        The candidate chains per block.
    metadata : dict
        The result of :func:`cache_metadata`.

    Returns
    -------
    pathlib.Path
        The written archive.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("wb") as handle:
        pickle.dump(
            {
                "metadata": metadata,
                "candidates": candidates,
            },
            handle,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    temporary.replace(destination)
    return destination


def load_candidates_cache(path: str | Path, expected_metadata: dict[str, Any]) -> Candidates:
    """Load and validate a candidate cache.

    Parameters
    ----------
    path : str or pathlib.Path
        Cache written by :func:`save_candidates_cache`.
    expected_metadata : dict
        The identity returned by :func:`cache_metadata` for the current model.

    Returns
    -------
    dict of int to list of tuple
        The candidate chains per block.

    Raises
    ------
    CandidateCacheError
        When the file is missing, corrupt, or belongs to another dataset or horizon.
    """
    source = Path(path)
    if not source.is_file():
        raise CandidateCacheError(f"candidate cache does not exist: {source}")
    try:
        with source.open("rb") as handle:
            payload = pickle.load(handle)
    except (OSError, pickle.UnpicklingError, EOFError) as exc:
        raise CandidateCacheError(f"cannot read candidate cache {source}: {exc}") from exc
    if not isinstance(payload, dict) or "metadata" not in payload or "candidates" not in payload:
        raise CandidateCacheError(f"candidate cache has an unexpected shape: {source}")
    if payload["metadata"] != expected_metadata:
        raise CandidateCacheError(
            "candidate cache does not match the current dataset or candidate horizon; "
            f"rebuild it explicitly: {source}"
        )
    candidates = payload["candidates"]
    if not isinstance(candidates, dict):
        raise CandidateCacheError(f"candidate cache does not contain a mapping: {source}")
    return candidates


class CompactCandidates:
    """A flat-array candidate map loaded without unpickling millions of Python tuples.

    The mapping is read-only and keeps the candidate/event arrays out of Python objects.
    It supports the small candidate protocol the GPU population needs: option counts,
    one chain by position, all chains for one block, and a chain-position lookup.

    Parameters
    ----------
    blocks : numpy.ndarray
        Sorted block ids.
    chain_offsets : numpy.ndarray
        Offset of each block's first chain, plus a sentinel.
    event_offsets : numpy.ndarray
        Offset of each chain's first event, plus a sentinel.
    event_years : numpy.ndarray
        Treatment year for each event.
    event_labels : numpy.ndarray
        Integer treatment-label id for each event.
    labels : tuple of str
        Treatment-label dictionary.
    """

    def __init__(
        self,
        blocks: Any,  # noqa: ANN401
        chain_offsets: Any,  # noqa: ANN401
        event_offsets: Any,  # noqa: ANN401
        event_years: Any,  # noqa: ANN401
        event_labels: Any,  # noqa: ANN401
        labels: tuple[str, ...],
    ) -> None:
        self.blocks = blocks
        self.chain_offsets = chain_offsets
        self.event_offsets = event_offsets
        self.event_years = event_years
        self.event_labels = event_labels
        self.labels = labels
        self._positions: dict[int, int] | None = None

    @classmethod
    def from_candidates(cls, candidates: Candidates) -> CompactCandidates:
        """Build the flat representation from a candidate mapping.

        Parameters
        ----------
        candidates : mapping of int to sequence of tuple
            Candidate chains per block.

        Returns
        -------
        CompactCandidates
            The flat representation.
        """
        blocks: list[int] = []
        chain_offsets = array("q", [0])
        event_offsets = array("q", [0])
        event_years = array("i")
        event_labels = array("i")
        label_ids: dict[str, int] = {}
        for block in sorted(int(value) for value in candidates):
            blocks.append(block)
            for chain in candidates[block]:
                for treatment, year in chain:
                    label = str(treatment)
                    label_id = label_ids.setdefault(label, len(label_ids))
                    event_years.append(int(year))
                    event_labels.append(label_id)
                event_offsets.append(len(event_years))
            chain_offsets.append(len(event_offsets) - 1)
        inverse = {value: key for key, value in label_ids.items()}
        return cls(
            blocks=__import__("numpy").asarray(blocks, dtype=__import__("numpy").int64),
            chain_offsets=__import__("numpy").asarray(
                chain_offsets, dtype=__import__("numpy").int64
            ),
            event_offsets=__import__("numpy").asarray(
                event_offsets, dtype=__import__("numpy").int64
            ),
            event_years=__import__("numpy").asarray(event_years, dtype=__import__("numpy").int64),
            event_labels=__import__("numpy").asarray(event_labels, dtype=__import__("numpy").int64),
            labels=tuple(inverse[index] for index in range(len(inverse))),
        )

    def save(self, path: str | Path) -> Path:
        """Write the compact mapping to one uncompressed NumPy archive.

        Parameters
        ----------
        path : str or pathlib.Path
            Destination archive.

        Returns
        -------
        pathlib.Path
            The written path.
        """
        import numpy as np

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            destination,
            blocks=self.blocks,
            chain_offsets=self.chain_offsets,
            event_offsets=self.event_offsets,
            event_years=self.event_years,
            event_labels=self.event_labels,
            labels=np.asarray(self.labels),
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> CompactCandidates:
        """Load a compact mapping with memory-mapped candidate/event arrays.

        Parameters
        ----------
        path : str or pathlib.Path
            Archive written by :meth:`save`.

        Returns
        -------
        CompactCandidates
            The loaded mapping.
        """
        import numpy as np

        with np.load(Path(path), mmap_mode="r", allow_pickle=False) as payload:
            return cls(
                blocks=payload["blocks"],
                chain_offsets=payload["chain_offsets"],
                event_offsets=payload["event_offsets"],
                event_years=payload["event_years"],
                event_labels=payload["event_labels"],
                labels=tuple(str(value) for value in payload["labels"].tolist()),
            )

    def _position(self, block: int) -> int | None:
        if self._positions is None:
            self._positions = {
                int(value): index for index, value in enumerate(self.blocks.tolist())
            }
        return self._positions.get(int(block))

    def option_count(self, block: int) -> int:
        """Return the number of candidate chains for one block.

        Parameters
        ----------
        block : int
            Block id.

        Returns
        -------
        int
            The option count, or zero when the block is absent.
        """
        position = self._position(block)
        if position is None:
            return 0
        return int(self.chain_offsets[position + 1] - self.chain_offsets[position])

    def chain_at(self, block: int, option: int) -> tuple[tuple[str, int], ...]:
        """Return one candidate chain by block and option position.

        Parameters
        ----------
        block : int
            Block id.
        option : int
            Candidate option position.

        Returns
        -------
        tuple of (str, int)
            The candidate chain.
        """
        position = self._position(block)
        if position is None:
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

    def chains(self, block: int) -> tuple[tuple[tuple[str, int], ...], ...]:
        """Return every chain for one block as Python tuples.

        Parameters
        ----------
        block : int
            Block id.

        Returns
        -------
        tuple of tuple of (str, int)
            The block's candidate chains.
        """
        return tuple(self.chain_at(block, option) for option in range(self.option_count(block)))

    def index_of(self, block: int, chain: tuple[tuple[str, int], ...]) -> int | None:
        """Return the option position for a chain, or None.

        Parameters
        ----------
        block : int
            Block id.
        chain : tuple of (str, int)
            Candidate chain to find.

        Returns
        -------
        int or None
            The option position, or None when the chain is absent.
        """
        for option in range(self.option_count(block)):
            if self.chain_at(block, option) == chain:
                return option
        return None

    def get(self, block: int, default: Any = None) -> Any:  # noqa: ANN401
        """Return one block's chains, matching the mapping interface.

        Parameters
        ----------
        block : int
            Block id.
        default : object, optional
            Value returned when the block is absent.

        Returns
        -------
        object
            The block's chains or ``default``.
        """
        if self._position(block) is None:
            return default
        return self.chains(block)

    def __getitem__(self, block: int) -> tuple[tuple[tuple[str, int], ...], ...]:
        """Return one block's candidate chains."""
        if self._position(block) is None:
            raise KeyError(block)
        return self.chains(block)

    def __contains__(self, block: object) -> bool:
        """Return whether one block is present."""
        try:
            value = int(block)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return False
        return self._position(value) is not None

    def __iter__(self) -> Iterator[int]:
        """Iterate over block ids."""
        return iter(self.blocks.tolist())

    def __len__(self) -> int:
        """Return the number of blocks."""
        return len(self.blocks)


def load_or_build_candidates(
    optimizer: Optimizer,
    path: str | Path,
    *,
    rebuild: bool = False,
) -> Candidates:
    """Load the candidate map, or build and persist it when needed.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer whose candidates are needed.
    path : str or pathlib.Path
        Cache file.
    rebuild : bool, optional
        Regenerate the map and replace the cache even when it matches.  Defaults to False.

    Returns
    -------
    dict of int to list of tuple
        The candidate chains per block.
    """
    metadata = cache_metadata(optimizer)
    if not rebuild and Path(path).is_file():
        return load_candidates_cache(path, metadata)
    candidates = optimizer.candidates()
    save_candidates_cache(path, candidates, metadata)
    return candidates
