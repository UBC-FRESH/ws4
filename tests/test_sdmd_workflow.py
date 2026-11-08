"""Tests for the FreshForge SDMD workflow provider."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

pytest.importorskip("freshforge")
pytest.importorskip("figrecover")

from freshforge.loading import load_workflow
from freshforge.planning import create_run_plan
from freshforge.providers import ProviderMetadata, ProviderRegistry
from freshforge.records import ProviderRunResult
from ws4.sdmd.workflow import sdmd_provider

pymupdf = pytest.importorskip("pymupdf")

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "sdmd-digitise.yaml"
LINE_WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "sdmd-line-import.yaml"
QMD_WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "sdmd-qmd-import.yaml"


def test_sdmd_workflow_plans_with_the_provider() -> None:
    """The four-node workflow validates against the WS4 provider."""
    spec, diagnostics = load_workflow(WORKFLOW)
    assert spec is not None
    registry = ProviderRegistry()
    registry.register(sdmd_provider())
    plan = create_run_plan(spec, diagnostics=diagnostics, registry=registry)
    assert not plan.has_errors
    assert [node.id for node in plan.nodes] == ["render", "extract", "overlay", "review"]


def test_line_import_workflow_plans_with_the_provider() -> None:
    """The line-import workflow validates against the WS4 provider."""
    spec, diagnostics = load_workflow(LINE_WORKFLOW)
    assert spec is not None
    registry = ProviderRegistry()
    registry.register(sdmd_provider())
    plan = create_run_plan(spec, diagnostics=diagnostics, registry=registry)
    assert not plan.has_errors
    assert [node.id for node in plan.nodes] == ["render", "import"]


def test_qmd_workflow_plans_with_the_provider() -> None:
    """The QMD workflow validates with the same import node."""
    spec, diagnostics = load_workflow(QMD_WORKFLOW)
    assert spec is not None
    registry = ProviderRegistry()
    registry.register(sdmd_provider())
    plan = create_run_plan(spec, diagnostics=diagnostics, registry=registry)
    assert not plan.has_errors
    assert [node.id for node in plan.nodes] == ["render", "import"]


def test_provider_metadata_names_the_five_nodes() -> None:
    """The provider advertises render, extract, overlay, review, and import."""
    metadata = cast(ProviderMetadata, sdmd_provider().metadata())
    assert metadata.id == "ws4.sdmd"
    assert [node.id for node in metadata.node_types] == [
        "render",
        "extract",
        "overlay",
        "review",
        "import-lines",
    ]


def test_import_lines_node_writes_matched_curves(tmp_path: Path) -> None:
    """The provider node imports a labelled family and records path provenance."""
    pdf = tmp_path / "synthetic.pdf"
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.draw_line((50, 250), (350, 150), color=(0, 0, 0), width=1.5, dashes="[ 3 2 ] 0")
    page.draw_line((50, 150), (350, 50), color=(0, 0, 0), width=1.5, dashes="[ 3 2 ] 0")
    page.insert_text((100, 231), "6 m", fontsize=10)
    page.insert_text((100, 131), "12 m", fontsize=10)
    document.save(pdf)

    provider = sdmd_provider()
    metadata = cast(ProviderMetadata, provider.metadata())
    node_type = next(item for item in metadata.node_types if item.id == "import-lines")
    context = SimpleNamespace(resolve_path=lambda value: tmp_path / str(value))
    node = SimpleNamespace(
        parameters={
            "pdf": pdf.name,
            "dash": "[ 3 2 ] 0",
            "width": 1.5,
            "unit": "m",
            "kind": "top_height",
            "values": [6, 12],
            "x_ticks": [[100, 50], [1000, 350]],
            "y_ticks": [[0.01, 250], [1, 50]],
            "out": "family.json",
        }
    )
    result = cast(ProviderRunResult, provider.run_node(node, node_type, context=context))
    assert result.ok
    payload = json.loads((tmp_path / "family.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "ws4.sdmd.line-import.v1"
    assert [(curve["value"], curve["path_index"]) for curve in payload["curves"]] == [
        (6.0, 0),
        (12.0, 1),
    ]
