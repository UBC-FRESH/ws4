# Phase close-out report: P103 SDMD pilot digitisation and trajectory evidence

Phase: P104 SDMD pilot digitisation and trajectory evidence (originally labelled P95, then P103; renumbered after phase-id collisions with #675 and #713)
Parent issue: #680
Branch: `feature/p104-sdmd-pilot`
Evidence head: `b521f39` (phase work); merge head `0bb0b4e`
Report commit: this metadata-only report update
Date: 2026-11-02
Status: approved and merged as `e5c4e9c` on 2026-11-03.

## Recommendation

Queue the pull request for `feature/p95-sdmd-pilot` into `main` and wait for the
maintainer's approval. Do not merge, tag, release, or change settings until that
approval is explicit.

After approval:

1. Squash-merge the pull request.
2. Delete the branch `feature/p95-sdmd-pilot`.
3. Close parent issue #680 with a closeout comment that cites the merge commit.
4. Launch the next phase only after the maintainer names it.

Settings changes: none. No tag, release, visibility, Pages, branch-protection, or
external account change is requested.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Four diagrams digitised and reviewed | `fdin`, `fdip`, `pln`, `plp`, all `reviewed` at `d9967f3`; review packet `notes/review/p95-curve-review.md` | met |
| Real PSP input for the pilot AUs | 11 public FAIB PSP points for each AU; `SOURCE.md` in both pilot stores | met with limits: 11-point extracts, not full inventories |
| Real FVS-BC paths | median-age clusters scaled to AU median TPH; `fresh-fvsbc` 0.20.0; two paths per AU | met with limits: one representative cluster per AU, not an AU-level tree list |
| PSP observed check | gate 1 requires a reviewed PSP plot and tree list; synthetic points warn and are excluded | met |
| Physical trajectory refusal | impossible density-and-volume steps refused by `validate_trajectory` | met |
| Extrapolated paths labelled | both trajectories assessed `extrapolated` against the observed envelope | met |
| Per-AU cap and zone rule in the solver | P95.3 closed; `sdmd_dir` guard tests and CLI hook | met |
| Eight gates on both pilot AUs | both `warn`; named reasons | met with limits: trajectory and initial-volume warnings |
| Option reduction recorded | FDI 7 → 6 regimes, 11 → 7 entries; PLI 7 → 6, 11 → 7 | met |
| Dashboard green | `python scripts/dashboard.py` at `b521f39` | met |
| CCISS species/BEC leads extracted | `tree_species.csv`, `species_traits.csv`, `idfdk3_stocking.csv`, `idfdk3_suitability.csv`, `idfdk3_sibec.csv`, `bec_crosswalk.csv` | met |

## 2. Workflow compliance

- Parent issue #680 was created before the phase work; branch `feature/p95-sdmd-pilot`.
- Child issues #681-#684 carry the phase tasks. #681, #682, and #683 are closed;
  #684 closes with this report.
- Every implementation commit starts with a P95 task identifier.
- Roadmap, changelog, notes, and issue bodies are in step.
- PR will be queued, not merged. Merge waits for the maintainer's approval.

## 3. Gate evidence

Both pilot AUs run all eight gates. `sdmd-fit` now passes because all four
diagrams are reviewed.

| Gate | FDI | PLI |
| --- | --- | --- |
| plot-support | pass: 11 PSP-backed, 0 synthetic | pass: 11 PSP-backed, 0 synthetic |
| density-plausibility | pass: within 0.1% | pass: within 0.2% |
| sdmd-fit | pass: reviewed diagram contains every point | pass: reviewed diagram contains every point |
| trajectory-plausibility | warn: at least one path leaves the envelope | warn: at least one path leaves the envelope |
| initial-volume | warn: none supplied | warn: none supplied |
| regime-completeness | pass: 7 regimes | pass: 7 regimes |
| solver-option-reduction | pass: 7 → 6 regimes, 11 → 7 entries | pass: 7 → 6 regimes, 11 → 7 entries |
| ui-payload-contract | pass | pass |
| Overall | warn | warn |

## 4. Real pilot evidence

### `AU-IDFdk3-TSA23-FDI`

- 11 reviewed public FAIB PSP clusters, TSA 23 / IDFdk3 / FD-leading, ages 52-139.
- Observed points: 4 competition-zone values and 7 density-management values.
- Diagram: reviewed `fdin` natural Interior Douglas-fir.
- FVS: median-age cluster `4025005-PSP1` (age 89), tree counts scaled by 0.864 to
  the AU median TPH; `fresh-fvsbc` 0.20.0, `SITECODE FD,60`, eight cycles.
- CT60: `THINBBA` at the first 10-year cycle, 60% basal-area removal. This is a
  first-entry treatment for an older stand, not a literal age-60 entry.
- Both paths are `extrapolated` against the observed envelope.

### `AU-IDFdk3-TSA23-PLI`

- 11 reviewed public FAIB PSP clusters, TSA 23 / IDFdk3 / PL-leading, ages 20-120.
- Observed points span understocked, density-management, and competition zones.
- Diagram: reviewed `pln` natural lodgepole pine; `plp` planted is also stored.
- FVS: median-age cluster `4025096-PSP1` (age 62), tree counts scaled by 1.670 to
  the AU median TPH; `fresh-fvsbc` 0.20.0, `SITECODE PL,55`, eight cycles.
- CT60: `THINBBA` at the first 10-year cycle, 60% basal-area removal.
- Both paths are `extrapolated` against the observed envelope.

## 5. Option reduction

The SDMD constraint layer removes forbidden regimes and entries without emptying
the option space:

- `AU-IDFdk3-TSA23-FDI`: 7 → 6 regimes, 11 → 7 entries.
- `AU-IDFdk3-TSA23-PLI`: 7 → 6 regimes, 11 → 7 entries.

The optimizer guard rejects a move that would exceed the per-AU entry cap or
minimum interval and records the count in `constraint_stats.sdmd_rejected`.

## 6. Known limits

- The `fdin` crown-closure curve was truncated at 2,951 TPH in P104; P106.1
  later recovered the continuous high-TPH branch. The P104 record is historical.
- The FVS paths use one representative cluster per AU, not a full AU-level tree
  list. The clusters are the median-age observations, scaled to AU median TPH.
- CT60 is applied at the first projection cycle for the older stands; the scenario
  is a first-entry 60% removal, not a literal age-60 entry.
- The PLI FVS path starts at mean tree volume 0.1708, above the observed 0.1238 for
  the source cluster. That is an input-volume mismatch, not an observed trajectory.
- No initial volume is supplied for either AU, so that gate warns.
- Both pilot extracts are 11-point samples, not full TSA 23 inventories.
- The CCISS crosswalk has 30 WS4-only and 34 CCISS-only BEC labels; it is a lead,
  not a resolved crosswalk.

## 7. Verification

Commands run at the evidence head:

```bash
python -m pytest tests/test_sdmd_diagram.py tests/test_sdmd_validation.py tests/test_sdmd_sources.py tests/test_sdmd_trajectories.py -q
ws4 sdmd validate --sdmd-dir ws4/sdmd/data/pilot-tsa23-idfdk3
ws4 sdmd validate --sdmd-dir ws4/sdmd/data/pilot-tsa23-idfdk3-pli
python scripts/check_workflow.py
python scripts/dashboard.py
```

Results:

- 100+ focused SDMD tests passed across the phase.
- Both pilot gates return `warn`, with the reasons in section 3.
- Workflow validator: 0 errors, 0 warnings.
- Dashboard: `OVERALL: GREEN` on all seven gates.

## 8. Pull request

PR #719 names the phase, the evidence head, the gate result, and the known
limits. It was squash-merged as `e5c4e9c` on 2026-11-03; the branch was deleted.
No tag, release, or settings change was made.
