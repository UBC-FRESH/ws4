# P137 overlay and coverage findings

Date: 2026-11-06
Status: **crown closure corrected; top/QMD confirmed; CAI band pending**

Crown closure is now a straight log-log line fitted from the source label angle
and the dotted source path. The top-height and QMD curves are confirmed by the
diagram tests and the corrected overlays; the earlier count mismatch was caused by
text extraction missing rotated labels. TASS is excluded because the source does
not label mortality levels. The CAI band is still not represented.

## Top-height/QMD count audit

Printed labels vs stored curve counts:

| Diagram | Top height printed/stored | QMD printed/stored |
| --- | --- | --- |
| `fdcn` | 11 / 11 | 10 / 10 |
| `fdcp` | 10 / 10 | 9 / 10 |
| `ssn` | 8 / 10 | 10 / 11 |
| `ssp` | 5 / 7 | 8 / 10 |
| `hwn` | 11 / 12 | 10 / 10 |
| `hwp` | 6 / 10 | 9 / 9 |
| `cwn` | 11 / 11 | 10 / 11 |
| `cwp` | 7 / 11 | 10 / 10 |
| `swn` | 9 / 9 | 6 / 9 |
| `swp` | 9 / 9 | 8 / 8 |

The apparent missing/extra top-height/QMD curves were a label-extraction artifact.
The stored curves are present and align with the source in the corrected overlays.

## TASS predicted mortality curves

The source TASS curves are plotted but **not labelled with mortality levels**.
Without a level, they cannot be stored as quantitative curves. Policy: explicitly
exclude them with a named source limitation. Do not add a `tass_mortality` schema
kind.

Consequence: the extra curves currently classified as top-height/QMD are likely
TASS paths. They must be removed and the printed-label counts rechecked.

## CAI density-range band

The grey "Density Range for Maximizing CAI" region is labelled as a region but has
no numeric level. Treat it as a display-only `cai_range` polygon if it can be
extracted cleanly; otherwise record a named refusal. It is not a quantitative
curve and cannot feed constraints.

## Crown closure

The raster-traced `crown_closure` curve was replaced with a straight log-log line
fitted from the source label angle and the dotted source line. It now follows the
source crown-closure line.

## Verdict

The 10 diagrams now have a straight crown-closure line that follows the source;
top/QMD curves align. TASS is explicitly excluded. The remaining gap is the grey
CAI band; it needs a display-only representation or a named refusal. Do not sign
off until that is decided.
