# P178 free-burn weather ensemble

Date: 2026-11-11
Phase: P178 (#1051)
Task: P178.2 (#1053)
Manifest: `notes/reports/p178-freeburn-ensemble.json`
CSV: `notes/reports/p178-freeburn-ensemble.csv`

## Result

Four large free-burn cases, five weather members each (20 runs):

| Case | Area bias | IoU | Time to observed area |
| --- | ---: | ---: | ---: |
| 2003_96 | 4.119x | 0.192 | 3,540–9,000 min |
| 2003_663 | 1.665x | 0.350 | 2,280–4,320 min |
| 2023_331 | 2.146x | 0.265 | 6,480–13,080 min |
| 2023_366 | 3.639x | 0.211 | 1,560–4,920 min |

All members produce the same final area and IoU per case. Wind ±20% and RH ±10 points produce
**zero spread** in final extent but move the time to observed area by **2,040–6,600 minutes**
within a case.

## Interpretation

The free-burn ensemble is degenerate because the model fills the burnable basin. Weather
perturbations change timing, not final extent. The timing endpoint now makes that statement
explicit: the first time at or above observed area varies within every case while final area and
IoU do not. The ensemble cannot provide a meaningful
uncertainty range until a stopping/containment mechanism or burnable-area constraint is added.

This also confirms the P176 diagnosis: the dominant limitation is basin filling, not weather
uncertainty.

## Decision

Do not use this ensemble as a risk distribution. Add containment/stopping or a defensible
burnable-area constraint before ensemble risk work. P164.3 remains paused.
