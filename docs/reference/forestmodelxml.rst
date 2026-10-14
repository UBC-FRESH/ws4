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

`ws4.build.compiler.build_canonical_dataset` maps the recipe and the fragments into the matrix:

- one track per select, in order, named by its statement;
- each fragment is assigned to the first select whose terms match its row (constants resolved);
- features, products, and treatments are emitted per track;
- a treatment's ``new_track`` is resolved by applying its transition to the source select's terms and
  matching the result against the selects;
- curves, blocks, groups, accounts, and messages are emitted.

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
