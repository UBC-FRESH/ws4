from __future__ import annotations
from typing import Literal, Optional, Dict, List, Tuple, Set
from pydantic import BaseModel, Field

Id = int
Period = int  # years since t0 (annual resolution)

class Fragment(BaseModel):
    fragment_id: Id
    block_id: Id
    area_ha: float
    age: int
    track_id: Id
    attrs: Dict[str, float] = Field(default_factory=dict)

class Block(BaseModel):
    block_id: Id
    # No static products/features here—computed on the fly by summing fragments.

class Track(BaseModel):
    track_id: Id
    name: str

class CurvePoint(BaseModel):
    curve_id: Id
    feature_id: Id
    age: int         # domain in years
    value: float     # e.g., m3/ha for product, or feature value

class Treatment(BaseModel):
    treatment_id: Id
    label: str
    # Eligibility & operability are fragment-level predicates (SQL-like or Python expr AST):
    eligibility_expr: str  # e.g., "species in {'PL','SB'} and slope <= 35"
    operability_expr: str  # e.g., "offset() >= 80 and season in {'winter'}"
    new_track_id: Optional[Id] = None
    reset_offset: bool = True

class Product(BaseModel):
    product_id: Id
    name: str
    yield_curve_id: Id
    dest_eligibility: Set[Id] = Field(default_factory=set)

class Destination(BaseModel):
    dest_id: Id
    name: str

class RouteEdge(BaseModel):
    u: Id; v: Id
    length_m: float
    build_cost: float = 0.0
    maintain_cost: float = 0.0

class TargetsConfig(BaseModel):
    periods: Tuple[int, int] = (0, 200)
    terms: List[Dict[str, object]]

class CanonicalDatasetManifest(BaseModel):
    version: str = "0.1"
    fragments_path: str
    blocks_map_path: Optional[str] = None
    tracks_path: str
    curves_path: str
    treatments_path: str
    products_path: str
    destinations_path: str
    routes_path: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)
