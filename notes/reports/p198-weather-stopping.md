# P198 weather-conditioned stopping diagnostic

Date: 2026-11-14
Phase: P198 (#1168)
Tasks: P198.1 (#1169), P198.2 (#1170), P198.3 (#1171)
Branch: `feature/p198-weather-stopping`
Artifact: `notes/reports/p198-gated-ensemble.json`
CSV: `notes/reports/p198-gated-ensemble.csv`

## Question

P178 found zero final area and IoU spread across five weather members because the four large
free-burn cases fill the burnable basin. Does a documented, non-oracle weather-step stopping gate
make final extent weather-sensitive?

## Gate

The existing `BurningConditions` contract is applied uniformly to every case and member:

- ISI greater than 8
- wind greater than 5 km/h
- relative humidity less than 50 percent

Source: P160 Dogrib/Prometheus diagnostic thresholds. The gate is not calibrated. It is a
sensitivity mechanism, not an operational threshold.

## Result

| Case | Area bias | IoU | Time to observed area |
| --- | ---: | ---: | ---: |
| 2003_96 | 0.435–4.119 | 0.067–0.274 | 15,840–23,460 min (one member never reached) |
| 2003_663 | 1.636–1.665 | 0.350–0.353 | 3,360–12,000 min |
| 2023_331 | 1.187–2.146 | 0.265–0.374 | 10,320–32,220 min |
| 2023_366 | 0.779–3.639 | 0.211–0.440 | 1,620–21,840 min |

The ungated P178 ensemble had identical area and IoU within every case. The gated ensemble does
not: final area and IoU vary in all four cases, strongly in three and only slightly in `2003_663`.

## Decision

**Go** for weather-conditioned stopping as a sensitivity lever. The gate breaks the zero-spread
degeneracy and is not an oracle on the observed perimeter.

**No-go** for this gate as an operational or calibrated threshold. The Dogrib/Prometheus values are
applied uniformly to four different cases; `2003_663` is nearly insensitive, and one `2003_96`
member never reaches the observed area. This is not a suppression or containment prediction.

## Limits

- One uniform threshold set across four cases.
- Reanalysis weather and daily perimeters.
- No calibration to observed area.
- No dynamic containment, firebreak or suppression model.
- A non-zero spread does not imply forecast skill.

## Next

Do not tune this threshold to the four cases. The next defensible step is a case-specific or
physically justified stopping model, or a real containment/firebreak scenario, with a no-go option.
