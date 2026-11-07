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
| 12 | 503 |
| 16 | 505 |
| 20 | 507 |
| 24 | 508 |
| 28 | 509 |
| 36 | 511 |
| 44 | 513 |
| 52 | 515 |

The intervening unlabelled top-height paths (502, 504, 506, 510, 512, 514, 516)
are not stored. The source page labels only the ten listed values.

The confirmed pattern is locked in `workflows/sdmd-line-import.yaml`:
`render` uses figrecover and `import` uses `ws4.sdmd.import-lines` to write a
`ws4.sdmd.line-import.v1` artifact. A local FreshForge run completed with
`render success` and `import success`, producing the same ten value/path pairs.

## Limits

- Crown closure is still the old provisional trace; it is not part of this
  top-height pass.
- The diagram is not site-series-specific; it covers coastal planted Douglas-fir.
