"""The portable fire-scene package and its standalone 3D viewer.

The package turns a P144 fire run and a synthetic individual-tree inventory into a scene
directory: a tree table, stand squares, fire events, per-tree animation, a manifest, and a
viewer HTML. The tree layer is synthetic and the fire event log remains the authority.
"""

from __future__ import annotations

from .ignition import IgnitionSamplingError, sample_tree_ignition
from .nemora import (
    NEMORA_ADAPTER_VERSION,
    NemoraAdapterError,
    VriFragment,
    load_nemora_scene,
    load_nemora_tree_table,
    load_vri_polygons,
    trees_from_nemora,
)
from .scene import (
    SCENE_SCHEMA_VERSION,
    FireScene,
    SceneError,
    SceneManifest,
    ScenePaths,
    compile_fire_scene,
)
from .trees import (
    TREE_COLUMNS,
    TREE_SCHEMA_VERSION,
    Tree,
    TreeError,
    TreeInventory,
    synthetic_tree_inventory,
)

__all__ = [
    "NEMORA_ADAPTER_VERSION",
    "SCENE_SCHEMA_VERSION",
    "TREE_COLUMNS",
    "TREE_SCHEMA_VERSION",
    "FireScene",
    "IgnitionSamplingError",
    "NemoraAdapterError",
    "SceneError",
    "SceneManifest",
    "ScenePaths",
    "Tree",
    "TreeError",
    "TreeInventory",
    "VriFragment",
    "compile_fire_scene",
    "load_nemora_scene",
    "load_nemora_tree_table",
    "load_vri_polygons",
    "sample_tree_ignition",
    "synthetic_tree_inventory",
    "trees_from_nemora",
]
