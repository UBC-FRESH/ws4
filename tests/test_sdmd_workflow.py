"""Tests for the FreshForge SDMD workflow provider."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

pytest.importorskip("freshforge")
pytest.importorskip("figrecover")

from freshforge.loading import load_workflow
from freshforge.planning import create_run_plan
from freshforge.providers import ProviderMetadata, ProviderRegistry
from ws4.sdmd.workflow import sdmd_provider

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "sdmd-digitise.yaml"


def test_sdmd_workflow_plans_with_the_provider() -> None:
    """The four-node workflow validates against the WS4 provider."""
    spec, diagnostics = load_workflow(WORKFLOW)
    assert spec is not None
    registry = ProviderRegistry()
    registry.register(sdmd_provider())
    plan = create_run_plan(spec, diagnostics=diagnostics, registry=registry)
    assert not plan.has_errors
    assert [node.id for node in plan.nodes] == ["render", "extract", "overlay", "review"]


def test_provider_metadata_names_the_four_nodes() -> None:
    """The provider advertises render, extract, overlay, and review."""
    metadata = cast(ProviderMetadata, sdmd_provider().metadata())
    assert metadata.id == "ws4.sdmd"
    assert [node.id for node in metadata.node_types] == [
        "render",
        "extract",
        "overlay",
        "review",
    ]
