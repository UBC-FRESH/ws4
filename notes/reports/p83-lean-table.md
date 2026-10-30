# Lean effect-table archive: full TSA23 end-to-end speedup

Date: 2026-10-30

## Result

The full TSA23 `ft_econ` 20 x 10 GPU population run no longer pays the 20M-entry
`row_index` unpickle on every start. A lean archive keeps the 567 MB CSR tensors and each
block's candidate row start, and loads in **0.72 s** instead of **125.7 s**.

The measured single-seed end-to-end times, including dataset/candidate load, lean table
load, population construction, search, and exact replay, are:

| Seed | Exact objective | Population s | Search s | End-to-end s | vs CPU 386 s |
|---:|---:|---:|---:|---:|---:|
| 7 | 0.0 | 12.1 | 8.3 | **96.4** | **4.0x** |
| 8 | 0.0 | 4.1 | 2.6 | **82.6** | **4.7x** |
| 9 | 0.0 | 5.2 | 2.7 | **83.8** | **4.6x** |

The previous normal archive took 153.6 / 132.3 / 142.5 s for the same three seeds including
its 125.7 s table load. The lean archive is about **1.6x faster end-to-end** than the
already-improved normal archive and about **4.0-4.7x faster than the CPU reference** for
these seeds.

Every result above was re-evaluated with a fresh `IncrementalObjective`; all three returned
**0.0**, matching the device score. Seed 7 used 1,000 generations and was best at generation
117; seeds 8 and 9 matched the earlier full-model runs.

## What changed

`EffectTable` now records `block_starts` (the first candidate row for each block) and
`extra_rows` (seed-only rows outside the candidate range) during a build.

`EffectTable.save(..., include_row_index=False, candidates=...)` writes a lean archive:

- the three sparse CSR tensors;
- cells, blocks, build metadata;
- `block_starts` and `extra_rows`;
- no full `(block, chain) -> row` dictionary.

`EffectTable.load` accepts both archive shapes. `GenomePopulation` uses `block_starts` to
build its option-row map; the old per-block row-id fallback remains for normal archives and
for tables that are not contiguous.

The one-time migration from the existing normal archive was:

- load the old archive: 109.2 s;
- write the lean archive: 4.9 s;
- lean file size: **567,864,334 bytes**.

That migration is not part of the repeated run. The lean archive is
`/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/effects-lean.pt`.

## Run breakdown

Lean single-seed setup:

| Stage | Seconds |
|---|---:|
| Dataset and candidate load | 75.2 |
| Lean table load and GPU upload | **0.72** |
| Population construction, seed 7 | 12.1 |
| Search, 1,000 generations, seed 7 | 8.3 |
| **Seed 7 end-to-end** | **96.4** |

The dataset/candidate load is now the largest setup cost. The GPU search itself is under
10 s for these seeds.

## Exactness and scope

- All three schedules have exact objective **0.0**.
- Existing normal-archive round-trip and exact-population tests still pass.
- A new test saves and loads a lean archive and compares the entire population's device
  scores with the exact evaluator.
- The GPU path keeps the established contract: one priority tier, no patch accounts, no
  route accounts, and no spatial rules.
- The table build and the one-time normal-to-lean migration are excluded from the timed
  runs.
- One target configuration, three seeds, one saved table. This is not evidence of
  seed-independent quality on a different landscape.
