# Process-ensemble fire-regime report

Status: implemented (P212)
Phase: P212 (#1232)
Date: 2026-11-14
Related: `notes/design/ws4-fire-regime-risk.md`,
`docs/reference/ecosystem-ensemble.rst`

## 1. Purpose

P188 summarizes fire events as a risk distribution. P212 connects that summary to the
process-driven ensemble: each scenario's replayable event log is summarized, and the result is
available per scenario.

The fire-regime layer remains distributional; it is not an event-perimeter comparison.

## 2. API

`ProcessEnsembleResult.fire_regime_summaries` takes:

- simulation years;
- burnable area;
- cell size;
- optional P188 target regime and historical sizes.

It returns a mapping of scenario id to `FireRegimeRiskSummary`.

## 3. Evidence

`tests/test_ecosystem_ensemble.py` runs a real two-scenario process ensemble and checks:

- both scenario keys are present;
- each summary's total burned area equals the scenario's summed annual
  `fire.burned_area_ha`;
- each summary is JSON-ready with schema `ws4.fire-regime-risk.v1`;
- a zero-fire ensemble produces zero fires and no fire return interval.

## 4. Layer boundary

- This is a distributional report over process events.
- It does not validate observed perimeters.
- It does not calibrate the fire model.
- The P181 account-overlay risk path remains separate.

## 5. Limits

- The event sizes are process events, not independent fire perimeters.
- Targets are optional and require an explicit historical sample.
- The summary inherits the P188 quantile and FRI definitions.
