# fdcn digitisation status

Source: `fdcn` Coastal Douglas-fir natural stands, version unversioned, published
1996-05-31, catalogued in `ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cdf-cwh-fdc-natural.json`, provisional. The top-height, QMD, and
boundary curves are vector paths. The crown-closure curve is a provisional raster
trace because the printed dotted curve is not a single vector path.

## Axis calibration

- X ticks: 200, 300, 400, 600, 800, 1,000, 2,000, 3,000, 4,000, 6,000, 8,000,
  10,000 trees/ha.
- Y ticks: 0.001 to 8.0 m3 in the printed sequence.

## Curve map

| Kind | Printed value | Drawing index | Dash | Width |
| --- | --- | --- | --- | --- |
| top_height | 6 m | 607 | `[ 3 2 ] 0` | 1.5 |
| top_height | 8 m | 608 | `[ 3 2 ] 0` | 1.5 |
| top_height | 12 m | 610 | `[ 3 2 ] 0` | 1.5 |
| top_height | 16 m | 612 | `[ 3 2 ] 0` | 1.5 |
| top_height | 20 m | 614 | `[ 3 2 ] 0` | 1.5 |
| top_height | 24 m | 615 | `[ 3 2 ] 0` | 1.5 |
| top_height | 28 m | 617 | `[ 3 2 ] 0` | 1.5 |
| top_height | 36 m | 619 | `[ 3 2 ] 0` | 1.5 |
| top_height | 44 m | 620 | `[ 3 2 ] 0` | 1.5 |
| top_height | 52 m | 623 | `[ 3 2 ] 0` | 1.5 |
| top_height | 60 m | 624 | `[ 3 2 ] 0` | 1.5 |
| qmd | 5 cm | 625 | `[ 6 4 ] 0` | 1.5 |
| qmd | 10 cm | 626 | `[ 6 4 ] 0` | 1.5 |
| qmd | 15 cm | 627 | `[ 6 4 ] 0` | 1.5 |
| qmd | 20 cm | 628 | `[ 6 4 ] 0` | 1.5 |
| qmd | 25 cm | 629 | `[ 6 4 ] 0` | 1.5 |
| qmd | 30 cm | 630 | `[ 6 4 ] 0` | 1.5 |
| qmd | 40 cm | 632 | `[ 6 4 ] 0` | 1.5 |
| qmd | 50 cm | 634 | `[ 6 4 ] 0` | 1.5 |
| qmd | 60 cm | 636 | `[ 6 4 ] 0` | 1.5 |
| qmd | 70 cm | 639 | `[ 6 4 ] 0` | 1.5 |
| competition | boundary | 641 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| self_thinning | boundary | 642 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown-closure curve

The printed **Crown Closure** curve is visible in the rendered page but is not one
of the `[ 3 2 ]`, `[ 6 4 ]`, or `[ 4 1 4 3 ]` path families. The `[ 3 2 ]` family
contains the top-height curves plus flat intermediate curves; the
`[ 4 1 4 3 ]` family is the TASS predicted-mortality set. The closure dots do not
appear as a single vector path in the page drawings.

The stored curve is a provisional raster trace through the printed curve:

`(200, 0.2)`, `(300, 0.12)`, `(400, 0.085)`, `(600, 0.05)`, `(800, 0.035)`,
`(1000, 0.025)`, `(1500, 0.012)`, `(2000, 0.007)`, `(2500, 0.004)`,
`(3000, 0.0025)`, `(4000, 0.0012)`.

These are approximate. The figrecover overlay in the review run is the check.
Do not treat the `fdcn` diagram as reviewed until that curve is compared with the
printed page.
