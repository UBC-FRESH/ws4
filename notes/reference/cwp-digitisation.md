# cwp digitisation status

Source: `cwp` western redcedar planted stands, version unversioned, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cwh-cw-planted.json`, reviewed. All five curve families and
the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 582.

## Curve map

Top height: 17 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 32, 36, 40, 44, 48 m`,
paths `548`–`564`, dash `[ 3 2 ] 0`, width 1.5. The printed labels are anchors;
the six unlabelled interior members (10, 14, 18, 22, 26, 40) are kept.

QMD: 15 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75 cm`,
paths `565`–`579`, dash `[ 6 4 ] 0`, width 1.5. The five unlabelled interior
members (35, 45, 55, 65, 75) are kept.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 548–564 | `[ 3 2 ] 0` | 1.5 |
| QMD | 565–579 | `[ 6 4 ] 0` | 1.5 |
| self-thinning | 580 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| competition | 581 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| crown closure | 582 | `[ 2 2 2 6 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 582, a single straight line:
`(200.503, 0.303069)` to `(2792.931, 0.002019)` trees/ha and m³.
