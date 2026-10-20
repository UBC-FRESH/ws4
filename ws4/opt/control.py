"""A run's control file: pause, resume or stop a search between iterations.

A web client cannot send a signal that leaves a clean summary, so the search polls a small JSON
file instead. ``{"action": "run"}`` is the normal state, ``pause`` holds the loop, and ``stop``
breaks it; the run then writes its schedule and summary exactly as at the end of its budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: The actions a control file may carry.
ACTIONS = frozenset({"run", "pause", "stop"})


@dataclass(frozen=True)
class RunControl:
    """A polled control file for one run.

    Attributes
    ----------
    path : Path
        The JSON file the client writes.
    """

    path: Path

    def action(self) -> str:
        """Return the current action, defaulting to ``run`` when the file is absent or invalid.

        Returns
        -------
        str
            ``run``, ``pause`` or ``stop``.
        """
        try:
            document = json.loads(Path(self.path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "run"
        action = str(document.get("action", "run")) if isinstance(document, dict) else "run"
        return action if action in ACTIONS else "run"
