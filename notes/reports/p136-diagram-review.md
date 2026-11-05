# P136.1 Provisional diagram review packet

Date: 2026-11-05
Parent: #830
Child: #831
Branch: `feature/p136-diagram-review`

## What changed

- Built `notes/review/p136-provisional-review.md`.
- Downloaded and SHA-256-checked the 10 source PDFs against
  `source_catalog.json`.
- Rendered the 10 source pages under `notes/review/p136-pages/`.
- Plotted the 10 stored-curve sets under `notes/review/p136-curves/`.
- Ran `validate_diagram` on all 10; every diagram passes.
- Added the maintainer checklist and the four no-diagram decisions.

## Result

All 10 diagrams remain **provisional**. The packet is evidence for the
maintainer's review, not an approval.

The diagrams are:

`cwn`, `cwp`, `fdcn`, `fdcp`, `hwn`, `hwp`, `ssn`, `ssp`, `swn`, `swp`.

Each has top-height, QMD, competition, self-thinning, and 60% crown-closure
curves. The source page and stored-curve plot are side-by-side; they are not
axis-registered overlays because the original digitisation specs are not in the
repository.

The four no-diagram labels remain `BAFAun`, `CMAun`, `CMAwh`, and `IMAun`. They
need either new public source material or a permanent refusal.

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
