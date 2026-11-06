# P137 overlay findings

Date: 2026-11-05
Status: **all 10 provisional diagrams rejected for re-digitization**

The source page was overlaid with the stored curves using the printed axis tick
labels. The stored curves do not follow the source curves. Crown closure is
grossly wrong in all 10, and several top-height/QMD families are offset or
misidentified.

| Diagram | Finding |
| --- | --- |
| `fdcn` | Source top heights are `60, 52, 44, 39, 34, 28, 24, 20, 16, 12, 8, 6 m`; stored has `36` and omits `39`/`34`. Crown closure is not the source curve. |
| `fdcp` | Stored top-height/QMD curves are offset from the source; crown closure does not follow the source. |
| `cwn` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |
| `cwp` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |
| `hwn` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |
| `hwp` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |
| `ssn` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |
| `ssp` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |
| `swn` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |
| `swp` | Stored top-height/QMD curves are offset; crown closure does not follow the source. |

## What this means

- These diagrams are not ready for maintainer review.
- `validate_diagram` only proves the JSON is structurally valid; it does not prove
  the curves match the source.
- The current coverage statuses that depend on these diagrams are too generous.
- The correct next step is re-digitization from the PDF vector paths, followed by
  a new overlay check.

## Evidence

- `notes/review/p137-overlays/<diagram>.png`: source page with stored curves.
- `notes/review/p137-pages/<diagram>.png`: rendered source page.
- `notes/review/p137-curves/<diagram>.svg`: stored-curve plot.

No diagram was marked reviewed.
