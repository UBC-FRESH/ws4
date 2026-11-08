# cwn digitisation status

Source: `cwn` western redcedar natural stands, version unversioned, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cwh-cw-natural.json`, provisional. All five curve families and
the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 653.

## Curve map

Top height: 17 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 30, 34, 38, 42, 46, 50 m`,
paths `617`–`633`, dash `[ 3 2 ] 0`, width 1.5. The printed labels are anchors;
the six unlabelled interior members (10, 14, 18, 22, 34, 42) are kept.

QMD: 16 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80 cm`,
paths `634`–`649`, dash `[ 6 4 ] 0`, width 1.5. The five unlabelled interior
members (35, 45, 55, 65, 75) are kept.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 617–633 | `[ 3 2 ] 0` | 1.5 |
| QMD | 634–649 | `[ 6 4 ] 0` | 1.5 |
| self-thinning | 651 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| competition | 652 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| crown closure | 653 | `[ 2 2 2 6 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 653, a single straight line:
`(199.301, 0.201636)` to `(4789.832, 0.001015)` trees/ha and m³.
