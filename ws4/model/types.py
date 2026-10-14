"""Canonical model types for WS4.

These pydantic models describe the logical parts of a forest estate model:
spatial fragments, their operational blocks, tracks, curves, treatments,
products, destinations, routes, and the compiled-dataset manifest.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

Id = int
Period = int  # years since t0 (annual resolution)


class Fragment(BaseModel):
    """Smallest spatial decision unit (for example, a stand polygon)."""

    fragment_id: Id
    block_id: Id
    area_ha: float
    age: int
    track_id: Id
    attrs: dict[str, float] = Field(default_factory=dict)


class Block(BaseModel):
    """Operational aggregate of fragments; attributes are derived at runtime."""

    block_id: Id
    # No static products/features here—computed on the fly by summing fragments.


class Track(BaseModel):
    """A succession pathway with its own growth and yield behaviour."""

    track_id: Id
    name: str


class CurvePoint(BaseModel):
    """One point of a long-format growth or yield curve."""

    curve_id: Id
    feature_id: Id
    age: int  # domain in years
    value: float  # e.g., m3/ha for product, or feature value


class Treatment(BaseModel):
    """An operation with fragment-level eligibility and operability rules."""

    treatment_id: Id
    label: str
    # Eligibility & operability are fragment-level predicates (SQL-like or Python expr AST):
    eligibility_expr: str  # e.g., "species in {'PL','SB'} and slope <= 35"
    operability_expr: str  # e.g., "offset() >= 80 and season in {'winter'}"
    new_track_id: Id | None = None
    reset_offset: bool = True


class Product(BaseModel):
    """A merchantable output tied to a yield curve and its destinations."""

    product_id: Id
    name: str
    yield_curve_id: Id
    dest_eligibility: set[Id] = Field(default_factory=set)


class Destination(BaseModel):
    """A mill or facility that receives a product."""

    dest_id: Id
    name: str


class RouteEdge(BaseModel):
    """One edge of the road network, with build and maintenance cost."""

    u: Id
    v: Id
    length_m: float
    build_cost: float = 0.0
    maintain_cost: float = 0.0


class TargetsConfig(BaseModel):
    """The period range and target terms for an optimization run."""

    periods: tuple[int, int] = (0, 200)
    terms: list[dict[str, object]]


class CanonicalDatasetManifest(BaseModel):
    """Manifest for a compiled dataset: schema version, tables, and sources."""

    schema_version: str = "0.1"
    tables: dict[str, str] = Field(default_factory=dict)
    sources: list[dict[str, str]] = Field(default_factory=list)
    options: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
