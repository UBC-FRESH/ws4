# P107 profile target telemetry

Date: 2026-11-03
Status: complete; PR #740

## Change

The GPU profile worker now emits target telemetry from the best genome in each generation,
at the same bounded cadence as schedule telemetry.

Each target event contains:

- active target index, account, period, year, flow kind, and value;
- the realized yearly series for every cell known to the resident population.

The web stream passes profile target events through directly, rather than recomputing them
against the service's possibly different targets file. **Run profile** now applies the
selected profile targets before launch, so the target table indices and live events align.

## Smoke

Base profile, population 8, zero generations:

- target values: **12**
- yearly series cells: **201**
- exact replay: **true**
- worker loop: 30.4 s
- wall including replay: 109.4 s

The event set is `step`, `targets`, `schedule`; the profile payload carries `profile: true`.

## Limits

- Target telemetry shares the bounded schedule cadence; it is not emitted every generation.
- Profile runs still do not populate the full report package; account values and product
  values are present.

## Pull request

PR #740 contains the target telemetry, web pass-through, UI target alignment, tests, and docs.
