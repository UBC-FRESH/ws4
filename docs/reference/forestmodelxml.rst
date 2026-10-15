ForestModelXML recipe
=====================

WS4 reads the established **ForestModelXML** model format as its recipe, and compiles it with a
fragment inventory into the compiled matrix dataset (see `notes/adr/0011` and
`notes/design/ws4-matrix-builder-and-interop.md`). The compiler is a matrix builder.

What the parser reads
---------------------

`ws4.io.forest_model_xml.parse_recipe` reads:

- the root ``ForestModel`` attributes ``horizon``, ``year``, and ``match``;
- ``curve`` elements and their points;
- ``define`` elements, split into field-to-column bindings and constants;
- the ``input`` element's ``block``, ``area``, and ``age`` expressions;
- the ``output`` element;
- ``select`` blocks, each with a statement, features, products, and a track with treatments;
- treatment ``minage``, ``maxage``, ``retain``, and ``transition`` assigns;
- attribute sources: a ``curve`` reference or an ``expression``.

Select statements are evaluated by ``ws4.io.expressions``: comparisons (``eq``, ``ne``, ``lt``, ``le``,
``gt``, ``ge``, ``in``), the boolean operators (``and``, ``or``, ``not``), string concatenation and
arithmetic, parentheses, and the functions ``startswith``, ``endswith``, ``substring``, ``int``,
``Number``, ``length``, ``lastindexof``, ``if``, ``lookupTable``, ``curveId``, ``attribute``, and
``operable``. An expression the evaluator cannot parse falls back to a term matcher that skips the
terms it cannot read, so a compile is best-effort for models that use a function the evaluator lacks.

Compilation
-----------

The matrix is a **Model II** model. State variables (themes) define a **stratum**; a **track** is a
unique trajectory over time between two treatments; and a **treatment** resets one or more state
variables, which moves a block to the stratum of the new values and therefore onto that stratum's track.

`ws4.build.compiler.build_canonical_dataset` builds the matrix with a Model II expansion
(`ws4.build.expansion`):

- the **state variables** are the recipe's non-constant define fields;
- each fragment's state is read from its columns, and the **reachable strata** are enumerated from the
  inventory and the treatment transitions, to a fixed point;
- each stratum becomes a **track** (``tracknames``), named by its state values;
- a stratum is governed by **every** select whose statement matches it, and features, products, and
  treatments accumulate across those selects;
- a treatment's ``new_track`` is the track of the stratum reached by applying its transition
  (a literal, a constant, a field reference such as ``au = auf``, or a concatenation such as
  ``'thn_'+au``);
- a ``<retention factor="RET">`` rule splits a fragment's area into a retained portion (the factor,
  moved to the assigned state, for example ``IFM = unmanaged``) and a base portion (the remainder);
  a ``<features>`` element nested inside the ``retention`` describes the retained fraction and attaches
  to the stratum the rule moves the area to;
- an ``expression``-sourced attribute resolves to a curve name, or, when it evaluates to a number, to a
  generated constant curve; ``attribute('label')`` resolves to a label already emitted for the same
  stratum, so an attribute can be derived from another (for example ``operable(attribute('…'))``);
- a block with fragments or portions in more than one stratum is emitted once per portion (``blocks``).

Validation
----------

The builder is validated against several reference compiled matrices. On each, it reproduces the
structural counts exactly:

.. list-table::
   :header-rows: 1
   :widths: 40 20 20 20

   * - Model
     - tracks / strata
     - treatments
     - blocks
   * - a 218-fragment instance (two variants)
     - 351 / 351
     - 263
     - 399
   * - the same instance, intensive variants
     - 732 / 732 and 553 / 553
     - 963 and 605
     - 427 and 427
   * - a 421,945-fragment instance
     - 524 / 524
     - 210
     - (not published)

On the MKRF canonical rebuild recipe and its fragments (1763 records), the builder reproduces the
reference matrix exactly: **tracks 7048/7048, strata 7048/7048, treatments 10014/10014, blocks
3183/3183, features 104311/104311, products 420588/420588, and protoaccounts 91/91** (row counts and
label sets; `scripts/acceptance.py`). The reference is the model's own canonical ``tracks/`` directory.
A matrix from a different model variant is not a valid comparison.

Legacy ingestion
----------------

`ws4.build.legacy.ingest_legacy_matrix` reads an existing matrix directory plus a fragments table,
maps the legacy column names to the schema, and records the mapping in the manifest.

.. code-block:: bash

   ws4 ingest --matrix legacy/matrix --fragments fragments.csv --out build/compiled

Reference output
----------------

A reference compiled matrix for a real, moderately complex model (a UBC research forest) sets the
target for the builder:

- ``tracknames`` and ``strata``: 2116 tracks, one per development stratum;
- ``treatments``: 2024 rows (treatments expand across the tracks they apply to);
- ``blocks``: 3183 rows, with a block split into a managed and an unmanaged portion;
- ``accounts``: 60 accounts;
- ``messages``: no rows (a clean compile).

The reference is the model's own ``Tracks/`` directory. Compare a builder run against the matrix from
the same recipe and fragments; a matrix from a different model variant is not a valid comparison.

Known gaps
----------

The following remain and are tracked in the backlog (``notes/backlog.md``):

- the wider expression function library (functions beyond those listed above);
- ``succession`` and ``produce`` semantics beyond treatment transitions;
- legacy-ingestion layouts beyond the known columns, and the road model;
- a replay of a run validated against a reference schedule.

API
---

.. autofunction:: ws4.io.forest_model_xml.parse_recipe

.. autofunction:: ws4.build.compiler.build_canonical_dataset

.. autofunction:: ws4.build.legacy.ingest_legacy_matrix
