# Regime-scale fire calibration protocol

Phase identifier: P164.8

Parent phase: #977

Task issue: #1421

Status: proposed; no calibration result exists yet

Branch: `feature/p164.8-regime-calibration`

## 1. Purpose

Pre-register a reproducible TSA24 fire-regime calibration with a fixed train/validation split,
a fixed parameter set, explicit acceptance gates, and a no-go rule.

This protocol replaces the exploratory 24-tile work. None of the exploratory numbers are
accepted calibration evidence.

## 2. Scope

In scope:

- real VRI fuel/crown, SRTM terrain, and water-edge layers at 250 m;
- a 10-hour active spread day;
- 90-day antecedent weather for FWI spin-up;
- relative suppression of potential fire size;
- 24 fixed 30 km tiles;
- event-size distribution metrics;
- deterministic seeds and manifests.

Out of scope:

- full TSA24 real-layer coverage;
- burn-probability skill scores (P164.3);
- treatment effects (P164.4);
- operational validation claims;
- changes to the FBP kernel.

## 3. Fixed tile split

Training tiles: `t01`–`t12`.

Validation tiles: `t13`–`t24`.

`t24` has no historical perimeter sample and is excluded from size metrics. The effective
validation set is `t13`–`t23` (11 tiles). This is declared before fitting; it will not be
changed after results are seen.

## 4. Fixed data inputs

- VRI fuel, crown closure, conifer fraction, water, and wet edges.
- SRTM slope, aspect, and elevation.
- Historical BC Wildfire perimeters clipped to each tile, 1950–2024.
- Historical fire dates for tail events.
- Open-Meteo historical weather, with 90 days before the event for FWI spin-up.
- 10 active spread hours per day.
- 30 fires per tile for the potential sample.
- All stochastic seeds fixed and recorded.

No post-hoc changes to the tile split, weather source, active hours, or metrics.

## 5. Model parameters

Only the following parameters are fitted:

| Parameter | Symbol | Bounds |
| --- | --- | ---: |
| Contained retained fraction, median | `contained_fraction_median` | 1e-5–0.01 |
| Contained fraction log-sigma | `contained_fraction_sigma` | 0.3–1.5 |
| Escaped retained fraction, median | `escaped_fraction_median` | 0.01–1.0 |
| Escaped fraction log-sigma | `escaped_fraction_sigma` | 0.05–0.6 |
| Escape cap | `escape_cap_ha` | 5,000–30,000 |
| Escape hazard intercept | `intercept` | -7.0 to -3.0 |

Fixed values:

- active hours per day: `10`
- antecedent FWI window: `90 days`
- duration weight: `0.5`
- FWI weight: `0.2`
- BUI weight: `0.1`
- wind weight: `0.1`
- minimum area: `6.25 ha`

No per-fire parameter and no validation-tile tuning are allowed.

## 6. Search

A deterministic random search of 1,500 parameter sets is evaluated on the training tiles only.
The random seed is fixed before the search. The search is repeated only if the harness or input
data changes, and any repeat is reported as a new run.

Candidate scores are computed from the training event-size distribution. The best candidate is
frozen and applied to the validation tiles exactly once.

## 7. Metrics and gates

Primary metrics:

- median
- p90
- p95
- fraction over 100 ha
- fraction over 500 ha
- fraction over 1,000 ha
- fraction over 5,000 ha
- maximum

Training and validation must both satisfy:

| Metric | Gate |
| --- | --- |
| median | 20–30 ha |
| p90 | 350–700 ha |
| over 100 ha | 20–30% |
| over 500 ha | 6–12% |
| over 1,000 ha | 4–9% |
| over 5,000 ha | 1–4% |
| maximum | ≥ 10,000 ha |

The objective may be used to rank training candidates, but it cannot relax these gates.

## 8. Decision rule

- **Supported:** both training and validation satisfy every gate.
- **Calibration-only:** training passes but validation fails; no transfer claim.
- **No-go:** training fails, or the harness cannot reproduce the fixed inputs.

A no-go is a complete result. Do not retune on validation tiles.

## 9. Artifacts

- `scripts/fire_regime/` harness and tests.
- `notes/design/ws4-regime-calibration-protocol.md` (this file).
- A manifest with source, date span, seed, and hashes.
- Training and validation CSV/JSON.
- A report with both tables and the verdict.
- Dashboard result.

Large cached data lives under the work disk, not `/tmp`, and is not tracked.

## 10. Approval gate

This protocol is committed and reviewed before any fitting. The implementation starts only after
explicit approval. No merge, tag, release, or settings change without maintainer approval.
