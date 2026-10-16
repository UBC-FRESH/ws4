"""Temperature schedules for simulated annealing.

The first WS4 schedule was geometric (``temperature *= cooling``). A geometric schedule needs
its two constants tuned by trial for each problem. This module adds the adaptive,
polynomial-time schedule of Aarts and Van Laarhoven (1985): the initial temperature is set from
the average uphill move, and the temperature is then decreased from the spread of the objective
values at the current temperature, so the schedule tunes itself to the instance.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdaptiveCooling:
    """The Aarts and Van Laarhoven (1985) polynomial-time cooling rule.

    Parameters
    ----------
    initial_acceptance : float, optional
        The acceptance ratio the initial temperature targets, in ``(0, 1)``. Defaults to 0.9.
    delta : float, optional
        The distance from stationarity the decrement allows; it must be positive. Defaults to
        0.1.
    """

    initial_acceptance: float = 0.9
    delta: float = 0.1

    def __post_init__(self) -> None:
        """Reject parameters the cooling rule is undefined for."""
        if not 0.0 < self.initial_acceptance < 1.0:
            raise ValueError("initial_acceptance must be in (0, 1)")
        if self.delta <= 0.0:
            raise ValueError("delta must be positive")

    def initial_temperature(self, increases: Sequence[float]) -> float:
        """Return the initial temperature for a sample of uphill move costs.

        ``c_0 = mean(positive dE) / ln(1 / chi_0)``, so a move that raises the objective by
        the observed average is accepted with probability ``chi_0`` at ``c_0``.

        Parameters
        ----------
        increases : sequence of float
            The objective changes of the sampled moves. Only positive changes are used.

        Returns
        -------
        float
            The initial temperature, or ``0.0`` when no sampled move was uphill.
        """
        uphill = [change for change in increases if change > 0.0]
        if not uphill:
            return 0.0
        return (sum(uphill) / len(uphill)) / math.log(1.0 / self.initial_acceptance)

    def cool(self, temperature: float, spread: float) -> float:
        """Return the next temperature from the current one and its objective spread.

        ``c_{k+1} = c_k / (1 + c_k ln(1 + delta) / (3 sigma_k))``. A non-positive spread
        leaves the temperature unchanged, because the rule is undefined there.

        Parameters
        ----------
        temperature : float
            The current temperature.
        spread : float
            The population standard deviation of the objectives at the current temperature.

        Returns
        -------
        float
            The next temperature.
        """
        if spread <= 0.0:
            return temperature
        return temperature / (1.0 + temperature * math.log1p(self.delta) / (3.0 * spread))


@dataclass
class TemperatureSchedule:
    """Advance the temperature: geometric, or the adaptive Aarts-Van Laarhoven rule.

    The schedule owns the temperature the solver reads each iteration. In adaptive mode the
    first ``window`` iterations form a random walk that estimates the initial temperature, and
    each following group of ``window`` iterations recomputes it from the spread of the
    objectives seen. In geometric mode the temperature is simply multiplied by ``cooling``.

    Parameters
    ----------
    initial : float
        The starting temperature, used as-is in geometric mode.
    cooling : float
        The geometric factor, used only in geometric mode.
    adaptive : bool
        Whether to use the adaptive rule.
    window : int
        The number of iterations per temperature in adaptive mode.

    Attributes
    ----------
    temperature : float
        The temperature the next iteration should read.
    """

    initial: float
    cooling: float
    adaptive: bool
    window: int
    rule: AdaptiveCooling = field(default_factory=AdaptiveCooling)
    temperature: float = field(init=False, default=0.0)
    _increases: list[float] = field(init=False, default_factory=list)
    _samples: list[float] = field(init=False, default_factory=list)
    _warmed: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        """Set the starting temperature and whether a warm-up is still due."""
        if self.window < 1:
            raise ValueError("window must be positive")
        # A random walk accepts every move, so the initial temperature is effectively infinite.
        self.temperature = math.inf if self.adaptive else self.initial
        self._warmed = not self.adaptive

    def observe(self, increase: float, objective: float) -> None:
        """Record one iteration, then advance the temperature.

        Parameters
        ----------
        increase : float
            The objective change the move proposed (positive for a worse objective).
        objective : float
            The objective of the current configuration after the move.
        """
        if not self.adaptive:
            self.temperature *= self.cooling
            return
        if not self._warmed:
            self._increases.append(increase)
            if len(self._increases) >= self.window:
                self.temperature = self.rule.initial_temperature(self._increases)
                self._increases.clear()
                self._warmed = True
            return
        self._samples.append(objective)
        if len(self._samples) >= self.window:
            self.temperature = self.rule.cool(self.temperature, statistics.pstdev(self._samples))
            self._samples.clear()

    @staticmethod
    def effective_window(iterations: int, window: int) -> int:
        """Return the adaptive window for an iteration budget.

        The warm-up and at least one cooling step both need a window of iterations, so the
        window is capped at half the budget.

        Parameters
        ----------
        iterations : int
            The iteration budget.
        window : int
            The requested window.

        Returns
        -------
        int
            The window to use, at least one.
        """
        return max(1, min(window, max(1, iterations // 2)))
