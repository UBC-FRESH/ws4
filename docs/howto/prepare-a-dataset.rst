=================
Prepare a dataset
=================

Everything downstream reads one artefact: a **compiled dataset**. This guide compiles one from a
recipe and a fragment inventory, shows how to import an existing matrix instead, and checks the
result.

Prerequisites
-------------

* WS4 installed, with the ``geo`` extra if your fragments are a shapefile.
* A model recipe (``recipe.xml`` in the ForestModelXML format, see
  :doc:`../reference/forestmodelxml`) and a fragment inventory (CSV or Parquet, or a shapefile with
  the ``geo`` extra).

Procedure
---------

**1. Compile from a recipe and fragments.**

.. code-block:: bash

   ws4 build --xml examples/synthetic/recipe.xml \
             --fragments examples/synthetic/fragments.csv \
             --out tmp/howto/compiled

.. code-block:: text

   Built dataset → tmp/howto/compiled

The API equivalent:

.. code-block:: python

   from pathlib import Path

   from ws4.build.compiler import build_canonical_dataset

   dataset = build_canonical_dataset(
       Path("examples/synthetic/recipe.xml"),
       Path("examples/synthetic/fragments.csv"),
       Path("tmp/howto/compiled"),
   )

**2. Import an existing matrix instead.** If your model already exists as a compiled matrix
(``tracknames``, ``strata``, ``treatments``, ``blocks``, ``features``, ``products``,
``protoaccounts``), skip the recipe and ingest it:

.. code-block:: bash

   ws4 ingest --matrix path/to/matrix --fragments path/to/fragments.shp --out tmp/howto/compiled

**3. Validate.**

.. code-block:: bash

   ws4 validate --dataset tmp/howto/compiled

.. code-block:: text

   Dataset is valid → tmp/howto/compiled

**4. Look inside.** The dataset is Parquet plus a manifest, and the model API reads it as frames:

.. code-block:: python

   from ws4.model.api import Model

   model = Model.from_dataset(dataset)
   print(sorted(model.tables))
   print(model.table("treatments").to_string(index=False))

.. code-block:: text

   ['accounts', 'blocks', 'curves', 'features', 'fragments', 'groups', 'messages',
    'products', 'protoaccounts', 'strata', 'tracks', 'treatments']

The tables you will query most often are ``fragments`` (the decision units), ``treatments`` (what is
operable, by age), and ``curves`` (growth and yield).

Troubleshooting
---------------

* **``build`` reports a missing dependency** — the recipe needs a reader from an extra. Install the
  extra it names (``geo`` for shapefiles).
* **``validate`` fails on a table** — the message names the file, the column, and the problem. Do not
  edit a compiled dataset by hand; change the inputs or the recipe and recompile, because the
  manifest records the inputs' digests.
* **Blocks are missing from the simulation** — check ``fragments.parquet``: a fragment with an
  unknown block, a zero area, or an age outside the curve domain will be reported by ``validate``.
* **Nothing is operable** — an empty ``treatments`` table, or age windows that exclude your stand
  ages. ``treatments.begin`` and ``treatments.end`` come from the recipe's ``minage`` and ``maxage``.

Notes
-----

* The compiled dataset is fragment-level, and blocks are a runtime view. One dataset therefore
  serves many block layouts.
* Compilation is deterministic: the same recipe and inventory compile to the same tables, which is
  what makes a study reproducible.
