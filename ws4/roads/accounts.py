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

import pandas as pd
import yaml

from .network import Route, RouteNetwork, load_route_eligibility

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
    unutilized : str, optional
        The account name that records surplus product. An empty string disables surplus.
    """

    network: RouteNetwork
    eligibility: Mapping[str, Sequence[str]] = field(default_factory=dict)
    unutilized: str = ""
    _assign_cache: dict[tuple[int, str], tuple[str, Route | None]] = field(
        default_factory=dict, compare=False, repr=False
    )

    def eligible(self, product: str) -> tuple[str, ...]:
        """Return the destinations a product may be sent to.

        Parameters
        ----------
        product : str
            The product label.

        Returns
        -------
        tuple of str
            The eligible destination names; all destinations when the product has no
            entry, or an empty tuple when the product is explicitly unutilized.
        """
        if product in self.eligibility:
            return tuple(self.eligibility[product])
        return self.network.destination_names()

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
        key = (block_id, product)
        cached = self._assign_cache.get(key)
        if cached is not None:
            return cached
        eligible = self.eligible(product)
        choice = self.network.nearest_destination(block_id, eligible)
        if choice is None:
            result: tuple[str, Route | None] = (self.unutilized, None)
        else:
            destination = choice[0]
            result = (destination, self.network.route(block_id, destination))
        self._assign_cache[key] = result
        return result


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
    """

    destination: str
    kind: str
    account: str
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
    period_width : int
        The planning-period width, in years.
    """

    model: RouteModel
    route_accounts: tuple[RouteAccount, ...] = ()
    duplicate_accounts: tuple[DuplicateAccount, ...] = ()
    period_width: int = 1


def load_route_config(path: Path) -> RouteConfig:
    """Load a route configuration from YAML.

    The file names the four route tables (``segments``, ``destinations``, ``linkages``), an
    optional ``eligibility`` table, an optional ``unutilized`` account, and lists of
    ``route_accounts`` and ``duplicate_accounts``. Relative paths resolve against the
    configuration file's directory.

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
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    eligibility = (
        load_route_eligibility(resolve(route["eligibility"])) if route.get("eligibility") else {}
    )
    model = RouteModel(
        network=network,
        eligibility=eligibility,
        unutilized=str(route.get("unutilized", "")),
    )
    route_accounts = tuple(
        RouteAccount(
            destination=str(item["destination"]),
            kind=str(item["kind"]),
            account=str(item["account"]),
            factor=float(item.get("factor", 1.0)),
        )
        for item in raw.get("route_accounts", [])
    )
    duplicate_accounts = tuple(
        DuplicateAccount(
            master=str(item["master"]),
            target=str(item["target"]),
            factor=float(item.get("factor", 1.0)),
        )
        for item in raw.get("duplicate_accounts", [])
    )
    return RouteConfig(
        model=model,
        route_accounts=route_accounts,
        duplicate_accounts=duplicate_accounts,
        period_width=int(raw.get("period_width", 1)),
    )


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
    """

    def __init__(self, network: RouteNetwork, period_width: int = 1, collect: bool = True) -> None:
        self.network = network
        self.period_width = period_width
        self.collect = collect
        self._by_id = {segment.segment_id: segment for segment in network.segments}
        self._segments: dict[tuple[int, int], _SegmentState] = {}
        self._by_destination: dict[tuple[int, str, int], _SegmentState] = {}
        self._built: set[int] = set()
        self._first_use: dict[int, int] = {}
        self._year_distance: dict[int, float] = {}
        self._year_volume: dict[int, float] = {}
        self._dest_totals: dict[tuple[int, str], dict[str, float]] = {}
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
        totals["maintain"] += route.maintain_cost
        for segment_id in route.segment_ids:
            segment = self._by_id[segment_id]
            is_new = segment_id not in self._built
            if is_new:
                self._built.add(segment_id)
                totals["build"] += segment.build_cost
            if not self.collect:
                continue
            state = self._segments.setdefault((year, segment_id), _SegmentState())
            if is_new:
                state.built_length += segment.length_m
                state.build_expense += segment.build_cost
                self._first_use.setdefault(segment_id, year)
            state.volume += volume
            state.haul_expense += volume * segment.haul_cost
            state.length = segment.length_m
            state.maintain_expense += segment.maintain_cost
            per_dest = self._by_destination.setdefault(
                (year, destination, segment_id), _SegmentState()
            )
            per_dest.volume += volume
            per_dest.haul_expense += volume * segment.haul_cost
            per_dest.length = segment.length_m
            per_dest.maintain_expense += segment.maintain_cost
            if is_new:
                per_dest.build_expense += segment.build_cost

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
        for account in route_accounts:
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

    def route_cost_report(self) -> pd.DataFrame:
        """Return the route cost report: one row per period.

        Returns
        -------
        pandas.DataFrame
            The report, in the established column order. Column labels use the
            established command-line tokens when written by :meth:`write`.
        """
        periods = sorted({year for year, _ in self._segments} | set(self._year_volume))
        rows: list[dict[str, float]] = []
        for period in periods:
            length = built_length = build = haul = maintain = 0.0
            for (year, _segment_id), state in self._segments.items():
                if year != period:
                    continue
                length += state.length
                built_length += state.built_length
                build += state.build_expense
                haul += state.haul_expense
                maintain += state.maintain_expense
            volume = self._year_volume.get(period, 0.0)
            average_distance = (
                self._year_distance.get(period, 0.0) / volume if volume > 0.0 else 0.0
            )
            rows.append(
                {
                    "period": period,
                    "year": period,
                    "period_width": self.period_width,
                    "length": length,
                    "built_length": built_length,
                    "build_expense": build,
                    "haul_expense": haul,
                    "maintain_expense": maintain,
                    "total": build + haul + maintain,
                    "volume": volume,
                    "average_haul_distance": average_distance,
                    "average_build_cost": build / volume if volume else 0.0,
                    "average_haul_cost": haul / volume if volume else 0.0,
                    "average_maintain_cost": maintain / volume if volume else 0.0,
                }
            )
        return pd.DataFrame(rows, columns=list(_ROUTE_COST_COLUMNS))

    def write(self, out_dir: Path) -> None:
        """Write the route accounts into a run directory.

        Parameters
        ----------
        out_dir : Path
            The run directory. The method writes ``route_values.csv``,
            ``network_table.csv``, the route cost report, and a route table per
            destination.
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
            table = self.route_table(destination)
            if not table.empty:
                safe = destination.replace("/", "_")
                table.to_csv(out_dir / f"route_table.{safe}.csv", index=False)
