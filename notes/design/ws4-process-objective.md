# Process schedule objective adapter

Status: implemented (P191)
Phase: P191 (#1130)
Date: 2026-11-13
Related: `notes/design/ws4-process-schedule-evaluation.md`, `ws4/opt/objective.py`

## 1. Purpose

P190 evaluates a schedule through the process engine but reports accounts only. P191 prices
those final accounts with the existing weighted-goal objective. This is the adapter the
optimizer will need before it can call the process evaluator for candidate schedules.

It is not the optimizer integration yet.

## 2. Compatibility rules

The final evaluation accounts are a **level** view at the final offset. A target is accepted
only when:

- it is a `Target`;
- it is a level target, not a flow target;
- its aggregation is `single`;
- it is not a snapshot period (period 0);
- its account is not accumulating (`product.` prefix);
- its account exists in the final accounts;
- its period ends at the final offset.

Unsupported forms fail loudly rather than reading a silent zero.

## 3. Outputs

`ProcessScheduleEvaluation` now carries:

- `targets`: the validated targets;
- `objective`: the total weighted penalty, or None when no targets were supplied;
- `terms`: one penalty per target.

The JSON summary and artifact include `objective`, `target_terms`, and `target_accounts`.

## 4. Exact test values

The 3 × 3 grid, one clearcut over fragments 1 and 2, and a one-year horizon produce a
`harvest.area_ha_total` of 20 ha.

- Target minimum 30 ha: objective **10.0**, terms **(10.0,)**.
- Target minimum 20 ha: objective **0.0**, terms **(0.0,)**.

Rejected cases include a period ending beyond the horizon, a flow target, a `product.` account,
a risk aggregation, a snapshot period, and an unknown account.

## 5. Limits

- Final-account level targets only; multi-period and flow objectives are unsupported.
- The adapter does not run a search or replace the optimizer's account overlay.
- The volume bridge and harvest semantics remain provisional.
- The accounts are a reporting view, not the compiled management contract.
