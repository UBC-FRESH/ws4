"""BEC label crosswalk between the WS4 coverage table and CCISS.

The WS4 table and the CCISS Western North America table were compiled at different
times and at different variant granularities. This module classifies each label
difference as an exact match, a WS4 split of a CCISS parent, a CCISS split of a WS4
parent, or unresolved. It does not invent a mapping for an unresolved label.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = ["BecRelationship", "classify_crosswalk", "classify_official"]


@dataclass(frozen=True)
class BecRelationship:
    """One BEC label relationship.

    Attributes
    ----------
    ws4_bec : str or None
        The WS4 label, when present.
    cciss_bec : str or None
        The CCISS label, when present.
    relationship : str
        The relationship: ``same``, ``ws4_split``, ``cciss_split``,
        ``unresolved`` for the CCISS crosswalk; ``official_exact``,
        ``ws4_finer``, ``official_finer``, ``not_in_official``, or
        ``not_in_ws4`` for the BEC 13.1 crosswalk.
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
        if parent is not None:
            rows.append(
                BecRelationship(
                    label,
                    parent,
                    "ws4_split",
                    f"{label} is a finer WS4 label than {parent}",
                )
            )
            continue
        children = [item for item in theirs if item.startswith(label) and item != label]
        if children:
            rows.append(
                BecRelationship(
                    label,
                    None,
                    "cciss_split",
                    f"{len(children)} finer CCISS labels start with {label}",
                )
            )
        else:
            rows.append(BecRelationship(label, None, "unresolved", "no CCISS parent"))
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


def classify_official(
    ws4_labels: Iterable[str],
    official_labels: Iterable[str],
) -> tuple[BecRelationship, ...]:
    """Classify WS4 labels against the current official BEC 13.1 list.

    Parameters
    ----------
    ws4_labels : iterable of str
        WS4 BEC labels.
    official_labels : iterable of str
        Official BEC 13.1 labels, without spaces.

    Returns
    -------
    tuple of BecRelationship
        One row per exact label, one per finer label, and one per label absent
        from the other list. Parent labels with finer official children are
        represented by the child rows, not as duplicates.
    """
    ours = {str(label) for label in ws4_labels if str(label)}
    official = {str(label) for label in official_labels if str(label)}
    rows: list[BecRelationship] = []
    for label in sorted(ours & official):
        rows.append(BecRelationship(label, label, "official_exact", "exact BEC 13.1 label"))
    for label in sorted(ours - official):
        parent = _longest_prefix(label, official)
        if parent is not None:
            rows.append(
                BecRelationship(label, parent, "ws4_finer", f"{label} is finer than {parent}")
            )
            continue
        children = [item for item in official if item.startswith(label) and item != label]
        if children:
            continue
        rows.append(BecRelationship(label, None, "not_in_official", "absent from BEC 13.1"))
    for label in sorted(official - ours):
        parent = _longest_prefix(label, ours)
        if parent is not None:
            rows.append(
                BecRelationship(parent, label, "official_finer", f"{label} is finer than {parent}")
            )
        else:
            rows.append(
                BecRelationship(None, label, "not_in_ws4", "absent from the WS4 coverage table")
            )
    rows.sort(key=lambda row: (row.ws4_bec or "", row.cciss_bec or ""))
    return tuple(rows)
