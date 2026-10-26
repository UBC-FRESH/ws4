"""Landscape resilience metrics derived from existing patch, spread, and age state.

The metrics are deliberately descriptive. They do not add a spatial model, a
disturbance simulator, or an objective term. Connectivity and fragmentation use
the block topology; age diversity uses the simulated fragment ages.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .patch.metrics import connected_patches, patch_metrics

RESILIENCE_SCHEMA_VERSION = "ws4.resilience.v1"
RESILIENCE_ACCOUNT_PREFIX = "resilience"
RESILIENCE_AGE_CLASS_WIDTH = 20.0
RESILIENCE_PATCH_BREAKS: tuple[float, ...] = (5.0, 10.0, 50.0)

METRIC_DEFINITIONS: dict[str, dict[str, str]] = {
    "resilience.connectivity.largest_component": {
        "unit": "ha",
        "semantics": "level",
        "definition": "Area of the largest connected set of untreated blocks.",
    },
    "resilience.connectivity.percolation_reach": {
        "unit": "ha",
        "semantics": "level",
        "definition": "Area-weighted mean untreated component area, sum(a^2)/sum(a).",
    },
    "resilience.connectivity.component_count": {
        "unit": "count",
        "semantics": "level",
        "definition": "Number of connected untreated components.",
    },
    "resilience.connectivity.untreated_area": {
        "unit": "ha",
        "semantics": "level",
        "definition": "Total untreated area represented in the connectivity graph.",
    },
    "resilience.age_class.shannon": {
        "unit": "index",
        "semantics": "level",
        "definition": "Shannon diversity of fragment area across 20-year age classes.",
    },
    "resilience.age_class.evenness": {
        "unit": "index",
        "semantics": "level",
        "definition": "Shannon evenness across occupied age classes, 0 to 1.",
    },
    "resilience.age_class.count": {
        "unit": "count",
        "semantics": "level",
        "definition": "Number of occupied 20-year age classes.",
    },
    "resilience.fragmentation.patch_count": {
        "unit": "count",
        "semantics": "flow",
        "definition": "Number of openings created in the current year.",
    },
    "resilience.fragmentation.mean_patch_area": {
        "unit": "ha",
        "semantics": "flow",
        "definition": "Mean opening-patch area in the current year.",
    },
    "resilience.fragmentation.largest_patch_area": {
        "unit": "ha",
        "semantics": "flow",
        "definition": "Largest opening-patch area in the current year.",
    },
    "resilience.fragmentation.area": {
        "unit": "ha",
        "semantics": "flow",
        "definition": "Area treated in the current year.",
    },
}

RESILIENCE_CAVEAT = (
    "Resilience metrics are descriptive. Connectivity and fragmentation depend on the "
    "block topology and aggregation scale; age diversity uses the simulation's own "
    "fragment ages. Connectivity and age metrics are levels; fragmentation metrics "
    "are per-year flows. They are not a fire model, a species model, or an objective."
)


class ResilienceError(RuntimeError):
    """Raised when resilience inputs or outputs are incomplete."""


@dataclass(frozen=True)
class ResilienceMetadata:
    """Definitions and provenance for one resilience computation.

    Parameters
    ----------
    topology : str
        Topology source path or description.
    age_class_width : float
        Age-class width, in years.
    patch_breaks : tuple of float
        Opening-patch size-class upper bounds, in hectares.
    notes : str or None
        Optional provenance note.
    """

    topology: str
    age_class_width: float = RESILIENCE_AGE_CLASS_WIDTH
    patch_breaks: tuple[float, ...] = RESILIENCE_PATCH_BREAKS
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-serializable metadata.

        Returns
        -------
        dict
            Metadata with the schema, metric definitions, and caveat.
        """
        return {
            "schema_version": RESILIENCE_SCHEMA_VERSION,
            "topology": self.topology,
            "age_class_width": self.age_class_width,
            "patch_breaks": list(self.patch_breaks),
            "metrics": METRIC_DEFINITIONS,
            "caveat": RESILIENCE_CAVEAT,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ResilienceMetadata:
        """Validate and read resilience metadata.

        Parameters
        ----------
        payload : mapping
            Decoded metadata.

        Returns
        -------
        ResilienceMetadata
            The validated metadata.

        Raises
        ------
        ResilienceError
            If the schema or a required value is invalid.
        """
        if payload.get("schema_version") != RESILIENCE_SCHEMA_VERSION:
            raise ResilienceError(
                f"resilience schema_version must be {RESILIENCE_SCHEMA_VERSION!r}"
            )
        topology = str(payload.get("topology", "")).strip()
        if not topology:
            raise ResilienceError("resilience metadata needs a topology")
        width = float(str(payload.get("age_class_width", RESILIENCE_AGE_CLASS_WIDTH)))
        if width <= 0:
            raise ResilienceError("resilience age_class_width must be positive")
        raw_breaks = payload.get("patch_breaks", list(RESILIENCE_PATCH_BREAKS))
        if not isinstance(raw_breaks, list) or not raw_breaks:
            raise ResilienceError("resilience patch_breaks must be a non-empty list")
        return cls(
            topology=topology,
            age_class_width=width,
            patch_breaks=tuple(float(str(value)) for value in raw_breaks),
            notes=None if payload.get("notes") is None else str(payload["notes"]),
        )


def connectivity_metrics(
    untreated_blocks: Sequence[int] | set[int],
    edges: Sequence[tuple[int, int, float]],
    block_area: Mapping[int, float],
) -> dict[str, float]:
    """Compute untreated connectivity from the full block topology.

    Parameters
    ----------
    untreated_blocks : sequence or set of int
        Blocks currently untreated.
    edges : sequence of (int, int, float)
        Topology edges; the length field is ignored here.
    block_area : mapping of int to float
        Block areas in hectares.

    Returns
    -------
    dict of str to float
        Largest component, percolation reach, component count, and untreated area.
    """
    pairs = [(int(source), int(target)) for source, target, *_rest in edges]
    patches = connected_patches(untreated_blocks, pairs)
    areas = [float(sum(block_area.get(block, 0.0) for block in patch)) for patch in patches]
    total = float(sum(areas))
    largest = max(areas) if areas else 0.0
    percolation = (sum(area * area for area in areas) / total) if total else 0.0
    return {
        "resilience.connectivity.largest_component": largest,
        "resilience.connectivity.percolation_reach": percolation,
        "resilience.connectivity.component_count": float(len(areas)),
        "resilience.connectivity.untreated_area": total,
    }


def age_class_diversity(
    fragment_ages: Sequence[tuple[float, float]],
    *,
    age_class_width: float = RESILIENCE_AGE_CLASS_WIDTH,
) -> dict[str, float]:
    """Compute Shannon diversity of area across age classes.

    Parameters
    ----------
    fragment_ages : sequence of (float, float)
        ``(age, area_ha)`` for every fragment.
    age_class_width : float, optional
        Age-class width in years.

    Returns
    -------
    dict of str to float
        Shannon index, evenness, and occupied class count.

    Raises
    ------
    ResilienceError
        If the width is not positive.
    """
    if age_class_width <= 0:
        raise ResilienceError("age_class_width must be positive")
    area_by_class: dict[int, float] = {}
    for age, area in fragment_ages:
        if not math.isfinite(float(age)) or not math.isfinite(float(area)):
            raise ResilienceError("fragment age and area must be finite")
        age_class = int(math.floor(max(0.0, float(age)) / age_class_width) * age_class_width)
        area_by_class[age_class] = area_by_class.get(age_class, 0.0) + max(0.0, float(area))
    total = sum(area_by_class.values())
    if total <= 0:
        return {
            "resilience.age_class.shannon": 0.0,
            "resilience.age_class.evenness": 0.0,
            "resilience.age_class.count": 0.0,
        }
    proportions = [area / total for area in area_by_class.values() if area > 0]
    shannon = -sum(proportion * math.log(proportion) for proportion in proportions)
    evenness = shannon / math.log(len(proportions)) if len(proportions) > 1 else 0.0
    return {
        "resilience.age_class.shannon": shannon,
        "resilience.age_class.evenness": evenness,
        "resilience.age_class.count": float(len(proportions)),
    }


def fragmentation_metrics(
    disturbed_blocks: Sequence[int] | set[int],
    edges: Sequence[tuple[int, int, float]],
    block_area: Mapping[int, float],
    *,
    patch_breaks: Sequence[float] = RESILIENCE_PATCH_BREAKS,
) -> dict[str, float]:
    """Compute current-year opening fragmentation from existing patch metrics.

    Parameters
    ----------
    disturbed_blocks : sequence or set of int
        Blocks treated in the current year.
    edges : sequence of (int, int, float)
        Topology edges.
    block_area : mapping of int to float
        Block areas in hectares.
    patch_breaks : sequence of float, optional
        Patch size-class upper bounds.

    Returns
    -------
    dict of str to float
        Patch count, mean area, largest area, and treated area.
    """
    pairs = [(int(source), int(target)) for source, target, *_rest in edges]
    metrics = patch_metrics(disturbed_blocks, pairs, block_area, patch_breaks)
    area = float(sum(block_area.get(block, 0.0) for block in disturbed_blocks))
    return {
        "resilience.fragmentation.patch_count": float(metrics["patch_count"]),
        "resilience.fragmentation.mean_patch_area": float(metrics["mean_patch_area"]),
        "resilience.fragmentation.largest_patch_area": float(metrics["max_patch_area"]),
        "resilience.fragmentation.area": area,
    }


def compute_resilience(
    fragment_ages: Sequence[tuple[float, float]],
    edges: Sequence[tuple[int, int, float]],
    block_area: Mapping[int, float],
    *,
    untreated_blocks: Sequence[int] | set[int],
    disturbed_blocks: Sequence[int] | set[int] = (),
    age_class_width: float = RESILIENCE_AGE_CLASS_WIDTH,
    patch_breaks: Sequence[float] = RESILIENCE_PATCH_BREAKS,
) -> dict[str, float]:
    """Compute all resilience metrics for one simulation offset.

    Parameters
    ----------
    fragment_ages : sequence of (float, float)
        ``(age, area_ha)`` for every fragment.
    edges : sequence of (int, int, float)
        Topology edges.
    block_area : mapping of int to float
        Block areas in hectares.
    untreated_blocks : sequence or set of int
        Blocks not yet treated (cumulative).
    disturbed_blocks : sequence or set of int, optional
        Blocks treated in the current year.
    age_class_width : float, optional
        Age-class width in years.
    patch_breaks : sequence of float, optional
        Opening-patch size-class upper bounds.

    Returns
    -------
    dict of str to float
        The connectivity, age-class, and fragmentation accounts.
    """
    result = connectivity_metrics(untreated_blocks, edges, block_area)
    result.update(age_class_diversity(fragment_ages, age_class_width=age_class_width))
    result.update(
        fragmentation_metrics(disturbed_blocks, edges, block_area, patch_breaks=patch_breaks)
    )
    return result


def write_resilience_metadata(metadata: ResilienceMetadata, path: Path) -> None:
    """Write resilience metadata to a JSON file.

    Parameters
    ----------
    metadata : ResilienceMetadata
        Definitions and provenance.
    path : Path
        Destination JSON.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def resilience_report(
    values: pd.DataFrame,
    metadata: Mapping[str, object] | None = None,
) -> pd.DataFrame:
    """Summarize resilience accounts for ``report_resilience.csv``.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value``.
    metadata : mapping or None, optional
        Resilience metadata for definitions and caveat.

    Returns
    -------
    pandas.DataFrame
        Baseline, final, change, total, mean, peak, unit, semantics, definition,
        and caveat per account.
    """
    columns = [
        "account",
        "baseline",
        "final",
        "change",
        "pct_change",
        "total",
        "mean",
        "peak",
        "unit",
        "semantics",
        "definition",
        "caveat",
    ]
    if values.empty or "account" not in values.columns:
        return pd.DataFrame(columns=columns)
    frame = values[values["account"].astype(str).str.startswith(f"{RESILIENCE_ACCOUNT_PREFIX}.")]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    offsets = sorted(frame["offset"].astype(float).unique())
    baseline_offset = -1.0 if -1.0 in offsets else offsets[0]
    final_offset = offsets[-1]
    metadata = metadata or {}
    caveat = str(metadata.get("caveat", RESILIENCE_CAVEAT))
    metrics = metadata.get("metrics", METRIC_DEFINITIONS)
    definitions = metrics if isinstance(metrics, dict) else {}
    rows: list[dict[str, object]] = []
    for account in sorted(frame["account"].astype(str).unique()):
        series = frame[frame["account"].astype(str) == account]
        baseline = float(
            series.loc[series["offset"].astype(float) == baseline_offset, "value"].sum()
        )
        final = float(series.loc[series["offset"].astype(float) == final_offset, "value"].sum())
        change = final - baseline
        definition = definitions.get(account, {})
        if not isinstance(definition, dict):
            definition = {}
        semantics = str(definition.get("semantics", "level"))
        numbers = [float(value) for value in series["value"].tolist()]
        rows.append(
            {
                "account": account,
                "baseline": baseline,
                "final": final,
                "change": change,
                "pct_change": (
                    (100.0 * change / baseline) if semantics == "level" and baseline else None
                ),
                "total": sum(numbers) if semantics == "flow" else None,
                "mean": (sum(numbers) / len(numbers)) if numbers else 0.0,
                "peak": max(numbers) if numbers else 0.0,
                "unit": definition.get("unit", "index"),
                "semantics": semantics,
                "definition": definition.get("definition", ""),
                "caveat": caveat,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def compare_resilience_runs(
    run_a: str | Path,
    run_b: str | Path,
) -> pd.DataFrame:
    """Compare two runs' per-year resilience metrics.

    Parameters
    ----------
    run_a : str or Path
        First run directory (contains ``resilience_metrics.csv``).
    run_b : str or Path
        Second run directory.

    Returns
    -------
    pandas.DataFrame
        One row per account with each run's baseline, final, mean, total, peak,
        and change.

    Raises
    ------
    ResilienceError
        If either run lacks the metrics file.
    """
    frames: list[pd.DataFrame] = []
    for label, run in (("a", Path(run_a)), ("b", Path(run_b))):
        path = run / "resilience_metrics.csv"
        if not path.is_file():
            raise ResilienceError(f"resilience metrics do not exist: {path}")
        frame = pd.read_csv(path)
        frame["run"] = label
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    rows: list[dict[str, object]] = []
    for account in sorted(combined["account"].astype(str).unique()):
        row: dict[str, object] = {"account": account}
        for label in ("a", "b"):
            selected = combined[
                (combined["run"] == label) & (combined["account"].astype(str) == account)
            ]
            if selected.empty:
                row[f"run_{label}_baseline"] = None
                row[f"run_{label}_final"] = None
                row[f"run_{label}_mean"] = None
                row[f"run_{label}_change"] = None
                row[f"run_{label}_total"] = None
                row[f"run_{label}_peak"] = None
                continue
            values = selected["value"].astype(float)
            row[f"run_{label}_baseline"] = float(values.iloc[0])
            row[f"run_{label}_final"] = float(values.iloc[-1])
            row[f"run_{label}_mean"] = float(values.mean())
            row[f"run_{label}_change"] = float(values.iloc[-1] - values.iloc[0])
            row[f"run_{label}_total"] = float(values.sum())
            row[f"run_{label}_peak"] = float(values.max())
        definition = METRIC_DEFINITIONS.get(account, {})
        semantics = str(definition.get("semantics", "level"))
        row["unit"] = definition.get("unit", "index")
        row["semantics"] = semantics
        if semantics == "flow":
            a_value = row.get("run_a_total")
            b_value = row.get("run_b_total")
        else:
            a_value = row.get("run_a_change")
            b_value = row.get("run_b_change")
        if a_value is not None and b_value is not None:
            row["same_direction"] = (float(str(a_value)) >= 0) == (float(str(b_value)) >= 0)
        else:
            row["same_direction"] = None
        rows.append(row)
    return pd.DataFrame(rows)


__all__ = [
    "METRIC_DEFINITIONS",
    "RESILIENCE_ACCOUNT_PREFIX",
    "RESILIENCE_AGE_CLASS_WIDTH",
    "RESILIENCE_CAVEAT",
    "RESILIENCE_PATCH_BREAKS",
    "RESILIENCE_SCHEMA_VERSION",
    "ResilienceError",
    "ResilienceMetadata",
    "age_class_diversity",
    "compare_resilience_runs",
    "compute_resilience",
    "connectivity_metrics",
    "fragmentation_metrics",
    "resilience_report",
    "write_resilience_metadata",
]
