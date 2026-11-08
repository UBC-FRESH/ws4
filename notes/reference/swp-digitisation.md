# swp digitisation status

Source: `swp` white spruce planted stands, version 1.30, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `sbs-sw-planted.json`, reviewed. All five curve families and the
CAI display polygon are stored. The old crown-closure raster trace was replaced by
source path 36.

## Curve map

Top height: 17 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38 m`,
paths `45`–`61`, dash `[ 2 2 ] 0`, width 1.5. The planted top-height labels are
offset; the complete series and the ordered paths are the check. The label 34 is
adjacent to paths 58 and 59, so ordered verification permits a one-path anchor
offset instead of guessing.

QMD: 8 paths, values `5, 10, 15, 20, 25, 30, 35, 40 cm`, paths `37`–`44`,
dash `[ 8 4 ] 0`, width 1.5.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 45–61 | `[ 2 2 ] 0` | 1.5 |
| QMD | 37–44 | `[ 8 4 ] 0` | 1.5 |
| competition | 34 | `[ 12 2 2 2 2 2 ] 0` | 1.8 |
| self-thinning | 35 | `[ 12 2 2 2 2 2 ] 0` | 1.8 |
| crown closure | 36 | `[ 12 2 2 2 ] 0` | 1.8 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 36, a single straight line:
`(302.097, 0.418492)` to `(2612.344, 0.002949)` trees/ha and m³.
