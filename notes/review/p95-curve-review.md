# P95.1 curve review packet

Phase: P95 SDMD pilot
Task: P95.1 digitised curve review
Evidence head: `d39faca` (diagrams and PLI pilot) and `265375e` (CCISS extracts)
Date: 2026-11-02
Status: four diagrams provisional; one known limit in `fdin`; reviewer sign-off pending.

This packet is the review surface for the four digitised diagrams. The figures
overlay the stored vector curves on the printed PDF labels. The review is about
curve identity and placement, not about whether the SDMD method itself is valid.

## Figures

- `p95-curves/fdin.png` — Interior Douglas-fir natural
- `p95-curves/fdip.png` — Interior Douglas-fir planted
- `p95-curves/pln.png` — lodgepole pine natural
- `p95-curves/plp.png` — lodgepole pine planted

The source PDFs are catalogued in `ws4/sdmd/data/sdmd/source_catalog.json`; the
stored JSON, not the figures, is the contract.

## Curve inventory

| Diagram | Top height | QMD | Boundaries | Crown closure | Status |
| --- | --- | --- | --- | --- | --- |
| `fdin` | 8, 10, 14, 18, 22, 26, 30, 34, 40, 46 m | 5–50 cm, 5 cm steps | competition, self-thinning | 48 points, ends at 2,951 TPH | provisional |
| `fdip` | 8, 10, 14, 18, 22, 26, 30, 34, 40, 46 m | 10–50 cm, 5 cm steps | competition, self-thinning | 65 points | provisional |
| `pln` | 6, 10, 14, 18, 22, 26, 30, 34 m | 10–40 cm, 5 cm steps | competition, self-thinning | 19 points | provisional |
| `plp` | 6, 10, 14, 18, 22, 26, 30 m | 10–40 cm, 5 cm steps | competition, self-thinning | 13 points | provisional |

All four pass `validate_diagram`.

## What the overlays show

### `fdin`

The printed top-height and QMD labels line up with the stored curve families.
The top-height 40 m and 46 m labels sit close together at the upper left; verify
that the 40 m/46 m pair is not swapped. The competition and self-thinning
boundaries are in the expected order (competition below self-thinning at high
TPH).

The crown-closure extraction originally joined two branches above 2,951 TPH and
produced a zigzag. The stored curve is now truncated at 2,951 TPH. The high-TPH
closure is therefore unresolved; record whether that is acceptable for the
provisional diagram or whether the high-TPH branch must be re-digitised.

### `fdip`

The printed top-height labels are offset from the curves in the PDF, as recorded
in `notes/reference/bc-sdmd-digitisation.md`. The overlay is the check for the
8–46 m assignment. The QMD and boundary curves are clean.

### `pln`

The printed QMD labels line up with the long-dash curves; the top-height labels
line up with the dotted curves. The 6 m curve sits low and close to the plot
edge; verify it is the intended top-height 6 m curve rather than a boundary
fragment. The competition/self-thinning pair is in the expected order.

### `plp`

The printed QMD labels line up with the long-dash curves. The top-height labels
line up with the dotted curves at 6, 10, 14, 18, 22, 26, and 30 m. This is the
stronger of the two lodgepole assignments; `plp` is stored for planted stands,
while the real PLI PSP AU uses natural `pln`.

## Review checklist

Mark each line as accepted or name the curve to correct.

- [ ] `fdin` top-height values 8–46 m
- [ ] `fdin` QMD values 5–50 cm
- [ ] `fdin` competition and self-thinning boundaries
- [ ] `fdin` crown closure, including the 2,951 TPH truncation
- [ ] `fdip` top-height values 8–46 m
- [ ] `fdip` QMD values 10–50 cm
- [ ] `fdip` competition, self-thinning, and crown-closure curves
- [ ] `pln` top-height values 6–34 m
- [ ] `pln` QMD values 10–40 cm
- [ ] `pln` competition, self-thinning, and crown-closure curves
- [ ] `plp` top-height values 6–30 m
- [ ] `plp` QMD values 10–40 cm
- [ ] `plp` competition, self-thinning, and crown-closure curves

Reviewer: ______________________  
Date: ______________________  
Decision: accept as provisional / correct before review / reject

## What changes on sign-off

For each accepted diagram, set in the JSON:

```json
"review": {
  "status": "reviewed",
  "reviewer": "<reviewer>",
  "reviewed_utc": "<UTC timestamp>"
}
```

Then rerun:

```bash
python -m pytest tests/test_sdmd_diagram.py tests/test_sdmd_sources.py -q
ws4 sdmd validate --sdmd-dir ws4/sdmd/data/pilot-tsa23-idfdk3
ws4 sdmd validate --sdmd-dir ws4/sdmd/data/pilot-tsa23-idfdk3-pli
python scripts/dashboard.py
```

The PLI AU uses `idf-dk3-pli-natural.json`; the planted `plp` diagram is not used
by that AU.

## Known limits to carry into the closeout

- The `fdin` high-TPH crown closure is not digitised.
- The `fdip` top-height labels were offset in the source PDF.
- The lodgepole diagrams store only the printed 6–34 m/6–30 m top-height labels,
  not the unlabelled intermediate dotted curves.
- The FVS PLI path starts above the observed mean tree volume; see
  `ws4/sdmd/data/pilot-tsa23-idfdk3-pli/SOURCE.md`.
- No initial volume has been supplied for either pilot AU.
