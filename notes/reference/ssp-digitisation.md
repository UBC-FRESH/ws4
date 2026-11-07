# ssp digitisation status

Source: `ssp` Sitka spruce planted stands, version unversioned, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cdf-cwh-ss-planted.json`, provisional. All five curve families
and the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 590.

## Curve map

Top height: 16 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 52 m`,
paths `557`–`572`, dash `[ 2 2 ] 0`, width 1.5. The printed labels are anchors;
the nine unlabelled interior members (10, 14, 18, 28, 32, 40, 44, 48, 52) are
kept.

QMD: 15 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75 cm`,
paths `573`–`587`, dash `[ 6 3 ] 0`, width 1.5. The five unlabelled interior
members (35, 45, 55, 65, 75) are kept.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 557–572 | `[ 2 2 ] 0` | 1.5 |
| QMD | 573–587 | `[ 6 3 ] 0` | 1.5 |
| self-thinning | 588 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| competition | 589 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| crown closure | 590 | `[ 2 2 2 6 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 590, a single straight line in the PDF:
`(245.034, 0.596208)` to `(3982.656, 0.003055)` trees/ha and m³.
