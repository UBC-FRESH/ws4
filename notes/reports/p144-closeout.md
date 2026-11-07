# Phase close-out report: P144 Stochastic landscape engine

Phase: P144, Stochastic landscape engine
Parent issue: #852
Pull request: #872
Merge commit: `d6522e3`
Branch: `feature/p144-stochastic-landscape`
Status: merged and closed on 2026-11-07 as `d6522e3`
Design note: `notes/design/ws4-stochastic-landscape.md`

## Recommendation

1. Squash-merged pull request #872 as `d6522e3`; the branch was deleted.
2. Closed task #858 and parent issue #852.
3. Keep the 3D fire visualization as the queued idea #868, not part of this phase.
4. The next engine phase should be succession, regeneration, and a calibrated yield bridge;
   full policy search and the estate-optimizer integration follow after that.

Settings changes: none. No tag, release, repository setting, or external account is part of
this phase.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Same inputs and seed produce an identical event log and account values. | `test_replay_is_exact_and_seed_sensitive`; `EventLog.read` digest validation; the 5×5 demo prints a stable replay digest. | Met |
| Common random numbers hold across candidate decisions. | `test_sample_average_approximation_best_and_crn` (same seed sequence across decisions); `test_common_random_numbers_reduce_paired_variance` (paired variance zero, independent variance positive). | Met |
| A fire process can be applied to a compiled dataset without changing the management contract. | `test_fire_run_reads_a_package_and_dataset`; the ecosystem package is a sidecar; `ws4 ecosystem validate-package` returns `valid: true`; no compiled-dataset writes. | Met |
| A risk-aggregated target (mean or CVaR) can be optimized and replayed. | `test_fire_evaluator_runs_scenarios_without_mutating_the_initial_state`; `test_out_of_sample_report`; the SAA report writes train/validation values and aggregates. | Met |
| Area and carbon conservation checks pass. | `CohortState.check_area_conservation`; `test_fire_effect_preserves_area_and_creates_snags`; `test_biomass_mass_balance_closes_after_fire_and_salvage` closes live biomass against killed, snag-created, and emitted shares. Full CBM pool-and-flux accounting is deferred. | Met for area and biomass mass balance |
| `python scripts/dashboard.py` is green. | Full dashboard green at the close-out commit. | Met |

## What changed

### P144.1 — design and contracts

- `notes/design/ws4-stochastic-landscape.md` specifies the event algebra, the
  `ws4.ecosystem.v1` sidecar, the cohort/fraction state, the landscape graph, the annual event
  phases, the counter-based tape, the optimizer coupling, the stochastic-optimization ladder,
  and the validation oracles.

### P144.2 — event record and random tape

- `ws4/ecosystem/events.py` — the unified `Event` record, canonical ids and attributes, the
  deterministic sort key, and the `femic.disturbance.v1` adapter.
- `ws4/ecosystem/log.py` — `EventLogMetadata`, `EventLog`, `EventLogBuilder`, the SHA-256
  replay digest, JSON read/write, and `verify_replay`.
- `ws4/ecosystem/tape.py` — `DrawKey` and the counter-based `RandomTape` (Philox 2x64) with
  common random numbers and vector draws.
- `ws4 ecosystem validate-log`.

### P144.3 — ecosystem package and cohort state

- `ws4/ecosystem/package.py` — the closed `ws4.ecosystem.v1` manifest, table loader, table
  hashes, package fingerprint, state schema, bridge declarations, dataset join, and
  `validate_ecosystem_package`.
- `ws4/ecosystem/state.py` — `StateVariable`, `StateSchema`, `BridgeSpec`, `NullBridge`, and
  `CohortState` with area-weighted aggregation, species fractions, absolute cohort areas,
  missing-fragment reporting, and area conservation.
- `find_ecosystem_package` and `load_dataset_ecosystem` return `None` when a dataset has no
  sidecar.
- `ws4 ecosystem validate-package`.

### P144.4 — fire vertical slice

- `ws4/ecosystem/fire.py` — Poisson ignition, fuel/distance/wind graph percolation, severity,
  cohort mortality, deterministic salvage, `FireRun`/`FireResult`, the synthetic grid, and the
  demo.
- `Event.to_disturbance_dict(start_year=...)` maps simulation offsets to calendar years.
- `examples/ecosystem_fire_demo.py` and `docs/reference/ecosystem-fire.rst`.
- Fire, salvage, state, and biomass accounts.

### P144.5 — scenarios and risk targets

- `ws4/ecosystem/scenarios.py` — `Scenario`, `ScenarioSet`, YAML/JSON load and write,
  train/validation split, common random numbers, `risk_account_values`, and
  `SampleAverageApproximation`.
- Risk aggregations: mean, min, max, CVaR lower/upper, quantile, probability, and regret.
- `Target.aggregation`, `risk_alpha`, `risk_minimum`, and `risk_maximum`; `load_targets`
  parses them. The default is `single`, so existing targets are unchanged.
- `OutOfSampleReport` and `fire_evaluator`.
- `docs/reference/ecosystem-scenarios.rst`.

### P144.6 — verification and close-out

- Added `fire.killed_biomass_t`, `fire.snag_created_t`, and `fire.emitted_biomass_t` and a
  live-biomass mass-balance test.
- Ran the full dashboard, the ecosystem coverage run, the 5×5 fire demo, the event-log and
  package validators, and an SAA out-of-sample report.
- Wrote this report and queued #872.

## Evidence

### Dashboard

```text
GATE                STATUS   SECONDS
lint                GREEN
format              GREEN
types               GREEN
tests               GREEN
validator           GREEN
docs                GREEN
docstrings          GREEN
OVERALL: GREEN. Every gate passed.
```

### Tests and coverage

- Ecosystem and objective suites: **233 tests**.
- `ws4.ecosystem` branch coverage: **90%** (event/log/tape/package/state/fire/scenarios).
- The full dashboard test gate is green (the repository's coverage gate is on `scripts/`; the
  ecosystem figure is reported separately).

### Fire demo

`python examples/ecosystem_fire_demo.py` (5×5 grid, 30 years, seed 7):

```text
events: 105
fire events: 44
salvage events: 40
replay digest: 8719b429b64b02556d2a3813b551a30c90a0a998b7e66d8077d5006299ca62a1
```

The final-year accounts include fire count, burned area, mortality area, severity, killed
biomass, snag-created biomass, emitted biomass, salvage, live biomass, fuel, and snags.

### Validators

`python -m ws4.cli ecosystem validate-log --events … --json` on a 3×3, 10-year, seed-7 fire
run:

- replay token `61dc98d9144e35eb2bbac3528c7ec351a92baf0da902bfb14956e6123e58569d`;
- processes `fire` and `salvage`;
- phases `ignition`, `propagation`, and `treatment`.

`python -m ws4.cli ecosystem validate-package --package … --json` on a synthetic package and
dataset:

```json
{"findings": [], "package": "…/dataset/ecosystem", "valid": true}
```

The package fingerprint is `4ecf06d74953cd862e2d0e65d78b623b5652727163d9c3522b86bc72110d3015`.

### Scenario ensemble

The SAA verification run used three training scenarios and two validation scenarios, a CVaR
upper target on burned area, and two fire configurations. It wrote:

- `train_values.csv` and `validation_values.csv`;
- `train_aggregated.csv` and `validation_aggregated.csv`;
- `summary.json` with the objective, scenario counts, target penalties, and the generalization
  gap.

The numeric out-of-sample evidence is in `test_out_of_sample_report` (training objective 8.0,
validation objective 5.5, gap -2.5).

## Deviations and limits

- **Full CBM carbon coupling is not implemented.** The fire slice closes a live-biomass mass
  balance (killed biomass = snag-created + emitted; initial live biomass = final live biomass
  + killed). The `CarbonLedger` and SIT compiler still consume the schedule; an ecosystem
  event source for fire/salvage is a later task.
- **The fire model is not calibrated.** It is a LANDIS-class skeleton with explicit parameters
  and analytic oracles, not a fire-behaviour or smoke model.
- **Only fire is implemented.** Wind, insects, drought, disease, succession, and regeneration
  are later processes.
- **The estate optimizer is not yet wired to the stochastic fire process.** The SAA layer is
  generic and demonstrates the bridge; the optimizer's incremental search still evaluates the
  deterministic compiled dataset.
- **Flow targets are not risk-aggregated.** A flow penalty compares a whole profile; it needs
  a different scenario treatment.
- **The package tables are CSV.** A columnar cohort table is a later performance decision.
- **Time is annual.** Continuous-time event scheduling and a raster site layer are later
  work.
- **The 3D fire visualization is not part of P144.** It is queued as #868 with a design note.

## Next

Recommended candidates, not commitments:

- **P145 — Succession, regeneration, and the calibrated yield bridge.** Turn the cohort state
  into a living ecological state and connect it back to the management track and volume
  curves.
- **P146 — Stochastic optimization in the estate search.** Wire the scenario/risk layer into
  the optimizer's evaluation path, then add policy search and two-stage recourse.
- **Parallel visual phase — 3D fire propagation (#868).** Synthetic individual-tree stands over
  real VRI polygons, real-time flames and smoke, and the WS4 Fire workspace.
