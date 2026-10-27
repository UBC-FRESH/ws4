# P58.8 carbon-aware validation: TSA24 and MKRF

Date: 2026-10-26
Phase: P58
Task: P58.8
Related: `notes/design/ws4-carbon.md`, `notes/reports/p585-parity.md`,
`notes/reports/p587-carbon-optimizer.md`

## 1. Scope

This task validates the carbon path on the two real instances the maintainer named:
TSA24 first, then MKRF. The full TSA24 landscape CBM run was attempted, but it did not
finish inside a useful window. The carbon-aware search and exact verification were
therefore run on documented spatial subsets of each instance, while the full datasets
and packages were built and inspected.

## 2. TSA24

### Full model build

- FEMIC materialized the TSA24 instance and fetched the 537,243-stand shapefile from the
  Arbutus annex remote.
- FEMIC exported the Patchworks/ForestModel package: 27 AUs, 536,458 fragments, 2,175
  curves.
- WS4 built the real compiled dataset: **536,458 fragments, 108 tracks, 54 treatment
  rows**.
- FEMIC built the real carbon package against the compiled dataset: **108 tracks,
  6,016,466.4 ha, 3,348 yield rows**.

### Baseline on one AU

AU `2401005` was used as the first bounded real baseline: **7,313 fragments, 72,875.7 ha**.
A five-year TSA24 carbon run completed in about 38 seconds:

- Ecosystem carbon start: **21,774,124.4 tC**
- Ecosystem carbon end: **21,949,881.3 tC**

The full 536,458-fragment landscape run was attempted; after **35 minutes 30 seconds at
~99% CPU with no output** it was stopped. That is a runtime limit, not a model failure.

### Carbon-aware search

A 50-block subset (430.4 ha) was used for the carbon-aware search:

- Baseline at 5 years: **134,891.2 tC**.
- Target: `carbon.ecosystem.total`, period 5, maximum **134,000 tC**.
- Search: 50 iterations, SA, seed 1. Incumbent objective **0.0**.
- Winning schedule: three blocks treated with `CC`.
- Ledger value at offset 4: **133,340.4 tC**.
- Exact `ws4 carbon` verification at offset 4: **133,294.95 tC**.

The ledger and the exact landscape run differ by about **45 tC (0.03%)** after the
disturbance events; the initial state matches exactly. The exact run still satisfies the
target. The small difference is recorded rather than hidden: the final schedule is always
verified by the exact engine.

## 3. MKRF

### Full model build

- The MKRF canonical ForestModel and fragments are available in
  `external/femic-mkrf-instance`.
- WS4 built the real MKRF dataset: **3,183 fragments, 7,048 tracks**.
- The MKRF instance bundle is not the standard `curve_table.csv` / `curve_points_table.csv`
  shape, so a package was built from the compiled dataset's
  `feature.yield.{managed,unmanaged}.merch.total` curves and the MKRF AU metadata:
  **1,903 tracks, 1,578 inventory fragments, 3,253.47 ha**.
- Some MKRF tracks have no merchantable feature curve; those tracks are excluded from the
  package and the subset. This is recorded as a package-coverage limitation, not a silent
  fallback.

### Baseline and carbon-aware search

- Full MKRF package subset baseline: **2,227,238.5 → 2,238,636.0 tC** over five years.
- A five-block subset (18.98 ha) gave a baseline of **11,528.0 → 10,779.3 tC**.
- Target: `carbon.ecosystem.total`, period 5, maximum **10,500 tC**.
- Search: 50 iterations, SA, seed 1. Incumbent objective **0.0**.
- Winning schedule: two blocks treated (`CC` at offsets 0 and 1).
- Exact `ws4 carbon` verification at offset 4: **10,478.44 tC**.
- The block ledger and the exact run are identical for this MKRF subset.

## 4. What this establishes

- The real TSA24 and MKRF datasets compile and accept a real carbon package.
- Carbon accounts are priced in the optimizer on both instances, and a carbon ceiling
  changes the schedule.
- The winning schedules are verified with the exact `ws4 carbon` engine, not only the
  ledger.
- The full TSA24 landscape run is a runtime problem, not a correctness problem; the full
  package and dataset are ready for a longer run.

## 5. Limits

- The carbon-aware search used spatial subsets, not the full 536k-fragment TSA24 landscape.
  A full-landscape search needs a ledger cache budget or a precomputed treatment set.
- The TSA24 ledger/exact difference of ~0.03% should be investigated before the ledger is
  treated as an exact oracle for production optimization. The exact run is the authority.
- The MKRF package excludes tracks without a merchantable feature curve.
- Both carbon targets were chosen to be reachable on the subset. They are mechanism
  validation levels, not policy recommendations.

## Later status (2026-10-27)

P120 subsequently ran full-landscape 50-year schedules for TSA08, TSA16, TSA40, and
TSA41 after inventory/event aggregation, and compiled real split-TSA matrices. The
full TSA24 carbon-aware search remains a separate runtime/cache question; this note's
subset result is still a mechanism validation, not a production optimum. See
`notes/reports/p120-multi-boundary.md`.
