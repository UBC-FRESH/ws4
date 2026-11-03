# P105 profile-run feedback

Date: 2026-11-03
Status: complete; PR #728

## Change

Profile-aware GPU runs now produce the normal web-run feedback:

- bounded schedule telemetry, with a full reset on the first event and changed blocks
  afterward;
- final schedule replay through the simulator, writing `account_values.csv`,
  `product_values.csv`, and `dataset.json`;
- exact summary remains the authority; profile run status completes only after replay.

## Smoke

Base profile, population 8, zero generations, replay enabled:

- exact_match: **true**
- account_values.csv: **present**
- schedule.csv: present
- telemetry: 4.7 MB (initial full schedule event dominates)
- wall: **86.1 s**
- worker search loop: 30.4 s

The replay adds about 30 s for this small run and writes the standard account/product
artefacts.

## Limits

- Target telemetry events are not emitted by the profile worker yet.
- The first schedule event carries the full 208,255-block schedule; later events are diffs.
- The remote origin still needs `main` pulled and the service restarted.

## Pull request

PR #728 contains the schedule feedback, final replay, tests, and docs.
