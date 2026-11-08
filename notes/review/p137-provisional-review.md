# P137 provisional SDMD diagram review packet

Status: all 4 diagrams remain **provisional**. This packet prepares the
maintainer's review; it does not approve any diagram.

The source page and stored-curve plot are side-by-side evidence. They are not
axis-registered overlays because the original digitisation specs are not in the
repository. The review still requires comparing curve identity and placement.
The stored-curve plot also shows the display-only CAI band; it has no numeric
level and never feeds placement or constraints.

## Diagrams

| Diagram | Species | BEC reference | Labels | Curves | Validation | Figures |
| --- | --- | --- | ---: | --- | --- | --- |
| `cwn` | CW | CWHvm | 193 | competition: 1: 1<br>crown_closure: 1: 60<br>qmd: 16: 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80<br>self_thinning: 1: 1<br>top_height: 17: 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 30, 34, 38, 42, 46, 50 | pass | [page](p137-pages/cwn.png) · [curves](p137-curves/cwn.svg) |
| `cwp` | CW | CWHvm | 193 | competition: 1: 1<br>crown_closure: 1: 60<br>qmd: 10: 5, 10, 15, 20, 25, 30, 40, 50, 60, 70<br>self_thinning: 1: 1<br>top_height: 11: 6, 8, 12, 16, 20, 24, 28, 32, 36, 44, 48 | pass | [page](p137-pages/cwp.png) · [curves](p137-curves/cwp.svg) |
| `swn` | SW | SBSdw | 196 | competition: 1: 1<br>crown_closure: 1: 60<br>qmd: 9: 5, 10, 15, 20, 25, 30, 35, 40, 45<br>self_thinning: 1: 1<br>top_height: 9: 6, 10, 14, 18, 22, 26, 30, 34, 38 | pass | [page](p137-pages/swn.png) · [curves](p137-curves/swn.svg) |
| `swp` | SW | SBSdw | 196 | competition: 1: 1<br>crown_closure: 1: 60<br>qmd: 8: 5, 10, 15, 20, 25, 30, 35, 40<br>self_thinning: 1: 1<br>top_height: 9: 6, 10, 14, 18, 22, 26, 30, 34, 38 | pass | [page](p137-pages/swp.png) · [curves](p137-curves/swp.svg) |

## Review checklist

Mark each line accepted or name the curve to correct. Do not mark a diagram
reviewed without the maintainer's name and UTC time.

- [ ] `cwn` curve identity, labels, boundaries, and crown closure
- [ ] `cwp` curve identity, labels, boundaries, and crown closure
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
