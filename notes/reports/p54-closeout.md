# P54 environmental accounts close-out

Date: 2026-10-26
Parent issue: ws4 #375
Status: complete

## Merged children

| Child | PR | Merge commit | Scope |
| --- | --- | --- | --- |
| P54.1 DHI | #463 | `b0438de` | `feature.DHI.*`, ingest/provenance, report, `/api/runs/{run}/dhi` |
| P54.2 Structure habitat | #471 | `b4f7caa` | exact Coops et al. (2016) components, coverage gap report, `feature.SHI.*`, DHI comparison |
| P54.3 Resilience | #475 | `865bef6` | `resilience.connectivity.*`, `.age_class.*`, `.fragmentation.*`, report and two-run comparison |

## Account contract

- DHI: levels in `index_ha`/`index`/`ha`; source version and raster coverage are
  required. The public WCS product used is a 2003-2022 composite, documented.
- Structure habitat: levels in `m`/`%`/`ha`; exact first-return metrics required.
  The real TFL 6 bundle reports missing metrics rather than substituting CHM
  proxies.
- Resilience: connectivity and age are levels; fragmentation is a per-year flow.
  Connectivity uses the full undirected topology; the directional spread account
  remains separate.
- None changes growth, constraints, the objective, or the solver.

## Verification

- P54.1 targeted suite: 10 DHI tests.
- P54.2 targeted suite: 11 structure tests.
- P54.3 targeted suite: 8 resilience tests; identical-schedule property passes.
- Structure pilot: exact-metric synthetic blocks 40 -> 20 ha under harvest.
- Resilience pilot: compact vs scattered openings, patch count 1 vs 4 with age
  count 5 vs 5.
- Post-merge `python scripts/dashboard.py` -> **GREEN** (lint 0.10 s, format
  0.12 s, types 29.15 s, tests 134.53 s, validator 0.90 s, docs 17.51 s,
  docstrings 2.98 s).

## Residual boundaries

- DHI is a coarse productivity surrogate, not a species observation.
- Structure habitat is unavailable on the current TFL 6 bundle; a CHM proxy
  would be a different index and needs a separate decision.
- Resilience topology is block-level; it cannot see within-block structure.
- No tag or release was created.
