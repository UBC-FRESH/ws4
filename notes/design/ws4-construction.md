# Faster simulator construction (performance spike)

Status: **spike**. Branch `spike/construction`, off P6 head `7e5c8db`. Checkpoint tag
`p6-construction-checkpoint` for one-command rollback.

Related: `notes/design/ws4-curve-grid.md` (the age table), `notes/performance.md`.

## 1. Motivation and evidence

`Simulator.from_dataset` construction is ~0.57 s (1.12 s under the profiler). cProfile on the C5 sample:

| Hot spot | Cost |
| --- | ---: |
| `pandas.sort_values` (3 603 calls) | 0.59 s cumulative |
| `_as_int` (56 177 calls) | 0.03 s |
| parquet reads | small |

`_curves` (a per-curve `group.sort_values("x")` for x and again for y: 2 × 1 801 sorts) is the bulk.
It was built for the per-curve interpolation, but after the age table it is used **only** as the
non-integer-age fallback in `_curve_value` — and every internal offset is an integer, so the fallback
is effectively dead code.

## 2. Hypothesis

A non-integer age is still served exactly by the age table: the curve is linear between integer
breakpoints, so a query at `x` is `table[a] + frac * (table[a+1] - table[a])` with `a = floor(x)`, and
clamping below 0 / above `age_max`. So `_curves` can be dropped entirely, removing its 0.59 s of sorts.

## 3. Design

- Add `CurveTable.value(curve_id, x) -> float`: the integer fast path is `table[row, x]`; a non-integer
  `x` interpolates between the bracketing integer columns; `x <= 0` and `x >= age_max` clamp; an absent
  curve returns `0.0`.
- `Simulator._curve_value` delegates to `CurveTable.value`.
- Remove `Simulator._curves` (the dict of per-curve sorted x/y arrays) and the fallback that used it.
- Keep the public `ws4.sim.curve.curve_value` (used by tests and callers) unchanged.

## 4. Correctness plan

- New unit test: `CurveTable.value` equals `curve_value` for integer **and** non-integer ages on the
  fixture's curves, including clamping and single-point curves.
- The existing suite is the gate; `_curve_value` results must be unchanged for all internal (integer)
  ages.

## 5. Targets

| Metric | Before | Target |
| --- | ---: | ---: |
| Simulator construction (C5) | ~0.57 s | < 0.35 s |

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| A caller relies on `_curves` | It is private; only `_curve_value` used it |
| Non-integer ages differ | `CurveTable.value` handles them; parity test vs `curve_value` |
| Clamping differs from `np.interp` | Explicit clamp at 0/age_max; tested |

## 7. Milestones

- **M1** `CurveTable.value` + parity test; drop `_curves`; full suite green; measure construction.
- **M2** A/B vs `p6-construction-checkpoint`; docs and decision.

Out of scope (noted): lazy table building for models with unused curves; parallel parquet reads (~2%
of construction after this change).

## 8. Decision and rollback

- **Adopt** if construction drops below 0.35 s with the suite green.
- **Abandon** otherwise: `git checkout feature/p6-performance`; the spike lives only on
  `spike/construction`.

## 9. Log

- 2026-10-16: plan written; profiling done (section 1). Starting M1.
- 2026-10-16 M1: added `CurveTable.value` (exact integer ages; linear between them; clamp; absent →
  0.0), made `_curve_value` delegate to it, and **removed `_curves`** (the per-curve sorted x/y dict).
  The only user was the non-integer fallback, now served by the table. Full suite green.
- 2026-10-16 M2 A/B vs `p6-construction-checkpoint` (clean tree; committed first):

  | Metric | Checkpoint | Spike | Speedup |
  | --- | ---: | ---: | ---: |
  | Simulator construction (C5) | ~0.55 s | **~0.15 s** | ~3.7× |

  **Decision: adopt.** Construction is well under the 0.35 s target with the suite green. The result
  is a deletion (less code, no new dependency), so the risk is low. Out of scope and unchanged: lazy
  table building for unused curves; parallel parquet reads (~2% of construction now).
