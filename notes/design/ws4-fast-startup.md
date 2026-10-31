# P84: Fast Model II startup via spliced track trajectories

Status: active
Phase: P84
Issue: #613
Date: 2026-10-31

## Problem

WS4 rebuilds and re-simulates block-level state at startup:

- `Optimizer.candidates()` regenerates the treatment graph;
- the exact evaluator steps blocks through the simulator;
- the watcher needs a seeded 208k-block reset before its first move.

This is a **Model II execution** problem. WS4 already compiles a Model II dataset:
strata, tracks, treatments, transitions, curves, features, and products. The defect is that
the runtime does not execute that compiled Model II graph directly. It re-simulates blocks.

Patchworks keeps **precompiled track state trajectories** and builds a block trajectory by
**splicing track segments at treatment event boundaries**, using time offsets from age 0 on
each track. Its SA scheduler can start from a blank block schedule immediately because
evaluating a block is a slice/splice operation, not a simulator run.

## Architecture target

```text
compiled dataset
  + precompiled track trajectories (features, accounts, product events by track/age)
  + transition/event index
  -> block trajectory = a small timeline of splice offsets
  -> at any horizon offset: binary-search the timeline, add the
     track-relative age, and read the track/age value vector
  -> schedule = one candidate option index per block
  -> SA starts blank and mutates indices
  -> exact replay only at checkpoints/final output

Do **not** precompute all possible splice combinations. The combinatorial object is the
per-block schedule, not the state. The state is a track-by-relative-age value array plus a
transition/event table.
```

## Definitions

For each track `t`:

- `state_t(age)` — the precomputed feature/account state at age `age` from the track's
  age-0 origin.
- `event_t(treatment, age)` — the precomputed product/yield emitted when a treatment is
  applied at `age`.
- `transition_t(treatment)` — `new_track`, `reset_age`.

A block's candidate chain is a sequence of `(track, treatment, event_year, reset_age)`
segments. The block trajectory is the concatenation of `state_t` over each segment, plus
the event yields, with the block's area multiplying every cell.

## Work packages

### P84.1 Track/age value arrays and splice index

- Build one value vector per track and relative age for all active account cells.
- Build per-track treatment-event yields and transitions.
- Build a per-block timeline of `(horizon_offset, track, age_at_splice)` segments.
- At runtime, binary-search the timeline and read `track_values[track, relative_age]`.
- Persist the track/age arrays and transition/event tables; do not persist candidate
  combinations.
- Acceptance: c5 sample splice lookup reproduces the current exact evaluator for every
  track/age and event cell used by the targets.

### P84.2 Spliced block evaluation

- Implement block evaluation as segment slicing and concatenation.
- Compare spliced cells/objective against `IncrementalObjective` on random c5 schedules.
- Keep exact mismatches visible; no tolerance hidden in the spliced path.
- Acceptance: exact objective equality on the c5 sample for generated schedules.

### P84.3 Candidate/transition index

- Replace runtime candidate generation with a compact transition index loaded from the
  compiled artifact.
- Represent a schedule as one candidate option index per block.
- Candidate timelines are small offset/track sequences; they are not state vectors.
- Acceptance: c5 watcher loads candidates without calling `Optimizer.candidates()`.

### P84.4 Blank-schedule SA and watcher

- Start SA from a blank schedule; no seeded categorical reset.
- Use spliced objective increments for search; exact replay at checkpoints/final.
- Make the watcher load the resident substrate once.
- Acceptance: c5 startup breakdown and first frame recorded; no TSA24/29 acceptance run.

## Non-goals

- No TSA24/29 large-model acceptance run in this phase.
- No change to target semantics or exactness.
- No claim of parity with Patchworks until c5 splicing is exact and measured.

## Baseline

Current c5 sample `watch --iterations 1 --plain` is ~6.0 s wall, with candidate generation
~3.2 s and ~1.4M candidate chains. The target is to eliminate both candidate generation and
the full categorical seed reset from startup.
