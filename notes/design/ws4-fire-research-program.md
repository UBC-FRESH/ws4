# WS4 fire-regime research program

Status: one-paper program, revised 2026-11-23 after adversarial review

## Decision

The four-draft portfolio is retired. The project will produce **one canonical paper** and **one
reproducibility archive**. The canonical paper is an open integration and negative-diagnostic study,
not a validated forecast, a fire-aware optimization, or a benchmark.

Canonical repository: `UBC-FRESH/fresh_ws4_fire_regime_manuscript`.

Working title: *An open, auditable fire-regime layer for forest estate risk: integration and
negative calibration, transfer, and event diagnostics on TSA24.*

Target: *Environmental Modelling & Software*; backup *Geoscientific Model Development*.

## What the paper may claim

| Claim | Status |
| --- | --- |
| Open, inspectable integration of FBP growth, reduced-form suppression, LANDIS succession, estate accounting, and estate-scale evaluation | Supported as software and methods |
| Compiled TSA24 data path | Supported for the 133 full-estate layers and compact results |
| Global calibration | Pre-registered no-go; training and validation gates failed |
| Regional calibration | In-sample fit only |
| Training-only transfer | Negative; ranking uncertain |
| Event reconstruction | Negative; in-sample, not independent |
| Five-seed risk and five-year fixed-schedule cases | Computational demonstrations |
| Fire-aware optimization | **Not supported** |
| Global optimum | **Not supported** |
| TSA24 external benchmark | **Not supported** |
| Operational forecast | **Not supported** |

## What the paper must not claim

- Independent validation or held-out regional calibration.
- Fire-aware optimization or a process-coupled optimization objective.
- Global or near-global optimality.
- A TSA24 external benchmark; Dogrib is one fire, and FireSTARR TSA24 failed.
- Operational suppression or forecast skill.
- Open data end-to-end while the archive is private and frozen inputs remain.

## Evidence base

- 133 full-estate layer tiles, 720 potential fires, 23 tile calibrations, 11 validation tiles.
- 3,450 realizations from 690 potential fires; five realizations are not independent.
- 10 in-sample point-ignition reconstructions; 8/10 areas occur in calibration histories.
- Five-seed full-layer risk ensemble.
- Five-year fixed-schedule estate case.
- 112-tile, 2,240-block harvest feasibility search; fire-blind schedule identical.
- One Dogrib growth check; FireSTARR TSA24 SIGFPE failure.

## Remaining work before submission

1. **Independent validation.** Refit the regional map with every event and validation year excluded,
   freeze it, and evaluate on genuinely unseen tiles/years. Until this exists, the event result stays
   in-sample.
2. **Multi-year weather.** Replace the 2023-only potential sample with multi-year weather drawn
   from 1980--2024 (or the full perimeter period) and rerun calibration/transfer. Treat the current
   regional fit as a 2023-weather-year fit until this is done.
3. **Support map.** Derive it from block geometry and regenerate the 24 named calibration layers from
   raw; document the 198,564 representative-cell assignments.
4. **Archive.** Publish with DOI, licence sign-off, environment lock, clean-host run, data dictionary,
   and known-failure table. The current archive is private and partial.
5. **Statistics.** Bootstrap and paired intervals for all comparisons; report sensitivity to the
   420-day event records, G40324, 30-day versus 90-day caps, and score weights.
6. **External benchmark.** Get a working TSA24 FireSTARR, FSim, BurnP3+, or Cell2Fire comparison, or
   keep the explicit no-benchmark boundary.
7. **Optimization.** If a separate optimization paper is ever revived, add a fire-risk objective and
   a near-global baseline and show the schedule changes.
8. **Submission package.** Final author list, funding, data-provider credit, target-journal format,
   and figure/table audit.

## Gates

- **No submission** while the paper uses the word "independent" for the event reconstruction.
- **No submission** while the regional map is described as held-out or transferred.
- **No submission** while the optimizer is described as fire-aware or global.
- **No submission** while the archive is private if the paper claims open reproducibility.
- **No separate paper** unless it answers a distinct question with independent evidence.

## Immediate next action

Finish the single canonical paper and the honest archive boundary. The next scientific work is a
genuine independent refit, not more manuscript splitting.
