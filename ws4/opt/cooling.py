"""Temperature schedules for simulated annealing.

Re-exported from the shared kernel; WS4 keeps this module so its imports and API remain
stable. See :mod:`fresh_solutions.kernel.cooling` for the implementation.
"""

from __future__ import annotations

from fresh_solutions.kernel.cooling import AdaptiveCooling, TemperatureSchedule

__all__ = ["AdaptiveCooling", "TemperatureSchedule"]
