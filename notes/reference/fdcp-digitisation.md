# fdcp digitisation status

Source: `fdcp` coastal Douglas-fir planted stands, version unversioned,
catalogued in `ws4/sdmd/data/sdmd/source_catalog.json`.

Stored as `cdf-cwh-fdc-planted.json`, **provisional**.

## Curve map

- Top height: 6, 8, 12, 16, 20, 24, 28, 36, 44, 52 m.
- QMD: 5, 10, 15, 20, 25, 30, 40, 50, 60, 70 cm.
- Competition: path 532.
- Self-thinning: path 531.
- Crown closure: still the old provisional trace; source path 533 is available for
  the next line-type pass.

Top-height paths `[ 3 2 ]`, QMD `[ 6 4 ]`, boundaries
`[ 2 2 2 2 10 2 ]`.

## Top-height import

The top-height labels are matched to paths by `read_labelled_curves`, which uses
the printed label position, the requested dash pattern and stroke width, and a
one-to-one nearest match. It refuses ambiguous, distant, duplicate, or
vertically unordered matches.

| Value (m) | Path |
| ---: | ---: |
| 6 | 500 |
| 8 | 501 |
| 10 | 502 |
| 12 | 503 |
| 14 | 504 |
| 16 | 505 |
| 18 | 506 |
| 20 | 507 |
| 24 | 508 |
| 28 | 509 |
| 32 | 510 |
| 36 | 511 |
| 40 | 512 |
| 44 | 513 |
| 48 | 514 |
| 52 | 515 |
| 60 | 516 |

The source page prints only ten of these labels; the other seven values are the
unlabelled members of the same path series. They are kept, not skipped.

## QMD import

The QMD family has 14 paths and ten printed labels. The full value series is
`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70 cm`; paths are
`517` through `530` in order. The four unlabelled members are 35, 45, 55, and
65 cm.

The high-QMD source curves end with a sharp upward bend. Bezier control points
are not data, so they are not emitted as points; if the final endpoint steps
back in TPH while rising, it is stored as a very short vertical up-tick. This
removes the false terminal zig-zag without flattening the bend.

The confirmed patterns are locked in `workflows/sdmd-line-import.yaml` for top
height and `workflows/sdmd-qmd-import.yaml` for QMD:
`render` uses figrecover and `import` uses `ws4.sdmd.import-lines` to write a
`ws4.sdmd.line-import.v1` artifact. A local FreshForge run completed with
`render success` and `import success`, producing the same ten value/path pairs.

## Limits

- Crown closure is still the old provisional trace; it is not part of this
  top-height pass.
- The diagram is not site-series-specific; it covers coastal planted Douglas-fir.
