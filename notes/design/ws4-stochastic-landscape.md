# WS4 Stochastic Landscape Engine

Status: design
Phase: P144 (Stochastic landscape engine)
Date: 2026-11-07
Related: `notes/design/ws4-architecture.md`, `notes/adr/0004-goal-programming-metaheuristic.md`,
`notes/adr/0005-annual-simulation-step.md`, `docs/concepts/the-simulation.rst`,
`docs/reference/compiled-dataset.rst`, `docs/reference/disturbance.rst`,
`docs/reference/carbon.rst`, `ws4/sim/engine.py`, `ws4/opt/engine.py`,
`ws4/opt/objective.py`, `ws4/disturbance.py`, `ws4/patch/`, `ws4/spread/`, issue #852

## 1. The problem

WS4 is a deterministic estate model. Given a compiled dataset and a schedule, the simulator
replays one annual step at a time and produces account values. The optimizer searches the
schedule with a parallel metaheuristic and prices each move exactly where the accounts are
additive (`ws4/sim/engine.py`, `ws4/opt/engine.py`, `ws4/opt/objective.py`, ADR 0005).

Landscape ecosystem models of the LANDIS-II, SpaDES, and SELES class ask a different
question. They simulate uncontrolled events — fire, wind, insects, drought, succession,
regeneration, mortality — on a spatially explicit state, often with stochastic transitions
and a discrete-event scheduler. Their output is a distribution of landscape trajectories,
not a single optimizable plan.

The usual debate treats these as rival software categories. They are not. They are two
projections of one object: a spatially explicit state-transition system. A schedule is a set
of **controlled events**. An ecological process is a set of **uncontrolled events**. Both act
on the same state through the same transition kernel. Once that is explicit, the paradigms
merge:

- a deterministic run is a stochastic run conditioned on one realized random tape;
- a stochastic run is a distribution over tapes;
- optimization is a search over the controlled subset of the event space, under a
  distribution of the uncontrolled subset;
- adaptive optimization is a search over decision policies, not only over fixed schedules.

The merge is not a wrapper around an external landscape model. It is one executor, one state,
one event log, one account system, and one optimizer. The process engine is a set of event
generators plugged into the existing annual executor.

## 2. What WS4 already brings

The extension is smaller than it first appears because the existing architecture is already
the right shape:

- **An annual scheduler.** `Simulator.simulate` steps year by year, applies treatments,
  records products, computes spatial metrics, and writes accounts. ADR 0005 fixes the annual
  accounting step.
- **An event-like decision stream.** A schedule is `(block, treatment, offset)` rows;
  `apply_treatments` applies them and records products and route events.
- **A landscape graph.** The patch subsystem loads a block adjacency edge list with distances
  and shared lengths; the spread subsystem adds bearings and a directional cone
  (`ws4/patch/`, `ws4/spread/accounts.py`).
- **A spatial state view.** Patch metrics, edge contrast, core area, spread connectivity, and
  route accounts are views over block and fragment state.
- **Exact incremental evaluation.** `Optimizer._evaluate` uses `_incremental_values` for
  additive accounts and falls back to whole-schedule evaluation for non-additive ones.
  `PatchModel` and `FloodRiskModel` are existing non-additive evaluation components.
- **A package precedent.** `CarbonLedger` and the `libcbm` driver run an external engine
  behind a protocol; the carbon package, FEMIC hydrology bundle, and LiDAR products are
  versioned sidecars (`ws4/carbon/`, `docs/reference/carbon.rst`).
- **A disturbance vocabulary.** `ws4/disturbance.py` already defines a validated event record
  with `event_id`, `event_type`, `year`, severity, confidence, fragment and block ids, and
  area. It is read-only today; it is the right seed for the full event record.
- **Seed discipline.** Every stochastic search records its seed; the simulator is
  deterministic given a schedule. `ws4/opt/repro.py` already carries the reproducibility
  surface.

The annual step is already a scheduler. Treatments are already events. The topology is
already a landscape graph. Accounts are already observers. The optimizer is already a search
over event streams. The extension adds the uncontrolled events and the state they act on.

## 3. The unified model

Define one event record and one executor.

### 3.1 State

```text
S_t = (management state, ecological state, spatial state)
```

- **Management state**: fragment track/stratum, offset age, area, operability. This is the
  existing state that drives growth and yield, treatments, products, and accounts.
- **Ecological state**: cohorts by species and age, biomass, fuel load, snags, canopy
  structure, habitat variables, carbon pools. This is the new state that drives process
  hazards and modifies management transitions.
- **Spatial state**: fragment and site membership, adjacency, distance, bearing, shared edge
  length, and any optional geometry.

### 3.2 Event

```text
Event = (event_id, scenario_id, process_id, event_type,
         time, year, location_ids, magnitude, area_ha,
         attributes, parent_event_id, source, confidence)
```

An event is either **controlled** (a decision) or **uncontrolled** (a process outcome). The
executor does not distinguish them. Both are ordered, applied, and logged the same way.

### 3.3 Sources

```text
DecisionSource:  static schedule | policy | salvage rule | road plan
ProcessSource:   fire | wind | insect | drought | disease |
                 succession | regeneration | natural mortality
```

A static schedule is a degenerate decision policy. A policy is a function of state, time, and
forecast. This is what makes the merge useful for optimization: the optimizer can search a
schedule, a policy, or both.

### 3.4 Executor

```text
execute(S_0, decision_sources, process_sources, tape, horizon):
    S = S_0
    for year in horizon:
        for phase in phases(year):
            events = union(source.events(S, year, phase) for source in sources)
            for event in order(events):
                S = apply(S, event)
                log.append(event)
        accounts.record(year, S)
    return S, log, accounts
```

The executor is deterministic given `(S_0, sources, tape, horizon)`. There is no hidden global
random state. The event log is the audit trail.

## 4. State: three levels, two tiers

WS4's current state is a fragment with `track_id`, `offset`/age, area, and attributes; blocks
aggregate fragments at runtime. That is enough for management, not for ecology. The extension
adds a second tier rather than replacing the first.

### 4.1 Levels

- **Site** (optional): a raster cell or sub-fragment polygon, used when fragment-level
  geometry is too coarse for a process.
- **Fragment**: the decision and accounting unit. It remains the thing that compiles and the
  thing a treatment names.
- **Block**: the operational aggregate. Unchanged.

The landscape graph is the common spatial contract. A site layer is an optional refinement,
not a requirement.

### 4.2 Tiers

- **Tier 1 — management state**: track/stratum, age, area, operability. Drives growth and
  yield, treatments, products, and the existing accounts.
- **Tier 2 — ecological state**: cohorts by species and age, biomass, fuel, snags, habitat,
  carbon. Drives process hazards and modifies Tier 1 transitions.

### 4.3 Cohorts as area fractions

A fragment holds a population of substates with area fractions:

```text
fragment 101 (120 ha)
  cohort A: 70%  species PL, age 80, biomass ..., fuel ...
  cohort B: 20%  species PY, age 12, biomass ..., fuel ...
  cohort C: 10%  bare / regenerating, age 2, ...
```

A fire can burn 30% of a fragment without splitting the fragment object; it shifts area
fractions between cohorts. A harvest can remove one cohort and leave another. The fragment
stays the decision unit; the block stays the operational aggregate; the cohort is the
ecological accounting unit.

This representation is deliberately chosen over dynamic polygon splitting. It handles
partial-area events, keeps the fragment count stable, and makes area conservation a simple
invariant. A true sub-fragment geometry layer is available later through the optional site
level.

### 4.4 The yield bridge

The hard part is the connection back to management. LANDIS-class models track species
biomass; WS4 tracks merchantable volume through curves. The bridge must be explicit:

```text
management_state' = bridge(ecological_state, management_state, bridge_params)
```

The bridge maps species mix, age, biomass, and size class to the management track, the
merchantable volume curve, and any age/offset adjustment. A **null bridge** treats each
fragment as a single cohort and leaves the current behaviour unchanged. A calibrated bridge
is a modelling decision with real uncertainty; it must be versioned, documented, and
testable, not hidden inside a curve.

## 5. Space and time

### 5.1 Space

The substrate is a **landscape graph**, not a mandatory raster:

```text
node:  fragment or site
edge:  (src, dst, distance_m, bearing_deg, shared_m)
```

ws4 already has most of this. `ws4/patch/` loads adjacency with distances and shared lengths;
`ws4/spread/accounts.py` uses bearings and a directional cone. An optional geometry sidecar
can carry polygon or raster data for processes that need it. A raster import can populate the
site level, but a polygon-based estate is not forced into a grid.

### 5.2 Time

The annual accounting lattice stays. Add an intra-year event schedule. The first
implementation uses deterministic **event phases**:

1. weather and climate forcing;
2. ignition and outbreak generation;
3. propagation (fire spread, wind, insects);
4. event effects (mortality, fuel consumption, cohort shifts);
5. growth and succession;
6. controlled treatments;
7. regeneration and establishment;
8. accounts and snapshots.

This is LANDIS-like annual resolution with SELES-like event ordering. Continuous event time
can be added later: an event queue with timestamps inside the year, with the same annual
accounting snapshots. The accounting contract does not change.

### 5.3 Ordering

The order must not depend on dictionary insertion order or thread scheduling. Define a stable
key:

```text
(time, phase, priority, spatial_id, event_id)
```

Every source emits events with an explicit priority. Ties break on the spatial id and then on
the event id. The same key is used in serial and parallel execution. This is a hard contract,
not an implementation detail.

## 6. Randomness and reproducibility

Use a **counter-based random tape**, not a global RNG. Every primitive draw is a deterministic
function of:

```text
(scenario_seed, process_id, spatial_unit_id, year, draw_index)
```

A counter-based generator (the Philox or Threefry family, behind a small WS4 protocol) makes
the draw independent of call order and of how many draws another process made. The tape can
be generated on demand or cached for audit.

Consequences:

- **Replay is exact.** Same inputs, same seed, same event log.
- **Parallelism is deterministic.** Each site/process draws from its own stream; there is no
  order dependence across threads or processes.
- **Common random numbers (CRN).** Two candidate schedules see the same underlying draws.
  Differences between candidates are due to decisions, not noise. This is the single biggest
  variance-reduction lever for stochastic optimization.
- **Scenario ensembles are cheap to manage.** A scenario is a seed plus parameter and climate
  overrides; the tape can be generated on demand.
- **Audit is possible.** Record the scenario seed, process versions, parameter hashes, and the
  event log with every run.

Rules:

- No module-level `random` or `numpy.random` state in the process layer.
- Every source receives a tape handle, not a global generator.
- The run manifest records the tape specification and the package hashes.
- A replay validator re-runs the executor from the log's seed and compares the log.

This extends the existing reproducibility rule in `AGENTS.md` and the seed discipline in
`ws4/opt/repro.py`.

## 7. The ecosystem package

The compiled dataset is the management contract. Ecology belongs in an optional sidecar,
following the carbon-package precedent. The runtime composes the two; old datasets remain
valid.

### 7.1 Layout

```text
ecosystem/
  manifest.json
  state.yaml
  processes.yaml
  scenarios.yaml
  calibration/
  tapes/            (optional cached tape)
```

### 7.2 Manifest

The manifest is a closed schema. Required fields:

- `schema_version` — `ws4.ecosystem.v1`.
- `package_id` — producer-assigned identifier.
- `created_utc` — ISO-8601 timestamp.
- `producer` — name and version.
- `sources` — upstream path and SHA-256 records.
- `state_schema` — the state-variable definitions.
- `processes` — the process definitions.
- `scenarios` — the scenario definitions.
- `calibration` — parameter values and provenance.
- `table_files` — optional table-name to file-name map.
- `table_hashes` — optional per-table SHA-256 digests.

Unknown fields are rejected, so a typo cannot silently disable a check. Hashes are verified
when present. The package is independent of the dataset: a dataset can be paired with
different ecology packages, and a package can be reused across datasets with the same state
schema.

### 7.3 Tables

- `state_variables`: `name`, `dtype`, `unit`, `scope`, `default`, `description`.
- `cohorts`: `fragment_id`, `cohort_id`, `species`, `age`, `area_fraction`,
  `biomass_t_ha`, `fuel_t_ha`, `snag_t_ha`, `attributes_json`.
- `processes`: `process_id`, `type`, `params_json`, `state_reads`, `state_writes`,
  `time_model`, `seed_stream`.
- `scenarios`: `scenario_id`, `seed`, `weight`, `overrides_json`, `description`.
- `events`: `event_id`, `scenario_id`, `process_id`, `event_type`, `time`, `year`,
  `fragment_ids`, `site_ids`, `block_ids`, `severity_class`, `severity_value`, `area_ha`,
  `attributes_json`, `parent_event_id`, `source`, `confidence`.
- `bridges`: `bridge_id`, `type`, `params_json`, `state_reads`, `state_writes`.

The `events` table is compatible with the `femic.disturbance.v1` consumer row: the existing
loader can read the subset it knows, and the extra fields are ignored. That keeps the current
`ws4 disturbance` command working while the richer engine uses the full record.

### 7.4 Validation

The loader fails closed:

- unknown manifest fields;
- missing or duplicate ids;
- a process whose state reads/writes are not declared;
- a cohort fraction that is negative or a fragment whose fractions do not sum to one;
- a scenario with no seed;
- a table hash that does not match;
- an event that names an unknown fragment, site, or block;
- an event whose year is outside the horizon;
- a bridge that writes a state variable it does not declare.

A dataset without a package is valid and deterministic. That is the backward-compatibility
contract.

## 8. Process protocol and the fire vertical slice

### 8.1 Protocol

```text
Process:
    id
    state_reads
    state_writes
    events(state, context) -> sequence[Event]
    apply(state, event) -> StateDelta

DecisionSource:
    decisions(state, context) -> sequence[Event]
```

A process declares what it reads and writes. The executor can then check conflicts, order
processes, and cache state. A process that wants a new state variable must declare it in the
package schema; it cannot silently create one.

### 8.2 Fire

The first process is fire, because it is spatially explicit, visually compelling, and
already has a read-only event contract and a spread-connectivity account in ws4.

- **Ignition**: a Poisson process over eligible spatial units, with an optional spatial
  weight (fuel, lightning, human access).
- **Spread**: graph percolation over the landscape graph. The probability of crossing an edge
  is a function of fuel, wind, slope, distance, and any barrier. The tape supplies the fixed
  threshold; a change in fuel changes the probability, not the draw.
- **Severity**: a distribution conditional on fire size and intensity.
- **Effects**: cohort mortality, fuel consumption, snag creation, and a disturbance event.
- **Salvage**: a controlled source. It removes burned biomass, produces products, and writes a
  carbon disturbance event.
- **Accounts**: burned area, fire count, severity distribution, mortality, salvage volume, and
  risk.

The fire process is not a calibrated fire-behaviour model. It is a LANDIS-class process
skeleton with explicit parameters and a validation oracle. Calibration is a later phase.

### 8.3 Analytic oracles

The fire slice must be testable against something that can fail:

- Poisson ignition counts over many seeds;
- exponential waiting times between ignitions;
- bond percolation on a one-dimensional or square lattice with a known threshold;
- a barrier of non-fuel units that stops spread;
- area conservation: burned area plus unburned area equals the fragment area;
- carbon conservation through the fire and salvage events.

## 9. Accounts, disturbance, and carbon

The event log is the primary output. Accounts are views over state and events:

- **Disturbance accounts** aggregate events by type, year, severity, and area. They are
  compatible with the existing `femic.disturbance.v1` vocabulary.
- **Risk accounts** aggregate across scenarios: `risk.mean.*`, `risk.cvar.*`, `risk.p95.*`,
  `risk.prob.*`. They are ordinary account rows with a scenario dimension.
- **Carbon** consumes fire, salvage, and harvest events through the carbon package's
  disturbance map. `CarbonLedger` already consumes schedule events; it gains an ecosystem
  event source. The package's `event_source` field names the source, so the cross-repo
  contract stays explicit.

The account frame gains a `scenario` column. Existing code that ignores the column still sees
one scenario. Aggregation is a new step, not a new account type.

## 10. Coupling to the optimizer

The optimizer currently searches a schedule and evaluates it exactly, using per-block deltas
where accounts are additive. Stochastic processes break both additivity and locality. The
coupling has three levels.

### 10.1 Exogenous process overlay

If hazards and event outcomes do not depend on the schedule, precompute the event stream once
per scenario. The simulator applies exogenous events like treatments. Within a scenario the
evaluation is deterministic, and the existing incremental machinery largely works. This covers
weather-driven ignitions, climate forcing, and some wind and insect scenarios.

### 10.2 State-dependent processes with a fixed tape

Fire spread depends on fuel, which a harvest changes. Given a fixed tape, the simulation is
deterministic, but a local decision can change future hazards and event outcomes. The exact
delta is no longer local. Three techniques, in order of implementation:

- **Causal-cone deltas.** A move changes a set of cells; propagate the change through the
  space-time dependency graph until event outcomes stop changing or a budget is exceeded.
  Recompute only the cone; fall back to full re-simulation when the cone is large.
- **Memoized event trees.** Cache event decisions keyed by the relevant state signature and
  tape slice; reuse unchanged subtrees across candidate schedules.
- **Multi-fidelity evaluation.** Use the fast deterministic core for the inner search loop and
  the full stochastic engine for elites, feasibility checks, and final reporting. This matches
  the existing research note's rule to verify every elite against the exact evaluator.

The design note must be explicit about the boundary: exact deltas stop where a process makes a
non-additive, non-local transition. We do not pretend otherwise.

### 10.3 Adaptive decisions

The decision object becomes a **policy**:

```text
policy(state, time, forecast; parameters) -> sequence[Event]
```

A static schedule is a degenerate policy. A salvage rule, a green-up-triggered harvest rule, a
replanning rule after a fire, or a road-opening rule are all policies. The optimizer searches
the parameters. This is where stochastic optimization becomes genuinely different from
deterministic optimization, because the decision can respond to the realized world.

### 10.4 Objective and risk

The existing weighted goal programming is the right skeleton. Extend the account frame with a
`scenario` dimension and give targets an aggregation:

```text
aggregation: mean | cvar | quantile | probability | min | max | regret
```

Risk measures become pseudo-accounts (`risk.cvar.volume`, `risk.prob.shortfall`,
`risk.p95.burned_area`) and flow through the existing `Target`, penalty, normalization, and
priority machinery in `ws4/opt/objective.py`. That is a small, clean change with large
expressive power.

A zero-variance ensemble must reproduce the deterministic objective exactly. That is the
compatibility test that keeps the extension honest.

## 11. The full stochastic optimization ladder

"Stochastic optimization" means several different things. It helps to name the rungs:

| Rung | Problem | Method | When |
| --- | --- | --- | --- |
| 0 | Deterministic schedule | Current metaheuristic and exact deltas | Baseline and fast exploration |
| 1 | Scenario-conditioned schedule | Optimize separately per scenario; compare | Stress testing and bounds |
| 2 | Expected-value schedule | Sample average approximation with CRN | First true stochastic optimization |
| 3 | Risk-averse schedule | Mean-CVaR, chance constraints, quantile targets | When shortfall tails matter |
| 4 | Two-stage plan and recourse | Stochastic MIP, Benders, or progressive hedging for small instances; scenario subproblems for large | Plan now, adapt later |
| 5 | Adaptive policy | Approximate dynamic programming, policy search, reinforcement learning | When decisions can respond to events |
| 6 | Distributionally robust or Bayesian | Ambiguity sets, posterior predictive, value of information | When process parameters are deeply uncertain |

All rungs share the same simulator, event log, accounts, and objective. The difference is the
evaluation backend and the decision representation, not a fork in the software.

## 12. Phase plan and task map

P144 is the design and first vertical slice. It is deliberately narrow.

- **P144.1** — this note and its contracts (#853).
- **P144.2** — event record, counter-based tape, event log, and replay validator (#854).
- **P144.3** — `ws4.ecosystem.v1` package, state schema, cohort fractions, and the null bridge
  (#855).
- **P144.4** — fire ignition, spread, severity, mortality, salvage, and disturbance accounts
  (#856).
- **P144.5** — scenario ensembles, common random numbers, risk-aggregated targets, and the SAA
  loop (#857).
- **P144.6** — verification, documentation, and close-out (#858).

Later candidate phases, not commitments:

- succession and regeneration with a calibrated yield bridge;
- wind, insects, drought, disease, and process interactions;
- continuous-time event scheduling and a raster site layer;
- policy search and two-stage stochastic programming;
- external-engine adapters for LANDIS-II, SpaDES, and SELES behind the same protocol;
- causal-cone deltas, GPU ensemble evaluation, and surrogate models at scale.

## 13. Validation oracles

A capability without a validator that can fail is not a capability. The phase uses:

- **Replay determinism**: same inputs and seed produce an identical event log.
- **Common random numbers**: a no-op change leaves the tape and outcomes unchanged; two
  candidates share the underlying draws.
- **Conservation**: area, cohort fractions, and carbon balance across events.
- **Analytic oracles**: Poisson counts, exponential waiting times, and percolation thresholds.
- **Cross-engine behaviour**: reproduce a published landscape-model benchmark at the level of
  a pattern or distribution, not code-level identity.
- **Out-of-sample search**: optimize on a training scenario set and report held-out
  performance separately.
- **Zero-variance identity**: a degenerate ensemble reproduces the deterministic result.
- **Performance budgets**: record the event count, wall time, and memory for the synthetic
  landscape and a larger instance.

## 14. Risks, open questions, and non-goals

### Risks

- **Scope creep.** The ecology programme is multi-year. P144 must stay at one process and one
  vertical slice.
- **Yield-bridge underspecification.** Species biomass to merchantable volume is a modelling
  decision. It must be explicit, versioned, and calibrated later.
- **Cost.** Stochastic simulation times optimization is expensive. CRN, causal cones,
  memoization, multi-fidelity, and GPU ensembles are required at scale.
- **Model risk.** "Stochastic" does not mean "more true." Structural uncertainty often
  dominates parametric uncertainty. The framework must represent both.
- **Provenance.** Third-party models and data are cited as concepts and benchmarks, never
  copied into tracked files, per `AGENTS.md`.
- **Semantic drift.** Every process declares its time model, spatial scope, state reads and
  writes, and effect kernel. Otherwise the framework becomes a pile of special cases.

### Open questions

- Is the cohort/fraction model sufficient for the first fire slice, or is a site layer needed
  immediately?
- Which bridge is the reference: a species-mix track selector, a biomass-to-volume curve, or
  both?
- How large a scenario ensemble is affordable inside the optimizer, and where does the
  multi-fidelity boundary sit?
- Does the first risk target use CVaR, a quantile, or a chance constraint?
- Which external benchmark is both public and usable under the repository's provenance rule?

### Non-goals

- A code-level clone of LANDIS-II, SpaDES, or SELES.
- A full multi-process ecology in P144.
- A production calibration of ecological parameters.
- A replacement for the compiled management dataset.
- A raster-only or continuous-time-only model.

## 15. References

WS4 pages and code this design extends:

- `AGENTS.md` — the working contract, reproducibility, and provenance rules.
- `notes/design/ws4-architecture.md` — the current system architecture.
- `notes/adr/0004-goal-programming-metaheuristic.md` — the optimization choice.
- `notes/adr/0005-annual-simulation-step.md` — the annual accounting step.
- `docs/concepts/the-simulation.rst` — the annual simulation contract.
- `docs/reference/compiled-dataset.rst` — the runtime dataset contract.
- `docs/reference/disturbance.rst` — the existing disturbance consumer.
- `docs/reference/carbon.rst` — the package-and-engine precedent.
- `ws4/sim/engine.py` — the annual executor and treatment application.
- `ws4/opt/engine.py` — the optimizer and incremental evaluation.
- `ws4/opt/objective.py` — targets, penalties, and flow semantics.
- `ws4/disturbance.py` — the event vocabulary seed.
- `ws4/patch/` and `ws4/spread/` — the topology and spread substrates.
- `ws4/carbon/` — the external-engine protocol and package loader.
