# WS4 SDMD and AU Explorer expansion plan

Status: active
Phase: **P87 — Stand density management and AU Explorer**
Branch: `feature/p87-sdmd-au-explorer`
Parent issue: #628
Workflow: `ubc-fresh-dev-workflow`

## 1. Purpose

Add a stand-density-management layer to ws4 that lets foresters:

- inspect AU-level yield and stand-density evidence;
- see an AU's observed PSP plots and compiled FVS trajectory on an SDMD;
- compare silviculture regimes as paths on the SDMD;
- constrain the allowed treatment sequences for selected AUs;
- pass those constraints to the ws4 solver so the option space is smaller and
  better posed.

The SDMD is a **diagnostic and constraint layer**, not a replacement for FVS or
the ws4 optimizer.

## 2. Scope

### In scope

- One region and a small AU set first.
- PSP, VRI, and LiDAR ingestion.
- SDMD digitization and AU placement.
- Regime state machine for even-aged regimes.
- AU Explorer API and web tab.
- Solver constraints and an option-count benchmark.

### Out of scope

- Uneven-aged SDMDs. The classic diagram assumes even-aged, healthy, untreated
  development. KC selection regimes are not directly SDMD-valid.
- Full provincial SDMD atlas.
- Legal-compliance determination.
- A new growth model. FVS-BC and PSP remain the growth sources.
- Calibrating SDMDs to AFRF without enough plots.

## 3. Workflow contract

Follow the UBC-FRESH pattern:

- one phase = one parent GitHub issue + one feature branch;
- one task = one child issue + one roadmap checkbox;
- subtasks = checklist items in the child issue body;
- one bounded move per commit;
- commit messages start with the task ID;
- every commit leaves `python scripts/dashboard.py` green;
- update `ROADMAP.md`, `CHANGE_LOG.md`, `notes/`, docs, and issues in the
  same change set;
- no phase merge without an approved close-out report.

Proposed issue map:

| Task | Child issue | Deliverable |
| --- | --- | --- |
| P87.1 | #629 | SDMD/regime schemas and ADR |
| P87.2 | #630 | PSP/VRI/LiDAR ingestion |
| P87.3 | #631 | SDMD digitization and AU placement |
| P87.4 | #632 | Regime state machine and constraints |
| P87.5 | #633 | AU Explorer API |
| P87.6 | #634 | AU Explorer web tab |
| P87.7 | #635 | Solver constraint integration |
| P87.8 | #636 | Provenance, docs, closeout |

## 4. Package layout

```text
ws4/ws4/sdmd/
  __init__.py
  schema.py
  ingest.py
  compile.py
  diagram.py
  regimes.py
  constraints.py
  api.py
  web/
    __init__.py
    routes.py
    static/
  data/
    sdmd/*.json          # digitized diagram vectors
```

Keep `femic` and `nemora` generic. This is a ws4 extension.

## 5. Data contracts

### 5.1 Plot table

```text
plot_id, region, bec_zone, bec_subzone, bec_variant,
tsa, au_id, visit_year, stand_age, site_index,
slope, aspect, elevation, plot_area_ha,
sources, review_status
```

### 5.2 Tree list

Use the existing nemora/FVS tree-list shape:

```text
plot_id, tree_id, species, dbh_cm, height_m,
crown_ratio, tph, live, damage, source
```

### 5.3 Stand summary

```text
plot_id, visit_year, age, tph, ba_m2_ha, qmd_cm,
top_height_m, mean_height_m, volume_m3_ha,
crown_cover_pct, source, review_status
```

### 5.4 SDMD point

```text
sdmd_id, au_id, region, species_group, site_index,
age, top_height_m, qmd_cm, tph, ba_m2_ha,
mean_tree_volume_m3, rd, sdi, sdi_max,
zone, source, review_status
```

### 5.5 Regime

```text
regime_id, au_id, name, entry_age,
entry_type, residual_ba_m2_ha, removal_fraction,
cycle_length, repeat_count,
post_treatment_track, eligibility_expr,
operability_expr, constraint_ids, review_status
```

### 5.6 AU constraint

```text
au_id, regime_id, allowed,
min_entry_age, max_entry_age,
max_entries, min_interval_years,
max_removal_fraction,
required_sdmd_zone, source, review_status
```

## 6. Ingestion and compilation

Pipeline:

```text
PSP plots + tree lists
VRI AU assignment
LiDAR piece size and clump evidence
        ↓
normalize and validate
        ↓
match plots to AU by BEC/TSA/species/age/site
        ↓
nemora only for gaps, labelled synthetic
        ↓
FVS-BC no-cut and regime trajectories
        ↓
SDMD points, envelope, and AU report
        ↓
regime library and constraints
```

Rules:

- PSP supplies total TPH, BA, QMD, height, and age support.
- VRI supplies AU identity and species composition.
- LiDAR supplies piece size, crown structure, and clump evidence.
- Never use canopy-only LiDAR TPH as total TPH.
- `nemora` is a gap-fill, not an observed-data source.
- Every synthetic plot is labelled.

## 7. SDMD layer

Digitize the species/region diagram into vector data:

- density axis: TPH;
- mean tree volume axis: m³/tree;
- top-height isopleths;
- QMD isopleths;
- crown-closure line;
- competition/density-management band;
- self-thinning/mortality boundary.

Store each isopleth as ordered points and metadata. Do not store only a raster.

The PDF supplied is a **how-to guide**, not the species atlas. The public BC set is
14 one-page diagrams: seven species, each natural and planted. The catalog is
`ws4/sdmd/data/sdmd/source_catalog.json`, and the 229-row BEC coverage table is
`ws4/sdmd/data/sdmd/bec_variants.csv`. For IDFdk3/FDI use `fdin` (natural) or
`fdip` (planted). The Farnden 1996 report is public and catalogued. Store vector
isopleths only; do not copy a PDF or third-party text into the repository.
Digitization must be signed off by a named reviewer before use: the maintainer, or
an RPF the maintainer designates.

## 8. AU report

For each AU:

- yield curves: volume, BA, TPH, QMD, top height;
- observed PSP points;
- FVS/PSP trajectory;
- SDMD placement;
- regime trajectories;
- plausibility status;
- data gaps and review status.

The report should explicitly reject trajectories outside the observed envelope.
The 1,173 m³/ha KC point is an example of an upper-tail/extrapolated point that
the report must flag.

## 9. Regime model

Regimes are ordered state machines, not one-off schedules:

- `untreated`
- `clearcut`
- `ct60`
- `fuel50`
- `selection80`
- `shelterwood40`
- `vr20`

Each regime declares:

- entry age range;
- residual BA or removal fraction;
- cycle length and repeat count;
- post-treatment track;
- eligibility and operability;
- SDMD trajectory;
- review status.

The solver may choose only regimes allowed for the AU.

## 10. Web UI — AU Explorer

Add one tab to the existing ws4 web shell.

### Layout

**Left rail**

- region;
- AU;
- species group;
- site index;
- age range;
- data source filter;
- review status.

**Main**

1. Yield curves.
2. SDMD with observed points and FVS trajectory.
3. Regime trajectory on the SDMD.
4. Constraint editor.

**Right**

- provenance;
- plot count and age support;
- SDMD source;
- caveats;
- “Use in scenario”.

### Constraint editor

- allow/deny regime;
- entry-age window;
- maximum entries;
- minimum interval;
- maximum removal fraction;
- save constraint set;
- show option-count reduction before/after.

## 11. API

```text
GET  /api/sdmd/regions
GET  /api/sdmd/aus?region=...
GET  /api/sdmd/au/{au_id}
GET  /api/sdmd/au/{au_id}/plots
GET  /api/sdmd/au/{au_id}/yield
GET  /api/sdmd/au/{au_id}/sdmd
GET  /api/sdmd/au/{au_id}/regimes
GET  /api/sdmd/au/{au_id}/trajectory?regime_id=...
POST /api/sdmd/au/{au_id}/constraints
GET  /api/sdmd/au/{au_id}/constraint-preview
```

Write endpoints need a validator. No validator, no capability.

## 12. Solver integration

- load `au_constraints`;
- filter regimes before building the optimization model;
- enforce entry-age and interval constraints;
- cap entries per AU;
- reject trajectories outside allowed SDMD zones;
- report `tracks_before`, `tracks_after`, `treatments_before`, `treatments_after`.

The acceptance test is not only a feasible solve. It is a measurable reduction in
the option space with no loss of allowed prescriptions.

## 13. Validation gates

1. Plot support.
2. Density plausibility.
3. SDMD fit.
4. Trajectory plausibility.
5. Initial volume plausibility.
6. Regime completeness.
7. Solver option reduction.
8. UI payload contract.

The initial-volume gate must reject the 863 m³/ha KC value. It must also flag
the 1,173 m³/ha trajectory as an extrapolation even if the volume is present in a
few old-growth PSP plots.

## 14. Test plan

- Unit: schema coercion, SDMD interpolation, regime transitions.
- Contract: API payloads, constraint files, dataset tables.
- Integration: ingest → compile → API → UI fixture.
- Property: monotone curve domains, valid regime sequences, no forbidden entry.
- UI: Playwright smoke test for tab render, chart selection, constraint save.
- Solver: before/after option-count benchmark.
- Negative: reject the 863 m³/ha initial volume and the 1,173 m³/ha trajectory.

## 15. Delivery sequence

### P87.1 Schemas and ADR

- Add `ws4.sdmd` package.
- Add `notes/adr/00xx-sdmd-as-constraint-layer.md`.
- Define tables and validators.
- Fixture: two AUs, ten plots.

### P87.2 Ingestion

- PSP/VRI/LiDAR adapters.
- AU matching.
- Provenance and review status.
- Reject canopy-only TPH as total density.

### P87.3 SDMD

- Digitize one species/region diagram.
- Build SDMD points and envelope.
- Overlay observed plots and FVS trajectory.
- Forester review of digitized isopleths.

### P87.4 Regimes and constraints

- State machine.
- Regime library.
- AU constraint table.
- Negative tests.

### P87.5 API

- Read endpoints.
- Constraint write endpoint.
- Option-count preview.

### P87.6 UI

- AU Explorer tab.
- Yield chart.
- SDMD chart.
- Regime trajectory.
- Constraint editor.
- Use-in-scenario.

### P87.7 Solver

- Regime filtering.
- Constraint enforcement.
- Benchmark reduction.
- Regression tests.

### P87.8 Closeout

- Docs.
- Changelog.
- Dashboard.
- PR.
- Phase close-out report.

## 16. Parallelization

Can run in parallel after P87.1:

- P87.2 ingestion and P87.3 SDMD digitization;
- P87.4 regimes and P87.5 API once schemas settle;
- P87.6 UI once API fixtures exist;
- P87.7 solver once constraints exist.

Do not start P87.6 before the API payload contract is stable.

## 17. Risks and controls

- **SDMD source.** Use the public BC diagrams or published equations; record the
  URL, version, and checksum; do not copy third-party text or figures into tracked
  files.
- **SDMD not valid for uneven-aged KC.** Scope to even-aged regimes; flag
  selection regimes as outside the diagram.
- **PSP coverage.** Do not invent density support. Mark unsupported AUs.
- **Digitization error.** Store vector points, not a raster, and require review.
- **UI complexity.** Build one chart at a time behind fixtures.
- **Solver regression.** Benchmark before/after and keep all previous tests.

## 18. First bounded move

Do only this first:

> Create `ws4.sdmd.schema`, an ADR, a two-AU fixture, and tests for the plot,
> tree-list, SDMD, and regime contracts. No UI, no ingestion, no solver.

That gives the parallel agent a stable contract and a green dashboard before any
chart or optimizer work.

## 19. Handoff commands

```bash
git switch feature/p87-sdmd-au-explorer
python scripts/check_workflow.py
python scripts/dashboard.py
```

## 20. Required reading for the next agent

1. `AGENTS.md`
2. `ROADMAP.md` — Phase 87 is the active phase, parent issue #628.
3. `CHANGE_LOG.md`
4. The `ubc-fresh-dev-workflow` pages `docs/reference/workflow-model.rst`,
   `docs/reference/phase-closeout.rst`, and `docs/agents/session-protocol.rst`.
5. This plan.
6. The SDMD how-to guide supplied by the maintainer, held outside the repository.
   Use it to inform the design; do not copy it into tracked files.
7. Farnden (1996) SDMD source for the actual species/region diagrams.
