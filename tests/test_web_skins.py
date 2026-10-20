"""Skin manifests are checked against a registry; unknown entries are refused by name."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.web.skins import load_skins

_SKIN = {
    "id": "reviewer",
    "title": "Reviewer",
    "panels": ["legend", "reports"],
    "layers": ["blocks", "treatments"],
    "actions": [],
    "read_only": True,
}


def _write(directory: Path, document: dict[str, object], name: str = "skin.json") -> Path:
    """Write one manifest into a directory."""
    path = directory / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_shipped_skins_load_and_are_unique() -> None:
    """The four manifests in the package are valid and distinct."""
    skins = load_skins(Path("ws4/web/skins"))
    assert sorted(skins) == ["model-builder", "reviewer", "scenario-analyst", "scenario-browser"]
    assert skins["reviewer"].read_only is True


def test_an_unknown_panel_layer_or_action_is_refused_by_name(tmp_path: Path) -> None:
    """A registry mismatch fails the load instead of being ignored."""
    panels = tmp_path / "panels"
    panels.mkdir()
    _write(panels, dict(_SKIN, panels=["deck"]))
    with pytest.raises(ValueError, match="deck"):
        load_skins(panels)
    layers = tmp_path / "layers"
    layers.mkdir()
    _write(layers, dict(_SKIN, layers=["raster"]))
    with pytest.raises(ValueError, match="raster"):
        load_skins(layers)
    actions = tmp_path / "actions"
    actions.mkdir()
    _write(actions, dict(_SKIN, actions=["delete"]))
    with pytest.raises(ValueError, match="delete"):
        load_skins(actions)


def test_a_read_only_skin_cannot_carry_a_mutating_action(tmp_path: Path) -> None:
    """The read-only rule is enforced at load, not left to the client."""
    directory = tmp_path / "ro"
    directory.mkdir()
    _write(directory, dict(_SKIN, actions=["save_targets"]))
    with pytest.raises(ValueError, match="read-only"):
        load_skins(directory)


def test_a_duplicate_id_is_refused(tmp_path: Path) -> None:
    """Two manifests cannot claim the same skin id."""
    directory = tmp_path / "dup"
    directory.mkdir()
    _write(directory, _SKIN, "a.json")
    _write(directory, _SKIN, "b.json")
    with pytest.raises(ValueError, match="already used"):
        load_skins(directory)
