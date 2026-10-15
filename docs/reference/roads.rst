Roads
=====

The road model routes each produced product from its block to a destination over a segment graph, and
reports the route length and the haul cost.

Network tables
--------------

A network is four CSV tables loaded by ``ws4.roads.network.load_route_tables``:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Table
     - Columns
   * - ``vertices.csv``
     - ``vertex_id`` — a road junction.
   * - ``segments.csv``
     - ``from_vertex``, ``to_vertex``, ``length_m``, ``cost`` — an undirected edge.
   * - ``destinations.csv``
     - ``dest_id``, ``vertex_id`` — a destination (for example a mill) attached to a vertex.
   * - ``linkages.csv``
     - ``block_id``, ``vertex_id`` — each block is assigned to exactly one vertex.

``RouteNetwork.from_tables`` builds the network, and ``route_length`` / ``route_cost`` return the
shortest path over the segment graph by length or by cost. ``nearest_destination`` returns the
block's nearest destination and route length, or ``None``.

Routing a run
-------------

The simulator routes each produced product to the block's **single nearest destination** — exclusive
by construction — when it is given a network, and writes ``route_values.csv``:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Column
     - Meaning
   * - ``year``
     - The year the product was produced.
   * - ``block_id``
     - The producing block.
   * - ``dest_id``
     - The destination the product was routed to.
   * - ``product``
     - The product label.
   * - ``volume``
     - The produced volume (area times the product curve at the pre-treatment offset).
   * - ``length_m``
     - The route length, in metres.
   * - ``cost``
     - The route cost.

Open items: destination eligibility per product, and route cost accounts (see ``notes/backlog.md``).

API
---

.. autofunction:: ws4.roads.network.load_route_tables

.. autoclass:: ws4.roads.network.RouteNetwork
   :members:
