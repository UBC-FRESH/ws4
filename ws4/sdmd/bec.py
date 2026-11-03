"""BEC label crosswalk between the WS4 coverage table and CCISS.

The WS4 table and the CCISS Western North America table were compiled at different
times and at different variant granularities. This module classifies each label
difference as an exact match, a WS4 split of a CCISS parent, a CCISS split of a WS4
parent, or unresolved. It does not invent a mapping for an unresolved label.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = ["BecRelationship", "classify_crosswalk"]


@dataclass(frozen=True)
class BecRelationship:
    """One BEC label relationship.

    Attributes
    ----------
    ws4_bec : str or None
        The WS4 label, when present.
    cciss_bec : str or None
        The CCISS label, when present.
    relationship : {"same", "ws4_split", "cciss_split", "unresolved"}
        The relationship.
    note : str
        A short explanation.
    """

    ws4_bec: str | None
    cciss_bec: str | None
    relationship: str
    note: str


def classify_crosswalk(
    ws4_labels: Iterable[str],
    cciss_labels: Iterable[str],
) -> tuple[BecRelationship, ...]:
    """Classify the union of two BEC label sets.

    A label is a split when the other side contains a strict prefix of it and no
    exact match. The longest prefix is used. Everything else is unresolved.

    Parameters
    ----------
    ws4_labels : iterable of str
        WS4 BEC labels.
    cciss_labels : iterable of str
        CCISS BEC labels.

    Returns
    -------
    tuple of BecRelationship
        One row per label or label pair, sorted by the WS4 label and then CCISS.
    """
    ours = {str(label) for label in ws4_labels if str(label)}
    theirs = {str(label) for label in cciss_labels if str(label)}
    rows: list[BecRelationship] = []
    for label in sorted(ours & theirs):
        rows.append(BecRelationship(label, label, "same", "exact label"))
    for label in sorted(ours - theirs):
        parent = _longest_prefix(label, theirs)
        if parent is None:
            rows.append(BecRelationship(label, None, "unresolved", "no CCISS parent"))
        else:
            rows.append(
                BecRelationship(
                    label,
                    parent,
                    "ws4_split",
                    f"{label} is a finer WS4 label than {parent}",
                )
            )
    for label in sorted(theirs - ours):
        parent = _longest_prefix(label, ours)
        if parent is None:
            rows.append(BecRelationship(None, label, "unresolved", "no WS4 parent"))
        else:
            rows.append(
                BecRelationship(
                    parent,
                    label,
                    "cciss_split",
                    f"{label} is a finer CCISS label than {parent}",
                )
            )
    rows.sort(key=lambda row: (row.ws4_bec or "", row.cciss_bec or ""))
    return tuple(rows)


def _longest_prefix(label: str, candidates: Sequence[str] | set[str]) -> str | None:
    """Return the longest strict prefix of a label, if one exists."""
    matches = [
        candidate for candidate in candidates if label.startswith(candidate) and candidate != label
    ]
    return max(matches, key=len) if matches else None
