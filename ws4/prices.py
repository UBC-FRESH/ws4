"""Read and report ``prices.v1`` scenario price paths.

The table is a read-only scenario input. It does not enter the compiled dataset,
the simulator, the objective, or the solver. WS4 compares the named paths against
the base path and writes the comparison with its provenance.

The values are scenario assumptions, not a forecast. Every table must say so in
its ``not_a_forecast`` field, and the written report repeats the statement.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PRICES_SCHEMA = "prices.v1"
PRICE_REPORT_SCHEMA = "ws4.prices.report.v1"
PRICE_PATH_IDS: tuple[str, ...] = ("base", "high", "low", "policy_shock")
BASE_PRICE_PATH = "base"
PRICE_COMPARISON_NAME = "price_path_comparison.csv"
PRICE_REPORT_NAME = "price_path_report.md"
PRICE_PROVENANCE_NAME = "price_path_provenance.json"


class PriceTableError(RuntimeError):
    """Raised when a ``prices.v1`` table cannot be consumed."""


@dataclass(frozen=True)
class PriceRow:
    """One product/period value for one named scenario path.

    Attributes
    ----------
    path_id : str
        One of ``base``, ``high``, ``low``, or ``policy_shock``.
    product : str
        Product identifier, such as ``sawlog``.
    period : int
        Non-negative period index.
    value : float
        Finite, non-negative price or cost per ``unit``.
    unit : str
        Unit of the value, such as ``CAD/m3``.
    currency : str
        ISO-4217-style currency code, such as ``CAD``.
    region : str
        Region the value applies to.
    source : str
        Source identifier for the value.
    source_version : str
        Source version, vintage, or access date.
    """

    path_id: str
    product: str
    period: int
    value: float
    unit: str
    currency: str
    region: str
    source: str
    source_version: str

    def to_dict(self) -> dict[str, object]:
        """Return the row in the flat ``prices.v1`` shape.

        Returns
        -------
        dict[str, object]
            The row fields with numeric values preserved.
        """
        return {
            "path_id": self.path_id,
            "product": self.product,
            "period": self.period,
            "value": self.value,
            "unit": self.unit,
            "currency": self.currency,
            "region": self.region,
            "source": self.source,
            "source_version": self.source_version,
        }


@dataclass(frozen=True)
class PriceTable:
    """Loaded and checksummed ``prices.v1`` scenario table.

    Attributes
    ----------
    path : pathlib.Path
        Resolved table path.
    sha256 : str
        SHA-256 digest of the table bytes.
    byte_size : int
        Size of the table in bytes.
    table_id : str
        Stable table identifier.
    generated_utc : str
        Producer generation timestamp.
    not_a_forecast : str
        Mandatory caveat stating that the values are not a forecast.
    caveats : tuple of str
        Additional source or interpretation caveats.
    path_ids : tuple of str
        Present path identifiers in canonical order, always including ``base``.
    products : tuple of str
        Product identifiers, sorted.
    periods : tuple of int
        Period indices, sorted ascending.
    currency : str
        The single currency shared by every row.
    region : str
        The single region shared by every row.
    rows : tuple of PriceRow
        Validated rows in canonical path/product/period order.
    """

    path: Path
    sha256: str
    byte_size: int
    table_id: str
    generated_utc: str
    not_a_forecast: str
    caveats: tuple[str, ...]
    path_ids: tuple[str, ...]
    products: tuple[str, ...]
    periods: tuple[int, ...]
    currency: str
    region: str
    rows: tuple[PriceRow, ...]

    def row(self, path_id: str, product: str, period: int) -> PriceRow:
        """Return one path/product/period row.

        Parameters
        ----------
        path_id : str
            Declared path identifier.
        product : str
            Declared product identifier.
        period : int
            Declared period.

        Returns
        -------
        PriceRow
            The matching row.

        Raises
        ------
        PriceTableError
            If the path/product/period key is not declared.
        """
        for row in self.rows:
            if row.path_id == path_id and row.product == product and row.period == period:
                return row
        raise PriceTableError(
            f"Price table has no row for path {path_id!r} product {product!r} period {period}."
        )

    def value(self, path_id: str, product: str, period: int) -> float:
        """Return one path's value for a product and period.

        Parameters
        ----------
        path_id : str
            Declared path identifier.
        product : str
            Declared product identifier.
        period : int
            Declared period.

        Returns
        -------
        float
            The row's value.
        """
        return self.row(path_id, product, period).value

    def to_dict(self) -> dict[str, object]:
        """Return the table as a JSON-serializable mapping.

        Returns
        -------
        dict[str, object]
            The schema, identity, caveat, caveats, and rows.
        """
        return {
            "schema_version": PRICES_SCHEMA,
            "table_id": self.table_id,
            "generated_utc": self.generated_utc,
            "not_a_forecast": self.not_a_forecast,
            "caveats": list(self.caveats),
            "rows": [row.to_dict() for row in self.rows],
        }


def _required_text(value: object, field: str) -> str:
    """Return a non-empty, stripped string or raise."""
    if not isinstance(value, str) or not value.strip():
        raise PriceTableError(f"{field} must be a non-empty string.")
    return value.strip()


def _required_int(value: object, field: str) -> int:
    """Return a non-negative integer, rejecting booleans and non-integers."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PriceTableError(f"{field} must be a non-negative integer.")
    return value


def _required_number(value: object, field: str) -> float:
    """Return a finite, non-negative number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PriceTableError(f"{field} must be a finite non-negative number.")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise PriceTableError(f"{field} must be a finite non-negative number.")
    return number


def _text_list(value: object, field: str) -> tuple[str, ...]:
    """Return a tuple of non-empty strings from an optional list."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise PriceTableError(f"{field} must be a list of non-empty strings.")
    return tuple(_required_text(item, field) for item in value)


def _row_from_mapping(payload: Mapping[str, object], index: int) -> PriceRow:
    """Validate one table row against the ``prices.v1`` row contract."""
    path_id = _required_text(payload.get("path_id"), f"row {index} path_id")
    if path_id not in PRICE_PATH_IDS:
        supported = ", ".join(PRICE_PATH_IDS)
        raise PriceTableError(f"row {index} path_id must be one of: {supported}; got {path_id!r}.")
    return PriceRow(
        path_id=path_id,
        product=_required_text(payload.get("product"), f"row {index} product"),
        period=_required_int(payload.get("period"), f"row {index} period"),
        value=_required_number(payload.get("value"), f"row {index} value"),
        unit=_required_text(payload.get("unit"), f"row {index} unit"),
        currency=_required_text(payload.get("currency"), f"row {index} currency"),
        region=_required_text(payload.get("region"), f"row {index} region"),
        source=_required_text(payload.get("source"), f"row {index} source"),
        source_version=_required_text(payload.get("source_version"), f"row {index} source_version"),
    )


def load_price_table(path: Path) -> PriceTable:
    """Load and validate a ``prices.v1`` JSON table.

    Parameters
    ----------
    path : pathlib.Path
        JSON table path.

    Returns
    -------
    PriceTable
        Checksummed table with the declared path grid and provenance.

    Raises
    ------
    PriceTableError
        If the file is missing, is not UTF-8 JSON, has the wrong suffix or schema,
        omits the base path, names an unknown path, repeats a row, does not cover
        the same product/period grid on every path, mixes currency, region, or a
        product's unit, contains an invalid value, or lacks the ``not a forecast``
        caveat.
    """
    resolved = path.expanduser().resolve()
    if resolved.suffix.lower() != ".json":
        raise PriceTableError("Price tables must be JSON.")
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise PriceTableError(f"Unable to read price table: {resolved}: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise PriceTableError(f"Price table is not UTF-8: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise PriceTableError(f"Invalid price-table JSON: {resolved}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise PriceTableError("Price table must be a JSON object.")
    if payload.get("schema_version") != PRICES_SCHEMA:
        raise PriceTableError(f"Unsupported price-table schema {payload.get('schema_version')!r}.")
    table_id = _required_text(payload.get("table_id"), "table_id")
    generated_utc = _required_text(payload.get("generated_utc"), "generated_utc")
    not_a_forecast = _required_text(payload.get("not_a_forecast"), "not_a_forecast")
    if "not a forecast" not in not_a_forecast.casefold():
        raise PriceTableError("not_a_forecast must state that the values are not a forecast.")
    caveats = _text_list(payload.get("caveats"), "caveats")
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, list) or not rows_payload:
        raise PriceTableError("Price table must contain at least one row.")

    seen: dict[tuple[str, str, int], PriceRow] = {}
    for index, item in enumerate(rows_payload, start=1):
        if not isinstance(item, Mapping):
            raise PriceTableError(f"Price-table row {index} must be an object.")
        row = _row_from_mapping(item, index)
        key = (row.path_id, row.product, row.period)
        if key in seen:
            raise PriceTableError(
                f"Duplicate price row for path {row.path_id!r} product {row.product!r} "
                f"period {row.period}."
            )
        seen[key] = row

    rows = list(seen.values())
    path_ids = tuple(
        path_id for path_id in PRICE_PATH_IDS if any(row.path_id == path_id for row in rows)
    )
    if BASE_PRICE_PATH not in path_ids:
        raise PriceTableError("Price table must declare the 'base' path.")

    base_grid = {(r.product, r.period) for r in rows if r.path_id == BASE_PRICE_PATH}
    for path_id in path_ids:
        grid = {(r.product, r.period) for r in rows if r.path_id == path_id}
        missing = sorted(base_grid - grid)
        if missing:
            product, period = missing[0]
            raise PriceTableError(
                f"Path {path_id!r} is missing {len(missing)} product/period row(s), "
                f"starting with product {product!r} period {period}."
            )
        extra = sorted(grid - base_grid)
        if extra:
            product, period = extra[0]
            raise PriceTableError(
                f"Path {path_id!r} has {len(extra)} undeclared product/period row(s), "
                f"starting with product {product!r} period {period}."
            )

    units: dict[str, str] = {}
    for row in rows:
        existing = units.setdefault(row.product, row.unit)
        if existing != row.unit:
            raise PriceTableError(
                f"Product {row.product!r} mixes units {existing!r} and {row.unit!r}."
            )
    currencies = sorted({row.currency for row in rows})
    if len(currencies) != 1:
        raise PriceTableError(f"Price table mixes currencies: {', '.join(currencies)}.")
    regions = sorted({row.region for row in rows})
    if len(regions) != 1:
        raise PriceTableError(f"Price table mixes regions: {', '.join(regions)}.")

    products = tuple(sorted({row.product for row in rows}))
    periods = tuple(sorted({row.period for row in rows}))
    rows.sort(key=lambda row: (PRICE_PATH_IDS.index(row.path_id), row.product, row.period))
    return PriceTable(
        path=resolved,
        sha256=digest,
        byte_size=len(raw),
        table_id=table_id,
        generated_utc=generated_utc,
        not_a_forecast=not_a_forecast,
        caveats=caveats,
        path_ids=path_ids,
        products=products,
        periods=periods,
        currency=currencies[0],
        region=regions[0],
        rows=tuple(rows),
    )


_COMPARISON_COLUMNS: tuple[str, ...] = (
    "path_id",
    "product",
    "period",
    "value",
    "unit",
    "currency",
    "region",
    "source",
    "source_version",
    "base_value",
    "delta",
    "delta_pct",
)


def _comparison_records(table: PriceTable) -> list[dict[str, object]]:
    """Build the base-relative comparison rows."""
    base = {
        (row.product, row.period): row.value for row in table.rows if row.path_id == BASE_PRICE_PATH
    }
    records: list[dict[str, object]] = []
    ordered = sorted(
        table.rows,
        key=lambda row: (row.product, row.period, PRICE_PATH_IDS.index(row.path_id)),
    )
    for row in ordered:
        base_value = base[(row.product, row.period)]
        delta = row.value - base_value
        records.append(
            {
                "path_id": row.path_id,
                "product": row.product,
                "period": row.period,
                "value": row.value,
                "unit": row.unit,
                "currency": row.currency,
                "region": row.region,
                "source": row.source,
                "source_version": row.source_version,
                "base_value": base_value,
                "delta": delta,
                "delta_pct": None if base_value == 0 else (delta / base_value) * 100.0,
            }
        )
    return records


def compare_price_paths(table: PriceTable) -> pd.DataFrame:
    """Compare every named path against the base path.

    Parameters
    ----------
    table : PriceTable
        A loaded price table.

    Returns
    -------
    pandas.DataFrame
        One row per path/product/period with ``base_value``, ``delta``, and
        ``delta_pct``. ``delta_pct`` is null when the base value is zero.
    """
    return pd.DataFrame(_comparison_records(table), columns=list(_COMPARISON_COLUMNS))


def _summary_records(table: PriceTable) -> list[dict[str, object]]:
    """Build one summary row per path and product."""
    comparison = compare_price_paths(table)
    records: list[dict[str, object]] = []
    for path_id in table.path_ids:
        path_rows = comparison[comparison["path_id"] == path_id]
        for product in table.products:
            frame = path_rows[path_rows["product"] == product]
            if frame.empty:
                continue
            deltas = [float(value) for value in frame["delta"].tolist()]
            deltas_pct = [
                float(value)
                for value in frame["delta_pct"].dropna().tolist()
                if math.isfinite(value)
            ]
            source = frame.iloc[0]
            records.append(
                {
                    "path_id": path_id,
                    "product": product,
                    "unit": str(source["unit"]),
                    "source": str(source["source"]),
                    "source_version": str(source["source_version"]),
                    "row_count": len(frame),
                    "min_value": float(frame["value"].min()),
                    "max_value": float(frame["value"].max()),
                    "mean_value": float(frame["value"].mean()),
                    "mean_delta": sum(deltas) / len(deltas),
                    "mean_delta_pct": (sum(deltas_pct) / len(deltas_pct) if deltas_pct else None),
                    "max_abs_delta_pct": max(abs(value) for value in deltas_pct)
                    if deltas_pct
                    else None,
                }
            )
    return records


def summarize_price_paths(table: PriceTable) -> pd.DataFrame:
    """Summarize each path and product against the base path.

    Parameters
    ----------
    table : PriceTable
        A loaded price table.

    Returns
    -------
    pandas.DataFrame
        One row per path/product with ``row_count``, minimum, maximum, mean,
        mean delta, mean percent delta, and maximum absolute percent delta.
    """
    return pd.DataFrame(_summary_records(table))


def _file_record(path: Path, name: str) -> dict[str, object]:
    """Hash one written report file, recording a missing file rather than raising."""
    try:
        raw = path.read_bytes()
    except OSError:
        return {"name": name, "bytes": None, "sha256": None, "status": "missing"}
    return {
        "name": name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "status": "hashed",
    }


def _source_records(table: PriceTable) -> list[dict[str, object]]:
    """Group rows by path, source, and source version."""
    grouped: dict[tuple[str, str, str], tuple[set[str], set[int]]] = {}
    for row in table.rows:
        key = (row.path_id, row.source, row.source_version)
        products, periods = grouped.setdefault(key, (set(), set()))
        products.add(row.product)
        periods.add(row.period)
    ordered = sorted(
        grouped.items(),
        key=lambda item: (
            PRICE_PATH_IDS.index(item[0][0]),
            item[0][1],
            item[0][2],
        ),
    )
    return [
        {
            "path_id": path_id,
            "source": source,
            "source_version": source_version,
            "products": sorted(products),
            "periods": sorted(periods),
        }
        for (path_id, source, source_version), (products, periods) in ordered
    ]


def build_price_provenance(
    table: PriceTable,
    out_dir: Path,
    file_names: Sequence[str],
) -> dict[str, object]:
    """Build the provenance record for a written price-path report.

    Parameters
    ----------
    table : PriceTable
        The source price table.
    out_dir : pathlib.Path
        Directory that holds the written report files.
    file_names : sequence of str
        The report file names to hash.

    Returns
    -------
    dict of str to object
        The ``ws4.prices.report.v1`` record with the source digest, the path and
        grid, the caveat, and each output file's size and digest.
    """
    out_dir = Path(out_dir)
    return {
        "schema_version": PRICE_REPORT_SCHEMA,
        "table_schema": PRICES_SCHEMA,
        "table_id": table.table_id,
        "generated_utc": table.generated_utc,
        "input": {
            "name": table.path.name,
            "bytes": table.byte_size,
            "sha256": table.sha256,
            "status": "hashed",
        },
        "baseline_path": BASE_PRICE_PATH,
        "path_ids": list(table.path_ids),
        "products": list(table.products),
        "periods": list(table.periods),
        "currency": table.currency,
        "region": table.region,
        "row_count": len(table.rows),
        "sources": _source_records(table),
        "not_a_forecast": table.not_a_forecast,
        "caveats": list(table.caveats),
        "comparison": {
            "rows": len(table.rows),
            "absolute_delta": "value - base_value",
            "percent_delta": (
                "100 * (value - base_value) / base_value; null when base_value is zero"
            ),
        },
        "files": [_file_record(out_dir / name, name) for name in file_names],
    }


def _format_number(value: float) -> str:
    """Format a value for the Markdown report."""
    return f"{value:,.2f}"


def _format_percent(value: float | None) -> str:
    """Format a percent delta for the Markdown report."""
    return "n/a" if value is None or not math.isfinite(value) else f"{value:+.2f}%"


def _as_float(value: object) -> float:
    """Return a numeric report value as a float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"expected a number, got {type(value).__name__}")
    return float(value)


def _render_price_report(
    table: PriceTable,
    summary: list[dict[str, object]],
    comparison: list[dict[str, object]],
) -> str:
    """Render the human-readable price-path report."""
    lines = [
        "# Scenario price paths",
        "",
        f"> **Not a forecast.** {table.not_a_forecast}",
        "",
        "## Provenance",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Table id | `{table.table_id}` |",
        f"| Input file | `{table.path.name}` |",
        f"| Input SHA-256 | `{table.sha256}` |",
        f"| Generated (UTC) | {table.generated_utc} |",
        f"| Currency | {table.currency} |",
        f"| Region | {table.region} |",
        f"| Paths | {', '.join(table.path_ids)} |",
        f"| Products | {', '.join(table.products)} |",
        f"| Periods | {', '.join(str(period) for period in table.periods)} |",
        f"| Rows | {len(table.rows)} |",
        "",
        "The base path is the comparison baseline. All deltas are the named path",
        "minus the base path at the same product and period.",
        "",
        "## Path summary",
        "",
        "| Path | Product | Unit | Rows | Min | Max | Mean | Mean delta | "
        "Mean delta % | Max abs delta % |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for record in summary:
        mean_pct_value = record["mean_delta_pct"]
        mean_pct = "n/a" if mean_pct_value is None else _format_percent(_as_float(mean_pct_value))
        max_pct_value = record["max_abs_delta_pct"]
        max_pct = "n/a" if max_pct_value is None else f"{_as_float(max_pct_value):.2f}%"
        cells = (
            str(record["path_id"]),
            str(record["product"]),
            str(record["unit"]),
            str(record["row_count"]),
            _format_number(_as_float(record["min_value"])),
            _format_number(_as_float(record["max_value"])),
            _format_number(_as_float(record["mean_value"])),
            _format_number(_as_float(record["mean_delta"])),
            mean_pct,
            max_pct,
        )
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            "| Path | Product | Period | Value | Base | Delta | Delta % | Unit |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for record in comparison:
        delta_pct_value = record["delta_pct"]
        delta_pct = (
            "n/a" if delta_pct_value is None else _format_percent(_as_float(delta_pct_value))
        )
        comparison_cells = (
            str(record["path_id"]),
            str(record["product"]),
            str(record["period"]),
            _format_number(_as_float(record["value"])),
            _format_number(_as_float(record["base_value"])),
            _format_number(_as_float(record["delta"])),
            delta_pct,
            str(record["unit"]),
        )
        lines.append("| " + " | ".join(comparison_cells) + " |")
    lines.extend(["", "## Caveats", "", f"- {table.not_a_forecast}"])
    lines.extend(f"- {caveat}" for caveat in table.caveats)
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "- These values are scenario inputs, not a forecast, a contract, or an offer.",
            "- The report does not convert currency, adjust for inflation, or fill a missing",
            "  product or period.",
            "- The table does not enter the compiled dataset, the objective, the schedule,",
            "  or the solver.",
            "",
        ]
    )
    return "\n".join(lines)


def write_price_report(table: PriceTable, out_dir: Path) -> dict[str, Path]:
    """Write a price-path comparison, its Markdown report, and its provenance.

    Parameters
    ----------
    table : PriceTable
        A loaded price table.
    out_dir : pathlib.Path
        Directory to write ``price_path_comparison.csv``,
        ``price_path_report.md``, and ``price_path_provenance.json`` into.

    Returns
    -------
    dict of str to pathlib.Path
        The written comparison, report, and provenance paths, keyed
        ``comparison``, ``report``, and ``provenance``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    comparison_records = _comparison_records(table)
    summary_records = _summary_records(table)
    comparison = pd.DataFrame(comparison_records, columns=list(_COMPARISON_COLUMNS))
    comparison_path = out_dir / PRICE_COMPARISON_NAME
    comparison.to_csv(comparison_path, index=False)
    report_path = out_dir / PRICE_REPORT_NAME
    report_path.write_text(
        _render_price_report(table, summary_records, comparison_records),
        encoding="utf-8",
    )
    provenance = build_price_provenance(
        table,
        out_dir,
        (PRICE_COMPARISON_NAME, PRICE_REPORT_NAME),
    )
    provenance_path = out_dir / PRICE_PROVENANCE_NAME
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "comparison": comparison_path,
        "report": report_path,
        "provenance": provenance_path,
    }
