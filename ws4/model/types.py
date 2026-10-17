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
    """Smallest spatial decision unit (for example, a stand polygon).

    Attributes
    ----------
    fragment_id : int
        The fragment identifier, unique within the dataset.
    block_id : int
        The block the fragment belongs to.
    area_ha : float
        The fragment area, in hectares.
    age : int
        The fragment's age at the start of the horizon, in years.
    track_id : int
        The succession track the fragment follows.
    attrs : dict of str to float
        Further fragment attributes, such as slope or species composition.
    """

    fragment_id: Id
    block_id: Id
    area_ha: float
    age: int
    track_id: Id
    attrs: dict[str, float] = Field(default_factory=dict)


class Block(BaseModel):
    """Operational aggregate of fragments; attributes are derived at runtime.

    Attributes
    ----------
    block_id : int
        The block identifier. The block's area, age and products are summed from its
        fragments rather than stored here.
    """

    block_id: Id
    # No static products/features here—computed on the fly by summing fragments.


class Track(BaseModel):
    """A succession pathway with its own growth and yield behaviour.

    Attributes
    ----------
    track_id : int
        The track identifier.
    name : str
        The human-readable track name.
    """

    track_id: Id
    name: str


class CurvePoint(BaseModel):
    """One point of a long-format growth or yield curve.

    Attributes
    ----------
    curve_id : int
        The curve the point belongs to.
    feature_id : int
        The feature the curve measures.
    age : int
        The curve's domain value, in years.
    value : float
        The curve's value at ``age``, such as cubic metres per hectare.
    """

    curve_id: Id
    feature_id: Id
    age: int  # domain in years
    value: float  # e.g., m3/ha for product, or feature value


class Treatment(BaseModel):
    """An operation with fragment-level eligibility and operability rules.

    Attributes
    ----------
    treatment_id : int
        The treatment identifier.
    label : str
        The treatment name, as it appears in a schedule.
    eligibility_expr : str
        The fragment-level eligibility predicate: a fragment may take the treatment only when
        the expression is true.
    operability_expr : str
        The fragment-level operability predicate, evaluated after eligibility.
    new_track_id : int or None
        The track the fragment moves to after the treatment, or None to keep its track.
    reset_offset : bool
        Whether the treatment resets the fragment's age offset to zero.
    """

    treatment_id: Id
    label: str
    # Eligibility & operability are fragment-level predicates (SQL-like or Python expr AST):
    eligibility_expr: str  # e.g., "species in {'PL','SB'} and slope <= 35"
    operability_expr: str  # e.g., "offset() >= 80 and season in {'winter'}"
    new_track_id: Id | None = None
    reset_offset: bool = True


class Product(BaseModel):
    """A merchantable output tied to a yield curve and its destinations.

    Attributes
    ----------
    product_id : int
        The product identifier.
    name : str
        The product name, as it appears in an account label.
    yield_curve_id : int
        The yield curve giving the product's volume per hectare by age.
    dest_eligibility : set of int
        The destinations that accept the product.
    """

    product_id: Id
    name: str
    yield_curve_id: Id
    dest_eligibility: set[Id] = Field(default_factory=set)


class Destination(BaseModel):
    """A mill or facility that receives a product.

    Attributes
    ----------
    dest_id : int
        The destination identifier.
    name : str
        The destination name.
    """

    dest_id: Id
    name: str


class RouteEdge(BaseModel):
    """One edge of the road network, with build and maintenance cost.

    Attributes
    ----------
    u : int
        The identifier of the edge's first vertex.
    v : int
        The identifier of the edge's second vertex.
    length_m : float
        The edge length, in metres.
    build_cost : float
        The cost of building the edge.
    maintain_cost : float
        The cost of maintaining the edge once it is built.
    """

    u: Id
    v: Id
    length_m: float
    build_cost: float = 0.0
    maintain_cost: float = 0.0


class TargetsConfig(BaseModel):
    """The period range and target terms for an optimization run.

    Attributes
    ----------
    periods : tuple of int
        The first and last period the run accounts over.
    terms : list of dict
        The target terms, one per goal.
    """

    periods: tuple[int, int] = (0, 200)
    terms: list[dict[str, object]]


class CanonicalDatasetManifest(BaseModel):
    """Manifest for a compiled dataset: schema version, tables, and sources.

    Attributes
    ----------
    schema_version : str
        The dataset schema version.
    tables : dict of str to str
        The table name to file name mapping.
    sources : list of dict
        The provenance records of the inputs the dataset was built from.
    options : dict
        The build options that affect the tables.
    metadata : dict
        Further free-form metadata.
    """

    schema_version: str = "0.1"
    tables: dict[str, str] = Field(default_factory=dict)
    sources: list[dict[str, str]] = Field(default_factory=list)
    options: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
