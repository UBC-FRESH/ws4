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
8. The grey "Density Range for Maximizing CAI" band is read from the large grey
   filled path as a polygon and stored under `cai_band` for display only.

## What is stored

- 10 top-height isopleths, 10 QMD isopleths, one crown-closure curve, one
  competition boundary, and one self-thinning boundary.
- Each isopleth is an ordered `(tph, mean_tree_volume_m3)` list.
- Source citation, version, licence note, and the catalogued PDF SHA-256.

## Known limits

- The 18 TASS predicted-mortality dotted curves are visible in the PDF but are not
  stored in the five-kind contract.
- The grey "density range for maximizing CAI" band is stored as an optional
  `cai_band` polygon for display only. It has no numeric level and never feeds
  placement or constraints.
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
`notes/review/p95-curve-review.md`. The `fdin` crown closure is the continuous dotted path from 210 to 9,996 TPH.
The earlier join to a second branch was removed in P106.1; the review packet and
source catalog record the correction.


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


## Tooling integration

The atlas pipeline uses two public UBC-FRESH tools:

- `figrecover` (MIT) renders the PDF page, draws the stored isopleths over the
  rendered page, computes QA records, and writes the review manifest.
- `freshforge` (MIT) carries the `render -> extract -> overlay -> review` workflow
  in `workflows/sdmd-digitise.yaml`.

The isopleth extraction itself remains the vector-path reader in
`ws4.sdmd.digitise`, because the public PDFs are vector Illustrators and direct
paths are more precise than raster tracing. The module is exposed as the
`ws4.sdmd.extract` node. A diagram spec supplies the axis ticks, path indices,
dash patterns, and printed values; the workflow does not invent them.

Install the optional tools with `python -m pip install -e '.[digitise]'`.

## fdcn status

The Coastal Douglas-fir natural diagram is stored as `cdf-cwh-fdc-natural.json`,
provisional. Top height, QMD, boundaries, and crown closure are vector paths; the
full top-height and QMD series include their unlabelled interior curves. Method and
path map: `notes/reference/fdcn-digitisation.md`.

## ssn status

Sitka spruce natural is stored as `cdf-cwh-ss-natural.json`, reviewed. Top
height, QMD, boundaries, and crown closure are vector paths. Top height and QMD
use full value series, so their unlabelled interior curves are kept. See
`notes/reference/ssn-digitisation.md`.

## hwn status

Western hemlock natural is stored as `cwh-hw-natural.json`, provisional. Top
height, QMD, boundaries, and crown closure are vector paths. Top height and QMD
use full value series, so their unlabelled interior curves are kept. See
`notes/reference/hwn-digitisation.md`.

## swn status

White spruce natural is stored as `sbs-sw-natural.json`, provisional. Top height,
QMD, and boundaries are vector; crown closure is a raster trace. See
`notes/reference/swn-digitisation.md`.

## cwn status

Western redcedar natural is stored as `cwh-cw-natural.json`, provisional. Top
height, QMD, and boundaries are vector; crown closure is a raster trace. See
`notes/reference/cwn-digitisation.md`.

## fdcp status

Coastal Douglas-fir planted is stored as `cdf-cwh-fdc-planted.json`, reviewed by
the maintainer. Top height, QMD, boundaries, and crown closure are vector paths.
Top height and QMD use full value series, so their unlabelled interior curves are
kept. The mapping is in `notes/reference/fdcp-digitisation.md`.

## ssp status

Sitka spruce planted is stored as `cdf-cwh-ss-planted.json`, provisional. Top
height, QMD, boundaries, and crown closure are vector paths. Top height and QMD
use full value series, so their unlabelled interior curves are kept. See
`notes/reference/ssp-digitisation.md`.

## hwp status

Western hemlock planted is stored as `cwh-hw-planted.json`, provisional. Top
height, QMD, and boundaries are vector; crown closure is a raster trace. See
`notes/reference/hwp-digitisation.md`.

## cwp status

Western redcedar planted is stored as `cwh-cw-planted.json`, provisional. Top
height, QMD, and boundaries are vector; crown closure is a raster trace. See
`notes/reference/cwp-digitisation.md`.

## swp status

White spruce planted is stored as `sbs-sw-planted.json`, provisional. Top
height, QMD, and boundaries are vector; crown closure is a raster trace. See
`notes/reference/swp-digitisation.md`.

## BEC crosswalk

The WS4/CCISS label review is in `notes/reports/p121-bec-crosswalk.md` and
`bec_crosswalk_review.csv`. The BECdb crosswalk in `bec_official_crosswalk.csv`
names every WS4 label as current, retired with a retirement version, or absent
from both BECdb tables. There are no unresolved WS4 labels.
