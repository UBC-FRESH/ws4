"""A deliberately imperfect module for the docstring-audit tests.

Each function below carries exactly one defect, so ``tests/test_doc_audit.py`` can assert that the
auditor reports the matching finding code. The module is never imported by the package itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


def good(a: int, b: str) -> int:
    """Return ``a``, ignoring ``b``.

    Parameters
    ----------
    a : int
        The value to return.
    b : str
        An argument that is accepted and ignored.

    Returns
    -------
    int
        The value of ``a``.
    """
    del b
    return a


def undocumented(a: int) -> int:
    """Return ``a``.

    Returns
    -------
    int
        The value of ``a``.
    """
    return a


def stale(a: int) -> int:
    """Return ``a``.

    Parameters
    ----------
    a : int
        The value to return.
    b : int
        A parameter the function no longer accepts.

    Returns
    -------
    int
        The value of ``a``.
    """
    return a


def no_returns(a: int) -> int:
    """Return ``a``.

    Parameters
    ----------
    a : int
        The value to return.
    """
    return a


def no_docstring(a: int) -> int:
    return a


def _private_helper(a: int) -> int:
    return a


@dataclass(frozen=True)
class Documented:
    """A dataclass documenting its fields as attributes.

    Attributes
    ----------
    a : int
        The value.
    """

    a: int


class WithDerived:
    """A class documenting a derived attribute alongside its parameter.

    Parameters
    ----------
    a : int
        The value to hold.

    Attributes
    ----------
    doubled : int
        Twice ``a``, computed on the fly.
    """

    def __init__(self, a: int) -> None:
        """Store the value."""
        self.a = a

    @property
    def doubled(self) -> int:
        """Return twice the held value.

        Returns
        -------
        int
            Twice the held value.
        """
        return self.a * 2


class Shape(Protocol):
    """A protocol, whose constructor signature is not its own.

    Attributes
    ----------
    weight : float
        The shape's weight.
    """

    weight: float

    def apply(self, a: int) -> int:
        """Return a modified value.

        Parameters
        ----------
        a : int
            The value to modify.

        Returns
        -------
        int
            The modified value.
        """


class Thing:
    """A thing with a documented constructor and method.

    Parameters
    ----------
    x : int
        The value to hold.
    """

    def __init__(self, x: int) -> None:
        """Store the value."""
        self.x = x

    def value(self) -> int:
        """Return the held value.

        Returns
        -------
        int
            The held value.
        """
        return self.x

    def undocumented(self) -> int:
        """Return a constant.

        Returns
        -------
        int
            One.
        """
        return 1
