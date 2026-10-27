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
* **Analysts and planners** — people building scenarios, targeting even flow or patch size
  distributions, routing products to mills, accounting for carbon, or repeating and scaling
  runs. See :doc:`howto/index` and :doc:`guides/index`.
* **Researchers and policy analysts** — people asking what the model assumes, where the
  evidence lives, and what a result does not claim. Start with :doc:`concepts/index`,
  :doc:`reference/carbon`, and :doc:`guides/limitations-and-boundaries`.
* **Instructors and students** — people learning forest estate modelling from a runnable,
  inspectable example. Start with :doc:`getting-started/first-model` and the
  :doc:`examples`.
* **LLM coding agents** — assistants that read and edit this repository. Follow ``AGENTS.md``,
  ``docs/llms.txt``, and :doc:`reference/index` for the contracts, invariants, and
  conventions to respect.

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
   * - :doc:`concepts/index`
     - New and returning users
     - What the model *is*: fragments, strata, annual growth, periods, and the objective.
   * - :doc:`howto/index`
     - Analysts
     - Task guides: targets, even flow, patch size distributions, routes, the Python API.
   * - :doc:`examples`
     - Everyone
     - Runnable notebooks, with their output, that you can read or adapt.
   * - :doc:`reference/carbon` and :doc:`howto/run-carbon`
     - Analysts, researchers, agents
     - Carbon packages, libcbm runs, carbon targets, fertilization, HWP lifecycle, carbon
       yield curves, and the GCBM bridge.
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
   :caption: Concepts

   concepts/index

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
