"""Explicit fire-behaviour classes and surface-to-crown transitions.

The FBP equations produce a crown fraction and flame length. This module turns those into a
small, auditable behaviour class so the event log and the 3D scene can distinguish ground,
surface, passive-crown, and active-crown fire. The ground class is a low-intensity proxy; it is
not a duff or peat combustion model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .crown import CrownFireResult
from .fuel import FireFuelError, _non_negative, _probability

GROUND_FLAME_LENGTH_M: Final[float] = 0.5
PASSIVE_CROWN_CFB: Final[float] = 0.1
ACTIVE_CROWN_CFB: Final[float] = 0.9


class FireBehaviourClass(StrEnum):
    """The four explicit fire-behaviour classes.

    Attributes
    ----------
    GROUND
        Low-intensity/smoldering proxy; no sustained flaming surface front.
    SURFACE
        Flaming surface fire without crown involvement.
    PASSIVE_CROWN
        Intermittent or passive crown fire.
    ACTIVE_CROWN
        Active crown fire.
    """

    GROUND = "ground"
    SURFACE = "surface"
    PASSIVE_CROWN = "passive_crown"
    ACTIVE_CROWN = "active_crown"


@dataclass(frozen=True)
class FireBehaviourTransition:
    """A transition between two behaviour classes.

    Parameters
    ----------
    previous : FireBehaviourClass
        Previous class.
    current : FireBehaviourClass
        Current class.
    """

    previous: FireBehaviourClass
    current: FireBehaviourClass

    @property
    def label(self) -> str:
        """Return a stable transition label.

        Returns
        -------
        str
            ``unchanged`` or ``previous->current``.
        """
        if self.previous == self.current:
            return "unchanged"
        return f"{self.previous.value}->{self.current.value}"

    @property
    def is_transition(self) -> bool:
        """Return whether the class changed.

        Returns
        -------
        bool
            True when the class changed.
        """
        return self.previous != self.current

    def to_dict(self) -> dict[str, str]:
        """Return the transition as a JSON-serializable mapping.

        Returns
        -------
        dict
            Previous, current, and label.
        """
        return {
            "previous": self.previous.value,
            "current": self.current.value,
            "label": self.label,
        }


def classify_fire_behaviour(
    *,
    crown_fraction_burned: float,
    flame_length_m: float,
    ground_flame_length_m: float = GROUND_FLAME_LENGTH_M,
) -> FireBehaviourClass:
    """Classify one cell's fire behaviour from FBP outputs.

    Parameters
    ----------
    crown_fraction_burned : float
        FBP crown fraction burned in [0, 1].
    flame_length_m : float
        Head flame length in metres.
    ground_flame_length_m : float, optional
        Flame length below which the low-intensity ground proxy is used (default 0.5 m).

    Returns
    -------
    FireBehaviourClass
        The explicit behaviour class.

    Raises
    ------
    FireFuelError
        If an input is outside its valid range.

    Notes
    -----
    The ground class is a proxy for a low-intensity or smoldering surface state. WS4 does not
    yet model duff/peat combustion or smoldering spread.
    """
    cfb = _probability(crown_fraction_burned, "crown_fraction_burned")
    flame = _non_negative(flame_length_m, "flame_length_m")
    threshold = _non_negative(ground_flame_length_m, "ground_flame_length_m")
    if cfb >= ACTIVE_CROWN_CFB:
        return FireBehaviourClass.ACTIVE_CROWN
    if cfb >= PASSIVE_CROWN_CFB:
        return FireBehaviourClass.PASSIVE_CROWN
    if flame < threshold:
        return FireBehaviourClass.GROUND
    return FireBehaviourClass.SURFACE


def classify_crown_fire(result: CrownFireResult) -> FireBehaviourClass:
    """Classify a full FBP crown-fire result.

    Parameters
    ----------
    result : CrownFireResult
        The FBP surface/crown result.

    Returns
    -------
    FireBehaviourClass
        The explicit behaviour class.
    """
    return classify_fire_behaviour(
        crown_fraction_burned=result.crown_fraction_burned,
        flame_length_m=result.flame_length_m,
    )


def transition(
    previous: FireBehaviourClass,
    current: FireBehaviourClass,
) -> FireBehaviourTransition:
    """Return the transition between two classes.

    Parameters
    ----------
    previous, current : FireBehaviourClass
        Ordered classes.

    Returns
    -------
    FireBehaviourTransition
        The transition record.

    Raises
    ------
    FireFuelError
        If either argument is not a FireBehaviourClass.
    """
    if not isinstance(previous, FireBehaviourClass) or not isinstance(current, FireBehaviourClass):
        raise FireFuelError("transitions require FireBehaviourClass values")
    return FireBehaviourTransition(previous=previous, current=current)
