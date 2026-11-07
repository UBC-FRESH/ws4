# P148 portfolio and promoted-run cleanup

Date: 2026-11-07
Status: active
Branch: `feature/p148-portfolio-cleanup`
Parent issue: #869
Task issue: #870

## Summary

Added guarded cleanup for the Search library:

- `DELETE /api/search/{name}` removes only a directory carrying `portfolio.json`;
- `DELETE /api/runs/{run}` removes only a derived run carrying
  `portfolio_source.json`;
- Search has **Delete** and **Clean failed** controls;
- Plan has **Delete promoted run** for the active promoted run;
- all deletion endpoints require `--allow-runs`.

Ordinary runs and non-portfolio search artifacts are refused.

## Verification

- API tests cover portfolio deletion, promoted-run deletion, ordinary-run refusal, and
  read-only refusal.
- Focused tests: 120 passed.
- Dashboard: `OVERALL: GREEN. Every gate passed.`

Live cleanup of the known failed probes follows deployment.
