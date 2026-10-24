"""Run reproducibility artefacts and dataset-quality checks.

A run already records its summary, schedule, report tables, and telemetry. This module adds
the two artefacts a reviewer needs to reproduce and qualify it:

* ``run_manifest.json`` records the code revision, dataset hashes, full configuration,
  seeds, environment, and a reproduce command;
* ``data_quality.json`` records the compiled dataset's metadata, table counts, target
  coverage, and explicit unknowns.

The quality report distinguishes **not supplied** from **checked and good**. A dataset with
no metadata is reported as ``unknown``, not as passing.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shlex
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..model.schema import dataset_reference
from .objective import load_targets

if TYPE_CHECKING:
    from .engine import OptimizeConfig

#: Accounts that the compiled matrix derives rather than stores in ``accounts.parquet``.
_DERIVED_PREFIXES = ("patch.", "route.", "spread.")
_PACKAGES = ("ws4", "numpy", "pandas", "pyarrow", "scipy", "pyproj", "fastapi")


def _sha256(path: Path) -> str | None:
    """Return a file's SHA-256, or None when it is missing."""
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_state() -> dict[str, object]:
    """Return the current Git commit and dirty flag, or an unavailable marker."""
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if root.returncode != 0:
            return {"commit": None, "dirty": None, "root": None}
        repo = Path(root.stdout.strip())
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return {
            "commit": commit.stdout.strip() or None if commit.returncode == 0 else None,
            "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
            "root": str(repo),
        }
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None, "root": None}


def _environment() -> dict[str, Any]:
    """Return the interpreter and package versions relevant to a run."""
    versions: dict[str, str] = {}
    for name in _PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": versions,
    }


def _table_rows(dataset_dir: Path, table: str, relative: str) -> int | None:
    """Return a Parquet table's row count from its metadata, or None."""
    path = dataset_dir / relative
    if not path.is_file():
        return None
    try:
        from pyarrow.parquet import ParquetFile  # type: ignore[import-untyped]  # pyarrow ships no stubs

        return int(ParquetFile(path).metadata.num_rows)
    except (OSError, ValueError):
        return None


def _target_accounts(targets_path: Path | None) -> list[str]:
    """Return the active target accounts, or an empty list when there are none."""
    if targets_path is None or not targets_path.is_file():
        return []
    try:
        return sorted({target.account for target in load_targets(targets_path) if target.active})
    except (OSError, ValueError):
        return []


def dataset_quality(dataset_dir: Path, targets_path: Path | None = None) -> dict[str, Any]:
    """Summarize the dataset's metadata, table counts, and target coverage.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset directory.
    targets_path : Path or None, optional
        The targets file, used to check whether target accounts are in the matrix.

    Returns
    -------
    dict of str to Any
        The full quality report, including checks, table counts, and a compact summary.
    """
    dataset_dir = Path(dataset_dir)
    manifest_path = dataset_dir / "manifest.json"
    checks: list[dict[str, str]] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    table_counts: dict[str, int | None] = {}
    if not manifest_path.is_file():
        checks.append(
            {"name": "manifest", "status": "warn", "detail": "dataset manifest is missing"}
        )
        warnings.append("dataset manifest is missing")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            manifest = {}
            checks.append({"name": "manifest", "status": "warn", "detail": f"cannot read: {error}"})
            warnings.append("dataset manifest cannot be read")
        raw_metadata = manifest.get("metadata", {})
        metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
        if metadata:
            checks.append(
                {"name": "metadata", "status": "ok", "detail": "dataset metadata supplied"}
            )
        else:
            checks.append(
                {
                    "name": "metadata",
                    "status": "unknown",
                    "detail": "no dataset data-quality metadata was supplied",
                }
            )
            warnings.append("data-quality metadata is not supplied")
        tables = manifest.get("tables", {})
        if isinstance(tables, Mapping):
            for name, relative in tables.items():
                if isinstance(relative, str):
                    table_counts[str(name)] = _table_rows(dataset_dir, str(name), relative)
        empty = [name for name, count in table_counts.items() if count == 0]
        missing = [name for name, count in table_counts.items() if count is None]
        if empty or missing:
            warnings.append("some dataset tables are empty or missing")
            checks.append(
                {
                    "name": "tables",
                    "status": "warn",
                    "detail": f"empty={empty}; missing={missing}",
                }
            )
        else:
            checks.append(
                {
                    "name": "tables",
                    "status": "ok",
                    "detail": f"{len(table_counts)} tables have rows",
                }
            )
    accounts_path = dataset_dir / "accounts.parquet"
    provided: set[str] = set()
    if accounts_path.is_file():
        try:
            import pandas as pd

            frame = pd.read_parquet(accounts_path, columns=["account"])
            provided = {str(value) for value in frame["account"].tolist()}
        except (OSError, ValueError, KeyError):
            provided = set()
    target_accounts = _target_accounts(targets_path)
    derived = [name for name in target_accounts if name.startswith(_DERIVED_PREFIXES)]
    checked = [name for name in target_accounts if name not in derived]
    missing_targets = sorted(name for name in checked if name not in provided)
    if missing_targets:
        warnings.append("target accounts are absent from the matrix")
        checks.append(
            {
                "name": "target_coverage",
                "status": "warn",
                "detail": "missing: " + ", ".join(missing_targets),
            }
        )
    elif target_accounts:
        checks.append(
            {
                "name": "target_coverage",
                "status": "ok",
                "detail": f"{len(checked)} matrix accounts checked; {len(derived)} derived",
            }
        )
    else:
        checks.append(
            {
                "name": "target_coverage",
                "status": "not-applicable",
                "detail": "no active targets",
            }
        )
    status = (
        "warn"
        if any(check["status"] == "warn" for check in checks)
        else ("unknown" if any(check["status"] == "unknown" for check in checks) else "ok")
    )
    limitations = [
        "Account values are model outputs; the dataset does not carry a field audit.",
        "A harvest schedule is not a guarantee of operability, markets, fire, or access.",
    ]
    if not metadata:
        limitations.append(
            "No inventory vintage, imputation share, or coverage metadata was supplied."
        )
    report: dict[str, Any] = {
        "dataset": str(dataset_dir),
        "manifest_sha256": _sha256(manifest_path),
        "metadata": metadata,
        "tables": table_counts,
        "target_accounts": {
            "checked": checked,
            "derived": derived,
            "missing": missing_targets,
        },
        "checks": checks,
        "limitations": limitations,
        "summary": {
            "status": status,
            "metadata_supplied": bool(metadata),
            "warnings": warnings,
            "table_count": len(table_counts),
        },
    }
    return report


def _reproduce_command(
    dataset_dir: Path, targets_path: Path | None, cfg: OptimizeConfig, out_dir: Path
) -> str:
    """Return a command that repeats the principal search settings."""
    parts = [
        "ws4",
        "optimize",
        "--dataset",
        str(dataset_dir),
        "--out",
        str(out_dir),
        "--years",
        str(cfg.years),
        "--iterations",
        str(cfg.iterations),
        "--seed",
        str(cfg.seed),
        "--threads",
        str(cfg.threads),
        "--engine",
        cfg.metaheuristic,
    ]
    if targets_path is not None:
        parts.extend(["--targets", str(targets_path)])
    return shlex.join(parts)


def write_reproducibility(out_dir: Path, dataset_dir: Path, cfg: OptimizeConfig) -> dict[str, Any]:
    """Write the run manifest and data-quality report.

    Parameters
    ----------
    out_dir : Path
        The run directory.
    dataset_dir : Path
        The compiled dataset.
    cfg : OptimizeConfig
        The run configuration.

    Returns
    -------
    dict of str to Any
        The manifest and quality report, with their file paths.
    """
    out_dir = Path(out_dir)
    dataset_dir = Path(dataset_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    targets_path = Path(cfg.targets_path) if cfg.targets_path else None
    quality = dataset_quality(dataset_dir, targets_path)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "code": {
            "package_version": _environment()["packages"].get("ws4"),
            "git": _git_state(),
        },
        "dataset": {
            "path": str(dataset_dir),
            "reference": dataset_reference(dataset_dir),
        },
        "targets": {
            "path": str(targets_path) if targets_path is not None else None,
            "sha256": _sha256(targets_path) if targets_path is not None else None,
            "active_accounts": _target_accounts(targets_path),
        },
        "configuration": asdict(cfg),
        "seeds": [cfg.seed + start for start in range(max(1, cfg.starts))],
        "environment": _environment(),
        "reproduce": {
            "command": _reproduce_command(dataset_dir, targets_path, cfg, out_dir),
            "note": "The command repeats the principal settings; the full configuration is above.",
        },
        "quality": quality,
    }
    manifest_path = out_dir / "run_manifest.json"
    quality_path = out_dir / "data_quality.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    quality_path.write_text(json.dumps(quality, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "manifest": manifest,
        "quality": quality,
        "manifest_path": str(manifest_path),
        "quality_path": str(quality_path),
    }
