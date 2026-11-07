# ssn digitisation status

Source: `ssn` Sitka spruce natural stands, version unversioned, catalogued in
`ws4/sdmd/data/sdmd/source_catalog.json`.

Status: stored as `cdf-cwh-ss-natural.json`, reviewed. All five curve families
and the CAI display polygon are stored. The old crown-closure raster trace was
replaced by source path 693.

## Curve map

Top height: 17 paths, values
`6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 52, 60 m`,
paths `657`–`673`, dash `[ 2 2 ] 0`, width 1.5. The printed labels are anchors;
the seven unlabelled interior members (10, 14, 18, 32, 40, 48, 60) are kept.

QMD: 17 paths, values
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85 cm`,
paths `674`–`690`, dash `[ 6 2 ] 0`, width 1.5. The six unlabelled interior
members (35, 45, 55, 65, 75, 80) are kept.

| Kind | Path | Dash | Width |
| --- | ---: | --- | ---: |
| top height | 657–673 | `[ 2 2 ] 0` | 1.5 |
| QMD | 674–690 | `[ 6 2 ] 0` | 1.5 |
| self-thinning | 691 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| competition | 692 | `[ 2 2 2 2 10 2 ] 0` | 2.0 |
| crown closure | 693 | `[ 2 2 2 6 ] 0` | 2.0 |

The path indices are zero-based positions in `page.get_drawings()`.

## Crown closure

The crown closure is source path 693, a single straight line in the PDF:
`(236.475, 0.382684)` to `(4566.856, 0.002046)` trees/ha and m³. It is no longer
a raster trace.

## Verification

Top height and QMD use `read_ordered_curves`: the complete value series is
declared, every path must be used, and printed labels must agree with the order.
Cubic control points are not emitted as data, and a terminal backward endpoint
with rising volume is stored as one short vertical up-tick.
