# Phase close-out report: P34 Search launcher

Phase: P34, Search launcher
Parent issue: #265
Pull requests: #271 (P34.1), this P34.2 PR
Evidence head: the P34.2 branch head
Date: 2026-10-25
Status: merged and closed on 2026-10-25 as `9cdae7`.

## Recommendation

1. Squash-merge the P34.2 pull request and delete `feature/p34-search-launch`.
2. Close task #272 and parent #265.
3. Proceed to the next web UI phase; no new phase is launched by this report.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A launcher writes a directory under the runs root and returns its id. | P34.1; c5 portfolio at `portfolio-20261025-063941`. | Met |
| Status reports running, done, failed, or stopped. | P34.2 stop/status endpoint; test covers stopping/stopped. | Met |
| A running job can be cancelled from the Search tab. | Stop control in the jobs list; endpoint terminates the process group. | Met |
| The job list stays bounded. | `SEARCH_JOB_LIMIT=20`; test with a limit of one. | Met |
| `python scripts/dashboard.py` is green. | Green at the report commit. | Met |

## 2. Deviations

- P34.1 merged before the phase close-out; the parent was reopened and this report covers both tasks.
- The launcher runs the CLI scripts in subprocesses; it does not reimplement search.
- Stopping sends SIGTERM to the process group and reports the final return code; it does not
  guarantee cleanup of files an interrupted script had started.

## 3. Verification

- c5 portfolio launch completed and appeared in the artifact list.
- Endpoint tests cover launch, running listing, stop/stopped, and the bounded list.
- Dashboard green.
