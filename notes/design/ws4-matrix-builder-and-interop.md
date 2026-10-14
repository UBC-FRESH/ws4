# WS4 Matrix Builder and Interoperability

Status: draft
Phase: P1 (Contracts and prototype)
Date: 2026-10-14
Related: `notes/design/ws4-architecture.md` (sections 4 and 6), `notes/adr/0006`, `notes/adr/0011`

## 1. Context

The lab already works with an established model format and a compiled matrix format:

- A **ForestModelXML** recipe describes the logical model: a horizon and base year, curves, an input
  block/area/age definition, output definitions, field definitions, attributes with curve references,
  select statements, treatments, transitions, and retention.
- A **matrix** dataset is the compiled form: `tracknames`, `strata`, `treatments`, `blocks`, `features`,
  `curves`, `products`, `accounts`, `groups`, and `messages`.
- A **fragments shapefile** carries the spatial inventory: `BLOCK`, `AREA_HA`, `F_AGE`, `AU`, `IFM`,
  `ORIGIN`, `RETENTION`, `TSA`, and geometry.

The lab's FEMIC project already exports this pair (ForestModelXML + fragments shapefile) and validates
it, with public functions such as `build_forestmodel_xml_tree`, `validate_forestmodel_xml_tree`,
`build_fragments_geodataframe`, `validate_fragments_geodataframe`, and `export_model_package`. Many
users and organisations hold legacy datasets in this format, dating back to 2001.

Inventing a new recipe format would discard that ecosystem and force every user to convert.

## 2. Decision

WS4 adopts the established formats rather than inventing new ones:

- The **recipe** is ForestModelXML. WS4 reads it and validates it against the same structural rules that
  the lab exporter enforces (root `ForestModel` with `horizon`, `year`, and `match`; an `<input>` with
  `block`, `area`, and `age`; an `<output>`; the `define` fields; a `unity` curve; at least one
  treatment; and every attribute curve reference resolving to a defined curve).
- The **compiler** is a matrix-builder module. It consumes ForestModelXML plus a fragments inventory and
  emits the compiled matrix that `notes/design/ws4-architecture.md` section 5 describes.
- The **inventory** is a fragments table with the established fields, read from a shapefile or a
  columnar file.
- WS4 **ingests legacy datasets**: an existing matrix directory, a blocks shapefile, a topology table,
  and a road model can be read directly, without a recompile.

## 3. Semantics that the formats carry

Three concepts stay separate, exactly as the lab's model-semantics contract requires:

- **IFM** (`managed` / `unmanaged`) is treatment eligibility only.
- **ORIGIN** (`natural` / `planted`) is curve provenance only.
- **RETENTION** is an orthogonal area reallocation; it may move area from managed to unmanaged and keeps
  its origin unless the model changes it explicitly.

Do not infer one from another, and do not use curve-family availability as a proxy for eligibility.

## 4. The stratum-and-track (Model II) formulation

The matrix format is a **Model II** forest estate model. The vocabulary has three levels:

- **State variables** (themes) are the block attributes the model tracks: eligibility, origin, seral
  state, analysis unit, operability, and so on.
- A **stratum** is a unique combination of state-variable values. It is the finest inventory unit the
  model distinguishes.
- A **track** is a unique trajectory over time between two treatments: a sequence of strata, one per
  offset age, that a block follows as it grows.

A **treatment** resets one or more state variables. Because a stratum is indexed by the state-variable
values, resetting them moves the block to the stratum of the new values, and therefore onto that
stratum's track. Treatments are the edges between tracks.

This is why the compiled matrix is large. The builder enumerates the reachable strata and expands each
one into a track, so a moderate model yields thousands of tracks (the reference MKRf matrix has 7048),
and treatments appear once per track they apply to (10014 rows). It is also why a block can appear more
than once: a block whose area is split between a managed and an unmanaged portion has one row per
portion, because the portions sit on different tracks.

The builder, then, is:

1. Enumerate the state variables and their value spaces.
2. Enumerate the reachable strata from the initial inventory.
3. For each stratum, grow the trajectory (growth and succession) into a track.
4. At each point where a treatment is eligible, apply it, reset the state variables, and connect to the
   target stratum's track.
5. Emit the tracks, strata, treatments, blocks (split by portion), features, products, and accounts.

## 5. Reuse and boundary

Recommended default: WS4 does not copy the exporter; it **reuses the format contract** and, where it
helps, calls the lab exporter's functions to produce or validate ForestModelXML and the fragments
shapefile. The matrix builder in WS4 is the reader/compiler side of the same contract.

Reason: one contract, two implementations (export and compile) is cheaper and less error-prone than a
second, divergent copy of the format.

## 6. Relationship to the P1.2 prototype

The P1.2 prototype parses a minimal XML recipe so the pipeline can be exercised end to end. That minimal
format is a placeholder. The production recipe parser (P2) replaces it with ForestModelXML, and the
prototype's synthetic fixture becomes a ForestModelXML fixture. The compiled matrix and the simulator do
not change, because the matrix is already the contract.

## 7. Legacy ingestion

A legacy dataset may arrive as:

- a compiled matrix directory (the tables above),
- a blocks shapefile plus a topology table,
- a road model (`vertices`, `segments`, `destinations`, `linkages`), and
- a launch control file that starts a run.

WS4 ingests the matrix and the spatial tables directly. Where a legacy matrix uses column names that
differ from the WS4 schema, an adapter maps them and records the mapping in the manifest.

## 8. Two construction paths

Precedent: WS3 has used the Woodstock input file format since 2015, and it remains the go-to format for
WS3 models. Teams also build or patch a `ws3.forest.ForestModel` instance directly when the file format
is clunky for something unusual, or when the model must change programmatically at runtime after
ingestion.

WS4 follows the same pattern, with two paths that meet at the same model:

- **File path.** ForestModelXML plus a fragments inventory goes through the matrix builder into the
  compiled matrix. This path is reproducible and shareable, and the matrix is the contract for a run.
- **Programmatic path.** A model API constructs or patches the model in memory: add or replace a track,
  a treatment, a curve, a fragment, or a block; override a parameter; apply a runtime update after
  ingestion.

The compiled matrix stays the file contract; the in-memory model is the programmatic contract. A
programmatically built model can be written to the matrix for a run, and a matrix can be loaded into the
model. Neither path is privileged: the file path serves the common case and interoperability, and the
programmatic path serves the unusual case and runtime changes.

## 9. Open questions

1. **Dependency direction.** Depend on the FEMIC package, or share the format contract and keep the
   code separate. Default: share the contract; depend only if the reuse is substantial.
2. **Schema mapping.** The exact column mapping between a legacy matrix and the WS4 schema. Default: an
   explicit adapter table, recorded in the manifest.
3. **Shapefile support.** The prototype reads CSV/Parquet; shapefile support needs the geo extra.
   Default: add the geo extra in P2.
