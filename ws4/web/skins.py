"""Skin manifests: one application, different panels and permissions.

A skin is a JSON document checked against a registry. An unknown panel, layer or action is
refused by name when the service starts, rather than ignored; a read-only skin may not carry a
mutating action. This is the rule that keeps a skin a presentation choice instead of a second
application.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The panels the application can render.
PANELS = frozenset(
    {"legend", "dataset", "lidar", "carbon", "targets", "reports", "comparison", "search"}
)

#: The layer families the map can offer.
LAYERS = frozenset({"blocks", "treatments", "patches", "compartments", "roads"})

#: The actions a skin may enable.
ACTIONS = frozenset({"edit_targets", "save_targets", "export"})

#: Actions that change state, which a read-only skin may not carry.
MUTATING = frozenset({"edit_targets", "save_targets"})


@dataclass(frozen=True)
class Skin:
    """A checked skin manifest.

    Attributes
    ----------
    id : str
        The skin's identifier, unique within the directory.
    title : str
        The label shown in the application.
    panels : tuple of str
        The panels the skin shows, from :data:`PANELS`.
    layers : tuple of str
        The layer families the skin offers, from :data:`LAYERS`.
    actions : tuple of str
        The actions the skin enables, from :data:`ACTIONS`.
    read_only : bool
        When true, no mutating action may be present.
    """

    id: str
    title: str
    panels: tuple[str, ...]
    layers: tuple[str, ...]
    actions: tuple[str, ...]
    read_only: bool

    def row(self) -> dict[str, Any]:
        """Return the manifest as a JSON-ready row.

        Returns
        -------
        dict of str to object
            The skin's fields, with lists instead of tuples.
        """
        return {
            "id": self.id,
            "title": self.title,
            "panels": list(self.panels),
            "layers": list(self.layers),
            "actions": list(self.actions),
            "read_only": self.read_only,
        }


def load_skins(directory: Path) -> dict[str, Skin]:
    """Load and validate the skin manifests in a directory.

    Parameters
    ----------
    directory : Path
        The directory of ``*.json`` manifests.

    Returns
    -------
    dict of str to Skin
        The skins by id.

    Raises
    ------
    ValueError
        When a manifest names an unknown panel, layer or action, repeats an id, or is read-only and
        carries a mutating action.
    """
    skins: dict[str, Skin] = {}
    for path in sorted(Path(directory).glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        skin = Skin(
            id=str(document.get("id", path.stem)),
            title=str(document.get("title", path.stem)),
            panels=tuple(str(name) for name in document.get("panels", [])),
            layers=tuple(str(name) for name in document.get("layers", [])),
            actions=tuple(str(name) for name in document.get("actions", [])),
            read_only=bool(document.get("read_only", False)),
        )
        for name in skin.panels:
            if name not in PANELS:
                raise ValueError(f"{path.name}: unknown panel {name!r}")
        for name in skin.layers:
            if name not in LAYERS:
                raise ValueError(f"{path.name}: unknown layer {name!r}")
        for name in skin.actions:
            if name not in ACTIONS:
                raise ValueError(f"{path.name}: unknown action {name!r}")
        if skin.read_only and set(skin.actions) & MUTATING:
            offending = sorted(set(skin.actions) & MUTATING)
            raise ValueError(f"{path.name}: a read-only skin cannot carry {offending}")
        if skin.id in skins:
            raise ValueError(f"{path.name}: the id {skin.id!r} is already used")
        skins[skin.id] = skin
    return skins
