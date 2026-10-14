"""Run telemetry: a per-step objective record and a run header.

Every solver records its objective trajectory to a JSONL file: one header line per run
and one line per iteration. The store is the substrate the tuning and portfolio layers
consume (see `notes/design/ws4-optimization-stack.md`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO


class RunLogger:
    """Append-only JSONL telemetry for one optimization run."""

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
