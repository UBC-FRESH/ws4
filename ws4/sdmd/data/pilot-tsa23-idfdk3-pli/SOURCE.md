# TSA 23 IDFdk3 lodgepole pine pilot extract

This store is the real lodgepole pine pilot AU. It uses the public FAIB PSP
compilation for the observed points and the published Farnden natural lodgepole
pine diagram (`pln`, version 1.20) for the density fit.

## Source

- Publisher: Forest Analysis and Inventory Branch, Government of British Columbia.
- Dataset: *Forest Inventory Ground Plot Data and Interactive Map*.
- Catalogue: `https://catalogue.data.gov.bc.ca/dataset/824e684b-4114-4a05-a490-aa56332b57f4`.
- Licence: Open Government Licence - British Columbia.
- Retrieved: 2026-11-02.
- Diagram: Farnden, C. 1996. Stand density management diagrams for lodgepole
  pine, white spruce and interior Douglas-fir. Pacific Forestry Centre
  Information Report BC-X-360. Lodgepole pine natural stands, version 1.20.
  The PDF is catalogued in `ws4/sdmd/data/sdmd/source_catalog.json`; its vector
  extraction is `idf-dk3-pli-natural.json`.

## Selection

The AU is `AU-IDFdk3-TSA23-PLI`:

- TSA 23, BEC zone `IDF`, subzone `dk`, variant `3`.
- Dominant species `PL` (lodgepole pine) by live basal area.
- Eleven reviewed PSP cluster visits, ages 20 to 120.
- Species summaries at the 2 cm close-utilization limit.

CCISS stocking standards list `Pl` as preferred on eight of nine IDFdk3 site
series and acceptable on the ninth. The observed points fall in the understocked,
density-management, and competition zones of the natural lodgepole pine diagram.

## Field derivation

The plot, stand, and SDMD-point fields use the same derivation as
`pilot-tsa23-idfdk3/SOURCE.md`: TPH and volume are the 2 cm live species sums,
QMD is computed from basal area and TPH, and age/height/site index come from the
dominant species site-age row. The SDI maximum is 1729, the McCarter and Long
(1986) lodgepole pine default.

## FVS trajectory

- Model: `fresh-fvsbc` 0.20.0, BC variant.
- Tree list: live trees of cluster `4025096-PSP1` (age 62), the median-age
  cluster of the 11 observations. Tree counts are scaled by `1979 / 1184.8 =
  1.670` so the FVS initial TPH matches the AU median TPH.
- Site: `SITECODE PL,55`.
- Horizon: 8 cycles of 10 years; `RANNSEED 1`.
- CT60: `THINBBA` at the first 10-year cycle with 60% basal-area removal. The
  projection starts at age 62, so this is a first-entry treatment, not a literal
  age-60 entry.
- Tree counts are scaled by `1979 / 1102.78 = 1.7946` so the FVS initial TPH
  matches the species-summary TPH. The volume is not rescaled.

## Limits

- The FVS path starts at 0.1708 mean tree volume, above the observed 0.1238 for
  the source cluster. That is an input-volume mismatch, not an observed trajectory.
- The natural `pln` diagram is provisional; the QMD/top-height labels and the
  crown-closure line need the maintainer's review.
- The AU is a public PSP extract, not a full TSA 23 inventory.
- No initial volume is supplied, so that gate warns.
