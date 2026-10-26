# P58 closeout: forest carbon accounting and carbon-aware planning

Date: 2026-10-26
Phase: P58
Parent issue: #357
Branch: `feature/p58-carbon`

## 1. What the phase delivered

P58 made carbon a first-class, reproducible outcome of a WS4 run and a target the
optimizer can search against. It did so without changing the compiled-dataset contract:
the carbon package is a separate FEMIC-produced input, and libcbm is an optional engine.

Delivered:

- A typed, closed-schema carbon package loader and track-name join (`P58.1`).
- A SIT compiler from the package, compiled dataset, and schedule (`P58.2`).
- A libcbm driver with a pinned optional extra and the `ws4 carbon` command (`P58.3`).
- Carbon accounts merged into simulation runs and the standard report (`P58.4`).
- WS3 parity, mass-balance/account reconciliation, and byte-level replay (`P58.5`).
- A block-level carbon ledger (`P58.6`).
- Carbon targets in the optimizer with exact per-block CBM deltas (`P58.7`).
- Real TSA24 and MKRF validation on bounded spatial subsets (`P58.8`).
- A GCBM results reader and comparison surface (`P58.9`).

## 2. Evidence

- WS4 dashboard: **GREEN** on lint, format, types, tests, validator, docs, docstrings.
- WS3/WS4 parity on the clipped TSA24 fixture: **exact** on every pool and flux column
  (`max_abs = 0.0`, 25 inventory rows, 24 yield rows).
- Real TSA24: full dataset (536,458 fragments, 108 tracks) and package (108 tracks,
  6,016,466.4 ha). One-AU baseline 21.77M -> 21.95M tC in 38 s. A 50-block carbon-aware
  subset met a 134,000 tC ceiling with objective 0.0; exact verification 133,294.95 tC.
- Real MKRF: full dataset (3,183 fragments, 7,048 tracks) and a dataset-derived package
  (1,903 tracks, 1,578 inventory fragments). A five-block subset met a 10,500 tC ceiling
  with objective 0.0; exact verification 10,478.44 tC.
- GCBM: the supplied package ran under Wine 9.0 on the bundled sample (11,347 land units,
  85 s), and the results reader produced 120 locations / 12 steps, 67,388.5 -> 52,880.9 tC.
- Two TSA24 carbon runs replayed byte-identically for accounts, pools, flux, and manifest.

Reports:

- `notes/reports/p585-parity.md`
- `notes/reports/p587-carbon-optimizer.md`
- `notes/reports/p588-carbon-validation.md`
- `notes/reports/p589-gcbm-results.md`

## 3. Boundaries and deferred work

- **Full TSA24 landscape carbon-aware search.** The full 536k-fragment CBM baseline was
  stopped after 35 minutes at ~99% CPU with no output. The package and dataset are ready;
  the search needs a ledger cache budget, a precomputed treatment set, or a longer run.
- **Ledger exactness on real data.** The TSA24 ledger and exact run differ by ~45 tC
  (0.03%) after disturbances, while MKRF is exact. The final schedule is always verified
  with `ws4 carbon`; the ledger is not advertised as an exact production oracle until that
  difference is explained.
- **Same-landscape GCBM comparison.** The reader and comparator are ready. The bundled
  GCBM sample is not TSA24 or MKRF; the same-footprint comparison needs the FEMIC
  walltowall export (P115.4). GCBM GeoTIFFs are not yet mapped to WS4 blocks.
- **MKRF package coverage.** Tracks without a merchantable feature curve are excluded.
- **Species resolution.** The package uses one CBM species per track; species-resolved
  curves and the CBM/CFS crosswalk review remain in the FEMIC lane.
- **CBM4.** The driver boundary is ready; CBM4 is not public yet.

## 4. Verification commands

```bash
python scripts/dashboard.py
ws4 carbon --dataset <dataset> --package <package> --schedule <schedule> --out <out>
ws4 optimize --dataset <dataset> --targets <targets> --carbon-package <package> --out <out>
ws4 gcbm --results gcbm_output.db --out <out>
```

## 5. Closeout state

- Child tasks P58.1 to P58.10 are closed or recorded with their deferral above.
- The phase branch is `feature/p58-carbon`.
- Pull request: #408, approved for squash-merge from `feature/p58-carbon` to `main`.
- Parent #357 closes after the merge; the branch is deleted after the merge.
