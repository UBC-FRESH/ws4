# P54: Environmental accounts (habitat and resilience)

Parent issue: `#375`
Branch: `feature/p54-environmental-accounts`
Status: active (2026-10-26); P54.1 implementation on `feature/p54.1-dhi-account`

## Purpose

Make biodiversity, habitat structure, and landscape resilience first-class ws4
accounts. Carbon is already owned by P51 (`#357`); this phase covers the
non-carbon values.

## Children

- `P54.1` (`#376`): Dynamic Habitat Indices biodiversity account.
- `P54.2` (`#377`): forest structure habitat index from ALS.
- `P54.3` (`#378`): spatial resilience metrics.

## Accounting contract

Each account declares a name, unit, level/flow semantics, source, version, and
uncertainty where available. Level accounts are read at the period's end offset;
flow accounts are summed over the period. The carbon account in P51 is the
reference pattern; reuse it rather than inventing a second account surface.

## Out of scope

- Carbon. It is owned by P51 and FEMIC P115.
- A species-specific habitat model or a full SDM.
- An objective, constraint, or solver change. Risk-aware planning is `PLAN-01`.
- A fire-spread simulator.
- FEMIC P114 hydrology.

## Acceptance

- Each account is reproducible from the scenario and its declared inputs.
- DHI and structure habitat cover the AOI or report their gaps.
- Identical schedules produce identical resilience metrics.
- Every account appears in a report or web view.
- No objective or constraint changes are made in this phase.

## Risks

- Layer staleness and scale mismatch.
- Metric redundancy across the three resilience metrics.
- False precision: an index is not a species observation.


## P54.1 implementation record

- Product: SILVIS Lab MODIS 6.1 Terra NDVI Composite RGB, 2003-2022, 500 m,
  EPSG:4326, public/no restrictions. The pilot stores a real WCS subset in
  `examples/dhi_pilot/`; the four blocks are synthetic test blocks.
- Ingest: `ws4 dhi ingest` samples block polygons (all-touched pixel mean),
  normalizes 8-bit values by 255, and refuses a block with no valid pixel.
- Account: `feature.DHI.cum`, `feature.DHI.min`, `feature.DHI.var` are levels
  in `index_ha`; the `.mean` variants are levels in `index`; `feature.DHI.area`
  is the surviving area in `ha`. A treated block leaves the account for the run.
- Outputs: `dhi_values.csv`, `dhi_metadata.json`, and `report_dhi.csv`; the web
  layer is `GET /api/runs/{run}/dhi` (or `?format=geojson`).
- Two schedules: the baseline keeps 40 ha of DHI; the harvest schedule drops to
  20 ha after blocks 1 and 3 are treated.
- Limit: the public product is a 2003-2022 composite, not an annual series. The
  trajectory is schedule-driven. No regrowth, species model, or objective change.

## P54.2 implementation record

- Definition: Coops et al. (2016) three-component structure index: P95 first-return
  height, first-return cover above 1.37 m, and SD of first-return heights above
  1.37 m. Breaks are 10/20 m, 33/66%, and 3/5 m. The paper has no weights; WS4
  records the equal-component statement and does not invent weights.
- Coverage: `ws4 shi diagnose` reports missing metrics and CHM proxies without
  substitution. The real TFL 6 bundle has CHM P95 and cover >=2 m, not the exact
  first-return metrics, so the index is not computable there.
- Accounts: `feature.SHI.height`, `.cover`, `.complexity` (area-weighted means),
  `.area`, and component class areas. `ws4 report` writes
  `report_structure_habitat.csv` with the caveat.
- Pilot: four synthetic exact-metric blocks; DHI comparison is exploratory n=4.
  The fixture is not ecological evidence.
