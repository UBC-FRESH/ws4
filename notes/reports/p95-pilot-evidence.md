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
| Observed points | Synthetic fixture for the method AUs; 11 real public PSP points for `AU-IDFdk3-TSA23-FDI` | `tests/fixtures/sdmd/sdmd_points.csv`, `ws4/sdmd/data/pilot-tsa23-idfdk3/` |
| PSP check | Gate 1 requires a reviewed PSP plot at each point age and a tree list | `ws4/sdmd/validation.py` |
| Solver guard | Per-AU entry cap and interval enforced in the optimizer | `ws4/opt/constraints.py`, `ws4/sdmd/solver.py` |

The diagram review status is `provisional`. The four method FVS runs record
`fresh-fvsbc` (FVS-BC), synthetic tree lists, eight ten-year cycles, and `RANNSEED 1`.
They are method runs, not AU projections. The real pilot AU below adds a public PSP
extract and two FVS runs from a real tree list.

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

## 2a. Real TSA 23 IDFdk3 pilot

The first real AU is `AU-IDFdk3-TSA23-FDI`, stored in
`ws4/sdmd/data/pilot-tsa23-idfdk3/`. It uses 11 reviewed public PSP cluster visits,
ages 52 to 139, selected from TSA 23 / IDFdk3 / FD-leading sites. The source and
field derivation are in the store's `SOURCE.md`.

| Gate | Result |
| --- | --- |
| plot-support | pass: 11 plots, 11 PSP-backed, 0 synthetic |
| density-plausibility | pass: within 0.1% |
| sdmd-fit | pass: reviewed diagram |
| trajectory-plausibility | warn: both paths leave the observed envelope |
| initial-volume | warn: no initial volume supplied |
| regime-completeness | pass: 7 regimes |
| solver-option-reduction | pass: 7 → 6 regimes, 11 → 7 entries |
| ui-payload-contract | pass |
| Overall | warn |

The FVS paths use the live trees of three clusters — `4024520-PSP2` (age 76),
`4025005-PSP1` (age 89), and `4024520-PSP4` (age 101) — each as a plot, scaled to
the AU median TPH. They use `fresh-fvsbc` 0.20.0, BC variant, `SITECODE FD,60`,
eight ten-year cycles, and `RANNSEED 1`. CT60 is `THINBBA` at the first 10-year
cycle with 60% basal-area removal. Both the untreated and CT60 paths
are stored as `provisional`; the CT60 path regenerates aspen after thinning, which is
the model's response rather than a recommendation.

## 2b. Real TSA 23 IDFdk3 lodgepole pine pilot

The second real AU is `AU-IDFdk3-TSA23-PLI`, stored in
`ws4/sdmd/data/pilot-tsa23-idfdk3-pli/`. It uses 11 reviewed public PSP cluster
visits, ages 20 to 120, selected from TSA 23 / IDFdk3 / PL-leading sites.

| Gate | Result |
| --- | --- |
| plot-support | pass: 11 plots, 11 PSP-backed, 0 synthetic |
| density-plausibility | pass: within 0.2% |
| sdmd-fit | warn: natural lodgepole pine diagram is provisional |
| trajectory-plausibility | warn: both paths leave the observed envelope |
| initial-volume | warn: no initial volume supplied |
| regime-completeness | pass: 7 regimes |
| solver-option-reduction | pass: 7 → 6 regimes, 11 → 7 entries |
| ui-payload-contract | pass |
| Overall | warn |

The diagram is the digitised natural lodgepole pine `pln` (version 1.20), not the
Interior Douglas-fir diagram. The FVS paths use five clusters — `4025305-PSP2` (age 50), `4025305-PSP3`
(age 61), `4025096-PSP1` (age 62), `4024449-PSP1` (age 73), and `4025245-PSP5`
(age 75) — each as a plot, `SITECODE PL,55`, eight cycles, and CT60 at the first
10-year cycle. Tree counts are scaled to the AU median TPH; the FVS start volume
remains above the observed value, which is named in the store's `SOURCE.md`.

## 3. Public PSP check of the pilot AU definition

The pilot fixture names TSA-24 and BEC `IDFdk3`. The public FAIB PSP header
(Open Government Licence - British Columbia) does not support that combination:

| TSA | PSP sites | BEC zones |
| --- | --- | --- |
| 24 | 558 | SBS 517, ESSF 23, ICH 13, SBPS 5 |
| 23 | 200 | IDF 162, SBS 15, SBPS 10, ESSF 7, ICH 6 |

TSA 24 has **no IDFdk3 PSP sites** in the public header. TSA 23 has **145**
`IDFdk3` sites. The original `TSA-24` pilot label is therefore synthetic, not a real
BEC/TSA/species unit. The real pilot AU is defined on TSA 23, and the synthetic
two-AU fixture remains for the method tests.

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

1. **Done:** define a real pilot AU on TSA 23 / IDFdk3 / FDI.
2. **Done:** build the PSP extract with plot and tree provenance and store it in
   `ws4/sdmd/data/pilot-tsa23-idfdk3/`.
3. Review the `fdin` and `fdip` curves and set `review.status` to `reviewed`.
4. **Partial:** run FVS-BC from the real tree list. One cluster is done; an
   AU-level tree list or a documented representative stand is still needed.
5. Re-run the gates, update this report, and close P95.1, P95.2, and P95.4 only
   after the review and the representative FVS evidence exist.

## 7. Verification

- `ws4 sdmd validate` on the pilot store: both AUs `warn`.
- `python scripts/dashboard.py`: `OVERALL: GREEN` on all seven gates at the
  evidence head.
- `tests/test_sdmd_validation.py`: 15 passed, including the real TSA 23 pilot.
- `tests/test_sdmd_solver.py`: 14 passed.
