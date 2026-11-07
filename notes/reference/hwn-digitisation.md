# hwn digitisation status

Source: `hwn` western hemlock natural stands, version unversioned, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cwh-hw-natural.json`, provisional. All five curve families and
the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 562.

## Curve map

Top height: 20 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 32, 36, 40, 44, 48, 52, 56, 60 m`,
paths `619`–`638`, dash `[ 3 2 ] 0`, width 1.5. The printed labels are anchors;
the eight unlabelled interior members (10, 14, 18, 22, 26, 40, 48, 56) are kept.

QMD: 14 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70 cm`,
paths `639`–`652`, dash `[ 6 4 ] 0`, width 1.5. The four unlabelled interior
members (35, 45, 55, 65) are kept.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 619–638 | `[ 3 2 ] 0` | 1.5 |
| QMD | 639–652 | `[ 6 4 ] 0` | 1.5 |
| self-thinning | 560 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| competition | 561 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| crown closure | 562 | `[ 2 2 2 6 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 562, a single straight line:
`(255.999, 0.067372)` to `(5358.757, 0.001029)` trees/ha and m³.
