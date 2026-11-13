# P187 close-out: scfm fire-regime benchmarks

Date: 2026-11-13
Phase: P187 (#1107)
Branch: `feature/p187-fire-regime-benchmarks`
Tasks: P187.1 (#1108), P187.2 (#1109), P187.3 (#1110), P187.4 (#1111)
Design note: `notes/design/ws4-fire-regime-benchmarks.md`

## Result

The scfm fire-regime parameter and diagnostic formulas are implemented in original Python
and reproduce the published toy values.

## What changed

- `ws4/fire/regime.py`:
  - ignition rate, escape probability, escaped-size statistics, empirical burn rate,
    per-pixel ignition probability, max burn cells;
  - target/achieved ignitions and escapes, mean/median size, and FRI diagnostics.
- Exact toy-regime and toy-diagnostics tests from scfm.
- API exports, docs, design note.

## Evidence

- Fire-regime tests: 4 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Toy polygon: ignition rate 4/(10×1125), escape probability 0.5, mean escaped size 75 ha,
  max burn cells 12.
- Toy diagnostics: target ignitions 1/year, achieved 1.5/year, target escapes 0.5/year,
  achieved 1/year, model mean 75 ha, historical mean/median 30 ha, achieved FRI 33.33 years,
  target FRI 100 years.

## Layer

This is a **distributional** benchmark. It does not simulate spatial fire growth and is not an
event-perimeter comparison.

## Limits

- No R/SpaDES runtime dependency.
- Only scfm formulas are implemented.
- LandMine FRI/reburn invariants remain a documented follow-up.
- The benchmark is separate from the P156 FBP growth kernel and P157 perimeter validation.

## Next

Add LandMine FRI/reburn invariants if a defensible landscape input is available, then connect
fire-regime distributions to scenario risk summaries.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
