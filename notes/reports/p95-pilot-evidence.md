# P95 pilot evidence report

Phase: P95 SDMD pilot digitisation and trajectory evidence
Parent issue: #680
Branch: `feature/p95-sdmd-pilot`
Evidence head: `999ebbe`
Date: 2026-11-02
Status: method-only evidence. The pilot is not ready for phase closeout.

This report records what the pilot data support and what they do not. It does not
claim a real AU projection.

## 1. What is in the pilot

| Item | Current state | Evidence |
| --- | --- | --- |
| Diagram | `fdin` natural and `fdip` planted, provisional | `ws4/sdmd/data/sdmd/idf-dk3-fdi-natural.json`, `idf-dk3-fdi-planted.json` |
| Trajectories | Four FVS-BC paths from synthetic tree lists | `ws4/sdmd/data/trajectories/AU-*/REG-*.json` |
| Observed points | Synthetic fixture, labelled `psp` or `synthetic` | `tests/fixtures/sdmd/sdmd_points.csv` |
| PSP check | Gate 1 requires a reviewed PSP plot at each point age and a tree list | `ws4/sdmd/validation.py` |
| Solver guard | Per-AU entry cap and interval enforced in the optimizer | `ws4/opt/constraints.py`, `ws4/sdmd/solver.py` |

The diagram review status is `provisional`. The four FVS runs record
`fresh-fvsbc` (FVS-BC), synthetic tree lists, eight ten-year cycles, and `RANNSEED 1`.
They are method runs, not AU projections.

## 2. The eight gates

Command:

```bash
ws4 sdmd validate --sdmd-dir <pilot-store>
```

| Gate | `AU-IDFdk3-FDI` | `AU-IDFdk3-PLI` |
| --- | --- | --- |
| plot-support | warn: 5 plots, 4 PSP-backed, 1 synthetic | pass: 5 plots, 5 PSP-backed |
| density-plausibility | pass: within 0.1% | pass: within 0.1% |
| sdmd-fit | warn: diagram is provisional | warn: diagram is provisional |
| trajectory-plausibility | warn: at least one path leaves the envelope | warn: at least one path leaves the envelope |
| initial-volume | warn: no initial volume supplied | warn: no initial volume supplied |
| regime-completeness | pass: 7 regimes | pass: 6 regimes |
| solver-option-reduction | pass: 7 → 6 regimes, 11 → 7 entries | pass: 6 → 5 regimes, 7 → 6 entries |
| ui-payload-contract | pass | pass |
| Overall | warn | warn |

All four stored trajectories are assessed as `extrapolated` against the
PSP-backed envelope. That is a finding about the synthetic input, not a physical
refusal: every path passes the monotonicity check.

## 3. Public PSP check of the pilot AU definition

The pilot fixture names TSA-24 and BEC `IDFdk3`. The public FAIB PSP header
(Open Government Licence - British Columbia) does not support that combination:

| TSA | PSP sites | BEC zones |
| --- | --- | --- |
| 24 | 558 | SBS 517, ESSF 23, ICH 13, SBPS 5 |
| 23 | 200 | IDF 162, SBS 15, SBPS 10, ESSF 7, ICH 6 |

TSA 24 has **no IDFdk3 PSP sites** in the public header. TSA 23 has **145**
`IDFdk3` sites. The pilot AU is therefore a synthetic label, not a real
BEC/TSA/species unit. Replacing the fixture with a real PSP extract requires a
real AU definition first.

Source: Forest Analysis and Inventory Branch, *Forest Inventory Ground Plot Data
and Interactive Map*, BC Data Catalogue,
`https://catalogue.data.gov.bc.ca/dataset/824e684b-4114-4a05-a490-aa56332b57f4`,
Open Government Licence - British Columbia. Header file retrieved 2026-11-02 and
counted locally; no third-party rows are copied into this report.

## 4. What the evidence supports

- The schema, ingestion, diagram, regime, API, UI, filter, and optimizer guard
  run end to end on a two-AU fixture.
- The solver removes forbidden regimes and entries: 7 → 6 regimes and 11 → 7
  entries for FDI; 6 → 5 regimes and 7 → 6 entries for PLI.
- The optimizer rejects a move that would exceed the per-AU cap or interval and
  records the rejection in `constraint_stats.sdmd_rejected`.
- A PSP point without a reviewed PSP plot or tree list fails the evidence layer;
  a synthetic point warns and is excluded from the envelope.

## 5. What the evidence does not support

- A real AU yield projection, a real initial volume, or a real regime ranking.
- A reviewed SDMD: both diagrams are provisional.
- A real PSP envelope: the points are fixtures, and the pilot TSA/BEC label does
  not match the public PSP population.
- A FVS calibration: the tree lists are synthetic and the site code is a single
  FVS code, not a measured site series.

## 6. Recommended next steps

1. Define a real pilot AU on a BEC/TSA/species combination that exists in the
   public PSP population. `TSA 23 / IDFdk3` is the first candidate for FDI.
2. Build the PSP extract for that AU, with plot and tree provenance, and replace
   the fixture points.
3. Review the `fdin` and `fdip` curves and set `review.status` to `reviewed`.
4. Re-run FVS-BC with the real tree lists, then store the paths with their source
   metadata.
5. Re-run the gates and update this report. Close P95.1, P95.2, and P95.4 only
   after that evidence exists.

## 7. Verification

- `ws4 sdmd validate` on the pilot store: both AUs `warn`.
- `python scripts/dashboard.py`: `OVERALL: GREEN` on all seven gates at the
  evidence head.
- `tests/test_sdmd_validation.py`: 13 passed.
- `tests/test_sdmd_solver.py`: 14 passed.
