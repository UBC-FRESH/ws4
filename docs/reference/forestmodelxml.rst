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

Select statements are parsed into terms. A term is ``field op value`` for ``eq``, ``ne``, ``lt``,
``le``, ``gt``, ``ge``, and ``in``. A term that uses a function call or a ``not`` expression is kept
as an opaque term (``op == '?'``) and skipped when matching, so a compile is best-effort for models
that use the full expression language.

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
- a treatment's ``new_track`` is the track of the stratum reached by applying its transition;
- a block with fragments in more than one stratum is emitted once per portion (``blocks``).

On the reference model's recipe and fragments, this expansion produces 1399 strata and 2024 treatment
rows. The reference matrix for the full model has 7048 strata, so the remaining gap is the additional
stratification (state variables beyond the recipe's defines).

Legacy ingestion
----------------

`ws4.build.legacy.ingest_legacy_matrix` reads an existing matrix directory plus a fragments table,
maps the legacy column names to the schema, and records the mapping in the manifest.

.. code-block:: bash

   ws4 ingest --matrix legacy/matrix --fragments fragments.csv --out build/compiled

Reference output
----------------

A reference compiled matrix for a real, moderately complex model (a UBC research forest) has these
dimensions, which set the target for the builder:

- ``tracknames`` and ``strata``: 7048 tracks, one per development stratum;
- ``treatments``: 10014 rows (treatments expand across the tracks they apply to);
- ``blocks``: 3183 rows, with a block split into a managed and an unmanaged portion;
- ``accounts``: 91 accounts;
- ``messages``: no rows (a clean compile).

WS4's current builder produces one track per select (11 for that model), so the main gaps are stratum
expansion over the theme space, block splitting into managed and unmanaged portions, and per-track
treatment expansion.

Known gaps
----------

The following are not implemented yet and are tracked in the P2 tasks:

- the additional stratification state variables (``origin``, ``statecode``, ``hasnatcurve``, and the
  rest) that the recipe's defines do not carry;
- full evaluation of the select expression language (function calls, ``not``, string functions);
- expression-based attribute labels and ``factor`` expressions, and the ``%f`` / ``%m`` / ``%au``
  label substitution patterns;
- ``expression``-sourced attribute curves (the curve is chosen by an expression at runtime);
- ``succession``, ``retention``, and ``produce`` semantics beyond treatment transitions;
- reading a fragments shapefile (needs the ``geo`` extra);
- evaluating expression-based ``input`` fields such as ``Int(RES_KEY)`` and ``Shape_Area/10000``.

API
---

.. autofunction:: ws4.io.forest_model_xml.parse_recipe

.. autofunction:: ws4.build.compiler.build_canonical_dataset

.. autofunction:: ws4.build.legacy.ingest_legacy_matrix
