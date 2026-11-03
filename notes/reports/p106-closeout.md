# Phase close-out report: P106 AU evidence depth

Phase: P106 AU evidence depth
Parent issue: #723
Branch: `feature/p106-au-evidence`
Evidence head: `6a07339`
Report commit: this metadata-only report update
Date: 2026-11-03
Status: queued for maintainer approval. Not merged.

## Recommendation

Queue the pull request for `feature/p106-au-evidence` into `main` and wait for the
maintainer's approval. Do not merge, tag, release, or change settings until that
approval is explicit.

After approval:

1. Squash-merge the pull request.
2. Delete the branch `feature/p106-au-evidence`.
3. Close parent issue #723 with a closeout comment that cites the merge commit.
4. The next phase is not launched until the maintainer names it.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| `fdin` crown closure complete or reviewed | continuous path from 210 to 9,996 TPH; test asserts it reaches above 9,000 TPH | met |
| AU-level FVS evidence, not one cluster | FDI 3-plot composite (ages 76/89/101); PLI 5-plot composite (ages 50-75) | met with a limit: multi-plot composite, not a statistical ensemble |
| Measured initial volume with provenance | FDI 213.41 m3/ha (limit 221.25); PLI 186.12 m3/ha (limit 252.69); `initial_volume.json` | met |
| Both pilot gates pass or warn only for named reasons | only `trajectory-plausibility` warns | met |
| Every remaining warning named and accepted | extrapolated paths in both stores | met |
| `python scripts/dashboard.py` green | dashboard green at the evidence head | met |

## 2. Workflow compliance

- Parent issue #723 and children #724-#727 created before the work.
- Branch `feature/p106-au-evidence`.
- Commits start with P106.
- #724, #725, and #726 are closed; #727 closes with this report.
- PR queued, not merged; merge waits for approval.

## 3. Gate evidence

| Gate | FDI | PLI |
| --- | --- | --- |
| plot-support | pass: 11 PSP-backed, 0 synthetic | pass: 11 PSP-backed, 0 synthetic |
| density-plausibility | pass: within 0.1% | pass: within 0.2% |
| sdmd-fit | pass: reviewed diagram | pass: reviewed diagram |
| trajectory-plausibility | warn: at least one path leaves the envelope | warn: at least one path leaves the envelope |
| initial-volume | pass: 213.41 m3/ha | pass: 186.12 m3/ha |
| regime-completeness | pass: 7 regimes | pass: 7 regimes |
| solver-option-reduction | pass: 7 → 6 regimes, 11 → 7 entries | pass: 7 → 6 regimes, 11 → 7 entries |
| ui-payload-contract | pass | pass |
| Overall | warn | warn |

## 4. FVS evidence

### FDI

Three plots: `4024520-PSP2` (age 76), `4025005-PSP1` (age 89), and
`4024520-PSP4` (age 101). Tree counts are scaled by 0.3583 to the AU median TPH
of 1,063. The first composite point is 1,173.75 TPH at 0.1750 mean tree volume.

### PLI

Five plots: `4025305-PSP2` (50), `4025305-PSP3` (61), `4025096-PSP1` (62),
`4024449-PSP1` (73), and `4025245-PSP5` (75). Tree counts are scaled by 0.3067 to
the AU median TPH of 1,979. The first composite point is 1,984.26 TPH at 0.1318
mean tree volume.

Both runs use `fresh-fvsbc` 0.20.0, the BC variant, eight cycles, and `RANNSEED 1`.
CT60 is `THINBBA` at the first 10-year cycle with 60% basal-area removal.

## 5. Measured initial volume

The optional `initial_volume.json` records the measured value, its evidence limit,
the source, and the review status. `SdmdStore` validates the AU, values, source,
and status; the AU payload exposes it; the gate uses it when no CLI override is
supplied.

- FDI: 213.41 m3/ha, limit 221.25, median of the three representative clusters.
- PLI: 186.12 m3/ha, limit 252.69, median of the five representative clusters.

## 6. Known limits

- The FVS evidence is a multi-plot composite with different plot ages, not a
  statistical ensemble.
- The stand summary is a composite, not a single even-aged stand.
- CT60 is a first-cycle treatment for the older stands, not a literal age-60 entry.
- Both trajectories remain extrapolated against the observed envelope.
- The PLI FVS start volume is above the observed value for its source clusters.
- The BEC crosswalk still has 30 WS4-only and 34 CCISS-only labels.

## 7. Verification

```bash
python -m pytest tests/test_sdmd_diagram.py tests/test_sdmd_validation.py tests/test_sdmd_api.py -q
ws4 sdmd validate --sdmd-dir ws4/sdmd/data/pilot-tsa23-idfdk3
ws4 sdmd validate --sdmd-dir ws4/sdmd/data/pilot-tsa23-idfdk3-pli
python scripts/check_workflow.py
python scripts/dashboard.py
```

Results:

- 82 focused diagram/validation/API tests passed.
- Both pilot gates return `warn`, only on trajectory plausibility.
- Workflow validator: 0 errors, 0 warnings.
- Dashboard: `OVERALL: GREEN`.

## 8. Pull request

The PR body names the phase, the evidence head, the gate result, and the known
limits. It is queued for approval. No merge, tag, release, or settings change is
performed by this report.
