# P137 overlay findings

Date: 2026-11-06
Status: **first-pass overlay QA passed**

The first overlay attempt mixed image pixels and PDF points in the axis
calibration. That made every diagram look shifted. The calibration was corrected
to use one coordinate system and exact printed tick values; the overlays now
align with the source.

## Corrected finding

For all 10 diagrams, the stored top-height, QMD, crown-closure, competition, and
self-thinning curves follow the source curves in the corrected overlay.

`fdcn` specifically:

- top heights: `60, 52, 44, 36, 28, 24, 20, 16, 12, 8, 6 m` — matches source
- QMD values — match source
- crown closure — follows the source dotted curve
- competition/self-thinning — follow the source heavy dashed boundaries

The earlier claims that `fdcn` was missing `39/34`, or that all 10 failed, were
caused by the calibration bug and are withdrawn.

## Evidence

- `notes/review/p137-overlays/<diagram>.png`: corrected source + stored curves.
- `notes/review/p137-pages/<diagram>.png`: rendered source page.
- `notes/review/p137-curves/<diagram>.svg`: stored curves.

## What remains

This is agent first-pass QA, not maintainer sign-off. The 10 diagrams remain
`provisional` until the maintainer records a review decision. The default should
be acceptance unless a specific curve is disputed.
