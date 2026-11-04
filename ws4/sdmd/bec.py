"""BEC label crosswalk between the WS4 coverage table and CCISS.

The WS4 table and the CCISS Western North America table were compiled at different
times and at different variant granularities. This module classifies each label
difference as an exact match, a split, a retired BEC label, or a current label that
is absent from WS4. The BECdb current and retired tables supply the retirement
version and recorded successors.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .au_integrity import default_bec_aliases

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
        ``not_in_cciss``, or ``not_in_ws4`` for the CCISS crosswalk;
        ``official_exact``, ``retired``, ``not_in_becdb``, or ``not_in_ws4``
        for the BECdb crosswalk.
    note : str
        A short explanation.
    retired_version : str or None
        The BEC version that retired the label, for ``retired`` rows.
    replaced_by : str
        Semicolon-separated current labels named as successors, when known.
    """

    ws4_bec: str | None
    cciss_bec: str | None
    relationship: str
    note: str
    retired_version: str | None = None
    replaced_by: str = ""


def classify_crosswalk(
    ws4_labels: Iterable[str],
    cciss_labels: Iterable[str],
) -> tuple[BecRelationship, ...]:
    """Classify unique label relationships between WS4 and CCISS.

    Phase aliases are normalized before comparison. A label is a split only when
    the other side contains a strict prefix of it and no exact match. Parent
    labels with finer children are represented by the child rows, not by a
    separate summary row. A label with no exact or prefix relationship is
    reported as absent from the other list; no equivalence is asserted.

    Parameters
    ----------
    ws4_labels : iterable of str
        WS4 BEC labels.
    cciss_labels : iterable of str
        CCISS BEC labels.

    Returns
    -------
    tuple of BecRelationship
        One row per unique label relationship, sorted by WS4 and then CCISS.
    """
    aliases = default_bec_aliases()

    def canonical(label: object) -> str:
        compact = "".join(str(label).split())
        return aliases.get(compact, compact)

    ours = {canonical(label) for label in ws4_labels if str(label).strip()}
    theirs = {canonical(label) for label in cciss_labels if str(label).strip()}
    rows: list[BecRelationship] = []
    seen: set[tuple[str | None, str | None]] = set()

    def add(row: BecRelationship) -> None:
        key = (row.ws4_bec, row.cciss_bec)
        if key not in seen:
            seen.add(key)
            rows.append(row)

    for label in sorted(ours & theirs):
        add(BecRelationship(label, label, "same", "exact label"))
    for label in sorted(ours - theirs):
        parent = _longest_prefix(label, theirs)
        if parent is not None:
            add(
                BecRelationship(
                    label,
                    parent,
                    "ws4_split",
                    f"{label} is a finer WS4 label than {parent}",
                )
            )
            continue
        if any(item.startswith(label) and item != label for item in theirs):
            continue
        add(BecRelationship(label, None, "not_in_cciss", "no CCISS label"))
    for label in sorted(theirs - ours):
        parent = _longest_prefix(label, ours)
        if parent is not None:
            add(
                BecRelationship(
                    parent,
                    label,
                    "cciss_split",
                    f"{label} is a finer CCISS label than {parent}",
                )
            )
            continue
        if any(item.startswith(label) and item != label for item in ours):
            continue
        add(BecRelationship(None, label, "not_in_ws4", "no WS4 label"))
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
    retired_versions: Mapping[str, str] | None = None,
    notes: Mapping[str, str] | None = None,
) -> tuple[BecRelationship, ...]:
    """Classify WS4 labels against the official BECdb current and retired units.

    Parameters
    ----------
    ws4_labels : iterable of str
        WS4 BEC labels.
    official_labels : iterable of str
        Current BEC 13.1 labels, without spaces.
    retired_versions : mapping of str to str, optional
        Retired BEC labels mapped to the BEC version that retired them.
    notes : mapping of str to str, optional
        Current-label notes from BECdb, used to name recorded successors.

    Returns
    -------
    tuple of BecRelationship
        One row per WS4 label and one per current label absent from WS4. A WS4
        label is ``official_exact``, ``retired``, or ``not_in_becdb``. A current
        label absent from WS4 is ``not_in_ws4``.
    """
    ours = {str(label) for label in ws4_labels if str(label)}
    official = {str(label) for label in official_labels if str(label)}
    retired = {str(label): str(version) for label, version in (retired_versions or {}).items()}
    current_notes = {str(label): str(note) for label, note in (notes or {}).items()}
    rows: list[BecRelationship] = []
    for label in sorted(ours):
        if label in official:
            note = current_notes.get(label, "")
            rows.append(
                BecRelationship(
                    label,
                    label,
                    "official_exact",
                    note or "exact current BEC 13.1 label",
                )
            )
        elif label in retired:
            successors = _successors(label, official, current_notes)
            note = current_notes.get(label, "")
            if not note:
                note = f"retired in BEC version {retired[label]}"
            if not successors:
                note = f"{note}; no successor recorded in BECdb"
            rows.append(
                BecRelationship(
                    label,
                    None,
                    "retired",
                    note,
                    retired_version=retired[label],
                    replaced_by=";".join(successors),
                )
            )
        else:
            rows.append(
                BecRelationship(
                    label,
                    None,
                    "not_in_becdb",
                    "absent from both the current and retired BECdb tables",
                )
            )
    for label in sorted(official - ours):
        children = sorted(item for item in ours if item.startswith(label) and item != label)
        if children:
            rows.append(
                BecRelationship(
                    None,
                    label,
                    "covered_by_finer",
                    f"{len(children)} finer WS4 labels represent the current BEC label",
                    replaced_by=";".join(children),
                )
            )
        else:
            rows.append(
                BecRelationship(
                    None,
                    label,
                    "not_in_ws4",
                    "current BEC 13.1 label absent from the WS4 coverage table",
                )
            )
    rows.sort(key=lambda row: (row.ws4_bec or "", row.cciss_bec or ""))
    return tuple(rows)


def _successors(
    label: str,
    current: set[str],
    notes: Mapping[str, str],
) -> list[str]:
    """Return current labels named by BECdb notes or by a shared prefix."""
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(label)}(?![A-Za-z0-9])", re.IGNORECASE)
    named = {item for item, note in notes.items() if pattern.search(note)}
    prefixed = {item for item in current if item.startswith(label) and item != label}
    return sorted(named | prefixed)
