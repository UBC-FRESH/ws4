# P143 web UI trust and cleanup

Date: 2026-11-07
Status: active
Branch: `feature/p143-web-trust`
Parent issue: #849
Task issue: #850

## Findings

- The state-cache fingerprint omitted the target and initial-schedule files.
- Portfolio artifacts were sorted by directory name; the UI could default to an
  older, failed artifact.
- Portfolio artifact records carried no member/front/failure metadata.
- Promoted-run Plan still showed live target rows.
- Profile files for TSA27/TSA29 still pointed at pre-stock90 targets.

## P143.1

- `search_artifacts` now returns `saved_utc`, `members`, `front_size`, `failures`,
  and `usable`.
- Artifacts sort newest first.
- The Pareto selector defaults to the newest usable artifact and labels member/front
  counts and failures.
- The portal state cache now keys on the active target file and initial schedule.
- Live TSA27 CPU state search completed after the cache-key change instead of raising
  `seed-state cache does not match the resident page shape`.

Remaining:

- Promoted Plan should show member target definitions read-only.
- Profile loading should not silently replace the generated stock90 default.
- TSA29 GPU validation with the stock guard.

## Verification

- Focused API/browser tests pass.
- Dashboard: `OVERALL: GREEN. Every gate passed.`
