# P188 close-out: fire-regime risk summaries

Date: 2026-11-13
Phase: P188 (#1114)
Branch: `feature/p188-fire-regime-risk`
Tasks: P188.1 (#1115), P188.2 (#1116), P188.3 (#1117), P188.4 (#1118)
Design note: `notes/design/ws4-fire-regime-risk.md`

## Result

Fire events can now be summarized as a deterministic risk distribution. The summary reports
annual burned area, burn probability, fire return interval, escaped-fire frequency, and fire
size quantiles, and can attach the P187 target diagnostics.

## What changed

- `ws4/fire/risk.py`:
  - event-log-like protocols without an ecosystem import;
  - fire-event extraction with area validation;
  - annual records and aggregate risk metrics;
  - linear-interpolated quantiles;
  - optional target diagnostics from P187.
- Exact synthetic event-log tests, including target diagnostics and invalid inputs.
- API exports, reference page, design note, and benchmark-registry status.

## Evidence

- Fire-risk tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Synthetic case: 4 years, 1000 ha, 10 ha cells, sizes 5, 20, 100, 1, and 2 ha.
  - total burned 128 ha;
  - mean annual burned 32 ha;
  - median annual burned 14 ha;
  - 90th-percentile annual burned 77.5 ha;
  - burn probability 0.75;
  - annual burn rate 0.032;
  - FRI 31.25 years;
  - mean fire size 25.6 ha;
  - median fire size 5 ha;
  - 90th-percentile fire size 68 ha;
  - escaped fires 2, or 0.5 per year.
- Target diagnostics: target ignitions 2/year, achieved 1.25/year; target escapes 1/year,
  achieved 0.5/year; model mean 60 ha; historical mean/median 75 ha; achieved escaped FRI
  33.33 years; target FRI 50 years.

## Boundary

The summary-level FRI uses all burned area. The P187 diagnostic FRI follows scfm and uses
escaped fires only. The two are reported separately.

This is a deterministic event summary. It is not a fire-growth simulation, a calibration, or
an observed-perimeter comparison. It does not replace the P181 account-overlay risk path.

## Limits

- No implicit calibration: target diagnostics need an explicit historical size sample.
- LandMine FRI/reburn invariants remain a follow-up.
- The process ensemble is not yet wired to management yield curves or the optimizer.

## Next

Use the summary in the process-ensemble report, then compare a short landscape trajectory
against an available LBSE-style reference. The R/SpaDES runtime is not installed here, so that
comparison remains blocked without a reference run or published numeric landscape output.

## Pull request

Merged as `80ffe40` (PR #1119); branch deleted.
