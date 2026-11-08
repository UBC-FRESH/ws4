# fdcn digitisation status

Source: `fdcn` Coastal Douglas-fir natural stands, version unversioned, published
1996-05-31, catalogued in `ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cdf-cwh-fdc-natural.json`, provisional. All five curve families
and the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 640.

## Curve map

Top height: 18 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60 m`,
paths `607`–`624` in value order. The printed labels are anchors; the seven
unlabelled interior members (10, 14, 18, 32, 40, 48, 56) are kept.

QMD: 14 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70 cm`,
paths `625`–`639` in value order. The four unlabelled interior members (35, 45,
55, 65) are kept.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 607–624 | `[ 3 2 ] 0` | 1.5 |
| QMD | 625–639 | `[ 6 4 ] 0` | 1.5 |
| crown closure | 640 | `[ 2 2 2 6 ] 0` | 2.0 |
| competition | 641 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| self-thinning | 642 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 640, a single straight line in the PDF:
`(199.300, 0.224160)` to `(3914.148, 0.001002)` trees/ha and m³. It is no longer a
raster trace.

## Verification

The top-height and QMD families were imported with `read_ordered_curves`: the
complete value series is declared, every path must be used, and printed labels
must agree with the ordered assignment. Cubic control points are not emitted as
data; a terminal backward endpoint with rising volume is stored as one short
vertical up-tick.
