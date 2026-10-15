"""Edge contrast accounts over a block adjacency topology.

An **edge contrast** metric measures the juxtaposition of one forest type beside another
(the established ``addEdgeTarget`` / ``addEdgeElement`` API). For each shared edge between
two adjacent blocks it takes the absolute difference in the two attributes' per-unit
values, times the shared edge length, and sums it into a named account. Adjacent blocks
with similar values contribute little; a hard boundary between two contrasting types
contributes the full edge length.

An edge element names the two attributes and a scale factor. The per-block values come
from feature curves (``Simulator.block_criteria``), so the account changes over time as
stands age and are treated.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .constraints import edge_contrast


@dataclass(frozen=True)
class EdgeElement:
    """One edge contrast specification (``addEdgeElement``).

    Attributes
    ----------
    account : str
        The account the contrast is summed into.
    attribute1 : str
        The first feature label.
    attribute2 : str
        The second feature label.
    factor : float
        A scale factor applied to the difference.
    """

    account: str
    attribute1: str
    attribute2: str
    factor: float = 1.0


def load_edge_elements(path: Path) -> tuple[EdgeElement, ...]:
    """Load edge elements from a CSV (``account,attribute1,attribute2,factor``).

    Parameters
    ----------
    path : Path
        The edge-element CSV. The ``factor`` column is optional (default 1).

    Returns
    -------
    tuple of EdgeElement
        The edge elements, in file order.
    """
    elements: list[EdgeElement] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            elements.append(
                EdgeElement(
                    account=(row.get("account") or "").strip(),
                    attribute1=(row.get("attribute1") or "").strip(),
                    attribute2=(row.get("attribute2") or "").strip(),
                    factor=float(row.get("factor") or 1.0),
                )
            )
    return tuple(elements)


def edge_values(
    elements: Sequence[EdgeElement],
    edges: Sequence[tuple[int, int, float]],
    criteria: Mapping[str, Mapping[int, float]],
) -> list[dict[str, object]]:
    """Return one record per edge element for a single period.

    Parameters
    ----------
    elements : sequence of EdgeElement
        The edge elements.
    edges : sequence of (int, int, float)
        The adjacency edges ``(src, dst, shared_length)``.
    criteria : mapping of str to mapping of int to float
        The per-block criterion values, keyed by feature label.

    Returns
    -------
    list of dict
        One record per element, with ``account`` and ``value``.
    """
    records: list[dict[str, object]] = []
    for element in elements:
        value = edge_contrast(
            criteria.get(element.attribute1, {}),
            criteria.get(element.attribute2, {}),
            edges,
            element.factor,
        )
        records.append({"account": element.account, "value": value})
    return records
