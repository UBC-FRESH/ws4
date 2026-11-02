# P103 profile-aware web runs

Date: 2026-11-02
Status: complete; PR #717

## Change

The web application can now launch a named scenario profile on the factorized GPU
population.

- `ws4.opt.gpu_profile_run` is a bounded worker subprocess.
- It reuses the resident GPU population, factorized vector cache, effect table, candidates,
  and seed schedule.
- It writes `telemetry.jsonl`, `control.json`, `schedule.csv`, and `summary.json` in the
  existing web-run layout.
- `POST /api/runs` accepts `profile`, `generations`, and `population`; CPU runs are
  unchanged.
- The Targets tab has **Generations** and **Run profile** controls beside the profile
  selector.

## Smoke

The base profile ran with population 8 and zero generations:

- exact replay: **true**
- factorized target cell: `(199, feature.Yield.managed.Total)`
- worker search loop: 30.4 s
- wall including model/cache load: 56.2 s

The smoke is a plumbing check, not a policy result.

## Limits

- The worker does not write `account_values.csv`, so run reports and live map schedule
  events are not available for profile runs yet.
- Live progress and objective status are available through the existing telemetry/status
  endpoints.
- A profile must provide table, factorized archive/cache, cache directory, and seed
  schedule paths.
- The remote demo origin still has to pull `main` and restart its service.

## Pull request

PR #717 contains the worker, API, UI controls, tests, and docs. The instance profile YAML and archive are outside git.
