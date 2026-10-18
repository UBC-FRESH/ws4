``check_notebooks``
====================

The notebook drift check. The examples gallery renders each notebook's **stored** outputs, and the
docs build never executes them, so an example can show output the current code no longer produces and
the build will publish it anyway. This script re-runs every example in memory and compares what it
produces, cell by cell, with what is committed.

Run it with ``python scripts/check_notebooks.py``. It exits non-zero when anything has drifted, naming
the notebook and the cell, and writes nothing. The remedy is ``--refresh``, which executes the
notebooks and writes their new outputs back, so the commit that follows is the one the check asks for.

What it cannot compare it says out loud: the environment's own version banner, a duration or a
throughput, and a path are normalised away and counted, and a cell whose output is a live render can
be tagged ``no-drift-check`` in the notebook itself. It takes several minutes, so it is its own CI job
rather than part of ``scripts/dashboard.py``.

.. automodule:: check_notebooks
   :members:
   :show-inheritance:
