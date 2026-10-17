===============
Getting started
===============

WS4 has two ways in, and most people need only one of them:

* **The command line.** One command per step of a study, from compiling a dataset to writing a
  report. No Python, nothing to import. Start with :doc:`quickstart`.
* **The Python API.** The same steps as library calls, for automation, custom diagnostics,
  sensitivity sweeps, and integration with other tools. Start with :doc:`python-api`.

Both paths read and write the same files, and both can be mixed: a command-line run can be
resumed in Python, and a Python study can shell out to the commands it does not want to
reimplement.

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Page
     - What it covers
   * - :doc:`installation`
     - Requirements, the optional extras, and a three-command install check.
   * - :doc:`quickstart`
     - The command-line walkthrough: compile, simulate, target, search, watch.
   * - :doc:`python-api`
     - The same walkthrough as Python, plus the in-memory evaluator and a hand-driven search.
   * - :doc:`first-model`
     - A complete small study, with the numbers checked by hand.
   * - :doc:`architecture`
     - How the parts fit together, and the pitfalls that follow from the design.

.. toctree::
   :maxdepth: 2
   :hidden:

   installation
   quickstart
   python-api
   first-model
   architecture
