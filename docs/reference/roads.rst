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

Run a route model from the Python API:

.. code-block:: python

   from ws4.roads.network import RouteNetwork, load_route_eligibility
   from ws4.roads.accounts import RouteModel
   from ws4.sim.engine import Simulator

   network = RouteNetwork.from_tables(segments, destinations, linkages)
   model = RouteModel(network, eligibility=load_route_eligibility(eligibility_csv))
   Simulator.from_dataset(dataset).run(schedule, years, out_dir, route_model=model)

Open items: destination eligibility per product and the route cost accounts are implemented; the
exclusive/unutilized/duplicate account wiring for the optimizer's objective, and core-area and
edge-contrast rules, remain (see ``notes/backlog.md``).

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

.. autoclass:: ws4.roads.accounts.RouteCostLedger
   :members:
