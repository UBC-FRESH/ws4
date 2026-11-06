# P137.1 Provisional diagram review packet

Date: 2026-11-05
Parent: #830
Child: #831
Branch: `feature/p137-diagram-review`

## What changed

- Built `notes/review/p137-provisional-review.md`.
- Downloaded and SHA-256-checked the 10 source PDFs against
  `source_catalog.json`.
- Rendered the 10 source pages under `notes/review/p137-pages/`.
- Plotted the 10 stored-curve sets under `notes/review/p137-curves/`.
- Ran `validate_diagram` on all 10; every diagram passes.
- Added the maintainer checklist and the four no-diagram decisions.

## Result

Agent first-pass overlay QA passed. A coordinate-system bug made the first
overlays untrustworthy; after correction, all 10 stored diagrams align with their
source. The earlier `fdcn`/all-10 failure claims are withdrawn. The diagrams remain
provisional until the maintainer records a review decision.

The diagrams are:

`cwn`, `cwp`, `fdcn`, `fdcp`, `hwn`, `hwp`, `ssn`, `ssp`, `swn`, `swp`.

Each has top-height, QMD, competition, self-thinning, and 60% crown-closure
curves. The source page and stored-curve plot are side-by-side; they are not
axis-registered overlays because the original digitisation specs are not in the
repository.

The four no-diagram labels remain `BAFAun`, `CMAun`, `CMAwh`, and `IMAun`. They
need either new public source material or a permanent refusal.

## PR

Queued in PR #832 after `abdb3bf`.

## Overlay finding

The first overlay pass had a coordinate-calibration bug. After correction, all
10 diagrams align with their source. The earlier `39/34` and all-10 failure
claims were wrong. This is agent first-pass QA, not maintainer sign-off.

Evidence: `notes/review/p137-overlay-findings.md` and
`notes/review/p137-overlays/`.

## Verification

```bash
python -m pytest tests/test_diagram_review_packet.py -q
python scripts/dashboard.py
```

Packet builder test: 2 passed. Dashboard: `OVERALL: GREEN`.

## Limits

- A validated diagram is structurally valid, not necessarily correct.
- The packet is not a substitute for the maintainer's curve review.
- No diagram is marked reviewed.
