"""Run telemetry: a per-step objective record and a run header.

Every solver records its objective trajectory to a JSONL file: one header line per run
and one line per iteration. The store is the substrate the tuning and portfolio layers
consume (see `notes/design/ws4-optimization-stack.md`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO


class RunLogger:
    """Append-only JSONL telemetry for one optimization run.

    The file opens with one run header, then one record per search step. A search is
    reproducible from the header (the seed and the configuration) and the step records.

    Parameters
    ----------
    path : Path
        The JSONL file to write.
    run_id : str
        The run identifier.
    config : mapping
        The run configuration to record in the header.
    auto_flush : bool, optional
        Flush after every record, so a live reader sees each step promptly. A header-only parent
        log can turn it off; a worker's own log leaves it on.
    """

    def __init__(
        self,
        path: Path,
        run_id: str,
        config: Mapping[str, Any],
        *,
        auto_flush: bool = True,
    ) -> None:
        """Open the log and write the run header.

        Parameters
        ----------
        path : Path
            The JSONL file to write.
        run_id : str
            The run identifier.
        config : mapping
            The run configuration to record in the header.
        auto_flush : bool, optional
            Flush after every record, so a live reader sees each step promptly. A header-only
            parent log can turn it off; a worker's own log leaves it on.
        """
        self.auto_flush = auto_flush
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_schedules: dict[str, dict[int, tuple[tuple[str, int], ...]]] = {}
        self._file: TextIO = self.path.open("w", encoding="utf-8")
        self._write({"type": "run", "run_id": run_id, "config": dict(config)})

    def _write(self, record: Mapping[str, Any]) -> None:
        """Write one JSON record, flushing when the logger is configured for a live reader."""
        self._file.write(json.dumps(record) + "\n")
        if self.auto_flush:
            self._file.flush()

    def flush(self) -> None:
        """Flush buffered records to the file for a live reader."""
        self._file.flush()

    def step(self, iteration: int, objective: float, island: str | None = None) -> None:
        """Record one iteration's objective.

        Parameters
        ----------
        iteration : int
            The iteration index.
        objective : float
            The incumbent objective at that iteration.
        island : str or None, optional
            The worker that reported it, when the search runs more than one.
        """
        record: dict[str, Any] = {
            "type": "step",
            "iteration": iteration,
            "objective": objective,
        }
        if island is not None:
            record["island"] = island
        self._write(record)

    def targets(
        self,
        iteration: int,
        values: Mapping[tuple[int, str], float],
        island: str | None = None,
    ) -> None:
        """Record the realized value of every tracked account cell at an iteration.

        Parameters
        ----------
        iteration : int
            The iteration index.
        values : mapping of (int, str) to float
            The realized total per ``(year, account)`` cell, as the move-based evaluator holds it.
        island : str or None, optional
            The worker that reported it, when the search runs more than one.
        """
        record: dict[str, Any] = {
            "type": "targets",
            "iteration": iteration,
            "values": [
                {"year": year, "account": account, "value": value}
                for (year, account), value in sorted(values.items())
            ],
        }
        if island is not None:
            record["island"] = island
        self._write(record)

    def schedule(
        self,
        iteration: int,
        schedule: Mapping[int, Sequence[tuple[str, int]]],
        island: str | None = None,
    ) -> None:
        """Record the incumbent's blocks that changed since the last snapshot.

        A full schedule every snapshot would be large and mostly still; the analyst needs the
        *movement*, so only the changed blocks are written. A block removed from the schedule is
        sent with an empty treatment and an offset of -1. Each worker keeps its own previous
        schedule, so a parallel search never reports one island's blocks as another's removal.

        Parameters
        ----------
        iteration : int
            The iteration index.
        schedule : mapping of int to sequence of (str, int)
            The incumbent schedule: each block's treatment chain, as (treatment, offset) events.
        island : str or None, optional
            The worker that reported it, when the search runs more than one.
        """
        key = island or ""
        previous = self._last_schedules.get(key, {})
        current = {block: tuple(chain) for block, chain in schedule.items()}
        changed: list[list[object]] = [
            [block, [[treatment, offset] for treatment, offset in chain]]
            for block, chain in current.items()
            if previous.get(block) != chain
        ]
        for block in sorted(set(previous) - set(current)):
            changed.append([block, []])
        self._last_schedules[key] = current
        if changed:
            record: dict[str, Any] = {
                "type": "schedule",
                "iteration": iteration,
                "changed": changed,
            }
            if island is not None:
                record["island"] = island
            self._write(record)

    def close(self) -> None:
        """Close the log."""
        self._file.close()

    def __enter__(self) -> RunLogger:
        """Return the logger."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the log on exit."""
        self.close()


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read a telemetry JSONL file.

    Parameters
    ----------
    path : Path
        The JSONL file.

    Returns
    -------
    list of dict
        The parsed records.
    """
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
