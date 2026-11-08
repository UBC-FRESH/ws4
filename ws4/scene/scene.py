"""Compile a P144 fire run and a synthetic tree inventory into a portable 3D scene.

The scene is a run artifact. It does not change the compiled dataset, the ecosystem package,
or the event log. The fire event log remains the authority for the fragment-level outcome; the
scene adds a per-tree ignition schedule and a standalone viewer.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pandas as pd

from ..ecosystem.events import Event
from ..ecosystem.fire import FireResult
from ..ecosystem.log import EventLog
from .trees import TREE_SCHEMA_VERSION, TreeInventory

SCENE_SCHEMA_VERSION: Final[str] = "ws4.fire.scene.v1"
VIEWER_TEMPLATE: Final[str] = "viewer.html"


class SceneError(ValueError):
    """Raised when a fire scene cannot be compiled or written."""


@dataclass(frozen=True)
class SceneManifest:
    """The provenance and counts of one fire scene.

    Parameters
    ----------
    scene_id : str
        Stable scene identifier.
    seed : int
        The fire scenario seed.
    run_replay_token : str
        The replay digest of the P144 event log.
    scenario_id : str
        The fire scenario id.
    fragment_count : int
        Number of fragments in the scene.
    tree_count : int
        Number of synthetic trees.
    synthetic_trees : bool
        Whether the tree layer is synthetic.
    source : str
        Tree generator provenance.
    particle_budget : int
        The viewer's particle budget.
    burn_duration_years : float
        The per-tree burn duration used by the animation.
    time_unit : str, optional
        The unit of the scene clock (default ``years``).
    created_utc : str or None
        Optional creation timestamp. None keeps the data deterministic.
    attributes : dict of str to object
        Further public-safe provenance.
    schema_version : str
        The scene schema version.
    """

    scene_id: str
    seed: int
    run_replay_token: str
    scenario_id: str
    fragment_count: int
    tree_count: int
    synthetic_trees: bool
    source: str
    particle_budget: int
    burn_duration_years: float
    time_unit: str = "years"
    created_utc: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)
    schema_version: str = SCENE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate the manifest."""
        if not self.scene_id.strip():
            raise SceneError("scene_id must be non-empty")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise SceneError("seed must be a non-negative integer")
        if not self.run_replay_token.strip():
            raise SceneError("run_replay_token must be non-empty")
        if not self.scenario_id.strip():
            raise SceneError("scenario_id must be non-empty")
        if self.fragment_count <= 0 or self.tree_count <= 0:
            raise SceneError("fragment_count and tree_count must be positive")
        if not isinstance(self.synthetic_trees, bool):
            raise SceneError("synthetic_trees must be a boolean")
        if not self.source.strip():
            raise SceneError("source must be non-empty")
        if isinstance(self.particle_budget, bool) or not isinstance(self.particle_budget, int):
            raise SceneError("particle_budget must be an integer")
        if self.particle_budget <= 0:
            raise SceneError("particle_budget must be positive")
        if not math.isfinite(self.burn_duration_years) or self.burn_duration_years <= 0.0:
            raise SceneError("burn_duration_years must be positive")
        if not self.time_unit.strip():
            raise SceneError("time_unit must be non-empty")
        if self.schema_version != SCENE_SCHEMA_VERSION:
            raise SceneError(f"schema_version must be {SCENE_SCHEMA_VERSION!r}")

    def to_dict(self) -> dict[str, object]:
        """Return the manifest as a JSON-serializable mapping.

        Returns
        -------
        dict
            The manifest fields.
        """
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "seed": self.seed,
            "run_replay_token": self.run_replay_token,
            "scenario_id": self.scenario_id,
            "fragment_count": self.fragment_count,
            "tree_count": self.tree_count,
            "synthetic_trees": self.synthetic_trees,
            "source": self.source,
            "particle_budget": self.particle_budget,
            "burn_duration_years": self.burn_duration_years,
            "time_unit": self.time_unit,
            "attributes": dict(self.attributes),
        }
        if self.created_utc is not None:
            payload["created_utc"] = self.created_utc
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> SceneManifest:
        """Validate and construct a manifest from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        SceneManifest
            The validated manifest.
        """
        if not isinstance(payload, Mapping):
            raise SceneError("manifest must be a mapping")
        raw_attributes = payload.get("attributes", {})
        if not isinstance(raw_attributes, Mapping):
            raise SceneError("manifest attributes must be a mapping")
        return cls(
            scene_id=str(payload["scene_id"]),
            seed=int(float(str(payload["seed"]))),
            run_replay_token=str(payload["run_replay_token"]),
            scenario_id=str(payload["scenario_id"]),
            fragment_count=int(float(str(payload["fragment_count"]))),
            tree_count=int(float(str(payload["tree_count"]))),
            synthetic_trees=bool(payload["synthetic_trees"]),
            source=str(payload["source"]),
            particle_budget=int(float(str(payload["particle_budget"]))),
            burn_duration_years=float(str(payload["burn_duration_years"])),
            time_unit=str(payload.get("time_unit", "years")),
            created_utc=None if payload.get("created_utc") is None else str(payload["created_utc"]),
            attributes={str(key): value for key, value in raw_attributes.items()},
            schema_version=str(payload.get("schema_version", SCENE_SCHEMA_VERSION)),
        )


@dataclass(frozen=True)
class ScenePaths:
    """The files written for one fire scene.

    Attributes
    ----------
    directory : Path
        Scene directory.
    manifest : Path
        ``manifest.json``.
    viewer : Path
        The standalone ``viewer.html``.
    trees : Path
        ``trees.parquet``.
    stands : Path
        ``stands.parquet``.
    fires : Path
        ``fires.csv``.
    animation : Path
        ``animation.parquet``.
    event_log : Path
        ``event_log.json``.
    summary : Path
        ``summary.json``.
    """

    directory: Path
    manifest: Path
    viewer: Path
    trees: Path
    stands: Path
    fires: Path
    animation: Path
    event_log: Path
    summary: Path


@dataclass(frozen=True)
class FireScene:
    """A compiled fire scene.

    Parameters
    ----------
    manifest : SceneManifest
        The scene provenance and counts.
    trees : TreeInventory
        The synthetic tree inventory.
    stands : pandas.DataFrame
        Fragment squares with their burn times.
    fires : pandas.DataFrame
        The fire events used by the viewer.
    animation : pandas.DataFrame
        The per-tree ignition schedule.
    event_log : EventLog
        The full P144 event log.
    time_unit : str, optional
        The unit of the scene clock (default ``years``).
    """

    manifest: SceneManifest
    trees: TreeInventory
    stands: pd.DataFrame
    fires: pd.DataFrame
    animation: pd.DataFrame
    event_log: EventLog
    time_unit: str = "years"

    def summary(self) -> dict[str, object]:
        """Return a stable scene summary.

        Returns
        -------
        dict
            The manifest, tree summary, fire count, and timeline end.
        """
        payload = self.viewer_payload()
        timeline = payload.get("timeline")
        timeline_end = float(timeline.get("end", 1.0)) if isinstance(timeline, dict) else 1.0
        return {
            "manifest": self.manifest.to_dict(),
            "trees": self.trees.summary(),
            "fire_count": len(self.fires),
            "timeline_end": timeline_end,
            "run_replay_token": self.event_log.replay_token,
        }

    def viewer_payload(self) -> dict[str, object]:
        """Return the compact payload embedded in the standalone viewer.

        Returns
        -------
        dict
            Bounds, stands, trees, fires, timeline, counts, and manifest.
        """
        stands: list[dict[str, object]] = []
        for stand in self.stands.itertuples(index=False):
            polygon_value = getattr(stand, "polygon", None)
            if not isinstance(polygon_value, (list, tuple)):
                polygon_value = None
            stands.append(
                {
                    "fragment_id": int(str(stand.fragment_id)),
                    "x": float(str(stand.x)),
                    "y": float(str(stand.y)),
                    "side": float(str(stand.side_m)),
                    "area_ha": float(str(stand.area_ha)),
                    "burn_time": None if pd.isna(stand.burn_time) else float(str(stand.burn_time)),
                    "polygon": polygon_value,
                }
            )
        animation = self.animation.set_index("tree_id")
        trees: list[dict[str, object]] = []
        for tree in self.trees.trees:
            animation_row = animation.loc[tree.tree_id]
            ignition = animation_row["ignition_time"]
            trees.append(
                {
                    "tree_id": tree.tree_id,
                    "fragment_id": tree.fragment_id,
                    "x": tree.x,
                    "y": tree.y,
                    "z": tree.z,
                    "species": tree.species,
                    "dbh_cm": tree.dbh_cm,
                    "height_m": tree.height_m,
                    "crown_ratio": tree.crown_ratio,
                    "crown_radius_m": tree.crown_radius_m,
                    "live": tree.live,
                    "crown_fuel_t": tree.crown_fuel_t,
                    "surface_fuel_t_ha": tree.surface_fuel_t_ha,
                    "burn_time": None if pd.isna(ignition) else float(str(ignition)),
                    "burn_duration": float(str(animation_row["burn_duration"])),
                    "flame_intensity": float(str(animation_row["flame_intensity"])),
                    "smoke_strength": float(str(animation_row["smoke_strength"])),
                    "post_fire_state": str(animation_row["post_fire_state"]),
                }
            )
        fires = [
            {
                "event_id": str(fire_row.event_id),
                "fragment_id": int(str(fire_row.fragment_id)),
                "time": float(str(fire_row.time)),
                "year": int(str(fire_row.year)),
                "severity": float(str(fire_row.severity)),
                "area_ha": float(str(fire_row.area_ha)),
                "ros_m_min": float(str(fire_row.ros_m_min)),
                "head_fire_intensity_kw_m": float(str(fire_row.head_fire_intensity_kw_m)),
                "flame_length_m": float(str(fire_row.flame_length_m)),
                "crown_fraction_burned": float(str(fire_row.crown_fraction_burned)),
                "smoke_strength": float(str(fire_row.smoke_strength)),
                "parent_event_id": None
                if pd.isna(fire_row.parent_event_id)
                else str(fire_row.parent_event_id),
            }
            for fire_row in self.fires.itertuples(index=False)
        ]
        if self.stands.empty:
            bounds = {"min_x": 0.0, "max_x": 1.0, "min_y": 0.0, "max_y": 1.0}
        else:
            points = [
                point
                for polygon in self.stands["polygon"]
                if polygon is not None
                for point in polygon
            ]
            if points:
                bounds = {
                    "min_x": min(float(point[0]) for point in points),
                    "max_x": max(float(point[0]) for point in points),
                    "min_y": min(float(point[1]) for point in points),
                    "max_y": max(float(point[1]) for point in points),
                }
            else:
                bounds = {
                    "min_x": float(self.stands["x"].min()),
                    "max_x": float((self.stands["x"] + self.stands["side_m"]).max()),
                    "min_y": float(self.stands["y"].min()),
                    "max_y": float((self.stands["y"] + self.stands["side_m"]).max()),
                }
        timeline_end = 1.0
        if not self.animation.empty:
            ignition = self.animation["ignition_time"].dropna()
            if not ignition.empty:
                ends = ignition + self.animation.loc[ignition.index, "burn_duration"]
                timeline_end = max(1.0, float(ends.max()))
        elif not self.fires.empty:
            timeline_end = max(1.0, float(self.fires["time"].max()) + 1.0)
        return {
            "schema_version": SCENE_SCHEMA_VERSION,
            "manifest": self.manifest.to_dict(),
            "bounds": bounds,
            "stands": stands,
            "trees": trees,
            "fires": fires,
            "timeline": {"start": 0.0, "end": timeline_end, "unit": self.time_unit},
            "counts": {
                "fragments": len(stands),
                "trees": len(trees),
                "fires": len(fires),
                "particle_budget": self.manifest.particle_budget,
            },
        }

    def write(self, out_dir: Path) -> ScenePaths:
        """Write the scene package and the standalone viewer.

        Parameters
        ----------
        out_dir : Path
            Destination directory. It is created when missing.

        Returns
        -------
        ScenePaths
            The written file paths.

        Raises
        ------
        SceneError
            If the viewer template is missing.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = out_dir / "manifest.json"
        trees_path = out_dir / "trees.parquet"
        stands_path = out_dir / "stands.parquet"
        fires_path = out_dir / "fires.csv"
        animation_path = out_dir / "animation.parquet"
        event_log_path = out_dir / "event_log.json"
        summary_path = out_dir / "summary.json"
        viewer_path = out_dir / "viewer.html"
        manifest_path.write_text(
            json.dumps(self.manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.trees.to_frame().to_parquet(trees_path, index=False)
        self.stands.to_parquet(stands_path, index=False)
        self.fires.to_csv(fires_path, index=False)
        self.animation.to_parquet(animation_path, index=False)
        self.event_log.write(event_log_path)
        summary_path.write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        template = Path(__file__).with_name(VIEWER_TEMPLATE)
        if not template.is_file():
            raise SceneError(f"viewer template not found: {template}")
        payload = json.dumps(self.viewer_payload(), separators=(",", ":"))
        payload = payload.replace("</", "<\\/")
        viewer_path.write_text(
            template.read_text(encoding="utf-8").replace("__SCENE_DATA__", payload),
            encoding="utf-8",
        )
        return ScenePaths(
            directory=out_dir,
            manifest=manifest_path,
            viewer=viewer_path,
            trees=trees_path,
            stands=stands_path,
            fires=fires_path,
            animation=animation_path,
            event_log=event_log_path,
            summary=summary_path,
        )


def _event_number(event: Event, name: str, default: float = 0.0) -> float:
    """Return a numeric event attribute or a default."""
    for key, value in event.attributes:
        if key == name and isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return default


def _fire_frame(fires: Sequence[Event]) -> pd.DataFrame:
    """Return the viewer's compact fire-event table."""
    rows: list[dict[str, object]] = []
    for event in fires:
        if event.event_type != "fire" or not event.fragment_ids:
            continue
        rows.append(
            {
                "event_id": event.event_id,
                "fragment_id": event.fragment_ids[0],
                "time": event.time,
                "year": event.year,
                "severity": 0.0 if event.severity_value is None else event.severity_value,
                "area_ha": 0.0 if event.area_ha is None else event.area_ha,
                "parent_event_id": event.parent_event_id,
                "ros_m_min": _event_number(event, "ros_m_min"),
                "head_fire_intensity_kw_m": _event_number(event, "head_fire_intensity_kw_m"),
                "flame_length_m": _event_number(event, "flame_length_m"),
                "crown_fraction_burned": _event_number(event, "crown_fraction_burned"),
                "smoke_strength": _event_number(event, "smoke_strength"),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "event_id",
            "fragment_id",
            "time",
            "year",
            "severity",
            "area_ha",
            "parent_event_id",
            "ros_m_min",
            "head_fire_intensity_kw_m",
            "flame_length_m",
            "crown_fraction_burned",
            "smoke_strength",
        ],
    )


def compile_fire_scene(
    fire: FireResult,
    trees: TreeInventory,
    *,
    scene_id: str | None = None,
    particle_budget: int = 4000,
    burn_duration_years: float = 0.15,
    time_unit: str = "years",
    created_utc: str | None = None,
) -> FireScene:
    """Compile a P144 fire run and a tree inventory into a scene.

    Parameters
    ----------
    fire : FireResult
        The completed fire run.
    trees : TreeInventory
        The synthetic tree inventory.
    scene_id : str or None, optional
        Scene id. None derives one from the event-log digest.
    particle_budget : int, optional
        The viewer particle budget (default 4000).
    burn_duration_years : float, optional
        Per-tree burn duration in the scene time unit (default 0.15).
    time_unit : str, optional
        Scene clock unit, such as ``years`` or ``minutes`` (default ``years``).
    created_utc : str or None, optional
        Optional creation timestamp. None keeps the scene data deterministic.

    Returns
    -------
    FireScene
        The compiled scene.

    Raises
    ------
    SceneError
        If a tree names a fragment outside the fire state or the inputs are invalid.
    """
    if not isinstance(fire, FireResult):
        raise SceneError("fire must be a FireResult")
    if not isinstance(trees, TreeInventory):
        raise SceneError("trees must be a TreeInventory")
    if not math.isfinite(burn_duration_years) or burn_duration_years <= 0.0:
        raise SceneError("burn_duration_years must be positive")
    unknown = sorted(set(trees.fragment_areas) - set(fire.state.fragment_areas))
    if unknown:
        raise SceneError(f"trees name fragments outside the fire state: {unknown}")
    fires = _fire_frame(fire.fires)
    earliest: dict[int, float] = {}
    if not fires.empty:
        for fire_row in fires.itertuples(index=False):
            fragment = int(str(fire_row.fragment_id))
            burn_time = float(str(fire_row.time))
            earliest[fragment] = min(burn_time, earliest.get(fragment, burn_time))
    stands_rows: list[dict[str, object]] = []
    for fragment, area in sorted(trees.fragment_areas.items()):
        origin = trees.fragment_origins[fragment]
        polygon = trees.fragment_polygons.get(fragment)
        stands_rows.append(
            {
                "fragment_id": fragment,
                "area_ha": area,
                "x": origin[0],
                "y": origin[1],
                "side_m": math.sqrt(area * 10_000.0),
                "burn_time": earliest.get(fragment, float("nan")),
                "polygon": None if polygon is None else [list(point) for point in polygon],
            }
        )
    stands = pd.DataFrame(stands_rows)
    behaviour: dict[int, tuple[float, float]] = {}
    if not fires.empty:
        for fire_row in fires.itertuples(index=False):
            fragment = int(str(fire_row.fragment_id))
            flame = float(str(fire_row.flame_length_m))
            smoke = float(str(fire_row.smoke_strength))
            previous = behaviour.get(fragment, (0.0, 0.0))
            behaviour[fragment] = (max(previous[0], flame), max(previous[1], smoke))
    animation_rows: list[dict[str, object]] = []
    for tree in trees.trees:
        tree_burn_time = earliest.get(tree.fragment_id)
        flame_length, smoke_strength = behaviour.get(tree.fragment_id, (0.0, 0.0))
        animation_rows.append(
            {
                "tree_id": tree.tree_id,
                "fragment_id": tree.fragment_id,
                "ignition_time": float("nan") if tree_burn_time is None else tree_burn_time,
                "burn_duration": 0.0 if tree_burn_time is None else burn_duration_years,
                "flame_intensity": 0.0
                if tree_burn_time is None
                else (
                    min(1.0, flame_length / 10.0)
                    if flame_length > 0.0
                    else min(1.0, 0.5 + tree.crown_fuel_t)
                ),
                "smoke_strength": 0.0
                if tree_burn_time is None
                else (
                    smoke_strength
                    if flame_length > 0.0
                    else min(1.0, 0.4 + tree.surface_fuel_t_ha / 20.0)
                ),
                "post_fire_state": "unburned" if tree_burn_time is None else "burned",
            }
        )
    animation = pd.DataFrame(animation_rows)
    manifest = SceneManifest(
        scene_id=scene_id or f"fire-{fire.log.replay_token[:12]}",
        seed=fire.log.metadata.scenario_seed or 0,
        run_replay_token=fire.log.replay_token,
        scenario_id=fire.log.metadata.scenario_id,
        fragment_count=len(stands),
        tree_count=len(trees.trees),
        synthetic_trees=True,
        source=trees.source,
        particle_budget=particle_budget,
        burn_duration_years=burn_duration_years,
        time_unit=time_unit,
        created_utc=created_utc,
        attributes={
            "tree_schema_version": TREE_SCHEMA_VERSION,
            "scene_schema_version": SCENE_SCHEMA_VERSION,
            "fire_event_count": len(fires),
        },
    )
    return FireScene(
        manifest=manifest,
        trees=trees,
        stands=stands,
        fires=fires,
        animation=animation,
        event_log=fire.log,
        time_unit=time_unit,
    )
