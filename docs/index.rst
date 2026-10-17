===================================
Wood Supply Simulation System (WS4)
===================================

Welcome to the **Wood Supply Simulation System** (``ws4``) documentation. WS4 is an
open-source, command-line-first forest estate model that treats **space as first-class**:
fragments are the decision units, blocks aggregate them at runtime, and adjacency, patch
structure, and road access are enforced inside simulation and optimization rather than
allocated after the fact.

Who Is This Documentation For?
==============================

* **New users** — forest planners, students, and land managers running a first wood supply
  simulation. Start with :doc:`getting-started/index`.
* **Analysts** — people building scenarios, targeting even flow or patch size distributions,
  routing products to mills, or repeating and scaling runs. See :doc:`howto/index` and
  :doc:`guides/index`.
* **LLM coding agents** — assistants that read and edit this repository. Follow ``AGENTS.md``
  and :doc:`reference/index` for the contracts, invariants, and conventions to respect.

Quick Navigation
================

.. list-table::
   :header-rows: 1
   :widths: 22 24 54

   * - Section
     - For Whom
     - What You Will Learn
   * - :doc:`getting-started/index`
     - New users
     - Installation, a first run, and how the pieces fit together.
   * - :doc:`howto/index`
     - Analysts
     - Task guides: targets, even flow, patch size distributions, routes, the Python API.
   * - :doc:`examples`
     - Everyone
     - Runnable notebooks, with their output, that you can read or adapt.
   * - :doc:`guides/index`
     - Power users
     - Troubleshooting, and what WS4 deliberately does not do yet.
   * - :doc:`reference/index`
     - Everyone
     - The dataset contract, the simulator, the optimizer, spatial rules, and roads.

Documentation Sections
----------------------

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   getting-started/index

.. toctree::
   :maxdepth: 2
   :caption: How-to guides

   howto/index

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples

.. toctree::
   :maxdepth: 2
   :caption: Guides

   guides/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/index

.. toctree::
   :maxdepth: 1
   :caption: Tooling

   api/index

Indices and Tables
==================

* :ref:`genindex`
* :ref:`search`
