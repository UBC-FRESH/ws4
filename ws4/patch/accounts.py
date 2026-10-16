"""Patch accounts: the size distribution of connected patches over a topology.

A **patch** is a connected set of topologically adjacent blocks that all meet a patch
membership criterion (a block value greater than a threshold). The established model
(the Patchworks ``6.7 Patch Accounts`` section) defines, for each size class, five
sub-accounts:

``area``
    The total patch area falling in the size class, in hectares.
``size``
    The area in the size class as a percentage of the total patch area.
``shape``
    The mean compactness of the patches in the class, 0 to 100 (100 is a circle).
``frequency``
    The number of patches in the size class.
``attractor``
    A flag that draws the average patch size toward the class; its value mimics ``size``.

The block contribution to a patch is its criterion value times its area, so a half
disturbed block contributes half its area.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .metrics import connected_patches

DEFAULT_SIZE_CLASSES: tuple[float, ...] = (50.0, 150.0, 250.0, 2500.0, math.inf)


@dataclass(frozen=True)
class PatchAccount:
    """A patch account definition.

    Attributes
    ----------
    name : str
        The account name.
    criteria : str
        The feature label used as the patch membership criterion.
    threshold : float
        The criterion value a block must exceed to join a patch.
    size_classes : tuple of float
        The size-class upper bounds, in hectares, ascending. The last may be ``inf``.
    attractor : int or None
        The index of the class an attractor sub-account is defined for, or None.
    search_distance : float or None
        The topology search distance, in metres: only edges whose endpoints are no further apart
        than it join a patch. The default ``0.0`` joins only blocks that literally touch (their
        polygons share a vertex); None considers every edge in the topology.
    """

    name: str
    criteria: str
    threshold: float = 0.0
    size_classes: tuple[float, ...] = DEFAULT_SIZE_CLASSES
    attractor: int | None = None
    search_distance: float | None = 0.0


def size_class_labels(size_classes: Sequence[float]) -> tuple[str, ...]:
    """Return the size-class labels, such as ``('0_50', '50_150', ..., '2500_9999999')``.

    Parameters
    ----------
    size_classes : sequence of float
        The upper bounds, ascending.

    Returns
    -------
    tuple of str
        One label per class.
    """
    labels: list[str] = []
    lower = 0.0
    for upper in size_classes:
        top = 9999999 if math.isinf(upper) else int(upper)
        labels.append(f"{int(lower)}_{top}")
        lower = upper
    return tuple(labels)


def _compactness(area_ha: float, perimeter_m: float) -> float:
    """Return a patch's compactness from 0 to 100 (100 is a circle).

    The area is converted from hectares to square metres so that it is commensurate with
    the perimeter, which is in metres.
    """
    area_m2 = area_ha * 10000.0
    if area_m2 <= 0.0 or perimeter_m <= 0.0:
        return 0.0
    return min(100.0, 100.0 * 4.0 * math.pi * area_m2 / (perimeter_m * perimeter_m))


def patch_account_values(
    account: PatchAccount,
    values: Mapping[int, float],
    edges: Sequence[tuple[int, int, float]],
    block_area: Mapping[int, float],
) -> dict[str, float]:
    """Compute one period's patch sub-account values.

    Parameters
    ----------
    account : PatchAccount
        The account definition.
    values : mapping of int to float
        The criterion value per block, in ``[0, 1]``.
    edges : sequence of (int, int, float)
        The adjacency edges ``(src, dst, shared_length)``.
    block_area : mapping of int to float
        The area of each block.

    Returns
    -------
    dict of str to float
        The sub-account values, keyed ``"<class>.<sub>"`` plus ``"TOTAL.area"`` and
        ``"TOTAL.frequency"``.
    """
    members = {block for block, value in values.items() if value > account.threshold}
    adjacency = [(source, target) for source, target, _ in edges]
    patches = connected_patches(members, adjacency)
    patch_of: dict[int, int] = {}
    for index, patch in enumerate(patches):
        for block in patch:
            patch_of[block] = index
    patch_area = [0.0] * len(patches)
    for block, index in patch_of.items():
        patch_area[index] += values.get(block, 0.0) * block_area.get(block, 0.0)
    # One pass over the edges gives every patch's perimeter (the edges with exactly one
    # member end), instead of re-scanning all edges per patch.
    patch_perimeter_length = [0.0] * len(patches)
    for source, target, length in edges:
        source_patch = patch_of.get(source)
        target_patch = patch_of.get(target)
        if source_patch is not None and target_patch is None:
            patch_perimeter_length[source_patch] += length
        elif target_patch is not None and source_patch is None:
            patch_perimeter_length[target_patch] += length
    total_area = sum(patch_area)
    labels = size_class_labels(account.size_classes)
    result: dict[str, float] = {}
    by_label: dict[str, list[tuple[float, float]]] = {label: [] for label in labels}
    for index, area in enumerate(patch_area):
        compactness = _compactness(area, patch_perimeter_length[index])
        for class_index, upper in enumerate(account.size_classes):
            lower = 0.0 if class_index == 0 else account.size_classes[class_index - 1]
            if lower < area <= upper:
                by_label[labels[class_index]].append((area, compactness))
                break
    for label in labels:
        members_in_class = by_label[label]
        class_area = sum(area for area, _ in members_in_class)
        result[f"{label}.area"] = class_area
        result[f"{label}.size"] = (100.0 * class_area / total_area) if total_area > 0.0 else 0.0
        result[f"{label}.frequency"] = float(len(members_in_class))
        result[f"{label}.shape"] = (
            sum(shape for _, shape in members_in_class) / len(members_in_class)
            if members_in_class
            else 0.0
        )
    result["TOTAL.area"] = total_area
    result["TOTAL.frequency"] = float(len(patches))
    if account.attractor is not None:
        label = labels[account.attractor]
        result[f"{label}.attractor"] = 1.0
    return result


def patch_account_values_indexed(
    account: PatchAccount,
    values: Mapping[int, float],
    neighbours: Mapping[int, Sequence[tuple[int, float]]],
    block_area: Mapping[int, float],
) -> dict[str, float]:
    """Compute one period's patch sub-account values from an indexed adjacency.

    This is :func:`patch_account_values` with the adjacency pre-grouped by block, so a
    period costs O(members x degree) instead of scanning every edge in the topology. The
    two agree exactly.

    Parameters
    ----------
    account : PatchAccount
        The account definition.
    values : mapping of int to float
        The criterion value per block (already restricted to the members).
    neighbours : mapping of int to sequence of (int, float)
        The adjacency ``(neighbour, shared_length)`` per block.
    block_area : mapping of int to float
        The area of each block.

    Returns
    -------
    dict of str to float
        The sub-account values, keyed ``"<class>.<sub>"`` plus ``"TOTAL.area"`` and
        ``"TOTAL.frequency"``.
    """
    members = values
    component: dict[int, int] = {}
    areas: list[float] = []
    perimeters: list[float] = []
    for start in members:
        if start in component:
            continue
        index = len(areas)
        stack = [start]
        component[start] = index
        area = 0.0
        perimeter = 0.0
        while stack:
            block = stack.pop()
            area += values[block] * block_area.get(block, 0.0)
            for other, length in neighbours.get(block, ()):
                if other in members:
                    if other not in component:
                        component[other] = index
                        stack.append(other)
                else:
                    perimeter += length
        areas.append(area)
        perimeters.append(perimeter)
    total_area = math.fsum(areas)
    labels = size_class_labels(account.size_classes)
    by_label: dict[str, list[tuple[float, float]]] = {label: [] for label in labels}
    for index, area in enumerate(areas):
        compactness = _compactness(area, perimeters[index])
        for class_index, upper in enumerate(account.size_classes):
            lower = 0.0 if class_index == 0 else account.size_classes[class_index - 1]
            if lower < area <= upper:
                by_label[labels[class_index]].append((area, compactness))
                break
    result: dict[str, float] = {}
    for label in labels:
        members_in_class = by_label[label]
        class_area = sum(area for area, _ in members_in_class)
        result[f"{label}.area"] = class_area
        result[f"{label}.size"] = (100.0 * class_area / total_area) if total_area > 0.0 else 0.0
        result[f"{label}.frequency"] = float(len(members_in_class))
        result[f"{label}.shape"] = (
            sum(shape for _, shape in members_in_class) / len(members_in_class)
            if members_in_class
            else 0.0
        )
    result["TOTAL.area"] = total_area
    result["TOTAL.frequency"] = float(len(areas))
    if account.attractor is not None:
        label = labels[account.attractor]
        result[f"{label}.attractor"] = 1.0
    return result


def load_patch_accounts(path: Path) -> tuple[PatchAccount, ...]:
    """Load patch account definitions from YAML.

    The file is a mapping with an ``accounts`` list; each entry has ``name``, ``criteria``,
    and any of ``threshold``, ``size_classes``, and ``attractor``.

    Parameters
    ----------
    path : Path
        The YAML file.

    Returns
    -------
    tuple of PatchAccount
        The definitions.
    """
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entries = raw.get("accounts", []) if isinstance(raw, dict) else []
    accounts: list[PatchAccount] = []
    for entry in entries:
        classes = tuple(float(value) for value in entry.get("size_classes", DEFAULT_SIZE_CLASSES))
        raw_distance = entry.get("search_distance", 0.0)
        accounts.append(
            PatchAccount(
                name=str(entry["name"]),
                criteria=str(entry["criteria"]),
                threshold=float(entry.get("threshold", 0.0)),
                size_classes=classes,
                attractor=entry.get("attractor"),
                search_distance=None if raw_distance is None else float(raw_distance),
            )
        )
    return tuple(accounts)


@dataclass
class PatchLedger:
    """Accumulate patch accounts over a run.

    Parameters
    ----------
    accounts : sequence of PatchAccount
        The patch account definitions.
    edges : sequence of (int, int, float, float)
        The adjacency edges ``(src, dst, shared_length, distance)``. Each account keeps only
        the edges within its own ``search_distance``.
    block_area : mapping of int to float
        The area of each block.
    period_width : int, optional
        The planning-period width, in years.
    """

    accounts: Sequence[PatchAccount]
    edges: Sequence[tuple[int, int, float, float]]
    block_area: Mapping[int, float]
    period_width: int = 1
    _records: list[dict[str, float]] = field(default_factory=list)
    _by_account: list[list[tuple[int, int, float]]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        """Keep, per account, only the edges within that account's search distance."""
        self._by_account = [
            [
                (source, target, length)
                for source, target, length, distance in self.edges
                if account.search_distance is None or distance <= account.search_distance
            ]
            for account in self.accounts
        ]

    def record(self, year: int, criteria: Mapping[str, Mapping[int, float]]) -> None:
        """Record one period's patch accounts.

        Parameters
        ----------
        year : int
            The year.
        criteria : mapping of str to mapping of int to float
            The criterion values per block, keyed by the criteria feature label.
        """
        row: dict[str, float] = {"period": float(year), "year": float(year)}
        for account, edges in zip(self.accounts, self._by_account, strict=True):
            values = criteria.get(account.criteria, {})
            for key, value in patch_account_values(account, values, edges, self.block_area).items():
                row[f"{account.name}.{key}"] = value
        self._records.append(row)

    def frame(self) -> pd.DataFrame:
        """Return the patch accounts as a frame, one row per period."""
        return pd.DataFrame(self._records)

    def write(self, out_dir: Path) -> None:
        """Write ``patch_accounts.csv`` into a run directory."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.frame().to_csv(out_dir / "patch_accounts.csv", index=False)


def load_patch_edges_detailed(
    csv_path: Path,
) -> list[tuple[int, int, float, float]]:
    """Load a proximal topology with both shared length and block distance.

    Parameters
    ----------
    csv_path : Path
        The topology CSV.

    Returns
    -------
    list of (int, int, float, float)
        The undirected edges ``(src, dst, shared_length, distance)``; the distance is 0.0
        when the file has no distance column.
    """
    frame = pd.read_csv(csv_path)
    columns = {name.lower(): name for name in frame.columns}

    def pick(*names: str) -> str | None:
        for name in names:
            if name in columns:
                return columns[name]
        return None

    source = pick("src_block", "block1", "source")
    target = pick("dst_block", "block2", "target")
    if source is None or target is None:
        raise ValueError(f"no block columns in {csv_path}")
    length = pick("shared_length", "length_m", "length")
    distance = pick("distance_m", "distance")
    edges: list[tuple[int, int, float, float]] = []
    for row in frame.itertuples(index=False):
        left = int(getattr(row, source))
        right = int(getattr(row, target))
        if left < 0 or right < 0:
            continue
        shared = float(getattr(row, length)) if length is not None else 0.0
        span = float(getattr(row, distance)) if distance is not None else 0.0
        edges.append((left, right, shared, span))
    return edges


def load_patch_edges(csv_path: Path) -> list[tuple[int, int, float]]:
    """Load a proximal topology edge list, accepting the established column names.

    The established file is ``BLOCK1,BLOCK2,DISTANCE,LENGTH``; the sentinel block
    ``-9999`` marks a boundary and is dropped. WS4's names are ``src_block,dst_block``
    with ``distance_m`` or ``length_m``.

    Parameters
    ----------
    csv_path : Path
        The topology CSV.

    Returns
    -------
    list of (int, int, float)
        The undirected edges with their shared boundary length.
    """
    frame = pd.read_csv(csv_path)
    columns = {name.lower(): name for name in frame.columns}

    def pick(*names: str) -> str | None:
        for name in names:
            if name in columns:
                return columns[name]
        return None

    source = pick("src_block", "block1", "source")
    target = pick("dst_block", "block2", "target")
    if source is None or target is None:
        raise ValueError(f"no block columns in {csv_path}")
    length = pick("shared_length", "length_m", "length", "distance_m", "distance")
    edges: list[tuple[int, int, float]] = []
    for row in frame.itertuples(index=False):
        left = int(getattr(row, source))
        right = int(getattr(row, target))
        if left < 0 or right < 0:
            continue
        shared = float(getattr(row, length)) if length is not None else 0.0
        edges.append((left, right, shared))
    return edges
