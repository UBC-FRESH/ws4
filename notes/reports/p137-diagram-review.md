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

Crown closure is now a straight log-log line fitted to the source, and the
top/QMD curves align in the corrected overlays. The apparent count mismatch was a
text-extraction artifact. TASS is explicitly excluded because the source does not
label mortality levels. The grey CAI band is still not represented; do not sign
off until that is decided.

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

The first overlay pass had a coordinate-calibration bug. After correction and
cleanup, top/QMD counts match, crown closure is a straight fitted line, and TASS
pseudo-curves are removed. The CAI band remains.

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
