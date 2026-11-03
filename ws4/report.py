"""Accounts and reporting over a run's values.

The simulator writes account values (and product values). This module turns them into
reports: a per-account summary, a ratio account, and a target-status table that says
whether each target was met.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .opt.objective import (
    Target,
    flow_series,
    normalization_scale,
    penalty,
    period_value,
    raw_penalty,
)
from .resilience import resilience_report
from .structure_habitat import structure_habitat_report

#: Schema name for the report provenance sidecar.
REPORT_PROVENANCE_SCHEMA = "ws4.report.provenance.v1"

#: Name of the sidecar written beside the report tables.
REPORT_PROVENANCE_NAME = "report_provenance.json"

#: Run-local metadata files that shape the report tables and are hashed when present.
SOURCE_METADATA_NAMES = (
    "dhi_metadata.json",
    "structure_habitat_metadata.json",
    "resilience_metadata.json",
)


def _by_offset(values: pd.DataFrame) -> dict[tuple[int, str], float]:
    """Index values by (offset, account)."""
    return {
        (int(float(str(row.offset))), str(row.account)): float(str(row.value))
        for row in values.itertuples(index=False)
    }


def account_summary(values: pd.DataFrame) -> pd.DataFrame:
    """Summarize each account across the years.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values, with ``year``, ``account``, and ``value`` columns.

    Returns
    -------
    pandas.DataFrame
        One row per account with ``min``, ``max``, ``mean``, and ``final`` value.
    """
    if values.empty:
        return pd.DataFrame(columns=["account", "min", "max", "mean", "final"])
    grouped = values.groupby("account")["value"]
    summary = grouped.agg(["min", "max", "mean"]).reset_index()
    final = (
        values.sort_values("offset").groupby("account")["value"].last().reset_index(name="final")
    )
    return summary.merge(final, on="account")


def ratio_account(
    values: pd.DataFrame, numerator: str, denominator: str, name: str
) -> pd.DataFrame:
    """Return a ratio account over the years.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values.
    numerator : str
        The numerator account.
    denominator : str
        The denominator account.
    name : str
        The name of the ratio account.

    Returns
    -------
    pandas.DataFrame
        The ratio account values, with ``year``, ``account``, and ``value`` columns.
    """
    index: Mapping[tuple[int, str], float] = _by_offset(values)
    offsets = sorted({offset for offset, _ in index})
    rows: list[dict[str, object]] = []
    for offset in offsets:
        top = index.get((offset, numerator), 0.0)
        bottom = index.get((offset, denominator), 0.0)
        rows.append({"offset": offset, "account": name, "value": (top / bottom) if bottom else 0.0})
    return pd.DataFrame(rows, columns=["offset", "account", "value"])


def target_kind(target: Target) -> str:
    """Return the target's reporting kind.

    Parameters
    ----------
    target : Target
        The target.

    Returns
    -------
    str
        ``"level"``, ``"flow.even"``, or ``"flow.ndy"``.
    """
    return f"flow.{target.flow}" if target.flow else "level"


def ending_inventory(values: pd.DataFrame) -> pd.DataFrame:
    """Return the final feature-inventory values.

    The ending inventory is the state at the last offset for accounts whose name starts
    with ``feature.``. A ``product.`` account is harvested output, not closing inventory.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value``.

    Returns
    -------
    pandas.DataFrame
        ``offset``, ``account``, and ``value`` at the final offset. Empty with those
        columns when there are no feature accounts.
    """
    columns = ["offset", "account", "value"]
    if values.empty or "offset" not in values.columns:
        return pd.DataFrame(columns=columns)
    final = int(float(values["offset"].astype(float).max()))
    frame = values[
        (values["offset"].astype(float) == final)
        & values["account"].astype(str).str.startswith("feature.")
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    ending = frame.groupby("account", sort=True)["value"].sum().reset_index().assign(offset=final)
    return ending[columns]


def _status(value: float, target: Target) -> str:
    """Return whether a value is within a target's bounds.

    Parameters
    ----------
    value : float
        The target's value for the period.
    target : Target
        The target.

    Returns
    -------
    str
        ``met``, ``below`` or ``above``.
    """
    if target.minimum is not None and value < target.minimum:
        return "below"
    if target.maximum is not None and value > target.maximum:
        return "above"
    return "met"


def target_status(values: pd.DataFrame, targets: list[Target]) -> pd.DataFrame:
    """Report each target's value, bounds, and whether it was met.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values.
    targets : list of Target
        The targets.

    Returns
    -------
    pandas.DataFrame
        One row per target with ``account``, ``year``, ``value``, ``minimum``,
        ``maximum``, ``raw_penalty``, ``penalty`` (normalized), ``scale``,
        ``normalization``, ``priority``, and ``status``.
    """
    index = _by_offset(values)
    horizon = max((offset for offset, _ in index), default=-1) + 1
    rows: list[dict[str, object]] = []
    for target in targets:
        if not target.active:
            rows.append(
                {
                    "account": target.account,
                    "period": target.period,
                    "year": target.year,
                    "value": 0.0,
                    "minimum": target.minimum,
                    "maximum": target.maximum,
                    "raw_penalty": 0.0,
                    "penalty": 0.0,
                    "scale": normalization_scale(target),
                    "normalization": target.normalization,
                    "priority": target.priority,
                    "kind": target_kind(target),
                    "status": "inactive",
                }
            )
            continue
        if target.flow:
            # A flow target constrains the shape of a profile, so its report is the series itself:
            # one row per period, exactly as the reference reports it, with a zero for the period an
            # even-flow comparison is made against. Reporting the single value a level target would
            # have made a flow target look met while the search paid for it.
            for end_offset, value in sorted(flow_series(index, target, horizon).items()):
                width = max(1, target.period_width)
                rows.append(
                    {
                        "account": target.account,
                        "period": (end_offset + 1) // width
                        if (end_offset + 1) % width == 0
                        else None,
                        "offset": end_offset,
                        "year": end_offset + 1,
                        "value": value,
                        "minimum": target.minimum,
                        "maximum": target.maximum,
                        "raw_penalty": raw_penalty(value, target),
                        "penalty": penalty(value, target),
                        "scale": normalization_scale(target),
                        "normalization": target.normalization,
                        "priority": target.priority,
                        "kind": target_kind(target),
                        "status": _status(value, target),
                    }
                )
            continue
        # A target is priced over its period exactly as the objective prices it: the window's sum
        # for an accumulating account, the period's end value for a level. Reading one year of it
        # reported a periodic target as unmet — with a penalty the search never applied — whenever
        # the period's later years carried it over the line.
        value = period_value(index, target)
        status = _status(value, target)
        rows.append(
            {
                "account": target.account,
                "period": target.period,
                "year": target.year,
                "value": value,
                "minimum": target.minimum,
                "maximum": target.maximum,
                "raw_penalty": raw_penalty(value, target),
                "penalty": penalty(value, target),
                "scale": normalization_scale(target),
                "normalization": target.normalization,
                "priority": target.priority,
                "kind": target_kind(target),
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def dhi_report(
    values: pd.DataFrame,
    source: Mapping[str, object] | None = None,
) -> pd.DataFrame:
    """Summarize DHI accounts for the report directory.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value``.
    source : mapping or None, optional
        DHI source metadata from ``dhi_metadata.json``.

    Returns
    -------
    pandas.DataFrame
        One row per DHI account with baseline, final, change, unit, source
        provenance, and the interpretation caveat.
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
        "year_range",
        "resolution_m",
        "crs",
        "licence",
        "caveat",
    ]
    if values.empty or "account" not in values.columns:
        return pd.DataFrame(columns=columns)
    frame = values[values["account"].astype(str).str.startswith("feature.DHI.")]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    offsets = sorted(frame["offset"].astype(float).unique())
    baseline_offset = -1.0 if -1.0 in offsets else offsets[0]
    final_offset = offsets[-1]
    source = source or {}
    caveat = (
        "DHI is a coarse productivity surrogate, not a species observation or a habitat "
        "suitability model. The account removes a block when the schedule treats it and does "
        "not model regrowth, recovery, or species response."
    )
    rows: list[dict[str, object]] = []
    for account in sorted(frame["account"].astype(str).unique()):
        series = frame[frame["account"].astype(str) == account]
        baseline = float(
            series.loc[series["offset"].astype(float) == baseline_offset, "value"].sum()
        )
        final = float(series.loc[series["offset"].astype(float) == final_offset, "value"].sum())
        change = final - baseline
        if account.endswith(".mean"):
            unit = "index"
        elif account.endswith(".area"):
            unit = "ha"
        else:
            unit = "index_ha"
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
                "year_range": source.get("year_range"),
                "resolution_m": source.get("resolution_m"),
                "crs": source.get("crs"),
                "licence": source.get("licence"),
                "caveat": caveat,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _sha256(path: Path) -> str | None:
    """Return a file's SHA-256 digest, or None when it cannot be read.

    Parameters
    ----------
    path : Path
        The file to hash.

    Returns
    -------
    str or None
        The lowercase hexadecimal digest, or None when the file is missing or unreadable.
    """
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _json_mapping(path: Path) -> tuple[dict[str, object] | None, str | None]:
    """Read a JSON object, returning a reason instead of raising on bad input.

    Parameters
    ----------
    path : Path
        The JSON file to read.

    Returns
    -------
    tuple of (dict or None, str or None)
        The decoded mapping and an error reason, or ``(None, reason)`` when the file is
        missing, unreadable, not valid JSON, or not a JSON object.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None, "cannot read file"
    except ValueError:
        return None, "not valid JSON"
    if not isinstance(raw, dict):
        return None, "not a JSON object"
    return raw, None


def _file_record(directory: Path, name: str, *, status: str = "hashed") -> dict[str, object]:
    """Return a report or metadata file record with its size and digest.

    Parameters
    ----------
    directory : Path
        The directory that holds the file.
    name : str
        The file name to record.
    status : str, optional
        The status to record when the file is readable.

    Returns
    -------
    dict of str to object
        ``name``, ``bytes``, ``sha256``, and ``status``. A missing or unreadable file
        keeps its name and reports a null size and digest.
    """
    path = directory / name
    try:
        size = path.stat().st_size
    except OSError:
        return {"name": name, "bytes": None, "sha256": None, "status": "missing"}
    digest = _sha256(path)
    if digest is None:
        return {"name": name, "bytes": size, "sha256": None, "status": "unreadable"}
    return {"name": name, "bytes": size, "sha256": digest, "status": status}


def _dataset_from_run_records(report_dir: Path) -> dict[str, object] | None:
    """Return a dataset identity from an existing run record, when one is present.

    Parameters
    ----------
    report_dir : Path
        The report or run directory.

    Returns
    -------
    dict of str to object or None
        A compact dataset identity, or None when no usable record exists.
    """
    for name in ("run_manifest.json", "data_quality.json"):
        path = report_dir / name
        if not path.is_file():
            continue
        payload, _error = _json_mapping(path)
        if payload is None:
            continue
        identity: dict[str, object] = {}
        raw_dataset = payload.get("dataset")
        if name == "run_manifest.json" and isinstance(raw_dataset, Mapping):
            raw_path = raw_dataset.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                identity["id"] = Path(raw_path).name
            reference = raw_dataset.get("reference")
            if isinstance(reference, Mapping):
                for key in ("schema_version", "manifest_sha256"):
                    if reference.get(key) is not None:
                        identity[key] = reference[key]
        elif name == "data_quality.json":
            if isinstance(raw_dataset, str) and raw_dataset.strip():
                identity["id"] = Path(raw_dataset).name
            if payload.get("manifest_sha256") is not None:
                identity["manifest_sha256"] = payload["manifest_sha256"]
        if identity:
            return identity
    return None


def _dataset_identity(report_dir: Path, dataset: Path | None) -> dict[str, object] | None:
    """Return the dataset identifier and manifest digest when they are available.

    Parameters
    ----------
    report_dir : Path
        The report or run directory, used to recover a previously written run record.
    dataset : Path or None
        The compiled dataset directory, when the caller knows it.

    Returns
    -------
    dict of str to object or None
        ``id``, ``manifest_sha256``, ``schema_version``, and a status where available.
    """
    if dataset is None:
        return _dataset_from_run_records(report_dir)
    dataset_dir = Path(dataset)
    identity: dict[str, object] = {"id": dataset_dir.name}
    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.is_file():
        identity["status"] = "missing"
        return identity
    payload, error = _json_mapping(manifest_path)
    if payload is None:
        identity["status"] = "invalid"
        if error is not None:
            identity["error"] = error
        return identity
    identity["status"] = "ok"
    identity["schema_version"] = payload.get("schema_version")
    identity["manifest_sha256"] = _sha256(manifest_path)
    sources = payload.get("sources")
    if isinstance(sources, list):
        identity["sources"] = sources
    return identity


def _uncertainty(
    metadata: Sequence[tuple[str, Mapping[str, object]]],
) -> dict[str, object]:
    """Return the uncertainty statement carried by the source metadata.

    Parameters
    ----------
    metadata : sequence of (str, mapping)
        The decoded source metadata files, in report order.

    Returns
    -------
    dict of str to object
        ``status``, ``source``, and ``statement``. The status is ``not_stated`` unless a
        source metadata file explicitly carries uncertainty.
    """
    for name, payload in metadata:
        raw = payload.get("uncertainty")
        if isinstance(raw, Mapping):
            status = raw.get("status", raw.get("level", "stated"))
            statement = raw.get("statement", raw.get("notes"))
            return {
                "status": str(status) if str(status).strip() else "stated",
                "source": name,
                "statement": str(statement) if statement is not None else None,
            }
        if isinstance(raw, str) and raw.strip():
            return {"status": "stated", "source": name, "statement": raw.strip()}
        raw_status = payload.get("uncertainty_status")
        if isinstance(raw_status, str) and raw_status.strip():
            return {"status": raw_status.strip(), "source": name, "statement": None}
    return {"status": "not_stated", "source": None, "statement": None}


def build_report_provenance(
    report_dir: Path,
    report_names: Sequence[str],
    *,
    dataset: Path | None = None,
    run_id: str | None = None,
    generated_utc: str | None = None,
) -> dict[str, object]:
    """Build the provenance record for one report directory.

    Parameters
    ----------
    report_dir : Path
        The directory that holds the report files.
    report_names : sequence of str
        The report file names to hash.
    dataset : Path or None, optional
        The compiled dataset directory, when the caller knows it.
    run_id : str or None, optional
        The run identifier; the report directory's name is used when omitted.
    generated_utc : str or None, optional
        A fixed ISO-8601 timestamp, for reproducible tests; the current UTC time is used
        when omitted.

    Returns
    -------
    dict of str to object
        The ``ws4.report.provenance.v1`` record. Missing or invalid inputs are recorded
        as statuses and warnings rather than raised.
    """
    report_dir = Path(report_dir)
    names = list(dict.fromkeys(name for name in report_names if name != REPORT_PROVENANCE_NAME))
    reports: list[dict[str, object]] = []
    warnings: list[str] = []
    for name in names:
        record = _file_record(report_dir, name)
        if record["status"] != "hashed":
            warnings.append(f"report file {name!r} is {record['status']}")
        reports.append(record)
    sources: list[dict[str, object]] = []
    metadata: list[tuple[str, Mapping[str, object]]] = []
    for name in SOURCE_METADATA_NAMES:
        path = report_dir / name
        if not path.is_file():
            continue
        record = _file_record(report_dir, name, status="ok")
        payload, error = _json_mapping(path)
        if payload is None:
            record["status"] = "invalid"
            if error is not None:
                record["error"] = error
            warnings.append(f"source metadata {name!r} is invalid: {error or 'unknown reason'}")
        else:
            metadata.append((name, payload))
        sources.append(record)
    resolved_run = run_id.strip() if run_id is not None and run_id.strip() else report_dir.name
    return {
        "schema_version": REPORT_PROVENANCE_SCHEMA,
        "generated_utc": generated_utc or datetime.now(UTC).isoformat(),
        "run": {"id": resolved_run},
        "dataset": _dataset_identity(report_dir, dataset),
        "reports": reports,
        "sources": sources,
        "uncertainty": _uncertainty(metadata),
        "warnings": warnings,
    }


def write_report_provenance(
    report_dir: Path,
    report_names: Sequence[str],
    *,
    dataset: Path | None = None,
    run_id: str | None = None,
    generated_utc: str | None = None,
) -> Path:
    """Write ``report_provenance.json`` beside a report directory's tables.

    Parameters
    ----------
    report_dir : Path
        The directory that holds the report files.
    report_names : sequence of str
        The report file names to hash.
    dataset : Path or None, optional
        The compiled dataset directory, when the caller knows it.
    run_id : str or None, optional
        The run identifier; the report directory's name is used when omitted.
    generated_utc : str or None, optional
        A fixed ISO-8601 timestamp, for reproducible tests.

    Returns
    -------
    Path
        The path to the written sidecar.
    """
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    provenance = build_report_provenance(
        report_dir,
        report_names,
        dataset=dataset,
        run_id=run_id,
        generated_utc=generated_utc,
    )
    path = report_dir / REPORT_PROVENANCE_NAME
    path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_report(
    values: pd.DataFrame,
    targets: list[Target],
    out_dir: Path,
    *,
    dataset: Path | None = None,
    run_id: str | None = None,
) -> None:
    """Write the report tables and their provenance sidecar to a directory.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values.
    targets : list of Target
        The targets.
    out_dir : Path
        Directory to write ``report_accounts.csv``, ``report_targets.csv``,
        ``ending_inventory.csv``, and ``report_provenance.json`` into.
    dataset : Path or None, optional
        The compiled dataset directory, recorded in the provenance sidecar when known.
    run_id : str or None, optional
        The run identifier, recorded in the provenance sidecar when known.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_names: list[str] = []
    account_summary(values).to_csv(out_dir / "report_accounts.csv", index=False)
    report_names.append("report_accounts.csv")
    target_status(values, targets).to_csv(out_dir / "report_targets.csv", index=False)
    report_names.append("report_targets.csv")
    ending_inventory(values).to_csv(out_dir / "ending_inventory.csv", index=False)
    report_names.append("ending_inventory.csv")
    metadata_path = out_dir / "dhi_metadata.json"
    metadata: dict[str, object] | None = None
    if metadata_path.is_file():
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = None
        metadata = loaded if isinstance(loaded, dict) else None
    dhi = dhi_report(values, metadata)
    if not dhi.empty:
        dhi.to_csv(out_dir / "report_dhi.csv", index=False)
        report_names.append("report_dhi.csv")
    structure_metadata_path = out_dir / "structure_habitat_metadata.json"
    structure_metadata: dict[str, object] | None = None
    if structure_metadata_path.is_file():
        try:
            loaded_structure = json.loads(structure_metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded_structure = None
        structure_metadata = loaded_structure if isinstance(loaded_structure, dict) else None
    structure = structure_habitat_report(values, structure_metadata)
    if not structure.empty:
        structure.to_csv(out_dir / "report_structure_habitat.csv", index=False)
        report_names.append("report_structure_habitat.csv")
    resilience_metadata_path = out_dir / "resilience_metadata.json"
    resilience_metadata: dict[str, object] | None = None
    if resilience_metadata_path.is_file():
        try:
            loaded_resilience = json.loads(resilience_metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded_resilience = None
        resilience_metadata = loaded_resilience if isinstance(loaded_resilience, dict) else None
    resilience = resilience_report(values, resilience_metadata)
    if not resilience.empty:
        resilience.to_csv(out_dir / "report_resilience.csv", index=False)
        report_names.append("report_resilience.csv")
    write_report_provenance(out_dir, report_names, dataset=dataset, run_id=run_id)
