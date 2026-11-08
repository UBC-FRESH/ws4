"""Tests for the provisional diagram review packet builder."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _builder() -> Any:  # noqa: ANN401 - test-only dynamic module loader
    """Load the packet builder without making ``scripts`` a package."""
    spec = importlib.util.spec_from_file_location(
        "build_diagram_review_packet_test",
        ROOT / "scripts" / "build_diagram_review_packet.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_review_rows_are_empty_after_all_reviews() -> None:
    """Every Atlas diagram is now reviewed, so the queue is empty."""
    rows = _builder().review_rows()
    assert len(rows) == 0


def test_packet_writes_ten_curve_plots_and_a_checklist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The packet builder writes figures and a maintainer checklist."""
    builder = _builder()
    monkeypatch.setattr(builder, "REVIEW", tmp_path)
    monkeypatch.setattr(builder, "PAGE_DIR", tmp_path / "pages")
    monkeypatch.setattr(builder, "CURVE_DIR", tmp_path / "curves")
    packet = builder.build_packet(download=False)
    text = packet.read_text(encoding="utf-8")
    assert "all 0 diagrams remain **provisional**" in text
    assert text.count("- [ ]") == 0
    assert len(list((tmp_path / "curves").glob("*.svg"))) == 0


def test_packet_renders_a_synthetic_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The row and figure path stay covered when the live queue is empty."""
    builder = _builder()
    row = {
        "diagram_id": "fdcp",
        "json": "cdf-cwh-fdc-planted.json",
        "species": "FDC",
        "bec": "CDFmm",
        "review": "reviewed",
        "curves": {"top_height": "17: 6-60"},
        "findings": [],
        "pdf_url": "https://example.invalid/fdcp.pdf",
        "labels": 25,
    }
    monkeypatch.setattr(builder, "REVIEW", tmp_path)
    monkeypatch.setattr(builder, "PAGE_DIR", tmp_path / "pages")
    monkeypatch.setattr(builder, "CURVE_DIR", tmp_path / "curves")
    monkeypatch.setattr(builder, "review_rows", lambda: [row])
    packet = builder.build_packet(download=False)
    text = packet.read_text(encoding="utf-8")
    assert "`fdcp`" in text
    assert (tmp_path / "curves" / "fdcp.svg").is_file()


def test_curve_summary_and_review_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The packet builder summarizes a diagram and reads a queue row."""
    from ws4.sdmd.diagram import load_diagram

    builder = _builder()
    diagram_path = ROOT / "ws4" / "sdmd" / "data" / "sdmd" / "cdf-cwh-fdc-planted.json"
    summary = builder.curve_summary(load_diagram(diagram_path))
    assert "top_height" in summary
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(diagram_path, data / "cdf-cwh-fdc-planted.json")
    (data / "bec_review_queue.csv").write_text(
        "diagram_id,pdf_url,label_count\nfdcp,https://example.invalid/fdcp.pdf,25\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(builder, "DATA", data)
    rows = builder.review_rows()
    assert len(rows) == 1
    assert rows[0]["diagram_id"] == "fdcp"
    assert rows[0]["curves"]


def test_download_verifies_the_catalogue_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The download helper writes and verifies a cached file."""

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"pdf-bytes"

    builder = _builder()
    monkeypatch.setattr(builder.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    digest = hashlib.sha256(b"pdf-bytes").hexdigest()
    path = builder._download("https://example.invalid/source.pdf", digest, cache=tmp_path)
    assert path.read_bytes() == b"pdf-bytes"
    with pytest.raises(ValueError, match="expected"):
        builder._download("https://example.invalid/source.pdf", "0" * 64, cache=tmp_path)
