# Candidate and simulator caches: full TSA23 end-to-end result

Date: 2026-10-30

## Result

The remaining full-model setup cost was the simulator load and candidate-chain generation,
not the table or search. Caching those two build products reduced the repeated full TSA23
`ft_econ` 20 x 10 GPU run from **96.4 s to 32.9 s** for seed 7, with all three seeds at
exact objective **0.0**.

| Seed | Exact objective | End-to-end cached | vs CPU 386 s |
|---:|---:|---:|---:|
| 7 | 0.0 | **32.9 s** | **11.7x** |
| 8 | 0.0 | **33.7 s** | **11.5x** |
| 9 | 0.0 | **35.5 s** | **10.9x** |

The previous lean-table runs were 96.4 / 82.6 / 83.8 s. The cached runs use a checked-in
runner, a matching simulator cache, a matching candidate cache, and the lean effect table.

## Profile that motivated the cache

On the full TSA23 model:

| Stage | Seconds |
|---|---:|
| Optimizer construction | 0.02 |
| Simulator/dataset load | **34.3** |
| Candidate generation | **32.6** |
| Targets + seed load | 0.68 |
| Lean effect-table load | 0.71 |
| Population construction | 11.8 |

Candidate generation and simulator loading were 67 s of the 96 s lean-table run.

## Cache measurements

### Candidates

- Build: 69.4 s
- Pickle write: 12.3 s
- Pickle load: **5.97 s**
- File size: 274,000,208 bytes
- Round-trip equality confirmed.

### Simulator

- Load from parquet and build: 34.7 s
- Pickle write: 7.5 s
- Pickle load: **4.15 s**
- File size: 781,076,306 bytes

Both caches record the compiled-dataset fingerprint: the manifest plus every table named by
it. A changed dataset or candidate horizon raises an explicit mismatch; it never silently
uses a stale map. The caches are local trusted artifacts.

## Cached run breakdown

Seed 7, 64 genomes, 1,000 generations:

| Stage | Seconds |
|---|---:|
| Optimizer + targets + seed | 0.25 |
| Simulator cache load | 4.38 |
| Candidate cache load | 8.86 |
| Lean table load | 0.74 |
| Population construction | 11.09 |
| Search, 1,000 generations | 6.79 |
| Fresh exact verification | 0.78 |
| **Total** | **32.90** |

Seeds 8 and 9 measured 33.72 s and 35.47 s with the same caches. All returned schedules
replayed to exact **0.0**.

## Reproducible runner

`examples/gpu_effects/run_full_model.py` now loads the candidate and simulator caches,
loads the lean table, runs a seed, writes the schedule, and performs the fresh exact replay.
The cache identity is checked automatically. Use `--rebuild-cache` after changing the
dataset or candidate horizon.

## Limits

- One target, three seeds, one saved simulator/candidate/effect-table set.
- Simulator and candidate build plus cache write are excluded from the repeated-run times.
- The caches are keyed by dataset content and candidate constants, not by target file; the
  effect table carries the target identity.
- The GPU path keeps the established contract: one priority tier, no patch accounts, no
  route accounts, and no spatial rules.
- The pickled caches are trusted local files; this is not a public artifact format.

## What remains

The repeated run is now mostly population construction (11 s) and search (7 s). Further
gains would require a persistent GPU process or a different population construction, not
another cache.
