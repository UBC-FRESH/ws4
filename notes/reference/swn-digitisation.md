# swn digitisation status

Source: `swn` white spruce natural stands, version 1.30, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `sbs-sw-natural.json`, provisional. All five curve families and
the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 49.

## Curve map

Top height: 17 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38 m`,
paths `59`–`75`, dash `[ 2 2 ] 0`, width 1.5. The printed labels are anchors;
the eight unlabelled interior members (8, 12, 16, 20, 24, 28, 32, 36) are kept.

QMD: 9 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45 cm`, paths `50`–`58`, dash `[ 8 4 ] 0`,
width 1.5. All nine are printed or anchored by the printed sequence.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 59–75 | `[ 2 2 ] 0` | 1.5 |
| QMD | 50–58 | `[ 8 4 ] 0` | 1.5 |
| competition | 47 | `[ 12 2 2 2 2 2 ] 0` | 1.8 |
| self-thinning | 48 | `[ 12 2 2 2 2 2 ] 0` | 1.8 |
| crown closure | 49 | `[ 12 2 2 2 ] 0` | 1.8 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 49, a single straight line:
`(259.914, 0.597912)` to `(2611.909, 0.002963)` trees/ha and m³.
