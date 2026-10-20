# Phase close-out report: P17 Roads opened to the period

Phase: P17 Roads opened to the period
Parent issue: #145
Pull requests: #147 (P17.1–P17.4), #148 (P17.2 aggregation), #149 (P17.5 maintenance), and the
documentation pull request that adds this report
Evidence head: `9a1770b`, plus the report commit
Date: 2026-10-20
Status: closing.

## Recommendation

1. Close parent issue #145 with a closeout comment citing `6a8135c`, `118ac3d`, `c9c0911` and this
   report.
2. P18 (the web front end) is the next planned phase; no settings changes.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Routes use only roads opened in the period | `RouteNetwork.opened`, `open_segments`, `initial_open` / `route.initial_roads`; `tests/test_roads_opened.py` | met |
| A planned path is opened when a block first needs it, and charged once | six tests, including build-once and cache invalidation | met |
| The period accounting matches the reference | `LENGTH` distinct per period (0.77×), maintenance once per period (0.93×), volume 1.00× | met |
| The remaining gap is measured and named | build per metre identical; the reference builds 1.9× more; WS4 hauls 22% farther at 0.46× per unit-km; named as *road selection and haul routing* | met |

## 2. Workflow compliance

- Parent issue before the branch: #145.
- Commits start with task IDs; the dashboard is green on each merged head.
- The roadmap, changelog, reports and issue comments are in step.
- No settings changes.

## 3. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The first `LENGTH`/maintenance comparison was wrong by the period width | the report summed annual distinct lengths and annual maintenance instead of counting a period's set and charging once | both fixed (`118ac3d`, `c9c0911`); tests assert the period semantics |
| A red commit was pushed early | the push was chained after the gates and formatting failed | fixed on the branch; the head is green |
| The early `BUILTLENGTH` spike was not reproduced | WS4 builds less than the reference; a model-objective difference, not accounting | measured and named in `p17-tradeoff.md` |

## 4. CI evidence

| Head | Conclusion |
| --- | --- |
| `6a8135c` (#147) | green before and after merge |
| `118ac3d` (#148) | green |
| `c9c0911` (#149) | green |
| `9a1770b` (`main`) | green, CI and Docs |

## 5. Next phase

P18 (the graphical web front end) is planned on `feature/p18-web-frontend`, issue #146. Its design note
must land before UI code.

## 7. Decision

- [x] Approve as written.
