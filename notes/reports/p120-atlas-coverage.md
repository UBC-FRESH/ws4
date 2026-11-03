# P120 SDMD atlas coverage

Date: 2026-11-03
Source catalog: `ws4/sdmd/data/sdmd/source_catalog.json`
Evidence: 14 digitised diagrams, all pass `validate_diagram`.

## Diagram set

| Source | Diagram ID | Species | Origin | Curves | Review |
| --- | --- | --- | --- | --- | --- |
| `fdin` | `idf-dk3-fdi-natural` | FDI | natural | 23 | reviewed |
| `fdip` | `idf-dk3-fdi-planted` | FDI | planted | 22 | reviewed |
| `pln` | `idf-dk3-pli-natural` | PLI | natural | 18 | reviewed |
| `plp` | `idf-dk3-pli-planted` | PLI | planted | 17 | reviewed |
| `fdcn` | `cdf-cwh-fdc-natural` | FDC | natural | 24 | provisional |
| `fdcp` | `cdf-cwh-fdc-planted` | FDC | planted | 23 | provisional |
| `ssn` | `cdf-cwh-ss-natural` | SS | natural | 24 | provisional |
| `ssp` | `cdf-cwh-ss-planted` | SS | planted | 20 | provisional |
| `hwn` | `cwh-hw-natural` | HW | natural | 25 | provisional |
| `hwp` | `cwh-hw-planted` | HW | planted | 22 | provisional |
| `cwn` | `cwh-cw-natural` | CW | natural | 25 | provisional |
| `cwp` | `cwh-cw-planted` | CW | planted | 24 | provisional |
| `swn` | `sbs-sw-natural` | SW | natural | 21 | provisional |
| `swp` | `sbs-sw-planted` | SW | planted | 20 | provisional |

Reviewed: 4. Provisional: 10. Every catalogued PDF has a stored JSON whose
`source_sha256` matches the catalog entry.

## BEC coverage

The BEC table is an inference, not a per-variant diagram set. The counts below
are the number of BEC variant rows where each source is listed as main or rare:

| Source | Main rows | Rare rows |
| --- | --- | --- |
| `pln` / `plp` | 175 | 43 |
| `fdin` / `fdip` | 96 | 89 |
| `cwn` / `cwp` | 78 | 120 |
| `swn` / `swp` | 60 | 143 |
| `hwn` / `hwp` | 56 | 49 |
| `ssn` / `ssp` | 28 | 38 |
| `fdcn` / `fdcp` | 22 | 0 |

The 229-row `bec_variants.csv` remains the coverage table. The CCISS crosswalk has
30 WS4-only and 34 CCISS-only labels; that difference is unresolved and is not
hidden by the atlas.

## Provenance

- Every diagram entry names the source PDF, URL, SHA-256, version, licence, and
  review status.
- The four reviewed diagrams were signed off in P104.
- The ten provisional diagrams have a curve note in `notes/reference/` and a
  figrecover overlay used during digitisation.
- Crown closure is a raster trace for the ten provisional diagrams; the four
  reviewed Interior Douglas-fir and lodgepole pine diagrams use vector closure
  curves.

## Limits

- The atlas is species/origin-level. It is not a site-series or BEC-variant
  diagram atlas.
- The provisional crown-closure traces are approximate.
- Planted top-height labels are offset in the source PDFs; those assignments are
  the first review item.
- The BEC rows are inferred from the BC Tree Species Compendium and require a
  forester's confirmation for an AU.
- The atlas is not calibrated to AFRF and is not a growth model.

## Verification

```bash
python -m pytest tests/test_sdmd_diagram.py tests/test_sdmd_sources.py -q
python scripts/check_workflow.py
python scripts/dashboard.py
```

At the evidence head: 68 focused tests pass, validator 0 errors, dashboard
`OVERALL: GREEN`.
