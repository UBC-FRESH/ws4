Roads, routes, and mills
========================

The road model routes each produced product from its block to a destination (usually a mill)
over a segment graph, chooses the destination, and accounts for the haul, build, and maintenance
costs. A destination is identified by its **account name** (for example ``destination.MILL1``),
not by its vertex: the sample route model attaches more than one mill to the same vertex.

Network tables
--------------

A network is four CSV tables loaded by ``ws4.roads.network.load_route_tables``:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Table
     - Columns
   * - ``vertices.csv``
     - ``vertex_id`` (``NODE``) — a road junction.
   * - ``segments.csv``
     - ``segment_id`` (``SEGMENT``), ``from_vertex`` (``FNODE``), ``to_vertex`` (``TNODE``),
       ``length_m`` (``LENGTH``), ``haul_cost`` (``HAUL``), ``build_cost`` (``BUILD``),
       ``maintain_cost`` (``MAINTAIN``) — an undirected edge.
   * - ``destinations.csv``
     - ``name`` (``ACCOUNT``), ``vertex_id`` (``NODE``) — a destination account attached to a
       vertex. Several destinations may share a vertex.
   * - ``linkages.csv``
     - ``block_id`` (``BLOCK``), ``vertex_id`` (``NODE``) — each block is assigned to exactly
       one vertex.

Both the WS4 names and the established route-table names are accepted.
``RouteNetwork.route`` returns the least-haul-cost route (its segments, length, and the haul,
build, and maintenance costs); ``route_length`` and ``route_cost`` return the shortest path by
length or by cost, and ``nearest_destination`` returns the least-haul-cost eligible destination.

The route model
---------------

``ws4.roads.accounts.RouteModel`` holds the network, the **eligibility** (which destinations a
product may reach), and an optional **unutilized** account for surplus. The destination choice is
**exclusive**: one destination per product per block, the least-haul-cost reachable eligible one.
A product with no reachable eligible destination is surplus (unutilized). Eligibility loads from a
``product,destination`` table with ``load_route_eligibility``.

The route cost ledger
---------------------

``ws4.roads.accounts.RouteCostLedger`` accumulates the route accounts over a run, following the
established route-account model:

- the **haul** cost is the volume times the sum of the segment haul rates on the route;
- the **build** cost is charged once, in the first period a segment is used;
- the **maintenance** cost is charged in each period a segment is used.

It writes, into the run directory:

- ``route_values.csv`` — one row per routed product
  (``year, block_id, destination, product, volume, length_m, haul_cost``);
- ``network_table.csv`` — one row per segment per period, with the total and per-destination
  volume and haul expense;
- ``route_table.<destination>.csv`` — the per-segment route table for one destination;
- ``route_cost_report.csv`` — one row per period, with the established columns
  (``PERIOD, YEAR, PERIODWIDTH, LENGTH, BUILTLENGTH, BUILD_EXPENSE, HAUL_EXPENSE,
  MAINTAIN_EXPENSE, TOTAL, VOLUME, AVERAGEHAULDIST, AVERAGEBUILDCOST, AVERAGEHAULCOST,
  AVERAGEMAINTCOST``).

Route accounts and duplicate accounts
-------------------------------------

A **route account** (``RouteAccount``, matching ``addRouteHaulAccount`` and friends) sums a route
value — haul, build, maintenance, or volume — for a destination into a named account. A
**duplicate account** (``DuplicateAccount``, matching ``duplicateAccount``) copies an account's
value into another, scaled by a factor. ``resolve_account_values`` combines the simulated account
values with the route account values and applies the duplicates, so the resulting accounts (for
example ``route.Total.haul``) can be targeted by the optimizer.

A **route configuration** file (YAML) names the four route tables, an optional eligibility table,
an optional unutilized account, the route accounts, and the duplicate accounts:

.. code-block:: yaml

   route:
     segments: segments.csv
     destinations: destinations.csv
     linkages: linkages.csv
     eligibility: eligibility.csv
     unutilized: product.Unutilized
   route_accounts:
     - {destination: destination.MILL1, kind: haul, account: route.Mill1.haul}
     - {destination: destination.MILL1, kind: volume, account: product.Mill1.Yield}
   duplicate_accounts:
     - {master: route.Mill1.haul, target: route.Total.haul}

Load it with ``load_route_config`` and pass the model, route accounts, and duplicate accounts to
the simulator or the optimizer (``OptimizeConfig.route_config_path`` or ``--route-config`` on the
command line):

.. code-block:: python

   from ws4.roads.accounts import load_route_config
   from ws4.sim.engine import Simulator

   config = load_route_config("route.yaml")
   Simulator.from_dataset(dataset).run(
       schedule, years, out_dir,
       route_model=config.model,
       route_accounts=config.route_accounts,
       duplicate_accounts=config.duplicate_accounts,
   )

The routing is **verified against the reference implementation's own outputs**: its sample ships
`cost_destination.<mill>.csv` (the summed haul rate per network node), and
`python scripts/acceptance.py --roads-sample <sample>/roads` compares WS4's least-haul-cost routes to
it node by node — 37 701 comparisons on the C5-class sample, with no differences.
`notes/design/ws4-parity-harness.md` records what the comparison covers and what it does not.

The route model runs in the optimizer's inner loop. Haul, maintenance, and volume route accounts are
additive over blocks, so a move is priced by a route delta and needs no re-routing; a **build** route
account, a **duplicate** account, and edge contrast are not additive, so any of them makes an
evaluation a whole-schedule pass. See `notes/design/ws4-performance.md` for the measurements.

API
---

.. autofunction:: ws4.roads.network.load_route_tables

.. autofunction:: ws4.roads.network.load_route_eligibility

.. autoclass:: ws4.roads.network.RouteNetwork
   :members:

.. autoclass:: ws4.roads.network.Route
   :members:

.. autoclass:: ws4.roads.accounts.RouteModel
   :members:

.. autoclass:: ws4.roads.accounts.RouteAccount
   :members:

.. autoclass:: ws4.roads.accounts.DuplicateAccount
   :members:

.. autoclass:: ws4.roads.accounts.RouteConfig
   :members:

.. autofunction:: ws4.roads.accounts.load_route_config

.. autofunction:: ws4.roads.accounts.resolve_account_values

.. autoclass:: ws4.roads.accounts.RouteCostLedger
   :members:
