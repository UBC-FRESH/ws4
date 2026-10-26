"""The published forest-structure habitat index and its block accounts.

The index follows Coops et al. (2016), *A forest structure habitat index based
on airborne laser scanning data*, Ecological Indicators 67:346-357. It has three
equal components: P95 height, first-return cover above 1.37 m, and the standard
deviation of first-return heights above 1.37 m. The paper does not assign
weights; its published product is a three-band class composite. WS4 preserves
that definition and refuses to compute the index when a required metric is
missing.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

STRUCTURE_HABITAT_SCHEMA_VERSION = "ws4.structure_habitat.source.v1"
STRUCTURE_HABITAT_INDEX_VERSION = "coops-2016-v1"
STRUCTURE_HABITAT_ACCOUNT_PREFIX = "feature.SHI"
STRUCTURE_HABITAT_CITATION = (
    "Coops et al. 2016, A forest structure habitat index based on airborne laser "
    "scanning data, Ecological Indicators 67:346-357, "
    "doi:10.1016/j.ecolind.2016.02.057"
)
STRUCTURE_HABITAT_REQUIRED_METRICS: tuple[str, ...] = (
    "height_p95_m",
    "cover_gt_1_37_pct",
    "complexity_sd_gt_1_37_m",
)
STRUCTURE_HABITAT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "height_p95_m": (10.0, 20.0),
    "cover_gt_1_37_pct": (33.0, 66.0),
    "complexity_sd_gt_1_37_m": (3.0, 5.0),
}
STRUCTURE_HABITAT_CLASSES: tuple[str, ...] = ("low", "medium", "high")
CLASS_COLUMNS: dict[str, str] = {
    "height_p95_m": "height_class",
    "cover_gt_1_37_pct": "cover_class",
    "complexity_sd_gt_1_37_m": "complexity_class",
}


class StructureHabitatError(RuntimeError):
    """Raised when structure habitat metrics or provenance are unusable."""


@dataclass(frozen=True)
class StructureHabitatSource:
    """Provenance and definition for one structure habitat index run.

    Parameters
    ----------
    source_id : str
        Product or workflow identifier.
    source_version : str
        Required source version or vintage label.
    index_version : str
        Published index version; only ``coops-2016-v1`` is supported.
    citation : str
        Published source citation.
    required_metrics : tuple of str
        Metric names required for the index.
    thresholds : mapping of str to tuple of float
        Lower and upper class breaks for each component.
    boundary_rule : str
        How values exactly on a threshold are classified.
    weights : str
        Weight statement. The published index has no weights.
    notes : str or None
        Optional provenance note.
    """

    source_id: str
    source_version: str
    index_version: str
    citation: str
    required_metrics: tuple[str, ...]
    thresholds: Mapping[str, tuple[float, float]]
    boundary_rule: str
    weights: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-serializable source descriptor.

        Returns
        -------
        dict
            Source descriptor including its schema version.
        """
        return {
            "schema_version": STRUCTURE_HABITAT_SCHEMA_VERSION,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "index_version": self.index_version,
            "citation": self.citation,
            "required_metrics": list(self.required_metrics),
            "thresholds": {key: list(value) for key, value in self.thresholds.items()},
            "boundary_rule": self.boundary_rule,
            "weights": self.weights,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> StructureHabitatSource:
        """Validate and build a source descriptor.

        Parameters
        ----------
        payload : mapping
            A decoded structure habitat metadata object.

        Returns
        -------
        StructureHabitatSource
            The validated descriptor.

        Raises
        ------
        StructureHabitatError
            If the schema, index version, source version, or thresholds are invalid.
        """
        if payload.get("schema_version") != STRUCTURE_HABITAT_SCHEMA_VERSION:
            raise StructureHabitatError(
                f"structure habitat schema_version must be {STRUCTURE_HABITAT_SCHEMA_VERSION!r}"
            )
        index_version = str(payload.get("index_version", "")).strip()
        if index_version != STRUCTURE_HABITAT_INDEX_VERSION:
            raise StructureHabitatError(
                f"unsupported structure habitat index_version: {index_version!r}"
            )
        source_version = str(payload.get("source_version", "")).strip()
        if not source_version:
            raise StructureHabitatError("structure habitat source_version must not be empty")
        raw_thresholds = payload.get("thresholds")
        if not isinstance(raw_thresholds, dict):
            raise StructureHabitatError("structure habitat thresholds must be a mapping")
        thresholds: dict[str, tuple[float, float]] = {}
        for metric in STRUCTURE_HABITAT_REQUIRED_METRICS:
            raw = raw_thresholds.get(metric)
            if not isinstance(raw, list) or len(raw) != 2:
                raise StructureHabitatError(f"thresholds for {metric!r} must have two values")
            thresholds[metric] = (float(str(raw[0])), float(str(raw[1])))
        required = payload.get("required_metrics")
        if not isinstance(required, list):
            raise StructureHabitatError("structure habitat required_metrics must be a list")
        return cls(
            source_id=str(payload.get("source_id", "")),
            source_version=source_version,
            index_version=index_version,
            citation=str(payload.get("citation", STRUCTURE_HABITAT_CITATION)),
            required_metrics=tuple(str(item) for item in required),
            thresholds=thresholds,
            boundary_rule=str(
                payload.get(
                    "boundary_rule",
                    "A value exactly on a break is assigned to the lower class.",
                )
            ),
            weights=str(payload.get("weights", "Equal components; no weights.")),
            notes=None if payload.get("notes") is None else str(payload["notes"]),
        )


def _class_index(value: float, breaks: tuple[float, float], label: str) -> int:
    """Return 0, 1, or 2 for a value and its two class breaks."""
    if not math.isfinite(value):
        raise StructureHabitatError(f"{label} must be finite")
    if value <= breaks[0]:
        return 0
    if value <= breaks[1]:
        return 1
    return 2


def _class_label(index: int) -> str:
    """Return the human-readable class label."""
    return STRUCTURE_HABITAT_CLASSES[index]


def compute_structure_habitat(metrics: pd.DataFrame) -> pd.DataFrame:
    """Compute the published three-component index from block metrics.

    The input must have ``block_id`` and exactly the required semantics:
    ``height_p95_m``, ``cover_gt_1_37_pct``, and
    ``complexity_sd_gt_1_37_m``. Missing values are an error; they are never
    imputed. Height and complexity are in metres, cover is a percentage.

    Parameters
    ----------
    metrics : pandas.DataFrame
        Block-level metrics.

    Returns
    -------
    pandas.DataFrame
        The input rows with component classes, a 0-26 ``class_code``, and a
        ``class_label`` such as ``H1-C2-K0``.

    Raises
    ------
    StructureHabitatError
        If a required column, unique block id, or finite value is missing.
    """
    if "block_id" not in metrics.columns:
        raise StructureHabitatError("structure habitat metrics need a block_id column")
    missing = [metric for metric in STRUCTURE_HABITAT_REQUIRED_METRICS if metric not in metrics]
    if missing:
        raise StructureHabitatError("structure habitat metrics are missing: " + ", ".join(missing))
    result = metrics.copy()
    if result["block_id"].duplicated().any():
        raise StructureHabitatError("structure habitat metrics have duplicate block_id values")
    for metric in STRUCTURE_HABITAT_REQUIRED_METRICS:
        result[metric] = pd.to_numeric(result[metric], errors="coerce")
    invalid = result.loc[~np.isfinite(result[list(STRUCTURE_HABITAT_REQUIRED_METRICS)]).all(axis=1)]
    if not invalid.empty:
        blocks = ", ".join(str(value) for value in invalid["block_id"].tolist()[:10])
        raise StructureHabitatError(
            f"structure habitat metrics are missing or non-finite: {blocks}"
        )
    if (result["height_p95_m"] < 0).any():
        raise StructureHabitatError("height_p95_m must be non-negative")
    if ((result["cover_gt_1_37_pct"] < 0) | (result["cover_gt_1_37_pct"] > 100)).any():
        raise StructureHabitatError("cover_gt_1_37_pct must be between 0 and 100")
    if (result["complexity_sd_gt_1_37_m"] < 0).any():
        raise StructureHabitatError("complexity_sd_gt_1_37_m must be non-negative")

    class_columns: list[str] = []
    for metric, class_column in CLASS_COLUMNS.items():
        breaks = STRUCTURE_HABITAT_THRESHOLDS[metric]
        result[class_column] = [
            _class_index(float(value), breaks, metric) for value in result[metric]
        ]
        class_columns.append(class_column)
    result["class_code"] = (
        result["height_class"] * 9 + result["cover_class"] * 3 + result["complexity_class"]
    ).astype(int)
    result["class_label"] = [
        f"H{height}-C{cover}-K{complexity}"
        for height, cover, complexity in zip(
            result["height_class"], result["cover_class"], result["complexity_class"], strict=True
        )
    ]
    return result


def diagnose_metrics(columns: Sequence[str]) -> dict[str, object]:
    """Report whether a table has the exact metrics the index requires.

    CHM fields are reported as proxies, never substituted silently. The caller
    must supply the published first-return metrics before the index is computed.

    Parameters
    ----------
    columns : sequence of str
        Column names available in a candidate metrics table.

    Returns
    -------
    dict[str, object]
        ``index_computable``, ``present``, ``missing``, ``proxies``, and
        ``message``.
    """
    available = {str(column) for column in columns}
    present = [metric for metric in STRUCTURE_HABITAT_REQUIRED_METRICS if metric in available]
    missing = [metric for metric in STRUCTURE_HABITAT_REQUIRED_METRICS if metric not in available]
    proxies: dict[str, str] = {}
    if "height_p95_m" not in available and "chm_p95" in available:
        proxies["height_p95_m"] = "chm_p95 is CHM-derived, not first-return P95"
    if "cover_gt_1_37_pct" not in available and "chm_cover_ge_2" in available:
        proxies["cover_gt_1_37_pct"] = "chm_cover_ge_2 uses a 2 m threshold, not 1.37 m"
    if "complexity_sd_gt_1_37_m" not in available:
        proxies["complexity_sd_gt_1_37_m"] = (
            "no first-return height standard deviation field is available"
            if "chm_p95" in available
            else "no source field is available"
        )
    message = (
        "Structure habitat index is computable."
        if not missing
        else (
            "Structure habitat index is not computable; missing required metrics: "
            + ", ".join(missing)
            + ". Proxies are reported but not substituted."
        )
    )
    return {
        "index_computable": not missing,
        "present": present,
        "missing": missing,
        "proxies": proxies,
        "message": message,
    }


def diagnose_femic_canopy_structure(payload: Mapping[str, object]) -> dict[str, object]:
    """Report index coverage for a FEMIC ``canopy_structure.json`` document.

    Parameters
    ----------
    payload : mapping
        Decoded FEMIC canopy structure summary.

    Returns
    -------
    dict[str, object]
        The same coverage report as :func:`diagnose_metrics`.
    """
    columns: list[str] = []
    height = payload.get("height_metrics")
    if isinstance(height, dict) and "p95_m" in height:
        columns.append("chm_p95")
    cover = payload.get("cover_fractions")
    if isinstance(cover, dict) and "ge_2m" in cover:
        columns.append("chm_cover_ge_2")
    return diagnose_metrics(columns)


def make_source(
    *,
    source_id: str,
    source_version: str,
    notes: str | None = None,
) -> StructureHabitatSource:
    """Build the fixed published-index descriptor.

    Parameters
    ----------
    source_id : str
        Product or workflow identifier.
    source_version : str
        Required source version or vintage label.
    notes : str or None, optional
        Optional provenance note.

    Returns
    -------
    StructureHabitatSource
        The validated descriptor.
    """
    if not source_version.strip():
        raise StructureHabitatError("structure habitat source_version must not be empty")
    return StructureHabitatSource(
        source_id=source_id,
        source_version=source_version,
        index_version=STRUCTURE_HABITAT_INDEX_VERSION,
        citation=STRUCTURE_HABITAT_CITATION,
        required_metrics=STRUCTURE_HABITAT_REQUIRED_METRICS,
        thresholds=STRUCTURE_HABITAT_THRESHOLDS,
        boundary_rule="A value exactly on a break is assigned to the lower class.",
        weights="Equal components; the published product has no weights.",
        notes=notes,
    )


def write_structure_habitat(
    stand: pd.DataFrame,
    source: StructureHabitatSource,
    output_csv: str | Path,
    metadata_json: str | Path,
) -> None:
    """Write the stand table and source metadata.

    Parameters
    ----------
    stand : pandas.DataFrame
        Output of :func:`compute_structure_habitat`.
    source : StructureHabitatSource
        Index provenance.
    output_csv : str or Path
        Destination stand table.
    metadata_json : str or Path
        Destination metadata JSON.
    """
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    stand.to_csv(output, index=False)
    metadata = Path(metadata_json)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(source.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


@dataclass(frozen=True)
class StructureHabitatAccount:
    """Block structure metrics and provenance used by the simulator.

    Parameters
    ----------
    values : pandas.DataFrame
        Computed stand table with ``block_id``, components, and classes.
    source : StructureHabitatSource
        Index provenance.
    """

    values: pd.DataFrame
    source: StructureHabitatSource

    def validate(self, block_area: Mapping[int, float]) -> None:
        """Require a structure row for every dataset block.

        Parameters
        ----------
        block_area : mapping of int to float
            Block areas in hectares.

        Raises
        ------
        StructureHabitatError
            If a block is missing or a value is outside its valid range.
        """
        missing = sorted(set(block_area) - set(self.values["block_id"].astype(int)))
        if missing:
            preview = ", ".join(str(block) for block in missing[:10])
            raise StructureHabitatError(
                f"structure habitat values are missing for {len(missing)} blocks: {preview}"
            )
        if len(self.values) != self.values["block_id"].nunique():
            raise StructureHabitatError("structure habitat values have duplicate block ids")

    def account_values(
        self,
        block_area: Mapping[int, float],
        *,
        excluded_blocks: set[int] | frozenset[int] = frozenset(),
    ) -> dict[str, float]:
        """Return landscape component means and class areas.

        Parameters
        ----------
        block_area : mapping of int to float
            Block areas in hectares.
        excluded_blocks : set of int, optional
            Treated blocks removed from the account.

        Returns
        -------
        dict of str to float
            Component means, class areas, and surviving area.
        """
        self.validate(block_area)
        frame = self.values.copy()
        frame["block_id"] = frame["block_id"].astype(int)
        frame = frame[~frame["block_id"].isin(excluded_blocks)]
        frame["_area"] = frame["block_id"].map(block_area).astype(float)
        area = float(frame["_area"].sum())
        result: dict[str, float] = {}
        units = {
            "height_p95_m": "height",
            "cover_gt_1_37_pct": "cover",
            "complexity_sd_gt_1_37_m": "complexity",
        }
        for metric, name in units.items():
            result[f"{STRUCTURE_HABITAT_ACCOUNT_PREFIX}.{name}"] = (
                float((frame[metric] * frame["_area"]).sum() / area) if area > 0 else 0.0
            )
        result[f"{STRUCTURE_HABITAT_ACCOUNT_PREFIX}.area"] = area
        for metric, class_column in CLASS_COLUMNS.items():
            name = units[metric]
            for index, label in enumerate(STRUCTURE_HABITAT_CLASSES):
                selected = frame[frame[class_column] == index]
                result[f"{STRUCTURE_HABITAT_ACCOUNT_PREFIX}.{name}.{label}_area"] = float(
                    selected["_area"].sum()
                )
        return result

    def write(self, out_dir: Path, block_area: Mapping[int, float]) -> None:
        """Write the run-local stand table, metadata, and landscape snapshot.

        Parameters
        ----------
        out_dir : Path
            The run directory.
        block_area : mapping of int to float
            Block areas in hectares.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.values.to_csv(out_dir / "structure_habitat_values.csv", index=False)
        (out_dir / "structure_habitat_metadata.json").write_text(
            json.dumps(self.source.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        landscape = landscape_table(self.values, block_area)
        landscape.to_csv(out_dir / "structure_habitat_landscape.csv", index=False)


def landscape_table(
    stand: pd.DataFrame,
    block_area: Mapping[int, float],
    *,
    excluded_blocks: set[int] | frozenset[int] = frozenset(),
) -> pd.DataFrame:
    """Build a landscape summary of component means and class areas.

    Parameters
    ----------
    stand : pandas.DataFrame
        Computed stand table.
    block_area : mapping of int to float
        Block areas in hectares.
    excluded_blocks : set of int, optional
        Treated blocks removed from the summary.

    Returns
    -------
    pandas.DataFrame
        Rows with ``component``, ``value``, ``unit``, and ``class``.
    """
    frame = stand.copy()
    frame["block_id"] = frame["block_id"].astype(int)
    frame = frame[~frame["block_id"].isin(excluded_blocks)]
    frame["_area"] = frame["block_id"].map(block_area).astype(float)
    area = float(frame["_area"].sum())
    rows: list[dict[str, object]] = []
    for metric, name in (
        ("height_p95_m", "height"),
        ("cover_gt_1_37_pct", "cover"),
        ("complexity_sd_gt_1_37_m", "complexity"),
    ):
        unit = "%" if metric == "cover_gt_1_37_pct" else "m"
        mean = float((frame[metric] * frame["_area"]).sum() / area) if area > 0 else 0.0
        rows.append({"component": name, "value": mean, "unit": unit, "class": "all"})
        class_column = CLASS_COLUMNS[metric]
        for index, label in enumerate(STRUCTURE_HABITAT_CLASSES):
            class_area = float(frame.loc[frame[class_column] == index, "_area"].sum())
            rows.append(
                {
                    "component": name,
                    "value": (100.0 * class_area / area) if area > 0 else 0.0,
                    "unit": "% area",
                    "class": label,
                }
            )
    return pd.DataFrame(rows, columns=["component", "value", "unit", "class"])


def read_structure_habitat(
    values_path: str | Path,
    metadata_path: str | Path,
) -> StructureHabitatAccount:
    """Read a saved structure habitat stand table and provenance.

    Parameters
    ----------
    values_path : str or Path
        Computed stand table.
    metadata_path : str or Path
        Structure habitat metadata JSON.

    Returns
    -------
    StructureHabitatAccount
        The stand table and source.

    Raises
    ------
    StructureHabitatError
        If either file is missing or the table lacks required metrics.
    """
    values_file = Path(values_path)
    metadata_file = Path(metadata_path)
    if not values_file.is_file():
        raise StructureHabitatError(f"structure habitat values do not exist: {values_file}")
    if not metadata_file.is_file():
        raise StructureHabitatError(f"structure habitat metadata do not exist: {metadata_file}")
    source = StructureHabitatSource.from_dict(json.loads(metadata_file.read_text(encoding="utf-8")))
    frame = pd.read_csv(values_file)
    missing = [metric for metric in STRUCTURE_HABITAT_REQUIRED_METRICS if metric not in frame]
    if missing:
        raise StructureHabitatError("structure habitat table is missing: " + ", ".join(missing))
    return StructureHabitatAccount(values=compute_structure_habitat(frame), source=source)


def structure_habitat_report(
    values: pd.DataFrame,
    source: Mapping[str, object] | None = None,
) -> pd.DataFrame:
    """Summarize structure habitat accounts for ``report_structure_habitat.csv``.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value``.
    source : mapping or None, optional
        Structure habitat source metadata.

    Returns
    -------
    pandas.DataFrame
        Baseline, final, change, unit, source fields, and the index caveat.
    """
    columns = [
        "account",
        "baseline",
        "final",
        "change",
        "pct_change",
        "unit",
        "source_id",
        "source_version",
        "index_version",
        "citation",
        "caveat",
    ]
    if values.empty or "account" not in values.columns:
        return pd.DataFrame(columns=columns)
    frame = values[
        values["account"].astype(str).str.startswith(f"{STRUCTURE_HABITAT_ACCOUNT_PREFIX}.")
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    offsets = sorted(frame["offset"].astype(float).unique())
    baseline_offset = -1.0 if -1.0 in offsets else offsets[0]
    final_offset = offsets[-1]
    source = source or {}
    caveat = (
        "The Coops et al. (2016) index is a three-component structural descriptor, "
        "not a species observation. The published product has no weights. Missing "
        "ALS metrics are reported, never imputed."
    )
    rows: list[dict[str, object]] = []
    for account in sorted(frame["account"].astype(str).unique()):
        series = frame[frame["account"].astype(str) == account]
        baseline = float(
            series.loc[series["offset"].astype(float) == baseline_offset, "value"].sum()
        )
        final = float(series.loc[series["offset"].astype(float) == final_offset, "value"].sum())
        change = final - baseline
        if account.endswith("_area") or account.endswith(".area"):
            unit = "ha"
        elif account.endswith(".height") or account.endswith(".complexity"):
            unit = "m"
        elif account.endswith(".cover"):
            unit = "%"
        else:
            unit = "index"
        rows.append(
            {
                "account": account,
                "baseline": baseline,
                "final": final,
                "change": change,
                "pct_change": (100.0 * change / baseline) if baseline else None,
                "unit": unit,
                "source_id": source.get("source_id"),
                "source_version": source.get("source_version"),
                "index_version": source.get("index_version"),
                "citation": source.get("citation"),
                "caveat": caveat,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _pearson(x: pd.Series, y: pd.Series) -> float | None:
    """Return Pearson's r, or None when it is undefined."""
    if len(x) < 2 or float(x.std(ddof=0)) == 0.0 or float(y.std(ddof=0)) == 0.0:
        return None
    return float(np.corrcoef(x.to_numpy(dtype=float), y.to_numpy(dtype=float))[0, 1])


def _spearman(x: pd.Series, y: pd.Series) -> float | None:
    """Return Spearman's rho via ranks, or None when it is undefined."""
    return _pearson(x.rank(method="average"), y.rank(method="average"))


def compare_to_dhi(
    structure: pd.DataFrame,
    dhi: pd.DataFrame,
    *,
    dhi_bands: Sequence[str] = ("cum", "min", "var"),
) -> pd.DataFrame:
    """Compare structure components with DHI bands on common blocks.

    The comparison is exploratory and reports the sample size. It does not run
    a significance test and does not claim a causal relationship.

    Parameters
    ----------
    structure : pandas.DataFrame
        Stand table with ``block_id`` and the three required metrics.
    dhi : pandas.DataFrame
        DHI values with ``block_id`` and band columns.
    dhi_bands : sequence of str, optional
        DHI band columns to compare.

    Returns
    -------
    pandas.DataFrame
        One row per structure metric and DHI band with ``n``, Pearson's r,
        Spearman's rho, direction, strength, and a note.

    Raises
    ------
    StructureHabitatError
        If required columns are missing.
    """
    missing_structure = [
        metric for metric in STRUCTURE_HABITAT_REQUIRED_METRICS if metric not in structure
    ]
    if "block_id" not in structure or missing_structure:
        raise StructureHabitatError(
            "structure comparison table is missing: " + ", ".join(["block_id", *missing_structure])
        )
    if "block_id" not in dhi:
        raise StructureHabitatError("DHI comparison table needs block_id")
    missing_bands = [band for band in dhi_bands if band not in dhi]
    if missing_bands:
        raise StructureHabitatError(
            "DHI comparison table is missing bands: " + ", ".join(missing_bands)
        )
    merged = structure.merge(dhi, on="block_id", how="inner", suffixes=("", "_dhi"))
    rows: list[dict[str, object]] = []
    for metric in STRUCTURE_HABITAT_REQUIRED_METRICS:
        for band in dhi_bands:
            pairs = merged[[metric, band]].dropna()
            n = len(pairs)
            pearson = _pearson(pairs[metric], pairs[band])
            spearman = _spearman(pairs[metric], pairs[band])
            if n < 3 or spearman is None:
                direction = "unavailable"
                strength = "unavailable"
            else:
                strength = (
                    "strong"
                    if abs(spearman) >= 0.6
                    else "moderate"
                    if abs(spearman) >= 0.3
                    else "weak"
                )
                direction = (
                    "positive" if spearman >= 0.3 else "negative" if spearman <= -0.3 else "none"
                )
            rows.append(
                {
                    "structure_metric": metric,
                    "dhi_band": band,
                    "n": n,
                    "pearson_r": pearson,
                    "spearman_r": spearman,
                    "direction": direction,
                    "strength": strength,
                    "note": (
                        "exploratory; no significance test"
                        if n >= 3
                        else "insufficient common blocks (n < 3)"
                    ),
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "structure_metric",
            "dhi_band",
            "n",
            "pearson_r",
            "spearman_r",
            "direction",
            "strength",
            "note",
        ],
    )


__all__ = [
    "CLASS_COLUMNS",
    "STRUCTURE_HABITAT_ACCOUNT_PREFIX",
    "STRUCTURE_HABITAT_CITATION",
    "STRUCTURE_HABITAT_CLASSES",
    "STRUCTURE_HABITAT_INDEX_VERSION",
    "STRUCTURE_HABITAT_REQUIRED_METRICS",
    "STRUCTURE_HABITAT_SCHEMA_VERSION",
    "STRUCTURE_HABITAT_THRESHOLDS",
    "StructureHabitatAccount",
    "StructureHabitatError",
    "StructureHabitatSource",
    "compare_to_dhi",
    "compute_structure_habitat",
    "diagnose_femic_canopy_structure",
    "diagnose_metrics",
    "landscape_table",
    "make_source",
    "read_structure_habitat",
    "structure_habitat_report",
    "write_structure_habitat",
]
