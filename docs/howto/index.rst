=============
How-to guides
=============

Task-shaped guides for the work WS4 is used for. Each one is self-contained, states what you need
first, and calls out the traps. Every command and snippet was run against the repository's own
example, and the output shown is the output it produced.

Two columns are worth noting: **CLI** guides are pure command line, **API** guides are Python, and
guides marked both show each path where they differ.

.. list-table::
   :header-rows: 1
   :widths: 34 10 56

   * - Guide
     - Mode
     - What it does
   * - :doc:`prepare-a-dataset`
     - both
     - Compile a recipe and a fragment inventory, import an existing matrix, and validate.
   * - :doc:`write-targets`
     - both
     - State what you want: accounts, levels, weights, shapes, periods, and how to balance them.
   * - :doc:`even-flow`
     - both
     - Hold a harvest profile flat, or stop a closing inventory declining, including the priming
       step that makes the term finite.
   * - :doc:`patch-targets`
     - both
     - Require that harvesting lands as openings of a size you choose, using block topology.
   * - :doc:`route-products`
     - both
     - Send products over a road network to mills, and target the haul, build, and maintenance
       accounts.
   * - :doc:`run-carbon`
     - both
     - Run a FEMIC carbon package through a baseline, an optimizer target, and optional
       fertilization, and read the carbon accounts.
   * - :doc:`watch-a-run`
     - both
     - Watch realized against target values while a search runs, one window per account.
   * - :doc:`automate-a-study`
     - API
     - Sweeps, seeds, and reading results back — what the Python API is for.
   * - :doc:`faq`
     - both
     - Short answers to the questions that come up first.

Prerequisites
-------------

* WS4 installed (:doc:`../getting-started/installation`).
* The quickstart run, in either form: :doc:`../getting-started/quickstart` or
  :doc:`../getting-started/python-api`.
* A compiled dataset to work on. The guides use the example in ``examples/synthetic``; swap in
  your own paths as you go.

.. toctree::
   :maxdepth: 2
   :hidden:

   prepare-a-dataset
   write-targets
   even-flow
   patch-targets
   route-products
   run-carbon
   watch-a-run
   automate-a-study
   faq
