# P162 calibration sensitivity

Date: 2026-11-10
Phase: P162 (Calibration sensitivity diagnostic)
Tasks: P162.1 (#962), P162.2 (#963)
Protocol: `notes/design/ws4-fire-calibration-protocol.md`

## Question

Do the P161 multipliers change the Hay River result when the comparison window is short enough
to avoid final-domain saturation?

## Fixed matrix

Windows:

| Window | Duration | Observed perimeter |
| --- | ---: | --- |
| day-1 | 660 min | 14 May 23:00, 29 ha |
| day-3 | 3,540 min | 16 May 23:00, 832 ha |
| full | 9,360 min | 20 May 23:00, 2,987 ha |

Parameter points:

- baseline `1.00, 1.00`
- low `0.70, 0.50`
- high `1.30, 1.50`

## Results

| Window | Point | Area (ha) | Observed (ha) | Area bias | Perimeter bias | IoU | Sorensen | Centroid (km) | Orientation | Score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| day-1 | baseline | 10,189 | 29 | +35,034% | +1,609% | 0.003 | 0.006 | 3.42 | 28.8° | 90.53 |
| day-1 | low | 2,692 | 29 | +9,183% | +403% | 0.011 | 0.021 | 1.44 | 39.6° | 24.01 |
| day-1 | high | 10,846 | 29 | +37,300% | +1,737% | 0.003 | 0.005 | 3.35 | 33.8° | 96.39 |
| day-3 | baseline | 10,846 | 832 | +1,204% | +283% | 0.077 | 0.142 | 2.27 | 52.2° | 3.894 |
| day-3 | low | 10,594 | 832 | +1,173% | +282% | 0.079 | 0.146 | 2.17 | 51.1° | 3.813 |
| day-3 | high | 10,846 | 832 | +1,204% | +283% | 0.077 | 0.142 | 2.27 | 52.2° | 3.894 |
| full | baseline | 10,846 | 2,987 | +263% | +223% | 0.275 | 0.431 | 1.43 | 27.6° | 1.344 |
| full | low | 10,846 | 2,987 | +263% | +223% | 0.275 | 0.431 | 1.43 | 27.6° | 1.344 |
| full | high | 10,846 | 2,987 | +263% | +223% | 0.275 | 0.431 | 1.43 | 27.6° | 1.344 |

## Sensitivity summary

| Window | Unique results | Sensitive? | Area range (ha) | IoU range |
| --- | ---: | --- | ---: | ---: |
| day-1 | 3 | yes | 2,692–10,846 | 0.003–0.011 |
| day-3 | 2 | yes | 10,594–10,846 | 0.077–0.079 |
| full | 1 | no | 10,846 | 0.275 |

Sensitivity exists, but only because the model is so far above the observed daily growth. At
the low bound, day-1 still overpredicts by roughly 93× and day-3 by roughly 13×. The
full-event comparison is saturated by the 131 × 117 domain.

## Interpretation

The Hay River fixture is not a viable calibration case for the current model and bounds:

- the observed day-1 perimeter is 29 ha while the lowest parameter point is 2,692 ha;
- the observed day-3 perimeter is 832 ha while the lowest parameter point is 10,594 ha;
- the model fills the full 10,846-cell burnable domain by day 3 at every point;
- the multipliers move the score, but not toward the observations.

The likely causes are structural, not a narrow parameter miss: point ignition at the first
satellite detection, no suppression, satellite-derived daily timing, and a small buffer domain.
A calibration fit cannot repair those with two global multipliers inside the registered box.

P162 therefore closes as a **no-go for calibration** even though the short windows are
parameter-sensitive. Do not start a new fit on this case.

## Limits

- One fire, one satellite-derived progression, one fuel/terrain subset.
- No suppression, spotting, or hourly BUI.
- The day windows use satellite-derived cumulative perimeters, not agency hourly perimeters.
- The low/high points are protocol diagnostic points, not a fitted set.
- No operational or regional claim.
