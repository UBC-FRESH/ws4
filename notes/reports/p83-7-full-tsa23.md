# P83.7 full-model TSA23 GPU population search

Date: 2026-10-30

## Result

The full TSA23 `ft_econ` 20 x 10 target is now solved by the GPU candidate-index population
search at **objective 0.0** on three seeds, with a **fresh exact** `IncrementalObjective`
replay matching every device result. The first full run took **153.6 s**, including loading
the dataset and the persisted effect table. The CPU 20 x 10 reference took **386 s** for
objective 0, so this is a **2.51x** total wall-clock speedup for that seed.

This is a full-model result, not a 2k/5k slice. It is a one-target, three-seed result with
table-build cost excluded; the table was built earlier and reused.

| Seed | Best objective | Best generation | Search s | Total s |
|---:|---:|---:|---:|---:|
| 7 | 0.0 | 117 | 12.6 | 153.6 |
| 8 | 0.0 | 105 | 8.2 | 132.3 |
| 9 | 0.0 | 104 | 3.3 | 142.5 |

Seeds 8 and 9 were run in one process that loaded the dataset and table once, so their
`Total s` values share the 106.2 s setup. All three schedules are saved under
`/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/`.

## Model and table

- Dataset: `/tmp/opencode/tsa23-runtime/runtime/ws4/compiled_ft_econ`
- Targets: `evenflow_ft_econ_20x10.yaml`
- Seed: `/tmp/opencode/femic-tsa23-instance/runtime/seed_evenflow_ft_econ_20x10.csv`
- Persisted table: `/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/effects.pt`
- Blocks: 66,584
- Candidate chains: 20,237,498
- Table rows: 20,237,499 (including the empty-chain row)
- Nonzeros: 25,320,796
- Sparse table size: 567,032,736 bytes
- Target cells: 200
- Seed blocks: 46,300

The earlier full-table build took 1,340 s and was not repeated. The persisted table is loaded
with `EffectTable.load`.

## Run breakdown

Final run, 64 genomes, 1,000 generations, seed 7, `check=1`:

| Stage | Seconds |
|---|---:|
| Dataset and candidate load | 83.3 |
| Persisted table load and upload | 125.7 |
| Population construction (including option map) | 140.0 |
| Search, 1,000 generations | 12.6 |
| **Total** | **153.6** |

- Option-map construction after the linear-row change: about **14.3 s**; the rest of population
  construction is base-state and seed setup.
- Evaluations: 64,064
- Initial objective: 21,023,339.72
- Best objective: **0.0**
- Best generation: 117
- Peak VRAM: 1.15 GB
- Peak host RSS: 12.5 GB
- Schedule: `/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/ga1000-schedule.csv`
- Log: `/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/ga1000-final.log`

## Exactness

The device objective was re-evaluated from the returned schedule with a new
`IncrementalObjective`, not with the population's pricer:

```text
verified_objective: 0.0
device_objective:   0.0
matches:            true
```

`check=1` also compared the first initial genome with a fresh exact evaluator. The exact
objective of 0 means the 20 x 10 target contract, including the period levels and even-flow
band, is satisfied under the evaluator used by the CPU reference.

## Comparison

| Path | Objective | Wall-clock |
|---|---:|---:|
| CPU 20 x 10 reference | 0.0 | 386 s |
| Full GPU population (this run) | **0.0** | **153.6 s** |
| GPU population, 100 generations | 6,988.12 | 545.9 s with the old 535 s option-map builder |

The 100-generation run used the pre-optimization option-map construction. It improved from
21.02M to 6,988 but did not reach the target. The 1,000-generation run reached 0 at generation
117; the extra generations were cheap because each generation is one batched device
evaluation.

## What changed

The original option-map construction made one Python `row_index` lookup for every one of the
20.2M candidate chains. The table's builder assigns each block's candidate rows consecutively,
so the population now resolves only the first and last candidate row per block and fills the
range with `arange`. A non-contiguous table still falls back to the exact per-chain lookup.
This reduced population construction from **534.9 s** (100-generation run) to **140.0 s** for
the final run, of which the option map is about 14 s.

The table build itself remains expensive and is not included. Dataset and table loading now
dominate the end-to-end cost, so a warm/reused process would be even faster.

## Scope and limits

- Three seeds, one target configuration, and one persisted table.
- The GPU population path keeps the established exactness contract: one priority tier, no
  patch accounts, no route accounts, and no spatial rules.
- The table must contain the seed chains; extra seed-only rows are supported, but this run did
  not need them.
- The result is a speedup at equal objective, not evidence that the GPU path is better on every
  seed or dataset. The earlier 5k TSA23 subset and the c5 portfolio comparison remain separate,
  limited results.
- The CPU 386 s reference and the GPU run are not a controlled benchmark matrix; they are the
  best available full-model result for the same target.

## Follow-up

The normal archive's `row_index` load was later removed by the lean archive; the full-model
end-to-end time fell from 153.6 s to 96.4 s for seed 7, with seeds 8 and 9 at 82.6 s and
83.8 s. See `notes/reports/p83-lean-table.md`.

