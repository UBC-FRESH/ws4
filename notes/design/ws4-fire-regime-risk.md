# Fire-regime risk summaries

Status: implemented (P188)
Phase: P188 (#1114)
Date: 2026-11-13
Related: `notes/design/ws4-fire-regime-benchmarks.md`, `ws4/fire/risk.py`

## 1. Purpose

P187 implements the scfm fire-regime formulas as a distributional benchmark. P188 turns those
formulas into a reusable risk summary over simulated fire events. The summary is the handoff
from process runs to risk reporting: it reports what the fire regime did, not whether one
observed perimeter matched.

## 2. Inputs

The summary reads event-log-like records structurally, using only:

- `year`;
- `event_type`;
- `area_ha`;
- `metadata.scenario_id`.

The fire package therefore does not import the ecosystem package. A real
`ws4.ecosystem.log.EventLog` and `ws4.ecosystem.events.Event` satisfy the protocols.

Only `event_type == "fire"` records contribute. A fire event without `area_ha` is an error,
not a silent zero.

## 3. Outputs

`FireRegimeRiskSummary` reports:

- one annual record per year: burned area, fire count, escaped count, and sizes;
- total, mean, median, 90th-percentile, and maximum annual burned area;
- burn probability;
- annual burn rate;
- fire return interval;
- total and escaped fire counts;
- escaped fires per year;
- mean, median, 90th-percentile, and maximum fire size;
- optional P187 target diagnostics.

`fire_return_interval_years` is `None` when nothing burned, so JSON output stays strict.
Quantiles use linear interpolation over the sorted sample.

## 4. Target diagnostics

When both a `FireRegimeParameters` target and the historical size sample are supplied, the
summary calls `fire_regime_diagnostics` from P187. The target supplies ignition rate, escape
probability, and empirical burn rate; the historical sample supplies the size distribution.

The diagnostic FRI follows scfm and uses escaped fires only. The summary-level FRI uses all
burned area. The two are reported side by side, not conflated.

## 5. Exact test values

`tests/test_fire_risk.py` uses four years, 1000 ha burnable, 10 ha cells, and fire sizes
5, 20, 100, 1, and 2 ha:

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

With a target ignition rate of 0.002/ha/year, escape probability 0.5, empirical burn rate
0.02, and historical sizes 5, 50, 100 ha, the diagnostics report target ignitions 2/year,
achieved ignitions 1.25/year, target escapes 1/year, achieved escapes 0.5/year, model mean
60 ha, historical mean/median 75 ha, achieved escaped FRI 33.33 years, and target FRI
50 years.

## 6. Limits

- The summary is deterministic given the event records.
- It does not simulate fire growth, calibrate the fire model, or compare perimeters.
- It does not replace the P181 account-overlay risk path.
- LandMine FRI/reburn invariants remain a follow-up.
- The target diagnostics require a historical size sample; there is no implicit calibration.
