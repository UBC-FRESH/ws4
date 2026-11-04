# P131 profile time budget overrides generations

Date: 2026-11-03
Status: complete

## Root cause

The profile Run action always sent the `profile-generations` value (default
5,000). The wall-clock field was passed as a maximum as well, so a 5,000
generation run finished in about 18 seconds even when the user requested a
minute. The time field looked like a minimum budget but behaved only as a cap.

## Change

- A valid `HH:MM:SS` time budget is authoritative for GPU profile runs.
- In that case the request uses the API’s maximum generation cap
  (`1,000,000`), allowing the wall-clock limit to stop the run.
- Without a time budget, the profile generation count remains authoritative.

## Verification

A 3-second profile run sent:

```json
{"generations":1000000,"time_limit":"00:00:03"}
```

and produced 1,269 generations with `status: stopped` and exact replay `true`.
