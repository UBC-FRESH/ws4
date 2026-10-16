# Incremental route accounts in the objective (performance spike)

Status: **spike**. Branch `spike/inc-route-accounts`, off P6 head `9c39e57`. Checkpoint tag
`p6-routeinc-checkpoint` for one-command rollback.

Related: `notes/design/ws4-performance.md` (WP4 incremental objective), `notes/performance.md`.

## 1. Motivation and evidence

The incremental objective (P6.4) makes feature-account evaluations ~7 ms, but it is disabled when a
**route account** is configured, so route-target runs fall back to a full simulation every evaluation
(~1.2 s on C5). Route accounts are the common way to set mill quotas and haul-cost targets, so this is
the largest remaining objective-path cost.

## 2. Hypothesis

Route accounts are additive over blocks: each block's produced products are routed independently, and
the ledger's haul, maintenance, and volume totals are per-record sums. So a route account value is a
per-block delta, exactly like a feature account — **except build cost**, which is charged once per
segment across the whole schedule (`RouteCostLedger._built`) and is therefore order-dependent and not
additive.

## 3. Design

- **Simulator** gains `block_route_accounts(block_id, treatment, year, years, route_model,
  route_accounts)`: simulate one block's fragments in isolation (apply the treatment in `year`, produce
  its products at the pre-treatment offset, `RouteModel.assign` each product, record into a fresh
  `RouteCostLedger(collect=False)`), then return the ledger's account values as
  `{(year, account): value}`. Reusing the ledger guarantees the per-block sum matches the full path for
  the additive kinds.
- **Optimizer**:
  - eligibility: incremental when there are no edge elements and either no route accounts or every
    route account's ``kind`` is not ``build``;
  - `_incremental_values` adds per-block route deltas (cached per `(block, treatment, year)`) to the
    feature base and resolves duplicates on the combined values;
  - a configuration with a **build** route account keeps the full path (documented as the one
    non-additive kind).
- **Scope:** `ws4/sim/engine.py` (the per-block route trajectory), `ws4/opt/engine.py` (eligibility and
  the incremental combine). No change to the ledger, the route model, or the dataset.

## 4. Correctness plan

- Parity test: with a route config (`haul`, `volume`, `maintain` accounts), the incremental values must
  match the full simulation cell-for-cell on the fixture, across several schedules.
- The existing `test_the_optimizer_resolves_route_accounts` (haul + a duplicate) must keep passing; it
  now takes the incremental path.
- Determinism/reproducibility tests must keep passing unchanged.

## 5. Targets

| Metric | Before | Target |
| --- | ---: | ---: |
| One objective evaluation, route-target config (C5, 10 y) | ~1.2 s | < 50 ms |
| Feature-only evaluation | ~7 ms | unchanged |

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| Per-block route totals differ from the full ledger | Parity test cell-for-cell; the ledger code is shared |
| Build cost mis-attributed | `build` route accounts are excluded from incremental (full path) |
| Cache grows | Deltas are cached per *used* `(block, treatment, year)`, as with feature deltas |
| Eligibility logic regresses a config | The full path remains the fallback; tests cover both |

## 7. Milestones

- **M1** `Simulator.block_route_accounts` + a parity test for the method on the fixture.
- **M2** optimizer eligibility + combine; parity vs the full path; measure; A/B vs
  `p6-routeinc-checkpoint`; docs and decision.

## 8. Decision and rollback

- **Adopt** if a route-target evaluation drops below 50 ms with parity green.
- **Abandon** otherwise: `git checkout feature/p6-performance`; the spike lives only on
  `spike/inc-route-accounts`.

## 9. Log

- 2026-10-16: plan written. Starting M1.
