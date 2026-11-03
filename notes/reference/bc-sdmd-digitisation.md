# BC SDMD digitisation method

The natural Interior Douglas-fir diagram is digitised from the public PDF
recorded in `ws4/sdmd/data/sdmd/source_catalog.json` (diagram `fdin`, version
1.10). The outputs are `ws4/sdmd/data/sdmd/idf-dk3-fdi-natural.json` and
`ws4/sdmd/data/sdmd/idf-dk3-fdi-planted.json`.

## Method

1. The PDF paths are read as ordered vector segments. No raster tracing is used.
2. The logarithmic axes are calibrated from the printed tick labels: TPH
   `10 ** (a*x + b)` and mean tree volume `10 ** (c*y + d)`. The fit residuals are
   below 1% on every axis label.
3. The curve families are separated by the PDF dash pattern and stroke width:
   long dash for QMD, dotted for top height, dash-dot for TASS mortality, and the
   thick long-dash-dot pair for the mean and lower competition-mortality limits.
4. The top-height curves are assigned the printed values 8, 10, 14, 18, 22, 26,
   30, 34, 40, and 46 m by the nearest printed label and the vertical order at the
   left edge.
5. The QMD curves are assigned the 5 cm sequence 5, 10, ..., 50 cm from the left
   edge and the printed labels.
6. The crown-closure curve is the dotted lower curve with the printed
   "Crown Closure" label; its descending and rising pieces are joined.
7. The two thick dash-dot lines are `competition` (the lower limit of the
   imminent competition-mortality zone) and `self_thinning` (the mean limit).

## What is stored

- 10 top-height isopleths, 10 QMD isopleths, one crown-closure curve, one
  competition boundary, and one self-thinning boundary.
- Each isopleth is an ordered `(tph, mean_tree_volume_m3)` list.
- Source citation, version, licence note, and the catalogued PDF SHA-256.

## Known limits

- The 18 TASS predicted-mortality dotted curves are visible in the PDF but are not
  stored in the five-kind contract.
- The grey "density range for maximizing CAI" band is not stored.
- The top-height and QMD curves only cover their printed domains; a point beyond a
  curve's last digitised point is reported as outside the isopleth range rather than
  extrapolated.
- The diagram is marked `provisional`. The maintainer must review the curves before
  a report may use it. The review checklist is: top-height values, QMD values,
  closure line, the two thick limits, and the pilot-AU compatibility.
- The planted diagram's printed labels are offset from the curves. Its 10
  top-height curves were assigned 8, 10, 14, 18, 22, 26, 30, 34, 40, and 46 m
  from the printed labels and the vertical order at the left edge. That assignment
  is provisional and must be reviewed before use.

## Review

Reviewer of record: Gregory Paradis (maintainer of record). Status: all four
diagrams are `reviewed` as of 2026-11-02T18:20:44+00:00. The review packet is
`notes/review/p95-curve-review.md`. The `fdin` crown closure is truncated at
2,951 TPH because the high-TPH branch was not resolved; that limit is recorded in
the review packet and the source catalog.


## Lodgepole pine planted diagram

The planted lodgepole pine PDF (`plp`, version 1.20) is digitised into
`ws4/sdmd/data/sdmd/idf-dk3-pli-planted.json`.

- The axis calibration uses the printed TPH ticks 200-4000 and the mean-tree-volume
  ticks 0.005-2.0 m3.
- The dashed curves are the printed QMD 10, 15, 20, 25, 30, 35, and 40 cm labels.
- The dotted curves are the printed top-height 6, 10, 14, 18, 22, 26, and 30 m
  labels. Unlabelled intermediate dotted curves are not stored.
- The thick dash-dot pair is stored as `competition` (lower) and `self_thinning`
  (upper).
- The low dotted curve near the printed Crown Closure label is stored as the 60%
  crown-closure boundary.
- Every path is sorted by increasing TPH. The source SHA-256 matches the
  catalogued `plp` PDF.

The natural lodgepole pine diagram (`pln`, version 1.20) is digitised into
`ws4/sdmd/data/sdmd/idf-dk3-pli-natural.json` with top height 6-34 m, QMD 10-40
cm, the competition/self-thinning boundaries, and the 60% crown-closure curve. A
real TSA 23 / IDFdk3 / PLI PSP store uses it in
`ws4/sdmd/data/pilot-tsa23-idfdk3-pli/`. Both lodgepole pine diagrams are
`provisional`; the QMD/top-height label assignments and the crown-closure curves
are the review items.
