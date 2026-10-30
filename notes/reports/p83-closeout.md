# P83 close-out: two-stage c5 even-flow and GPU search

Date: 2026-10-30

## Outcome

P83 added the two-stage c5 even-flow path, closed the c5 target tension with an explicit
policy decision, and produced a full-model TSA23 GPU path that matches the CPU objective.

The c5 result keeps its accepted gaps. The TSA23 full-model result is exact and faster on
three seeds. These are separate results; the c5 flow gap is not a TSA23 claim.

## c5 two-stage even-flow

- Stage 1 pulls harvest with the linear over-maximum target; stage 2 enables the nonlinear
  plus/minus 5% even-flow target and continues from the stage-1 schedule.
- The 100,000-iteration c5 run reached objective **39,133,750** in **36.1 s**, final stock
  **20.96M**, and conifer flow **-8.12% / +6.01%**.
- The selected 79% final-stock target is **20,979,565.28**. The result is 20,957,070.69, an
  accepted **22,494.59** shortfall (0.085% of initial stock).
- The remaining conifer flow gap is accepted as part of the same policy compromise.
  Plus/minus 5% conifer flow is **not** claimed.
- The decision is recorded in
  `notes/design/ws4-c5-evenflow-performance.md` and the scenario uses
  `targets_balanced_stock79.yaml`.

## Performance and GPU work

- Bounded LNS, seeded process islands, flow-directed repair, and batch-effect benchmarks
  reduced search overhead without changing target semantics.
- The sparse float64 effect table was built for the full TSA23 model: 20,237,499 rows,
  25,320,796 nonzeros, 567 MB, 200 target cells, 1,340 s cold build.
- `EffectTable.save`/`load` persists the table; the full-model run reuses it.
- The GPU candidate-index population search evaluates whole genomes in one batched device
  operation, with exact `IncrementalObjective` scores.

## Full TSA23 ft_econ 20 x 10

Final run, 64 genomes, 1,000 generations, seed 7:

| Stage | Seconds |
|---|---:|
| Dataset and candidate load | 83.3 |
| Persisted table load | 125.7 |
| Population construction | 140.0 |
| Search, 1,000 generations | 12.6 |
| **Total** | **153.6** |

- Initial objective 21,023,339.72 -> **0.0**.
- Fresh exact `IncrementalObjective` replay: **0.0**, matching the device result.
- Best generation 117; 64,064 evaluations.
- CPU 20 x 10 reference: 386 s at objective 0.
- Total speedup: **2.51x** for this seed.
- Seed 8: exact **0.0** in 132.3 s; seed 9: exact **0.0** in 142.5 s, with one shared setup.
- Schedules: `/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/ga1000-schedule.csv` and
  `ga1000-seed{8,9}.csv`.
- Evidence: `notes/reports/p83-7-full-tsa23.md`.

The 1,340 s table build is excluded. This is a three-seed, one-target result.

## Population and portfolio findings

- c5 2k GPU GA: 36.09-36.17M in 1.3-1.6 s against 40.94-45.15M CPU in 28-41 s; 20.8-26.0x
  search-only and 2.5-3.6x including the 9.6 s table build. Single island was the best
  configuration; seven-worker ring/AGrp was slower and no better on c5.
- TSA23 5k subset: GA was modestly better, but the cold table build dominated.
- Fixed round-robin master/worker portfolio: 0.33-1.33% worse than the best single GA at an
  equal 15 s c5 budget (mean +0.75%). GA produced the incumbent on 2/3 seeds, SA on 1/3,
  and LNS never entered the archive. This is the negative baseline adaptive credit must beat.
- No adaptive-credit portfolio or multi-seed full-model matrix is claimed.

## Verification

- Focused GPU population, portfolio, table, and search tests pass.
- Full dashboard reports **OVERALL: GREEN**.
- The full-model TSA23 schedule was replayed with a fresh exact evaluator.

## Remaining work

- Multi-seed full TSA23 GPU validation.
- Adaptive-credit portfolio only if it beats the single-GA baseline.
- Decide whether the GPU path should become a production optional path; no CLI wiring is
  included in P83.
