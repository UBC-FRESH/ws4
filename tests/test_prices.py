"""Tests for the ``prices.v1`` scenario price-path reader and report."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import pytest
from ws4.prices import (
    PRICE_COMPARISON_NAME,
    PRICE_PROVENANCE_NAME,
    PRICE_REPORT_NAME,
    PriceTableError,
    compare_price_paths,
    load_price_table,
    summarize_price_paths,
    write_price_report,
)

FIXTURE = Path(__file__).parent / "fixtures" / "prices" / "paths.json"


def _payload() -> dict[str, object]:
    """Return the fixture table as a mutable mapping."""
    payload: object = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _rows(payload: dict[str, object]) -> list[dict[str, object]]:
    """Return the fixture's rows as mutable mappings."""
    rows = payload["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
    return rows


def _write(tmp_path: Path, payload: dict[str, object], name: str = "paths.json") -> Path:
    """Write a table payload to a scratch file."""
    target = tmp_path / name
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_load_reports_the_paths_products_and_grid() -> None:
    """The loader exposes the four named paths, both products, and the periods."""
    table = load_price_table(FIXTURE)

    assert table.path_ids == ("base", "high", "low", "policy_shock")
    assert table.products == ("pulp", "sawlog")
    assert table.periods == (1, 2, 3)
    assert table.currency == "CAD"
    assert table.region == "British Columbia, Canada"
    assert table.row("base", "sawlog", 1).value == pytest.approx(72.5)
    assert table.value("policy_shock", "pulp", 3) == pytest.approx(34.0)
    assert "not a forecast" in table.not_a_forecast.casefold()


def test_load_records_the_source_digest_and_size() -> None:
    """The loaded table carries the input file's digest and byte size."""
    table = load_price_table(FIXTURE)

    assert table.sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert table.byte_size == FIXTURE.stat().st_size


def test_compare_is_relative_to_the_base_path() -> None:
    """Every non-base row reports its absolute and percent delta from base."""
    frame = compare_price_paths(load_price_table(FIXTURE))

    base = frame[frame["path_id"] == "base"]
    assert (base["delta"] == 0).all()
    assert (base["delta_pct"] == 0).all()
    high = frame[
        (frame["path_id"] == "high") & (frame["product"] == "sawlog") & (frame["period"] == 1)
    ].iloc[0]
    assert high["base_value"] == pytest.approx(72.5)
    assert high["delta"] == pytest.approx(10.0)
    assert high["delta_pct"] == pytest.approx(13.793103, rel=1e-5)
    shock = frame[
        (frame["path_id"] == "policy_shock")
        & (frame["product"] == "sawlog")
        & (frame["period"] == 2)
    ].iloc[0]
    assert shock["delta"] == pytest.approx(-7.4)
    assert shock["delta_pct"] == pytest.approx(-10.0)


def test_zero_base_value_has_no_percent_delta(tmp_path: Path) -> None:
    """A zero base value yields a null percent delta rather than a division."""
    payload = _payload()
    for row in _rows(payload):
        if row["path_id"] == "base" and row["product"] == "sawlog" and row["period"] == 1:
            row["value"] = 0.0
    table = load_price_table(_write(tmp_path, payload))

    frame = compare_price_paths(table)
    shock = frame[
        (frame["path_id"] == "policy_shock")
        & (frame["product"] == "sawlog")
        & (frame["period"] == 1)
    ].iloc[0]

    assert pd.isna(shock["delta_pct"])
    assert shock["delta"] == pytest.approx(72.5)


def test_summary_groups_by_path_and_product() -> None:
    """The summary has one row per path/product with base-relative means."""
    summary = summarize_price_paths(load_price_table(FIXTURE))

    assert len(summary) == 8
    row = summary[(summary["path_id"] == "high") & (summary["product"] == "sawlog")].iloc[0]
    assert row["row_count"] == 3
    assert row["mean_value"] == pytest.approx((82.5 + 85.0 + 88.0) / 3)
    assert row["mean_delta"] == pytest.approx(((82.5 - 72.5) + (85.0 - 74.0) + (88.0 - 75.5)) / 3)
    assert row["mean_delta_pct"] == pytest.approx(
        ((10.0 / 72.5) + (11.0 / 74.0) + (12.5 / 75.5)) / 3 * 100.0
    )


def test_write_report_writes_the_three_artifacts(tmp_path: Path) -> None:
    """The writer produces a comparison, a Markdown report, and a provenance sidecar."""
    written = write_price_report(load_price_table(FIXTURE), tmp_path / "report")

    assert set(written) == {"comparison", "report", "provenance"}
    assert written["comparison"].name == PRICE_COMPARISON_NAME
    assert written["report"].name == PRICE_REPORT_NAME
    assert written["provenance"].name == PRICE_PROVENANCE_NAME
    assert pd.read_csv(written["comparison"]).shape[0] == 24
    text = written["report"].read_text(encoding="utf-8")
    assert "**Not a forecast.**" in text
    assert "policy_shock" in text
    assert "| Path | Product | Period |" in text


def test_provenance_records_source_and_output_digests(tmp_path: Path) -> None:
    """The sidecar repeats the caveat and hashes the input and both outputs."""
    table = load_price_table(FIXTURE)
    written = write_price_report(table, tmp_path / "report")
    payload: object = json.loads(written["provenance"].read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    assert payload["schema_version"] == "ws4.prices.report.v1"
    assert payload["table_schema"] == "prices.v1"
    assert payload["baseline_path"] == "base"
    assert payload["row_count"] == 24
    assert "not a forecast" in str(payload["not_a_forecast"]).casefold()
    source = payload["input"]
    assert isinstance(source, dict)
    assert source["sha256"] == table.sha256
    assert source["bytes"] == table.byte_size
    files = payload["files"]
    assert isinstance(files, list)
    records = {str(record["name"]): record for record in files if isinstance(record, dict)}
    for name in (PRICE_COMPARISON_NAME, PRICE_REPORT_NAME):
        assert (
            records[name]["sha256"]
            == hashlib.sha256((tmp_path / "report" / name).read_bytes()).hexdigest()
        )
        assert records[name]["status"] == "hashed"


def test_table_round_trips_through_its_flat_shape(tmp_path: Path) -> None:
    """The table's own mapping reloads to the same rows and grid."""
    table = load_price_table(FIXTURE)

    reloaded = load_price_table(_write(tmp_path, table.to_dict()))

    assert reloaded.rows == table.rows
    assert reloaded.path_ids == table.path_ids
    assert reloaded.not_a_forecast == table.not_a_forecast


def test_non_json_suffix_is_rejected(tmp_path: Path) -> None:
    """Only JSON tables are accepted."""
    target = tmp_path / "paths.csv"
    target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(PriceTableError, match="must be JSON"):
        load_price_table(target)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    """A missing table reports the path it could not read."""
    with pytest.raises(PriceTableError, match="Unable to read price table"):
        load_price_table(tmp_path / "missing.json")


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    """Malformed JSON fails with the file name."""
    target = tmp_path / "bad.json"
    target.write_text("{not json", encoding="utf-8")

    with pytest.raises(PriceTableError, match="Invalid price-table JSON"):
        load_price_table(target)


def test_non_utf8_table_is_rejected(tmp_path: Path) -> None:
    """A table that is not UTF-8 fails before parsing."""
    target = tmp_path / "bad.json"
    target.write_bytes(b"\xff\xfe")

    with pytest.raises(PriceTableError, match="is not UTF-8"):
        load_price_table(target)


def test_wrong_schema_is_rejected(tmp_path: Path) -> None:
    """The schema version is exact."""
    payload = _payload()
    payload["schema_version"] = "prices.v2"

    with pytest.raises(PriceTableError, match="Unsupported price-table schema"):
        load_price_table(_write(tmp_path, payload))


def test_non_object_table_is_rejected(tmp_path: Path) -> None:
    """The root value must be an object."""
    target = tmp_path / "list.json"
    target.write_text("[]", encoding="utf-8")

    with pytest.raises(PriceTableError, match="must be a JSON object"):
        load_price_table(target)


def test_empty_rows_are_rejected(tmp_path: Path) -> None:
    """A table must carry at least one row."""
    payload = _payload()
    payload["rows"] = []

    with pytest.raises(PriceTableError, match="at least one row"):
        load_price_table(_write(tmp_path, payload))


def test_missing_base_path_is_rejected(tmp_path: Path) -> None:
    """The base path is mandatory because it is the comparison baseline."""
    payload = _payload()
    payload["rows"] = [row for row in _rows(payload) if row["path_id"] != "base"]

    with pytest.raises(PriceTableError, match="must declare the 'base' path"):
        load_price_table(_write(tmp_path, payload))


def test_unknown_path_is_rejected(tmp_path: Path) -> None:
    """Only the four named paths are accepted."""
    payload = _payload()
    _rows(payload)[0]["path_id"] = "extreme"

    with pytest.raises(PriceTableError, match="path_id must be one of"):
        load_price_table(_write(tmp_path, payload))


def test_duplicate_row_is_rejected(tmp_path: Path) -> None:
    """A path/product/period key appears once."""
    payload = _payload()
    rows = _rows(payload)
    rows.append(dict(rows[0]))

    with pytest.raises(PriceTableError, match="Duplicate price row"):
        load_price_table(_write(tmp_path, payload))


def test_missing_grid_row_is_rejected(tmp_path: Path) -> None:
    """Every path must cover every base product/period."""
    payload = _payload()
    payload["rows"] = [
        row
        for row in _rows(payload)
        if not (
            row["path_id"] == "policy_shock" and row["product"] == "sawlog" and row["period"] == 1
        )
    ]

    with pytest.raises(PriceTableError, match="is missing 1 product/period row"):
        load_price_table(_write(tmp_path, payload))


def test_extra_grid_row_is_rejected(tmp_path: Path) -> None:
    """A path cannot add a product/period that the base does not declare."""
    payload = _payload()
    extra = dict(_rows(payload)[7])
    extra["path_id"] = "high"
    extra["product"] = "veneer"
    _rows(payload).append(extra)

    with pytest.raises(PriceTableError, match="undeclared product/period row"):
        load_price_table(_write(tmp_path, payload))


def test_mixed_units_are_rejected(tmp_path: Path) -> None:
    """A product keeps one unit across every path."""
    payload = _payload()
    for row in _rows(payload):
        if row["path_id"] == "high" and row["product"] == "sawlog" and row["period"] == 1:
            row["unit"] = "USD/m3"

    with pytest.raises(PriceTableError, match="mixes units"):
        load_price_table(_write(tmp_path, payload))


def test_mixed_currencies_are_rejected(tmp_path: Path) -> None:
    """The table carries one currency."""
    payload = _payload()
    for row in _rows(payload):
        if row["path_id"] == "high" and row["product"] == "pulp" and row["period"] == 1:
            row["currency"] = "USD"

    with pytest.raises(PriceTableError, match="mixes currencies"):
        load_price_table(_write(tmp_path, payload))


def test_mixed_regions_are_rejected(tmp_path: Path) -> None:
    """The table carries one region."""
    payload = _payload()
    for row in _rows(payload):
        if row["path_id"] == "low" and row["product"] == "pulp" and row["period"] == 1:
            row["region"] = "Alberta, Canada"

    with pytest.raises(PriceTableError, match="mixes regions"):
        load_price_table(_write(tmp_path, payload))


def test_negative_value_is_rejected(tmp_path: Path) -> None:
    """A price or cost value is non-negative."""
    payload = _payload()
    _rows(payload)[0]["value"] = -1.0

    with pytest.raises(PriceTableError, match="finite non-negative number"):
        load_price_table(_write(tmp_path, payload))


def test_non_finite_value_is_rejected(tmp_path: Path) -> None:
    """A non-finite value is not a price."""
    payload = _payload()
    _rows(payload)[0]["value"] = math.nan

    with pytest.raises(PriceTableError, match="finite non-negative number"):
        load_price_table(_write(tmp_path, payload))


def test_non_integer_period_is_rejected(tmp_path: Path) -> None:
    """A period is a non-negative integer."""
    payload = _payload()
    _rows(payload)[0]["period"] = 1.5

    with pytest.raises(PriceTableError, match="period must be a non-negative integer"):
        load_price_table(_write(tmp_path, payload))


def test_missing_caveat_is_rejected(tmp_path: Path) -> None:
    """The ``not_a_forecast`` statement is mandatory."""
    payload = _payload()
    payload.pop("not_a_forecast")

    with pytest.raises(PriceTableError, match="not_a_forecast must be a non-empty string"):
        load_price_table(_write(tmp_path, payload))


def test_caveat_without_the_phrase_is_rejected(tmp_path: Path) -> None:
    """The statement must actually say the values are not a forecast."""
    payload = _payload()
    payload["not_a_forecast"] = "Certain market prices for the next decade."

    with pytest.raises(PriceTableError, match="must state that the values are not a forecast"):
        load_price_table(_write(tmp_path, payload))


def test_missing_source_is_rejected(tmp_path: Path) -> None:
    """Every row names its source."""
    payload = _payload()
    _rows(payload)[0].pop("source")

    with pytest.raises(PriceTableError, match="source must be a non-empty string"):
        load_price_table(_write(tmp_path, payload))


def test_non_mapping_row_is_rejected(tmp_path: Path) -> None:
    """Every row is an object."""
    payload = _payload()
    rows = _rows(payload)
    payload["rows"] = [rows[0], "not-a-row"]

    with pytest.raises(PriceTableError, match="row 2 must be an object"):
        load_price_table(_write(tmp_path, payload))


def test_caveats_must_be_a_list(tmp_path: Path) -> None:
    """The optional caveats field is a list when present."""
    payload = _payload()
    payload["caveats"] = "no inflation adjustment"

    with pytest.raises(PriceTableError, match="caveats must be a list"):
        load_price_table(_write(tmp_path, payload))
