# P137 overlay findings

Date: 2026-11-06
Status: **fdcn crown closure rejected; the earlier blanket rejection was premature**

The first overlay attempt mixed image pixels and PDF points in the axis
calibration. That made every diagram look shifted. The calibration was corrected
to use one coordinate system; the x and y fits are now essentially exact.

## What the corrected overlay shows

`fdcn`:

- Top-height labels match the source: `60, 52, 44, 36, 28, 24, 20, 16, 12, 8, 6 m`.
  The earlier claim of missing `39/34` was wrong; those values are not in the source.
- QMD labels match the source.
- The stored `crown_closure` curve is **not** the source crown-closure curve.
  The source crown closure is the dotted curve through the middle of the plot;
  the stored green curve starts at the left edge and is the wrong shape.

So `fdcn` is rejected for a crown-closure correction, not because every curve is
wrong.

## What is still uncertain

The other nine overlays used the flawed calibration. Their apparent offsets are
not evidence of failure. They need corrected per-page overlays before any
request/reject decision.

## Evidence

- `notes/review/p137-overlays/fdcn.png`: corrected source + stored curves.
- `notes/review/p137-pages/fdcn.png`: rendered source page.
- `notes/review/p137-curves/fdcn.svg`: stored curves.

No diagram is marked reviewed.
