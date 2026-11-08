# P137 provisional SDMD diagram review packet

Status: all 2 diagrams remain **provisional**. This packet prepares the
maintainer's review; it does not approve any diagram.

The source page and stored-curve plot are side-by-side evidence. They are not
axis-registered overlays because the original digitisation specs are not in the
repository. The review still requires comparing curve identity and placement.
The stored-curve plot also shows the display-only CAI band; it has no numeric
level and never feeds placement or constraints.

## Diagrams

| Diagram | Species | BEC reference | Labels | Curves | Validation | Figures |
| --- | --- | --- | ---: | --- | --- | --- |
| `swn` | SW | SBSdw | 196 | competition: 1: 1<br>crown_closure: 1: 60<br>qmd: 9: 5, 10, 15, 20, 25, 30, 35, 40, 45<br>self_thinning: 1: 1<br>top_height: 17: 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38 | pass | [page](p137-pages/swn.png) · [curves](p137-curves/swn.svg) |
| `swp` | SW | SBSdw | 196 | competition: 1: 1<br>crown_closure: 1: 60<br>qmd: 8: 5, 10, 15, 20, 25, 30, 35, 40<br>self_thinning: 1: 1<br>top_height: 9: 6, 10, 14, 18, 22, 26, 30, 34, 38 | pass | [page](p137-pages/swp.png) · [curves](p137-curves/swp.svg) |

## Review checklist

Mark each line accepted or name the curve to correct. Do not mark a diagram
reviewed without the maintainer's name and UTC time.

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
