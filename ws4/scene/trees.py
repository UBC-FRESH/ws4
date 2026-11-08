"""The synthetic individual-tree inventory used by the fire-scene viewer.

The tree layer is a plausible realization of a stand, not a measured inventory. The scene
manifest marks it synthetic and records the generator and seed. The contract is deliberately
small: position, species, size, crown shape, live/dead state, and the fuel values the viewer
needs to decide what burns and how brightly.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

TREE_SCHEMA_VERSION: Final[str] = "ws4.tree.inventory.v1"

TREE_COLUMNS: Final[tuple[str, ...]] = (
    "tree_id",
    "fragment_id",
    "x",
    "y",
    "z",
    "species",
    "dbh_cm",
    "height_m",
    "crown_ratio",
    "crown_radius_m",
    "live",
    "decay_class",
    "crown_fuel_t",
    "surface_fuel_t_ha",
    "snag_t",
    "provenance",
)


class TreeError(ValueError):
    """Raised when a tree or a tree inventory is invalid."""


def _text(value: object, field: str) -> str:
    """Return a non-empty, stripped string."""
    if not isinstance(value, str) or not value.strip():
        raise TreeError(f"{field} must be a non-empty string")
    return value.strip()


def _number(value: object, field: str) -> float:
    """Return a finite float, normalizing negative zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TreeError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise TreeError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _positive(value: object, field: str) -> float:
    """Return a finite, strictly positive float."""
    number = _number(value, field)
    if number <= 0.0:
        raise TreeError(f"{field} must be positive")
    return number


def _probability(value: object, field: str) -> float:
    """Return a number in [0, 1]."""
    number = _number(value, field)
    if number < 0.0 or number > 1.0:
        raise TreeError(f"{field} must be between 0 and 1")
    return number


@dataclass(frozen=True)
class Tree:
    """One synthetic individual tree.

    Parameters
    ----------
    tree_id : str
        Stable identifier within the inventory.
    fragment_id : int
        The WS4 fragment the tree belongs to.
    x, y, z : float
        Scene coordinates in metres. z is the ground elevation.
    species : str
        Species label.
    dbh_cm : float
        Diameter at breast height.
    height_m : float
        Total tree height.
    crown_ratio : float
        Live crown length divided by height, in [0, 1].
    crown_radius_m : float
        Crown radius in metres.
    live : bool
        Whether the tree is live at scene start.
    decay_class : int
        Dead-wood decay class, 0 for live.
    crown_fuel_t : float
        Crown fuel mass in tonnes.
    surface_fuel_t_ha : float
        Local surface fuel load.
    snag_t : float
        Standing dead mass in tonnes.
    provenance : str
        Generator provenance label.
    """

    tree_id: str
    fragment_id: int
    x: float
    y: float
    z: float
    species: str
    dbh_cm: float
    height_m: float
    crown_ratio: float
    crown_radius_m: float
    live: bool
    decay_class: int
    crown_fuel_t: float
    surface_fuel_t_ha: float
    snag_t: float
    provenance: str

    def __post_init__(self) -> None:
        """Validate the tree record."""
        tree_id = _text(self.tree_id, "tree_id")
        if isinstance(self.fragment_id, bool) or not isinstance(self.fragment_id, int):
            raise TreeError("fragment_id must be an integer")
        if self.fragment_id <= 0:
            raise TreeError("fragment_id must be positive")
        for field in ("x", "y", "z"):
            _number(getattr(self, field), field)
        species = _text(self.species, "species")
        dbh = _positive(self.dbh_cm, "dbh_cm")
        height = _positive(self.height_m, "height_m")
        crown_ratio = _probability(self.crown_ratio, "crown_ratio")
        crown_radius = _number(self.crown_radius_m, "crown_radius_m")
        if crown_radius < 0.0:
            raise TreeError("crown_radius_m must be non-negative")
        if not isinstance(self.live, (bool, np.bool_)):
            raise TreeError("live must be a boolean")
        if isinstance(self.decay_class, bool) or not isinstance(self.decay_class, int):
            raise TreeError("decay_class must be an integer")
        if self.decay_class < 0:
            raise TreeError("decay_class must be non-negative")
        crown_fuel = _number(self.crown_fuel_t, "crown_fuel_t")
        surface_fuel = _number(self.surface_fuel_t_ha, "surface_fuel_t_ha")
        snag = _number(self.snag_t, "snag_t")
        if crown_fuel < 0.0 or surface_fuel < 0.0 or snag < 0.0:
            raise TreeError("fuel values must be non-negative")
        provenance = _text(self.provenance, "provenance")
        object.__setattr__(self, "tree_id", tree_id)
        object.__setattr__(self, "species", species)
        object.__setattr__(self, "dbh_cm", dbh)
        object.__setattr__(self, "height_m", height)
        object.__setattr__(self, "crown_ratio", crown_ratio)
        object.__setattr__(self, "crown_radius_m", crown_radius)
        object.__setattr__(self, "crown_fuel_t", crown_fuel)
        object.__setattr__(self, "surface_fuel_t_ha", surface_fuel)
        object.__setattr__(self, "snag_t", snag)
        object.__setattr__(self, "provenance", provenance)

    @property
    def basal_area_m2(self) -> float:
        """Return the tree's basal area in square metres.

        Returns
        -------
        float
            ``pi * (dbh_cm / 200) ** 2``.
        """
        return math.pi * (self.dbh_cm / 200.0) ** 2

    def to_dict(self) -> dict[str, object]:
        """Return the tree as a JSON/Parquet-serializable mapping.

        Returns
        -------
        dict
            The tree fields.
        """
        return {
            "tree_id": self.tree_id,
            "fragment_id": self.fragment_id,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "species": self.species,
            "dbh_cm": self.dbh_cm,
            "height_m": self.height_m,
            "crown_ratio": self.crown_ratio,
            "crown_radius_m": self.crown_radius_m,
            "live": self.live,
            "decay_class": self.decay_class,
            "crown_fuel_t": self.crown_fuel_t,
            "surface_fuel_t_ha": self.surface_fuel_t_ha,
            "snag_t": self.snag_t,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> Tree:
        """Validate and construct a tree from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        Tree
            The validated tree.
        """
        if not isinstance(payload, Mapping):
            raise TreeError("tree must be a mapping")
        required = TREE_COLUMNS
        missing = [field for field in required if field not in payload]
        if missing:
            raise TreeError(f"missing tree fields: {', '.join(missing)}")
        live = payload["live"]
        if not isinstance(live, (bool, np.bool_)):
            raise TreeError("live must be a boolean")
        live = bool(live)
        return cls(
            tree_id=_text(payload["tree_id"], "tree_id"),
            fragment_id=int(float(str(payload["fragment_id"]))),
            x=_number(payload["x"], "x"),
            y=_number(payload["y"], "y"),
            z=_number(payload["z"], "z"),
            species=_text(payload["species"], "species"),
            dbh_cm=_positive(payload["dbh_cm"], "dbh_cm"),
            height_m=_positive(payload["height_m"], "height_m"),
            crown_ratio=_probability(payload["crown_ratio"], "crown_ratio"),
            crown_radius_m=_number(payload["crown_radius_m"], "crown_radius_m"),
            live=live,
            decay_class=int(float(str(payload["decay_class"]))),
            crown_fuel_t=_number(payload["crown_fuel_t"], "crown_fuel_t"),
            surface_fuel_t_ha=_number(payload["surface_fuel_t_ha"], "surface_fuel_t_ha"),
            snag_t=_number(payload["snag_t"], "snag_t"),
            provenance=_text(payload["provenance"], "provenance"),
        )


@dataclass(frozen=True)
class TreeInventory:
    """A deterministic synthetic tree inventory over a fragment layout.

    Parameters
    ----------
    trees : tuple of Tree
        The trees.
    fragment_areas : mapping of int to float
        Fragment area in hectares.
    fragment_origins : mapping of int to (float, float)
        Lower-left scene coordinates of each fragment's square footprint.
    seed : int
        Generator seed.
    source : str
        Generator provenance label.
    """

    trees: tuple[Tree, ...]
    fragment_areas: Mapping[int, float]
    fragment_origins: Mapping[int, tuple[float, float]]
    seed: int
    source: str

    def __post_init__(self) -> None:
        """Validate the inventory's ids, areas, and origins."""
        trees = tuple(self.trees)
        seen: set[str] = set()
        for tree in trees:
            if not isinstance(tree, Tree):
                raise TreeError("trees must contain Tree records")
            if tree.tree_id in seen:
                raise TreeError(f"duplicate tree id: {tree.tree_id!r}")
            seen.add(tree.tree_id)
            if tree.fragment_id not in self.fragment_areas:
                raise TreeError(f"tree {tree.tree_id!r} names an unknown fragment")
        areas = {
            int(fragment): _positive(area, "fragment area")
            for fragment, area in self.fragment_areas.items()
        }
        origins: dict[int, tuple[float, float]] = {}
        for fragment, origin in self.fragment_origins.items():
            if fragment not in areas:
                raise TreeError(f"origin names an unknown fragment: {fragment}")
            if len(origin) != 2:
                raise TreeError("fragment origins must be (x, y) pairs")
            origins[int(fragment)] = (
                _number(origin[0], "origin x"),
                _number(origin[1], "origin y"),
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise TreeError("seed must be a non-negative integer")
        source = _text(self.source, "source")
        object.__setattr__(self, "trees", trees)
        object.__setattr__(self, "fragment_areas", areas)
        object.__setattr__(self, "fragment_origins", origins)
        object.__setattr__(self, "source", source)

    def to_frame(self) -> pd.DataFrame:
        """Return the inventory as a table.

        Returns
        -------
        pandas.DataFrame
            One row per tree with the ``TREE_COLUMNS`` columns.
        """
        return pd.DataFrame([tree.to_dict() for tree in self.trees], columns=list(TREE_COLUMNS))

    @classmethod
    def from_frame(
        cls,
        frame: pd.DataFrame,
        *,
        fragment_areas: Mapping[int, float],
        fragment_origins: Mapping[int, tuple[float, float]],
        seed: int,
        source: str,
    ) -> TreeInventory:
        """Build an inventory from a tree table.

        Parameters
        ----------
        frame : pandas.DataFrame
            A table with the ``TREE_COLUMNS`` columns.
        fragment_areas : mapping of int to float
            Fragment area in hectares.
        fragment_origins : mapping of int to (float, float)
            Fragment square origins.
        seed : int
            Generator seed.
        source : str
            Generator provenance label.

        Returns
        -------
        TreeInventory
            The validated inventory.

        Raises
        ------
        TreeError
            If a required column is missing or a row is invalid.
        """
        missing = [column for column in TREE_COLUMNS if column not in frame.columns]
        if missing:
            raise TreeError(f"tree table is missing columns: {', '.join(missing)}")
        trees = tuple(
            Tree.from_dict({str(key): value for key, value in row.items()})
            for row in frame.to_dict(orient="records")
        )
        return cls(
            trees=trees,
            fragment_areas=fragment_areas,
            fragment_origins=fragment_origins,
            seed=seed,
            source=source,
        )

    def summary(self) -> dict[str, object]:
        """Return a stable inventory summary.

        Returns
        -------
        dict
            Tree count, area, stems per hectare, basal area, mean size, species, seed, and
            source.
        """
        area = sum(self.fragment_areas.values())
        count = len(self.trees)
        basal = sum(tree.basal_area_m2 for tree in self.trees)
        return {
            "schema_version": TREE_SCHEMA_VERSION,
            "tree_count": count,
            "area_ha": area,
            "stems_per_ha": 0.0 if area <= 0.0 else count / area,
            "basal_area_m2_per_ha": 0.0 if area <= 0.0 else basal / area,
            "mean_dbh_cm": 0.0 if count == 0 else sum(tree.dbh_cm for tree in self.trees) / count,
            "mean_height_m": 0.0
            if count == 0
            else sum(tree.height_m for tree in self.trees) / count,
            "live_trees": sum(1 for tree in self.trees if tree.live),
            "species": sorted({tree.species for tree in self.trees}),
            "seed": self.seed,
            "source": self.source,
        }

    def fragment_summary(self) -> pd.DataFrame:
        """Return per-fragment tree statistics.

        Returns
        -------
        pandas.DataFrame
            Fragment id, area, tree count, stems per hectare, basal area, mean size, and
            crown fuel.
        """
        if not self.trees:
            return pd.DataFrame(
                columns=[
                    "fragment_id",
                    "area_ha",
                    "tree_count",
                    "stems_per_ha",
                    "basal_area_m2_per_ha",
                    "mean_dbh_cm",
                    "mean_height_m",
                    "crown_fuel_t",
                ]
            )
        frame = self.to_frame()
        rows: list[dict[str, object]] = []
        for fragment, group in frame.groupby("fragment_id", sort=True):
            fragment_key = int(str(fragment))
            area = self.fragment_areas[fragment_key]
            count = len(group)
            rows.append(
                {
                    "fragment_id": fragment_key,
                    "area_ha": area,
                    "tree_count": count,
                    "stems_per_ha": 0.0 if area <= 0.0 else count / area,
                    "basal_area_m2_per_ha": 0.0
                    if area <= 0.0
                    else float((math.pi * (group["dbh_cm"].astype(float) / 200.0) ** 2).sum())
                    / area,
                    "mean_dbh_cm": float(group["dbh_cm"].astype(float).mean()),
                    "mean_height_m": float(group["height_m"].astype(float).mean()),
                    "crown_fuel_t": float(group["crown_fuel_t"].astype(float).sum()),
                }
            )
        return pd.DataFrame(rows)

    def bounds_violations(self) -> tuple[str, ...]:
        """Return trees outside their fragment's synthetic square footprint.

        Returns
        -------
        tuple of str
            The violating tree ids, sorted.
        """
        violations: list[str] = []
        for tree in self.trees:
            area = self.fragment_areas[tree.fragment_id]
            side = math.sqrt(area * 10_000.0)
            origin = self.fragment_origins[tree.fragment_id]
            if (
                tree.x < origin[0] - 1e-6
                or tree.x > origin[0] + side + 1e-6
                or tree.y < origin[1] - 1e-6
                or tree.y > origin[1] + side + 1e-6
            ):
                violations.append(tree.tree_id)
        return tuple(sorted(violations))


def synthetic_tree_inventory(
    fragment_areas: Mapping[int, float],
    *,
    seed: int,
    trees_per_ha: float = 200.0,
    species: str = "PL",
    dbh_mean_cm: float = 30.0,
    dbh_sd_cm: float = 8.0,
    surface_fuel_t_ha: float = 10.0,
    provenance: str = "ws4.scene.synthetic.v1",
    fragment_origins: Mapping[int, tuple[float, float]] | None = None,
) -> TreeInventory:
    """Build a deterministic synthetic tree inventory over square fragments.

    Parameters
    ----------
    fragment_areas : mapping of int to float
        Fragment area in hectares.
    seed : int
        Generator seed.
    trees_per_ha : float, optional
        Target density (default 200).
    species : str, optional
        Species label (default ``PL``).
    dbh_mean_cm : float, optional
        Mean DBH (default 30 cm).
    dbh_sd_cm : float, optional
        DBH standard deviation (default 8 cm).
    surface_fuel_t_ha : float, optional
        Local surface fuel load (default 10 t/ha).
    provenance : str, optional
        Generator provenance label.
    fragment_origins : mapping of int to (float, float) or None, optional
        Lower-left origin of each fragment's square. None lays the fragments out in a
        near-square grid.

    Returns
    -------
    TreeInventory
        The deterministic inventory.

    Raises
    ------
    TreeError
        If the inputs are invalid.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise TreeError("seed must be a non-negative integer")
    density = _positive(trees_per_ha, "trees_per_ha")
    mean = _positive(dbh_mean_cm, "dbh_mean_cm")
    sd = _positive(dbh_sd_cm, "dbh_sd_cm")
    fuel = _number(surface_fuel_t_ha, "surface_fuel_t_ha")
    if fuel < 0.0:
        raise TreeError("surface_fuel_t_ha must be non-negative")
    species = _text(species, "species")
    provenance = _text(provenance, "provenance")
    areas = {
        int(fragment): _positive(area, "fragment area") for fragment, area in fragment_areas.items()
    }
    if not areas:
        raise TreeError("at least one fragment is required")
    if fragment_origins is None:
        count = len(areas)
        cols = max(1, math.ceil(math.sqrt(count)))
        side = max(math.sqrt(area * 10_000.0) for area in areas.values())
        origins = {
            fragment: (float(index % cols) * side, float(index // cols) * side)
            for index, fragment in enumerate(sorted(areas))
        }
    else:
        origins = {
            int(fragment): (float(origin[0]), float(origin[1]))
            for fragment, origin in fragment_origins.items()
        }
        missing = sorted(set(areas) - set(origins))
        if missing:
            raise TreeError(f"missing fragment origins: {missing}")
    sigma = math.sqrt(math.log(1.0 + (sd / mean) ** 2))
    mu = math.log(mean) - 0.5 * sigma * sigma
    trees: list[Tree] = []
    for fragment in sorted(areas):
        area = areas[fragment]
        side = math.sqrt(area * 10_000.0)
        origin = origins[fragment]
        rng = np.random.default_rng([seed, fragment])
        count = max(1, round(density * area))
        for index in range(count):
            dbh = float(min(150.0, max(2.0, rng.lognormal(mu, sigma))))
            height = 1.3 * dbh**0.8
            crown_ratio = float(rng.uniform(0.35, 0.55))
            crown_radius = 0.12 * height * float(rng.uniform(0.8, 1.2))
            biomass = 0.25 * (dbh / 30.0) ** 2.5
            trees.append(
                Tree(
                    tree_id=f"{fragment}-{index:04d}",
                    fragment_id=fragment,
                    x=origin[0] + float(rng.uniform(0.0, side)),
                    y=origin[1] + float(rng.uniform(0.0, side)),
                    z=0.0,
                    species=species,
                    dbh_cm=dbh,
                    height_m=height,
                    crown_ratio=crown_ratio,
                    crown_radius_m=crown_radius,
                    live=True,
                    decay_class=0,
                    crown_fuel_t=0.2 * biomass,
                    surface_fuel_t_ha=fuel,
                    snag_t=0.0,
                    provenance=provenance,
                )
            )
    return TreeInventory(
        trees=tuple(trees),
        fragment_areas=areas,
        fragment_origins=origins,
        seed=seed,
        source=provenance,
    )
