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
label mortality levels. The grey CAI band is stored as a display-only `cai_band`
polygon and rendered behind the curves. The diagrams remain provisional; the
maintainer's sign-off is still required.

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
pseudo-curves are removed. The grey CAI band is now stored and displayed.

`fdcp` is the first line-type-wise re-import. The source has 17 top-height
paths, ten printed labels, and seven unlabelled interior members. The importer
uses the complete value series and requires one path per value; the printed
labels are anchors. All 17 mappings are recorded in
`notes/reference/fdcp-digitisation.md`. Direct inspection of the rendered overlay
shows all 17 red top-height curves on their black dotted source paths.

The QMD family similarly keeps all 14 paths, including the unlabelled 35, 45, 55,
and 65 cm curves. Its mapping is `517`–`530` in value order. The pattern is locked
in `workflows/sdmd-qmd-import.yaml`.

Evidence: `notes/review/p137-overlay-findings.md` and
`notes/review/p137-overlays/`.

## Verification

```bash
python -m pytest tests/test_diagram_review_packet.py tests/test_sdmd_diagram.py \
  tests/test_sdmd_api.py tests/test_sdmd_ui.py -q
python scripts/dashboard.py
```

Targeted tests passed. Dashboard: `OVERALL: GREEN`.

Live portal check at `http://127.0.0.1:8790/instance/sdmd-pilot/?view=sdmd`:

- the SDMD payload carries a five-point `cai_band`;
- the rendered SVG has one `polygon.sdmd-cai-band`;
- the legend names “CAI density range”;
- the coverage header reads `219 BEC labels · 6 reviewed · 209 mixed · 4 gaps`.

## Limits

- A validated diagram is structurally valid, not necessarily correct.
- The packet is not a substitute for the maintainer's curve review.
- No diagram is marked reviewed.
