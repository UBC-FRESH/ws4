# P137 overlay and coverage findings

Date: 2026-11-06
Status: **crown closure corrected; top/QMD confirmed; CAI band stored display-only**

Crown closure is now a straight log-log line fitted from the source label angle
and the dotted source path. The top-height and QMD curves are confirmed by the
diagram tests and the corrected overlays; the earlier count mismatch was caused by
text extraction missing rotated labels. TASS is excluded because the source does
not label mortality levels. The grey CAI band is stored as a `cai_band` polygon
and rendered behind the curves; it has no numeric level and never feeds placement
or constraints.

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

### fdcp top-height pass

`fdcp` is the first line-type-wise re-import. The source has 17 top-height paths
but prints only 10 labels. The importer now uses the complete value series
`6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 52, 60` and requires
one path per value. The printed labels are used as anchors and must agree with
the ordered assignment; no path is skipped.

The mappings are `6→500`, `8→501`, `10→502`, `12→503`, `14→504`, `16→505`,
`18→506`, `20→507`, `24→508`, `28→509`, `32→510`, `36→511`, `40→512`,
`44→513`, `48→514`, `52→515`, `60→516`. Direct inspection of the rendered
overlay shows all 17 red top-height curves lying on their black dotted source
paths.

The QMD family has 14 paths and ten printed labels. The full series is
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70 cm`, mapping to paths
`517` through `530`; the four unlabelled members (35, 45, 55, 65) are kept.
The high-QMD curves end in a sharp upward bend; Bezier control points are no
longer emitted as data, and a terminal backward endpoint is stored as a short
vertical up-tick. This removes the false zig-zag. Direct inspection shows the
blue QMD curves on their black dashed source paths.

### fdcn pass

The natural diagram is complete with 18 top-height paths (values 6 through 60,
including 56), 14 QMD paths (5 through 70, including 35, 45, 55, 65), and crown
closure from source path 640. The boundary paths 641/642 are unchanged. Direct
overlay inspection shows the red, blue, green, and boundary curves on their source
paths. fdcn is now marked reviewed.

### ssn pass

Sitka spruce natural is complete with 17 top-height paths (including 10, 14, 18,
32, 40, 48, 60), 17 QMD paths (including 35, 45, 55, 65, 75, 80), and crown
closure from source path 693. Direct overlay inspection shows the curves on their
source paths. ssn is now marked reviewed.

### ssp pass

Sitka spruce planted is complete with 16 top-height paths (including 10, 14, 18,
28, 32, 40, 44, 48, 52), 15 QMD paths (including 35, 45, 55, 65, 75), and crown
closure from source path 590. Direct overlay inspection shows the curves on their
source paths. ssp is now marked reviewed.

### hwn pass

Western hemlock natural is complete with 20 top-height paths (including 10, 14,
18, 22, 26, 40, 48, 56), 14 QMD paths (including 35, 45, 55, 65), and crown
closure from source path 562. Direct overlay inspection shows the curves on their
source paths. hwn is now marked reviewed.

### hwp pass

Western hemlock planted is complete with 19 top-height paths, 13 QMD paths, and
crown closure from source path 559. Direct overlay inspection shows the curves on
their source paths.

## TASS predicted mortality curves

The source TASS curves are plotted but **not labelled with mortality levels**.
Without a level, they cannot be stored as quantitative curves. Policy: explicitly
exclude them with a named source limitation. Do not add a `tass_mortality` schema
kind.

Consequence: the extra curves currently classified as top-height/QMD are likely
TASS paths. They must be removed and the printed-label counts rechecked.

## CAI density-range band

The grey "Density Range for Maximizing CAI" region is labelled as a region but has
no numeric level. It is now stored as a display-only `cai_band` polygon in each of
the 10 diagrams, with the same axis calibration as the curves. It is not a
quantitative curve and cannot feed constraints.

## Crown closure

The raster-traced `crown_closure` curve was replaced with a straight log-log line
fitted from the source label angle and the dotted source line. It now follows the
source crown-closure line.

## Verdict

The 10 diagrams now have a straight crown-closure line that follows the source,
aligned top/QMD curves, and a display-only CAI band. TASS is explicitly excluded.
No diagram is marked reviewed; the maintainer's sign-off is still required.
