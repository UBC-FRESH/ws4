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
    """

    def __init__(self, path: Path, run_id: str, config: Mapping[str, Any]) -> None:
        """Open the log and write the run header.

        Parameters
        ----------
        path : Path
            The JSONL file to write.
        run_id : str
            The run identifier.
        config : mapping
            The run configuration to record in the header.
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_schedule: dict[int, tuple[tuple[str, int], ...]] = {}
        self._file: TextIO = self.path.open("w", encoding="utf-8")
        self._write({"type": "run", "run_id": run_id, "config": dict(config)})

    def _write(self, record: Mapping[str, Any]) -> None:
        """Write one JSON record."""
        self._file.write(json.dumps(record) + "\n")

    def step(self, iteration: int, objective: float) -> None:
        """Record one iteration's objective.

        Parameters
        ----------
        iteration : int
            The iteration index.
        objective : float
            The incumbent objective at that iteration.
        """
        self._write({"type": "step", "iteration": iteration, "objective": objective})

    def targets(self, iteration: int, values: Mapping[tuple[int, str], float]) -> None:
        """Record the realized value of every tracked account cell at an iteration.

        Parameters
        ----------
        iteration : int
            The iteration index.
        values : mapping of (int, str) to float
            The realized total per ``(year, account)`` cell, as the move-based evaluator holds it.
        """
        self._write(
            {
                "type": "targets",
                "iteration": iteration,
                "values": [
                    {"year": year, "account": account, "value": value}
                    for (year, account), value in sorted(values.items())
                ],
            }
        )

    def schedule(self, iteration: int, schedule: Mapping[int, Sequence[tuple[str, int]]]) -> None:
        """Record the incumbent's blocks that changed since the last snapshot.

        A full schedule every snapshot would be large and mostly still; the analyst needs the
        *movement*, so only the changed blocks are written. A block removed from the schedule is
        sent with an empty treatment and a period of -1.

        Parameters
        ----------
        iteration : int
            The iteration index.
        schedule : mapping of int to sequence of (str, int)
            The incumbent schedule: each block's treatment chain, as (treatment, period) events.
        """
        current = {block: tuple(chain) for block, chain in schedule.items()}
        changed: list[list[object]] = [
            [block, [[treatment, period] for treatment, period in chain]]
            for block, chain in current.items()
            if self._last_schedule.get(block) != chain
        ]
        for block in sorted(set(self._last_schedule) - set(current)):
            changed.append([block, []])
        self._last_schedule = current
        if changed:
            self._write({"type": "schedule", "iteration": iteration, "changed": changed})

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
