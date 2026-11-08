# hwp digitisation status

Source: `hwp` western hemlock planted stands, version unversioned, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cwh-hw-planted.json`, provisional. All five curve families and
the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 559.

## Curve map

Top height: 19 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60 m`,
paths `525`–`543`, dash `[ 3 2 ] 0`, width 1.5. The printed labels are anchors;
the nine unlabelled interior members (10, 14, 18, 22, 28, 40, 48, 56, 60) are
kept.

QMD: 13 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65 cm`,
paths `544`–`556`, dash `[ 6 4 ] 0`, width 1.5. The four unlabelled interior
members (35, 45, 55, 65) are kept.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 525–543 | `[ 3 2 ] 0` | 1.5 |
| QMD | 544–556 | `[ 6 4 ] 0` | 1.5 |
| self-thinning | 557 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| competition | 558 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| crown closure | 559 | `[ 2 2 2 6 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 559, a single straight line:
`(199.791, 0.161017)` to `(4252.824, 0.002016)` trees/ha and m³.
