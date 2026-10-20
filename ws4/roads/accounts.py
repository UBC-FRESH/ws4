"""Route accounts: destination choice, and haul, build, and maintenance costs.

This module implements the established route-account model (see the Patchworks Route
Model sections of the user guide, and the Route Cost Report in the reporting chapter):

- a **destination account** receives the products routed to it;
- a **route cost account** sums the haul, build, and maintenance costs of the segments
  used, into a named account (``addRouteHaulAccount`` and friends);
- **eligibility** decides which destinations may receive a product; when a product has
  more than one eligible destination, the choice is exclusive — one destination per
  product per block — and this simulator picks the least-haul-cost reachable one;
- a product that has no reachable eligible destination is **unutilized** (surplus).

Build cost is charged once, in the first period a segment is used. Maintenance cost is
charged in each period a segment is used. Haul cost is the volume times the sum of the
segment haul rates along the route.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd
import yaml

from .network import Route, RouteNetwork, existing_segments, load_route_eligibility

# The report column order of the established Route Cost Report.
_ROUTE_COST_COLUMNS: tuple[str, ...] = (
    "period",
    "year",
    "period_width",
    "length",
    "built_length",
    "build_expense",
    "haul_expense",
    "maintain_expense",
    "total",
    "volume",
    "average_haul_distance",
    "average_build_cost",
    "average_haul_cost",
    "average_maintain_cost",
)

# The command-line tokens of the established Route Cost Report header.
_ROUTE_COST_LABELS: dict[str, str] = {
    "period": "PERIOD",
    "year": "YEAR",
    "period_width": "PERIODWIDTH",
    "length": "LENGTH",
    "built_length": "BUILTLENGTH",
    "build_expense": "BUILD_EXPENSE",
    "haul_expense": "HAUL_EXPENSE",
    "maintain_expense": "MAINTAIN_EXPENSE",
    "total": "TOTAL",
    "volume": "VOLUME",
    "average_haul_distance": "AVERAGEHAULDIST",
    "average_build_cost": "AVERAGEBUILDCOST",
    "average_haul_cost": "AVERAGEHAULCOST",
    "average_maintain_cost": "AVERAGEMAINTCOST",
}


@dataclass
class RouteModel:
    """The route model: which destinations a product may reach, and the costs.

    Attributes
    ----------
    network : RouteNetwork
        The road network.
    eligibility : mapping of str to sequence of str, optional
        The destination names each product may be sent to. A product absent from the map
        may go to any destination. When present and empty, the product is unutilized.
    unutilized : str or mapping of str to str, optional
        The account name that records surplus product, either for every product or per
        product label. The reference declares its surplus per master product — the conifer
        split has no such account at all, the deciduous split has its own — so a single
        shared account would file one product's surplus under another's. An empty string,
        or a product with no entry, disables surplus for that product.
    delivery : sequence of DeliveryTarget, optional
        The volumes destinations must receive each year. A run fills them before it routes,
        from the blocks nearest each destination, and leaves every other block to the cost
        rule, which is how the reference's mill products are split.
    """

    network: RouteNetwork
    eligibility: Mapping[str, Sequence[str]] = field(default_factory=dict)
    unutilized: str | Mapping[str, str] = ""
    delivery: Sequence[DeliveryTarget] = ()
    # what a run has decided for the year it is simulating, by (block, product); a delivery target
    # fills its volume this way, and everything else is left to the cost rule
    _overrides: dict[tuple[int, str], str] = field(default_factory=dict, compare=False, repr=False)

    def surplus_account(self, product: str) -> str:
        """Return the account that records a product's surplus.

        Parameters
        ----------
        product : str
            The product label.

        Returns
        -------
        str
            The surplus account for the product, or an empty string when it has none.
        """
        if isinstance(self.unutilized, str):
            return self.unutilized
        return str(self.unutilized.get(product, ""))

    _assign_cache: dict[tuple[int, str], tuple[str, Route | None]] = field(
        default_factory=dict, compare=False, repr=False
    )

    def eligible(self, product: str) -> tuple[str, ...]:
        """Return the destinations a product may be sent to.

        A map that names products is also the list of what the model delivers: a product it does
        not name is routed nowhere, because a configuration that says where wood goes is saying
        what the wood is. Leaving a product out otherwise puts areas, sera classes and volume
        classes on the road beside the yield — which is what WS4 did until the route report made
        its volume 2.3 times the reference's for exactly that reason. A model with no map at all
        delivers every product to every destination, which is what it did before there was a map.

        Parameters
        ----------
        product : str
            The product label.

        Returns
        -------
        tuple of str
            The destinations the product may be sent to: what the map names for it; nothing when
            the map names other products but not this one, or when the product is explicitly
            unutilized; and every destination when there is no map.
        """
        if product in self.eligibility:
            return tuple(self.eligibility[product])
        if self.eligibility:
            return ()
        return self.network.destination_names()

    def delivers(self, product: str) -> bool:
        """Return whether a product is routed at all.

        Parameters
        ----------
        product : str
            The product label.

        Returns
        -------
        bool
            True when the product has at least one destination it may be sent to.
        """
        return bool(self.eligible(product))

    def set_overrides(self, overrides: Mapping[tuple[int, str], str]) -> None:
        """Replace the destinations a run has decided, dropping the choices cached before them.

        Parameters
        ----------
        overrides : mapping of (int, str) to str
            The destination per ``(block, product)`` this year, or an empty mapping for none.
        """
        self._overrides = dict(overrides)
        self._assign_cache.clear()

    def assign(self, block_id: int, product: str) -> tuple[str, Route | None]:
        """Choose a destination for a block's product.

        The choice is exclusive: one destination per product per block, the least
        haul-cost reachable eligible destination. When none is reachable and an
        unutilized account is configured, the product is surplus. The choice is fixed for
        a given block and product, so it is computed once and cached.

        Parameters
        ----------
        block_id : int
            The block.
        product : str
            The product label.

        Returns
        -------
        tuple of (str, Route or None)
            The chosen destination name, and its route (None for surplus).
        """
        decided = self._overrides.get((block_id, product))
        if decided is not None:
            return (decided, self._route_or_build(block_id, decided))
        key = (block_id, product)
        cached = self._assign_cache.get(key)
        if cached is not None:
            return cached
        eligible = self.eligible(product)
        choice = self.network.nearest_destination(block_id, eligible)
        if choice is None and self.network.opened is not None:
            # no opened road reaches the block: choose over the planned network, which is the
            # path its access will be built along
            choice = self.network.nearest_destination(block_id, eligible, open_only=False)
        if choice is None:
            result: tuple[str, Route | None] = (self.surplus_account(product), None)
        else:
            destination = choice[0]
            result = (destination, self._route_or_build(block_id, destination))
        self._assign_cache[key] = result
        return result

    def _route_or_build(self, block_id: int, destination: str) -> Route | None:
        """Return a route over the opened roads, opening the planned path when none exists.

        A block the opened network does not reach is accessed along its least-haul path over the
        whole planned network; that path's segments are opened, and the route over the planned
        path is returned so every segment it opens is also used and charged. Later blocks see the
        opened segments and are routed over them, which is what makes the road set grow instead
        of being rebuilt.

        Parameters
        ----------
        block_id : int
            The block.
        destination : str
            The destination account name.

        Returns
        -------
        Route or None
            The route, or None when the destination is not linked or no planned path exists.
        """
        route = self.network.route(block_id, destination)
        if route is not None or self.network.opened is None:
            return route
        planned = self.network.route(block_id, destination, open_only=False)
        if planned is None:
            return None
        if self.network.open_segments(planned.segment_ids):
            # a choice cached before the network grew may no longer be the least-cost one
            self._assign_cache.clear()
        return planned


@dataclass(frozen=True)
class RouteAccount:
    """A route account definition (``addRouteHaulAccount`` and friends).

    Attributes
    ----------
    destination : str
        The destination the account tracks.
    kind : {"haul", "build", "maintain", "volume"}
        The route value to sum: a cost, or the product volume.
    account : str
        The name to add the value into.
    factor : float
        A scaling factor, applied to the value (default 1; use -1 to subtract).
    product : str or None
        The product a ``volume`` account tracks, or None for every product routed there. A cost
        account cannot name a product: the ledger prices a route, not a tonne of it.
    """

    destination: str
    kind: str
    account: str
    factor: float = 1.0
    product: str | None = None

    def __post_init__(self) -> None:
        """Refuse a product on a cost account, rather than ignoring it."""
        if self.product is not None and self.kind != "volume":
            raise ValueError(
                f"{self.account}: a product can only be named on a volume account, not a "
                f"{self.kind} one"
            )


@dataclass(frozen=True)
class DeliveryTarget:
    """A volume a destination must receive each year, and the rule that fills it.

    The reference declares these per mill with ``setMinimumAnnual`` — 80,000 a year for Mill 1 on
    the 2026 sample — and its own report states them per period as that figure times the period
    width, which is why a ten-year period reads 800,000. Its achieved volume sits *just above*
    most periods (802,887; 804,388; 818,537), which is what filling a volume from whole blocks looks
    like, and WS4's own least-haul-cost rule takes no notice of it: it sends every block to the
    cheapest mill, so its split is 66/34 where the reference's is 62/38.

    Attributes
    ----------
    destination : str
        The destination account the volume goes to.
    product : str
        The product label the volume is measured in.
    per_year : float
        The volume of that product the destination receives each year.
    """

    destination: str
    product: str
    per_year: float


@dataclass(frozen=True)
class MaintenanceCharge:
    """What a used road costs to maintain in one year.

    The reference charges each segment it is used on once a period, whatever traffic passes over
    it: nothing when nothing uses it, and the segment's annual maintenance cost as soon as
    anything does — ``f(0) = 0`` and ``f(x > 0) = b``. WS4 also offers the affine form the
    maintainer specified, which is what a road budget actually looks like: nothing at no traffic,
    then a fixed annual cost the moment any traffic uses the segment, plus a cost proportional to
    the traffic — ``f(x > 0) = b + a x``. The reference's reading is the ``a = 0`` case, and it is
    the default, so a divergence has to be asked for by name.

    Attributes
    ----------
    model : {"reference", "traffic"}
        Which reading to use. ``reference`` is the reference's own, and the default.
    per_volume : float
        ``a``: the cost per unit of traffic, used by ``traffic`` (default 0).
    """

    model: Literal["reference", "traffic"] = "reference"
    per_volume: float = 0.0

    def __post_init__(self) -> None:
        """Refuse a reading that is not one of the two, rather than falling back to the default."""
        if self.model not in ("reference", "traffic"):
            raise ValueError(
                f"maintenance model {self.model!r} is not one WS4 has: it has the reference's "
                "'reference' reading and the affine 'traffic' one"
            )

    def of(self, base: float, volume: float) -> float:
        """Return what a segment costs to maintain in a year.

        Parameters
        ----------
        base : float
            ``b``: the segment's annual maintenance cost.
        volume : float
            ``x``: the traffic the segment carried that year.

        Returns
        -------
        float
            The charge: nothing when nothing used the segment, and otherwise the reference's
            annual cost with the traffic term on top when it was asked for.
        """
        if volume <= 0.0:
            return 0.0
        if self.model == "traffic":
            return base + self.per_volume * volume
        return base


@dataclass(frozen=True)
class ProductAllocation:
    """A master product partitioned across the destinations it is routed to.

    The reference expresses its mill products this way: an account that splits a master product
    between destinations, with an account for whatever does not move. The shares come from the
    ledger's routed volumes, so the parts sum back to the master's own value.

    Attributes
    ----------
    master : str
        The product account being partitioned.
    allocations : tuple of tuple of (str, str)
        ``(destination, account)`` per share.
    unallocated : str
        The account for what the master did not send anywhere, or an empty string for none.
    factor : float
        A scaling factor applied to every share (default 1).
    """

    master: str
    allocations: tuple[tuple[str, str], ...]
    unallocated: str = ""
    factor: float = 1.0


@dataclass(frozen=True)
class DuplicateAccount:
    """A duplicate account (``duplicateAccount(master, target, factor)``).

    Attributes
    ----------
    master : str
        The account whose value is copied.
    target : str
        The account the value is added into.
    factor : float
        A scaling factor (default 1; use -1 to subtract).
    """

    master: str
    target: str
    factor: float = 1.0


@dataclass(frozen=True)
class RouteConfig:
    """A loaded route configuration.

    Attributes
    ----------
    model : RouteModel
        The route model (network, eligibility, surplus).
    route_accounts : tuple of RouteAccount
        The route accounts to resolve.
    duplicate_accounts : tuple of DuplicateAccount
        The duplicate accounts to resolve.
    product_allocations : tuple of ProductAllocation
        The master products to partition across their destinations.
    period_width : int
        The planning-period width, in years.
    delivery : tuple of DeliveryTarget
        The volumes destinations must receive each year, which is how the reference's mill products
        are split.
    maintenance : MaintenanceCharge
        How a used road's maintenance is charged. The default is the reference's own reading; a
        divergence from it has to be asked for by name under ``divergences``.
    """

    model: RouteModel
    route_accounts: tuple[RouteAccount, ...] = ()
    duplicate_accounts: tuple[DuplicateAccount, ...] = ()
    product_allocations: tuple[ProductAllocation, ...] = ()
    period_width: int = 1
    delivery: tuple[DeliveryTarget, ...] = ()
    maintenance: MaintenanceCharge = field(default_factory=MaintenanceCharge)


def _divergences(raw: object) -> MaintenanceCharge:
    """Read the named divergences from a route configuration.

    Parameters
    ----------
    raw : object
        The configuration's ``divergences`` mapping, or None when it states none.

    Returns
    -------
    MaintenanceCharge
        How maintenance is charged: the reference's reading unless the configuration names the
        traffic one.

    Raises
    ------
    ValueError
        When a divergence is one WS4 does not have, naming it rather than ignoring it.
    """
    if not raw:
        return MaintenanceCharge()
    if not isinstance(raw, Mapping):
        raise ValueError("divergences must be a mapping of names to settings")
    named = set(raw)
    if named - {"maintenance"}:
        unknown = ", ".join(sorted(named - {"maintenance"}))
        raise ValueError(
            f"WS4 has one divergence to declare, 'maintenance', and the configuration names "
            f"{unknown}: a setting WS4 does not apply is refused rather than ignored"
        )
    maintenance = raw.get("maintenance") or {}
    if not isinstance(maintenance, Mapping):
        raise ValueError("divergences.maintenance must be a mapping of model and per_volume")
    return MaintenanceCharge(
        model=str(maintenance.get("model", "reference")),  # type: ignore[arg-type]
        per_volume=float(maintenance.get("per_volume", 0.0)),
    )


def _surplus_accounts(raw: object) -> str | dict[str, str]:
    """Normalise a configuration's surplus account, which may be one name or one per product."""
    if isinstance(raw, dict):
        return {str(product): str(account) for product, account in raw.items()}
    return str(raw)


def load_route_config(path: Path) -> RouteConfig:
    """Load a route configuration from YAML.

    The file names the four route tables (``segments``, ``destinations``, ``linkages``), an
    optional ``eligibility`` table, an optional ``unutilized`` account — one name, or a name
    per product — and lists of ``route_accounts`` and ``duplicate_accounts``. ``initial_roads``
    is ``all`` (the default, the whole planned network) or ``existing`` (the zero-build-cost
    roads open at period 1, the rest opened on demand). Relative paths
    resolve against the configuration file's directory.

    **Parity is the default and a divergence has to be named.** Everything WS4 computes the way the
    reference does needs no configuration; what WS4 computes *differently* is asked for under
    ``divergences``, one named entry per quantity, so that what a run does is explicit rather than
    implicit. The one entry there is ``maintenance`` — ``model: reference`` (the default, and what
    parity uses) or ``model: traffic`` with ``per_volume`` for the affine charge — and an entry WS4
    does not know is refused rather than ignored.

    Parameters
    ----------
    path : Path
        The YAML configuration file.

    Returns
    -------
    RouteConfig
        The loaded configuration.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.parent
    route = raw.get("route", {})

    def resolve(name: str) -> Path:
        candidate = Path(name)
        return candidate if candidate.is_absolute() else base / candidate

    table_names = ("segments", "destinations", "linkages")
    missing = [name for name in table_names if name not in route]
    if missing:
        raise ValueError(f"route config needs {', '.join(missing)}")
    segments = pd.read_csv(resolve(route["segments"]))
    destinations = pd.read_csv(resolve(route["destinations"]))
    linkages = pd.read_csv(resolve(route["linkages"]))
    initial_roads = str(route.get("initial_roads", "all")).lower()
    if initial_roads not in ("all", "existing"):
        raise ValueError(
            f"route.initial_roads is 'all' or 'existing', and {initial_roads!r} is neither"
        )
    initial_open = existing_segments(segments) if initial_roads == "existing" else None
    network = RouteNetwork.from_tables(segments, destinations, linkages, initial_open=initial_open)
    eligibility = (
        load_route_eligibility(resolve(route["eligibility"])) if route.get("eligibility") else {}
    )
    model = RouteModel(
        network=network,
        eligibility=eligibility,
        unutilized=_surplus_accounts(route.get("unutilized", "")),
    )
    route_accounts = tuple(
        RouteAccount(
            destination=str(item["destination"]),
            kind=str(item["kind"]),
            account=str(item["account"]),
            factor=float(item.get("factor", 1.0)),
            product=item.get("product"),
        )
        for item in raw.get("route_accounts", [])
    )
    product_allocations = tuple(
        ProductAllocation(
            master=str(item["master"]),
            allocations=tuple(
                (str(pair["destination"]), str(pair["account"])) for pair in item["allocations"]
            ),
            unallocated=str(item.get("unallocated", "")),
            factor=float(item.get("factor", 1.0)),
        )
        for item in raw.get("product_allocations", [])
    )
    duplicate_accounts = tuple(
        DuplicateAccount(
            master=str(item["master"]),
            target=str(item["target"]),
            factor=float(item.get("factor", 1.0)),
        )
        for item in raw.get("duplicate_accounts", [])
    )
    delivery = tuple(
        DeliveryTarget(
            destination=str(item["destination"]),
            product=str(item["product"]),
            per_year=float(item["per_year"]),
        )
        for item in raw.get("delivery", [])
    )
    model.delivery = delivery
    return RouteConfig(
        model=model,
        route_accounts=route_accounts,
        duplicate_accounts=duplicate_accounts,
        maintenance=_divergences(raw.get("divergences", {})),
        product_allocations=product_allocations,
        period_width=int(raw.get("period_width", 1)),
    )


def resolve_allocation_values(
    values: pd.DataFrame,
    volumes: pd.DataFrame,
    allocations: Sequence[ProductAllocation],
) -> pd.DataFrame:
    """Partition each master product across its destinations, with an account for the rest.

    Parameters
    ----------
    values : pandas.DataFrame
        The account values (``year``, ``account``, ``value``) the partitions are taken from.
    volumes : pandas.DataFrame
        The routed volumes (``year``, ``destination``, ``product``, ``volume``).
    allocations : sequence of ProductAllocation
        The partitions.

    Returns
    -------
    pandas.DataFrame
        One row per year and account for the shares and the unallocated remainder.

    Raises
    ------
    ValueError
        When the routed shares of a master exceed its own value, which would mean the
        configuration and the routing disagree about what the master is.
    """
    if not allocations:
        return pd.DataFrame(columns=["year", "account", "value"])
    totals = values.groupby(["year", "account"], as_index=False)["value"].sum()
    rows: list[dict[str, object]] = []
    for allocation in allocations:
        master = totals[totals["account"] == allocation.master]
        if master.empty:
            continue
        moved: dict[int, float] = {int(year): 0.0 for year in master["year"]}
        for destination, account in allocation.allocations:
            share = volumes[
                (volumes["destination"] == destination) & (volumes["product"] == allocation.master)
            ]
            for year, volume in zip(share["year"], share["volume"], strict=True):
                year = int(year)
                value = float(volume) * allocation.factor
                moved[year] = moved.get(year, 0.0) + value
                rows.append({"year": year, "account": account, "value": value})
        # Check every year either side knows about, not just the master's own: a share routed in a
        # year the master has no value for is still a share of it.
        totals_by_year = {
            int(year): float(value)
            for year, value in zip(master["year"], master["value"], strict=True)
        }
        for year in sorted(set(totals_by_year) | set(moved)):
            total = totals_by_year.get(year, 0.0)
            rest = total - moved.get(year, 0.0)
            if rest < -1e-6:
                raise ValueError(
                    f"{allocation.master}: the shares routed in year {year} exceed its own value "
                    f"({moved[year]:.6f} against {total:.6f})"
                )
            if allocation.unallocated:
                rows.append(
                    {"year": year, "account": allocation.unallocated, "value": max(rest, 0.0)}
                )
    return pd.DataFrame(rows, columns=["year", "account", "value"])


def resolve_account_values(
    values: pd.DataFrame,
    extra: pd.DataFrame | None = None,
    duplicates: Sequence[DuplicateAccount] = (),
) -> pd.DataFrame:
    """Combine account values, apply duplicate accounts, and sum by year and account.

    Parameters
    ----------
    values : pandas.DataFrame
        The simulated account values (``year``, ``account``, ``value``).
    extra : pandas.DataFrame or None, optional
        Additional account values (for example route cost accounts).
    duplicates : sequence of DuplicateAccount, optional
        Duplicate accounts. Each copies the value of its master account (summed over the
        year) into its target, scaled by its factor. Duplicates are applied once, in
        order, against the combined values (they do not chain).

    Returns
    -------
    pandas.DataFrame
        The resolved values, with ``year``, ``account``, and ``value`` columns, summed by
        year and account.
    """
    frames = [values]
    if extra is not None and not extra.empty:
        frames.append(extra)
    combined = pd.concat(frames, ignore_index=True) if len(frames) > 1 else values.copy()
    if duplicates:
        totals = combined.groupby(["year", "account"], as_index=False)["value"].sum()
        additions: list[pd.DataFrame] = []
        for duplicate in duplicates:
            source = totals[totals["account"] == duplicate.master]
            if source.empty:
                continue
            copied = source.copy()
            copied["account"] = duplicate.target
            copied["value"] = copied["value"] * duplicate.factor
            additions.append(copied)
        if additions:
            combined = pd.concat([combined, *additions], ignore_index=True)
    return pd.DataFrame(combined.groupby(["year", "account"], as_index=False)["value"].sum())


@dataclass
class _SegmentState:
    """The per-period state of one segment."""

    volume: float = 0.0
    haul_expense: float = 0.0
    length: float = 0.0
    built_length: float = 0.0
    build_expense: float = 0.0
    maintain_expense: float = 0.0

    @property
    def used(self) -> bool:
        """Return whether the segment carried any volume this period."""
        return self.volume > 0.0 or self.haul_expense > 0.0


class RouteCostLedger:
    """Accumulate route costs over a run and render the route accounts.

    The ledger records each routed product, then writes:

    - the network table (one row per segment per period, with the total and
      per-destination volume and haul expense);
    - a route table per destination;
    - the route cost report (one row per period).

    Parameters
    ----------
    network : RouteNetwork
        The road network.
    period_width : int, optional
        The planning-period width, in years, recorded in the report.
    collect : bool, optional
        When True (the default), also keep the per-segment detail that the network table,
        the route tables, and the route cost report need. When False, only the
        per-destination totals that :meth:`account_values` needs are kept, so a search can
        evaluate route accounts without the reporting overhead.
    maintenance : MaintenanceCharge or None, optional
        How a used road's maintenance is charged. The default is the reference's own reading;
        a divergence from it has to be asked for by name.
    """

    def __init__(
        self,
        network: RouteNetwork,
        period_width: int = 1,
        collect: bool = True,
        maintenance: MaintenanceCharge | None = None,
    ) -> None:
        self.network = network
        self.period_width = period_width
        self.collect = collect
        self.maintenance = maintenance if maintenance is not None else MaintenanceCharge()
        self._by_id = {segment.segment_id: segment for segment in network.segments}
        self._segments: dict[tuple[int, int], _SegmentState] = {}
        self._by_destination: dict[tuple[int, str, int], _SegmentState] = {}
        # the segments each destination used, and the traffic it put on each of them, so the
        # maintenance is charged per segment per period from the traffic (_charge_maintenance)
        self._dest_segments: dict[tuple[int, str], set[int]] = {}
        self._traffic: dict[tuple[int, str, int], float] = {}
        # the roads that exist at the start are already built: they are open from period 1 and
        # are not counted as built length or charged a build expense
        self._built: set[int] = set(network.opened) if network.opened is not None else set()
        self._first_use: dict[int, int] = {}
        self._year_distance: dict[int, float] = {}
        self._year_volume: dict[int, float] = {}
        self._dest_totals: dict[tuple[int, str], dict[str, float]] = {}
        self._flows: dict[tuple[int, str, tuple[int, ...]], list[float]] = {}
        # the volume per destination and product, so an account can name the product it tracks
        self._product_volume: dict[tuple[int, str, str], float] = {}
        # the volume-weighted distance per destination per year, which the report needs per mill
        self._dest_distance: dict[tuple[int, str], float] = {}
        self._route_rows: list[dict[str, object]] = []

    def record(
        self,
        year: int,
        block_id: int,
        product: str,
        volume: float,
        destination: str,
        route: Route | None,
    ) -> None:
        """Record a routed product.

        Parameters
        ----------
        year : int
            The year of the routing.
        block_id : int
            The producing block.
        product : str
            The product label.
        volume : float
            The produced volume.
        destination : str
            The destination account name.
        route : Route or None
            The route, or None for a surplus (unutilized) product.
        """
        if self.collect:
            self._route_rows.append(
                {
                    "year": year,
                    "block_id": block_id,
                    "destination": destination,
                    "product": product,
                    "volume": volume,
                    "length_m": route.length_m if route is not None else 0.0,
                    "haul_cost": route.haul_cost if route is not None else 0.0,
                }
            )
        if route is None or volume <= 0.0:
            return
        self._year_volume[year] = self._year_volume.get(year, 0.0) + volume
        self._year_distance[year] = self._year_distance.get(year, 0.0) + volume * route.length_m
        totals = self._dest_totals.setdefault(
            (year, destination), {"haul": 0.0, "build": 0.0, "maintain": 0.0, "volume": 0.0}
        )
        totals["volume"] += volume
        totals["haul"] += volume * route.haul_cost
        self._dest_distance[(year, destination)] = (
            self._dest_distance.get((year, destination), 0.0) + volume * route.length_m
        )
        product_key = (year, destination, str(product))
        self._product_volume[product_key] = self._product_volume.get(product_key, 0.0) + volume
        # The traffic each segment carries for each destination, which is what maintenance is a
        # function of. Both collecting modes keep it: a search runs with ``collect=False`` and
        # still prices the maintenance account.
        for segment_id in route.segment_ids:
            self._dest_segments.setdefault((year, destination), set()).add(segment_id)
            carried = (year, destination, segment_id)
            self._traffic[carried] = self._traffic.get(carried, 0.0) + volume
        if self.collect:
            # Aggregate per (year, destination, route): products of the same block to the
            # same destination share the route, so the per-segment work runs once per route
            # at flush time.
            key = (year, destination, route.segment_ids)
            flow = self._flows.get(key)
            if flow is None:
                self._flows[key] = [volume]
            else:
                flow[0] += volume
            return
        for segment_id in route.segment_ids:
            if segment_id not in self._built:
                self._built.add(segment_id)
                totals["build"] += self._by_id[segment_id].build_cost

    def _flush(self) -> None:
        """Fold the aggregated route flows into the per-segment tables.

        Called by every reader, so the per-segment tables are materialized only when an
        output needs them; the per-segment work runs once per route rather than once per
        produced product.
        """
        if self._flows:
            self._materialize()
        self._charge_maintenance()

    def _materialize(self) -> None:
        """Fold the aggregated route flows into the per-segment tables.

        Called by every reader, so the per-segment tables are materialized only when an
        output needs them; the per-segment work runs once per route rather than once per
        produced product.
        """
        for (year, destination, segment_ids), flow in self._flows.items():
            volume = flow[0]
            for segment_id in segment_ids:
                segment = self._by_id[segment_id]
                is_new = segment_id not in self._built
                if is_new:
                    self._built.add(segment_id)
                    self._dest_totals.setdefault(
                        (year, destination),
                        {"haul": 0.0, "build": 0.0, "maintain": 0.0, "volume": 0.0},
                    )["build"] += segment.build_cost
                state = self._segments.setdefault((year, segment_id), _SegmentState())
                if is_new:
                    state.built_length += segment.length_m
                    state.build_expense += segment.build_cost
                    self._first_use.setdefault(segment_id, year)
                state.volume += volume
                state.haul_expense += volume * segment.haul_cost
                state.length = segment.length_m
                per_dest = self._by_destination.setdefault(
                    (year, destination, segment_id), _SegmentState()
                )
                per_dest.volume += volume
                per_dest.haul_expense += volume * segment.haul_cost
                per_dest.length = segment.length_m
                if is_new:
                    per_dest.built_length += segment.length_m
                    per_dest.build_expense += segment.build_cost
        self._flows.clear()

    def _charge_maintenance(self) -> None:
        """Charge each used segment's maintenance once for the period, from the traffic on it.

        Maintenance is a function of the traffic a road carries, so it is charged for a period
        after every flow of that period is in — not once per route, which is what a per-use
        charge amounts to, and not per produced product, which is what it used to be. Nothing is
        charged for a period a segment was not used at all. Setting rather than adding makes this
        idempotent, which is what lets every reader call it.
        """
        for (year, destination), used_segments in self._dest_segments.items():
            total = 0.0
            for segment_id in used_segments:
                traffic = self._traffic.get((year, destination, segment_id), 0.0)
                charge = self.maintenance.of(self._by_id[segment_id].maintain_cost, traffic)
                total += charge
                if self.collect:
                    per_dest = self._by_destination.get((year, destination, segment_id))
                    if per_dest is not None:
                        per_dest.maintain_expense = charge
            self._dest_totals.setdefault(
                (year, destination), {"haul": 0.0, "build": 0.0, "maintain": 0.0, "volume": 0.0}
            )["maintain"] = total
        if self.collect:
            # the network-wide figure is a property of the segment, so it is charged from the
            # traffic every destination put on it, not from one destination's share
            for (_year, segment_id), state in self._segments.items():
                state.maintain_expense = self.maintenance.of(
                    self._by_id[segment_id].maintain_cost, state.volume
                )

    def route_rows(self) -> pd.DataFrame:
        """Return the per-product routing rows.

        Returns
        -------
        pandas.DataFrame
            ``year``, ``block_id``, ``destination``, ``product``, ``volume``,
            ``length_m``, ``haul_cost``.
        """
        return pd.DataFrame(
            self._route_rows,
            columns=[
                "year",
                "block_id",
                "destination",
                "product",
                "volume",
                "length_m",
                "haul_cost",
            ],
        )

    def product_volumes(self) -> pd.DataFrame:
        """Return the routed volume per year, destination and product.

        Returns
        -------
        pandas.DataFrame
            ``year``, ``destination``, ``product`` and ``volume`` columns.
        """
        return pd.DataFrame(
            [
                {"year": year, "destination": destination, "product": product, "volume": volume}
                for (year, destination, product), volume in sorted(self._product_volume.items())
            ],
            columns=["year", "destination", "product", "volume"],
        )

    def network_table(self) -> pd.DataFrame:
        """Return the network table: one row per segment per period.

        Returns
        -------
        pandas.DataFrame
            ``period``, ``segment_id``, ``length``, ``built_length``, ``build_expense``,
            ``maintain_expense``, ``initial_use``, ``volume``, and, for each destination,
            ``<destination>.volume`` and ``<destination>.haul_expense``.
        """
        rows: list[dict[str, object]] = []
        self._flush()
        destinations = self.network.destination_names()
        for (year, segment_id), state in sorted(self._segments.items()):
            row: dict[str, object] = {
                "period": year,
                "segment_id": segment_id,
                "length": state.length,
                "built_length": state.built_length,
                "build_expense": state.build_expense,
                "maintain_expense": state.maintain_expense,
                "initial_use": self._first_use.get(segment_id, 0),
                "volume": state.volume,
            }
            for destination in destinations:
                per_dest = self._by_destination.get((year, destination, segment_id))
                row[f"{destination}.volume"] = per_dest.volume if per_dest else 0.0
                row[f"{destination}.haul_expense"] = per_dest.haul_expense if per_dest else 0.0
            rows.append(row)
        columns = [
            "period",
            "segment_id",
            "length",
            "built_length",
            "build_expense",
            "maintain_expense",
            "initial_use",
            "volume",
            *(f"{destination}.volume" for destination in destinations),
            *(f"{destination}.haul_expense" for destination in destinations),
        ]
        return pd.DataFrame(rows, columns=list(columns))

    def route_table(self, destination: str) -> pd.DataFrame:
        """Return the route table for one destination: one row per segment per period.

        Parameters
        ----------
        destination : str
            The destination account name.

        Returns
        -------
        pandas.DataFrame
            ``period``, ``segment_id``, ``from_vertex``, ``to_vertex``, ``volume``,
            ``haul_expense``, ``length``, ``haul_cost``, ``distance``.
        """
        rows: list[dict[str, object]] = []
        self._flush()
        for (year, name, segment_id), state in sorted(self._by_destination.items()):
            if name != destination:
                continue
            segment = self._by_id[segment_id]
            rows.append(
                {
                    "period": year,
                    "segment_id": segment_id,
                    "from_vertex": segment.from_vertex,
                    "to_vertex": segment.to_vertex,
                    "volume": state.volume,
                    "haul_expense": state.haul_expense,
                    "length": segment.length_m,
                    "haul_cost": segment.haul_cost,
                }
            )
        return pd.DataFrame(
            rows,
            columns=[
                "period",
                "segment_id",
                "from_vertex",
                "to_vertex",
                "volume",
                "haul_expense",
                "length",
                "haul_cost",
            ],
        )

    def account_values(self, route_accounts: Sequence[RouteAccount]) -> pd.DataFrame:
        """Return the route account values, one row per period and account.

        Each :class:`RouteAccount` sums a route value (haul, build, maintenance, or
        volume) for its destination into its named account, scaled by its factor.

        Parameters
        ----------
        route_accounts : sequence of RouteAccount
            The route accounts to resolve.

        Returns
        -------
        pandas.DataFrame
            ``year``, ``account``, and ``value`` columns.
        """
        rows: list[dict[str, object]] = []
        self._flush()
        for account in route_accounts:
            if account.product is not None:
                for (year, destination, product), volume in self._product_volume.items():
                    if destination != account.destination or product != account.product:
                        continue
                    rows.append(
                        {"year": year, "account": account.account, "value": volume * account.factor}
                    )
                continue
            for (year, destination), totals in self._dest_totals.items():
                if destination != account.destination:
                    continue
                rows.append(
                    {
                        "year": year,
                        "account": account.account,
                        "value": totals.get(account.kind, 0.0) * account.factor,
                    }
                )
        return pd.DataFrame(rows, columns=["year", "account", "value"])

    def route_cost_report(self, destination: str | None = None) -> pd.DataFrame:
        """Return the route cost report: one row per period of the model.

        The report is folded into the model's own periods, so its rows are the reference's: a
        period is labelled by the year it **ends** at and carries the model's period width. The
        expenses and the volume are summed over the period's years. ``LENGTH`` is the length of
        the **distinct** road used at any time in the period, counted once — a road used in five
        of the period's ten years is one road, not five — which is the reference's reading of the
        column. ``BUILTLENGTH`` is the length first built in the period, also counted once. The
        averages are recomputed from those figures rather than averaged, which is what makes them
        mean the same thing in a ten-year period as in a one-year one.

        With the default period width of one this is one row per year, unchanged.

        Parameters
        ----------
        destination : str or None, optional
            A destination account to report on alone, which is how the reference ships this
            report — one table per mill. None reports the whole network, where a shared segment
            is counted once rather than once per destination it carries wood for.

        Returns
        -------
        pandas.DataFrame
            The report, in the established column order. Column labels use the
            established command-line tokens when written by :meth:`write`.
        """
        self._flush()
        width = max(int(self.period_width), 1)
        states = (
            ((year, segment_id, state) for (year, segment_id), state in self._segments.items())
            if destination is None
            else (
                (year, segment_id, state)
                for (year, one, segment_id), state in self._by_destination.items()
                if one == destination
            )
        )
        # LENGTH is a segment-set quantity: the distinct road in use at any time in the period,
        # counted once. Summing the annual figures would count a road once per year it was used,
        # which is what made WS4's period LENGTH 2.6 times the reference's.
        used_segments: dict[int, set[int]] = {}
        built_length: dict[int, float] = {}
        build: dict[int, float] = {}
        haul: dict[int, float] = {}
        maintain: dict[int, float] = {}
        for year, segment_id, state in states:
            used_segments.setdefault(year, set()).add(segment_id)
            built_length[year] = built_length.get(year, 0.0) + state.built_length
            build[year] = build.get(year, 0.0) + state.build_expense
            haul[year] = haul.get(year, 0.0) + state.haul_expense
            maintain[year] = maintain.get(year, 0.0) + state.maintain_expense
        if destination is None:
            volume = self._year_volume
            distance = self._year_distance
        else:
            volume = {
                year: totals["volume"]
                for (year, one), totals in self._dest_totals.items()
                if one == destination
            }
            distance = {
                year: value
                for (year, one), value in self._dest_distance.items()
                if one == destination
            }
        # a period's years, from the year they end at: period 1 is years 1..width, and period 0 is
        # the initial snapshot at year 0, which is how the reference labels its own first row
        periods: dict[int, list[int]] = {}
        for year in sorted(set(used_segments) | set(volume)):
            periods.setdefault(0 if year <= 0 else (year - 1) // width + 1, []).append(year)
        rows: list[dict[str, float]] = []
        for period, years in sorted(periods.items()):
            period_segments: set[int] = set()
            for year in years:
                period_segments |= used_segments.get(year, set())
            period_length = sum(self._by_id[segment_id].length_m for segment_id in period_segments)
            period_built_length = sum(built_length.get(year, 0.0) for year in years)
            period_build = sum(build.get(year, 0.0) for year in years)
            period_haul = sum(haul.get(year, 0.0) for year in years)
            period_maintain = sum(maintain.get(year, 0.0) for year in years)
            period_volume = sum(volume.get(year, 0.0) for year in years)
            period_distance = sum(distance.get(year, 0.0) for year in years)
            rows.append(
                {
                    # a period is labelled by the year it ends at, as the reference labels its own;
                    # a run that stops inside a period covers only the years it simulated
                    "period": period,
                    "year": period * width,
                    "period_width": self.period_width,
                    "length": period_length,
                    "built_length": period_built_length,
                    "build_expense": period_build,
                    "haul_expense": period_haul,
                    "maintain_expense": period_maintain,
                    "total": period_build + period_haul + period_maintain,
                    "volume": period_volume,
                    "average_haul_distance": (
                        period_distance / period_volume if period_volume > 0.0 else 0.0
                    ),
                    "average_build_cost": (period_build / period_volume if period_volume else 0.0),
                    "average_haul_cost": (period_haul / period_volume if period_volume else 0.0),
                    "average_maintain_cost": (
                        period_maintain / period_volume if period_volume else 0.0
                    ),
                }
            )
        return pd.DataFrame(rows, columns=list(_ROUTE_COST_COLUMNS))

    def write(self, out_dir: Path) -> None:
        """Write the route accounts into a run directory.

        Parameters
        ----------
        out_dir : Path
            The run directory. The method writes ``route_values.csv``,
            ``network_table.csv``, the route cost report, and a route table and a route cost
            report per destination.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.route_rows().to_csv(out_dir / "route_values.csv", index=False)
        network = self.network_table()
        if not network.empty:
            network.to_csv(out_dir / "network_table.csv", index=False)
        report = self.route_cost_report()
        report.rename(columns=_ROUTE_COST_LABELS).to_csv(
            out_dir / "route_cost_report.csv", index=False
        )
        for destination in self.network.destination_names():
            safe = destination.replace("/", "_")
            table = self.route_table(destination)
            if not table.empty:
                table.to_csv(out_dir / f"route_table.{safe}.csv", index=False)
            # the reference ships this report one table per mill, so WS4 does too
            per_destination = self.route_cost_report(destination)
            if not per_destination.empty:
                per_destination.rename(columns=_ROUTE_COST_LABELS).to_csv(
                    out_dir / f"route_cost_report.{safe}.csv", index=False
                )
