=======================
Route products to mills
=======================

The road model routes each produced product from its block to a **destination** — usually a mill —
over a network of segments, chooses the destination, and accounts for the **haul**, **build**, and
**maintenance** costs. Those become accounts you can target like any other, so "keep haul cost under
X" or "at least Y volume to Mill 1" are ordinary targets.

Prerequisites
-------------

* A compiled dataset whose ``blocks`` table has the same block ids as the network's linkages.
* Four network tables, or the established equivalents (see :doc:`../reference/roads`):
  ``vertices.csv``, ``segments.csv``, ``destinations.csv``, ``linkages.csv``. The sample estate ships
  all of them, with two mills, so the guide's commands run as they are.
* Optionally an eligibility table (``product,destination``) saying which mill may receive which
  product.

Procedure
---------

**1. Write the route configuration.**

.. code-block:: yaml

   # examples/estate/route.yaml — the shipped configuration, with two mills
   route:
     segments: segments.csv
     destinations: destinations.csv
     linkages: linkages.csv
     eligibility: eligibility.csv      # optional
     unutilized: product.Unutilized    # optional: where unreachable volume is recorded
   route_accounts:
     - {destination: destination.MILL1, kind: haul, account: route.Mill1.haul}
     - {destination: destination.MILL2, kind: haul, account: route.Mill2.haul}
     - {destination: destination.MILL1, kind: volume, account: product.Mill1.Yield}
     - {destination: destination.MILL2, kind: volume, account: product.Mill2.Yield}
   duplicate_accounts:
     - {master: route.Mill1.haul, target: route.Total.haul}
     - {master: route.Mill2.haul, target: route.Total.haul}

A **route account** sums one route value (``haul``, ``build``, ``maintain``, or ``volume``) for one
destination into a named account. A **duplicate account** copies an account into another, scaled by a
factor, which is how a per-mill cost becomes a total.

**2. Simulate with routing.** That writes the route outputs beside the account values:

.. code-block:: bash

   ws4 simulate --dataset tmp/estate/compiled --schedule tmp/estate/schedule.csv \
                --years 60 --topology examples/estate/topology.csv \
                --route-config examples/estate/route.yaml --out tmp/estate/run

Cutting eight blocks in year 0 on the sample estate splits between the mills by least haul cost, and
the route accounts resolve into the account values:

.. code-block:: text

   year                account        value
      0   product.Harvested.CC  8793.814286
      0   product.Mill1.Yield  3423.514286
      0   product.Mill2.Yield  5370.300000
      0      route.Mill1.haul   684.702857
      0      route.Mill2.haul   749.115000
      0    route.Total.haul  1433.817857

``route_values.csv`` says where each load went: a block at the west end goes to ``destination.MILL1``,
and one further east to ``destination.MILL2``, because that is the cheaper chain of segments even
though its own spur is longer.

The run directory gains ``route_values.csv`` (one row per routed product), ``network_table.csv`` (one
row per segment per period), ``route_table.<destination>.csv``, and ``route_cost_report.csv``.

**3. Target a route account.** Because the route accounts are resolved into the account values, they
are ordinary targets:

.. code-block:: yaml

   targets:
     - account: route.Total.haul
       year: 0
       maximum: 500000
       max_weight: 1.0
       period_width: 10

**4. Search with routing.** Pass the same configuration to the search:

.. code-block:: bash

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/route-targets.yaml \
                --years 100 \
                --route-config tmp/howto/route.yaml \
                --time-limit 00:05:00 --seed 1 --out tmp/howto/route-run

**5. The same in Python.**

.. code-block:: python

   from ws4.roads.accounts import load_route_config
   from ws4.sim.engine import Simulator

   config = load_route_config("tmp/howto/route.yaml")
   Simulator.from_dataset(dataset).run(
       schedule_csv,
       years=100,
       out_dir=Path("tmp/howto/routed"),
       route_model=config.model,
       route_accounts=config.route_accounts,
       duplicate_accounts=config.duplicate_accounts,
   )

Troubleshooting
---------------

* **Everything is surplus** — no destination is eligible for the product. Check the eligibility
  table, and check that the destinations are reachable from the block's linkage vertex.
* **Haul cost is zero** — the product was not routed at all, usually the same cause as above. Look at
  ``route_values.csv``: a missing row is a routing problem, a zero cost is a rate problem.
* **The search became very slow** — usually a **build** route account, a **duplicate** account, or
  an edge-contrast element. Haul, maintenance, and volume route accounts are additive, so the search
  prices a move with a route delta; those three are not, and force a whole-schedule evaluation per
  step. Keep them out while you tune, then add them (`notes/design/ws4-performance.md` in the
  repository records the measurements).
* **Build cost appears once and never again** — that is the model: a segment is charged its build
  cost in the first period it is used and its maintenance cost in every period it is used.
* **Two mills share a vertex and the choice looks arbitrary** — destinations are identified by
  **account name**, not by vertex, and the choice is exclusive: the least-haul-cost reachable
  eligible destination wins.
