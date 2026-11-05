# P136 provisional SDMD diagram review packet

Status: all 10 diagrams remain **provisional**. This packet prepares the
maintainer's review; it does not approve any diagram.

The source page and stored-curve plot are side-by-side evidence. They are not
axis-registered overlays because the original digitisation specs are not in the
repository. The review still requires comparing curve identity and placement.

## Diagrams

| Diagram | Species | BEC reference | Labels | Curves | Validation | Figures |
| --- | --- | --- | ---: | --- | --- | --- |
| `cwn` | CW | CWHvm | 193 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 11 curves; values 5.0..80.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 11 curves; values 6.0..50.0 | pass | [page](p136-pages/cwn.png) · [curves](p136-curves/cwn.svg) |
| `cwp` | CW | CWHvm | 193 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 10 curves; values 5.0..70.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 11 curves; values 6.0..48.0 | pass | [page](p136-pages/cwp.png) · [curves](p136-curves/cwp.svg) |
| `fdcn` | FDC | CDFmm | 25 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 10 curves; values 5.0..70.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 11 curves; values 6.0..60.0 | pass | [page](p136-pages/fdcn.png) · [curves](p136-curves/fdcn.svg) |
| `fdcp` | FDC | CDFmm | 25 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 10 curves; values 5.0..70.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 10 curves; values 6.0..52.0 | pass | [page](p136-pages/fdcp.png) · [curves](p136-curves/fdcp.svg) |
| `hwn` | HW | CWHvm | 106 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 10 curves; values 5.0..65.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 12 curves; values 6.0..60.0 | pass | [page](p136-pages/hwn.png) · [curves](p136-curves/hwn.svg) |
| `hwp` | HW | CWHvm | 106 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 9 curves; values 5.0..60.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 10 curves; values 6.0..52.0 | pass | [page](p136-pages/hwp.png) · [curves](p136-curves/hwp.svg) |
| `ssn` | SS | CDFmm | 72 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 11 curves; values 5.0..85.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 10 curves; values 6.0..52.0 | pass | [page](p136-pages/ssn.png) · [curves](p136-curves/ssn.svg) |
| `ssp` | SS | CDFmm | 72 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 10 curves; values 5.0..70.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 7 curves; values 6.0..36.0 | pass | [page](p136-pages/ssp.png) · [curves](p136-curves/ssp.svg) |
| `swn` | SW | SBSdw | 196 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 9 curves; values 5.0..45.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 9 curves; values 6.0..38.0 | pass | [page](p136-pages/swn.png) · [curves](p136-curves/swn.svg) |
| `swp` | SW | SBSdw | 196 | competition: 1 curves; values 1.0..1.0<br>crown_closure: 1 curves; values 60.0..60.0<br>qmd: 8 curves; values 5.0..40.0<br>self_thinning: 1 curves; values 1.0..1.0<br>top_height: 9 curves; values 6.0..38.0 | pass | [page](p136-pages/swp.png) · [curves](p136-curves/swp.svg) |

## Review checklist

Mark each line accepted or name the curve to correct. Do not mark a diagram
reviewed without the maintainer's name and UTC time.

- [ ] `cwn` curve identity, labels, boundaries, and crown closure
- [ ] `cwp` curve identity, labels, boundaries, and crown closure
- [ ] `fdcn` curve identity, labels, boundaries, and crown closure
- [ ] `fdcp` curve identity, labels, boundaries, and crown closure
- [ ] `hwn` curve identity, labels, boundaries, and crown closure
- [ ] `hwp` curve identity, labels, boundaries, and crown closure
- [ ] `ssn` curve identity, labels, boundaries, and crown closure
- [ ] `ssp` curve identity, labels, boundaries, and crown closure
- [ ] `swn` curve identity, labels, boundaries, and crown closure
- [ ] `swp` curve identity, labels, boundaries, and crown closure

## No-diagram labels

`BAFAun`, `CMAun`, `CMAwh`, and `IMAun` have no diagram in the 14-public
Atlas. For each, choose one: acquire/digitize a public source, or record a
permanent refusal. Do not substitute an unrelated diagram.

## Known limits

- No axis-registered overlay is available; the original specs are not tracked.
- The source pages are rendered for review, not copied into the data layer.
- A validated diagram is structurally valid, not necessarily correct.
- The maintainer remains reviewer of record.
