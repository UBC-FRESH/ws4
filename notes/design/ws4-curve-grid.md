# Shared age-grid curve table (performance spike)

Status: **spike**, not a phase deliverable. Branch `spike/shared-grid`, off P6 head `42a3ca1`.
Checkpoint tag `p6-sharedgrid-checkpoint` (green) for one-command rollback.

Owner: whoever runs the spike. This note is the plan of record; keep it current as the work proceeds
(record surprises and plan adjustments here, not only in commits).

Related: `notes/design/ws4-performance.md` (the phase plan and the thread/vectorization negative
results), `notes/performance.md` (measurements), ADR 0002 (the compiled dataset is the contract), ADR
0008 (native kernels for profiled bottlenecks — this spike is the *alternative* to kernels).

## 1. Motivation and evidence

The base simulate is ~95% `account_values` (measured: 0.358 s of 0.376 s over 30 years on C5). That
function currently evaluates the feature curves by looping over the ~1 114 curves referenced by the
join and calling `numpy.interp` per curve group (5.8 ms per year). Two earlier attempts failed:

| Attempt | Result |
| --- | ---: |
| Threads over the curve loop (4/8/16) | 0.35× / 0.29× / 0.23× (GIL-bound, slower) |
| One vectorized multi-curve interpolation (disjoint-domain `searchsorted`) | 0.32× (slower) |

So neither threads nor a generic vectorization helps. This spike tests a **data-layout** change
instead.

## 2. Hypothesis

Every offset that reaches curve evaluation is an **integer age** (fragment `age` + years; product and
feature offsets alike). If every curve breakpoint is also an integer, then a curve can be
**precomputed at every integer age once**, and evaluation becomes a **2-D gather** off a table. That
removes the per-curve `interp` loop and all per-call Python overhead.

## 3. Data analysis (C5, measured 2026-10-16)

| Property | Value |
| --- | --- |
| Distinct curves | 1 801 |
| Distinct x grids | 335 |
| Curve x values | **all integers**, range 0…842 |
| Distinct x values | 557 (min positive gap 1.0) |
| Table (1 801 curves × 843 ages) | 12.15 MB float64, 6.07 MB float32 |

Conclusion: a per-age table is exact here (integer breakpoints) and small.

## 4. Design

- **`CurveTable`** (in `ws4/sim/curve.py`, alongside the existing `curve_value`):
  - `table`: `ndarray[float64]`, shape `(n_curves, age_max + 1)`, `table[row, a] = curve(a)`.
  - `row_of`: `dict[int, int]` — curve id → row.
  - `age_max`: the largest age the table covers (`int(max curve x)`), clamp above it.
  - built from the curves table: for each curve, `np.interp(arange(age_max+1), xs, ys)` (clamping
    matches `np.interp`).
  - `value(curve_id, x)`: scalar; an integer `x` in range is `table[row, int(x)]`; above `age_max`
    clamps; a non-integer or unknown curve falls back to the existing `curve_value`.
  - `values(rows, ages)`: vectorized `table[rows, np.clip(ages, 0, age_max)]`; the fast path used by
    `account_values`, `block_criteria`, and `block_trajectory`.
- **Simulator** builds the table in `__init__` (replacing the `_curves` group-by dict, or beside it
  for the fallback). The fragment-to-feature join stores `pair_row` (the curve's table row) instead of
  per-curve groups, so `account_values` is one gather plus `np.bincount`.
- **Scope of change:** `ws4/sim/engine.py` (build + `account_values` + `_curve_value` +
  `block_criteria` + `block_trajectory`), `ws4/sim/curve.py` (`CurveTable`). The route model does not
  evaluate curves. The compiled dataset is unchanged (the table is derived, cached in memory).

## 5. Correctness plan

- Exactness: query ages are integers and breakpoints are integers, so the table reproduces
  `np.interp` exactly. Clamping above `age_max` matches `np.interp`.
- Parity tests: a new unit test compares `CurveTable.value`/`values` to `curve_value`/`np.interp` on
  the fixture and on a random subset, including single-point curves and out-of-range ages.
- The existing suite (simulator, prototype, optimizer, performance parity, acceptance) must pass
  **unchanged** — that is the primary gate.

## 6. Performance targets and outcome

| Metric | Before | Target | Achieved |
| --- | ---: | ---: | ---: |
| `account_values`, per year | ~11.9 ms | < 2 ms | **2.33 ms** (5.1×) |
| C5 base simulate, 30 years (warm) | 0.376 s | < 0.2 s | **0.095 s** (3.9×) |
| C5 base simulate, 30 years (cold, incl. join build) | 0.376 s | < 0.2 s | 0.266 s (the 0.13 s join rebuild dominates) |
| Construction | 0.52 s | < +50 MB | 0.57 s (+~0.05 s for the table; ~12 MB float64) |

The target is met on the warm path (the optimizer's case). On a **cold** simulate the fragment-to-
feature join rebuild (0.13 s) now dominates; that is separate from curves and is the next cold-path
candidate, not part of this spike.

## 7. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Non-integer x reaches evaluation | Fall back to `curve_value`; keep both paths parity-tested |
| Age above the table range | Clamp (same as `np.interp`); test the boundary |
| Memory on very large models | Table is `n_curves × (age_max+1)`; document the bound; consider float32 only if parity holds |
| Behavior drift | The whole existing suite is the gate; no dataset/schema change |
| The gather is not actually faster | Measure at M2 before wiring further; adjust or abandon here |

## 8. Milestones (each a commit; stop and record if a gate fails)

- **M1** `CurveTable` + unit tests (parity, boundaries, single-point curves). No wiring yet.
- **M2** wire `account_values` to the table; measure `account_values`/year and 30-y simulate on C5;
  parity via the existing performance/optimizer tests.
- **M3** wire `_curve_value` (treatments), `block_criteria`, `block_trajectory` (products) to the
  table; keep the `curve_value` fallback.
- **M4** docs (`notes/performance.md`, `docs/reference/performance.rst`), the guardrail test, and a
  checkpoint comparison vs `p6-sharedgrid-checkpoint`.

## 9. Decision and rollback

- **Adopt** if the 30-year base simulate drops below 0.2 s with parity green.
- **Adjust** if only `account_values` improves but the gather is near the loop's cost: record why and
  keep the smallest change that helps, or abandon.
- **Abandon** if it is not clearly faster or if parity cannot hold: `git checkout feature/p6-performance`
  (or `git reset --hard p6-sharedgrid-checkpoint`); the spike lives only on `spike/shared-grid`.

**Decision: adopt.** The warm 30-year base simulate is 0.095 s (3.9×) and `account_values` is 5.1×,
with the full suite and the curve-table parity tests green. The gain is a data-layout change (an
integer-age table), not a kernel or threads. The cold-path join rebuild is the next candidate and is
recorded for a follow-up. The spike can be merged into `feature/p6-performance` or abandoned; the
checkpoint tag `p6-sharedgrid-checkpoint` gives a clean rollback either way.

## 10. Log (updated as the work proceeds)

- 2026-10-16: plan written; reconnaissance complete (section 3). Starting M1.
- 2026-10-16 M1: `CurveTable` + 8 unit tests (parity, clamp, single-point, non-integer, empty). Green.
  Note: I twice committed with the format gate red by chaining the commit on a pipe; fixed both.
- 2026-10-16 M2: wired `account_values` to the table gather.
  - Surprise: the build with per-curve masking was slow (construction 0.52 → 1.41 s). **Adjustment:**
    build the table from one `sort_values(["curve_id","x"])` and slice groups (construction back to
    ~0.57 s).
  - Surprise: `account_values` measured against the *isolated* loop was misleading; the real function
    went from ~11.9 ms/yr to **2.33 ms/yr (5.1×)**.
  - Surprise (insight): the empty-schedule simulate was dominated not by curve evaluation but by a
    **join rebuild (0.13 s)** triggered on every `reset()`. **Adjustment:** `reset()` now invalidates
    the join only when the tracks actually changed. Cold 30-y simulate 0.376 → 0.266 s; warm
    0.376 → **0.095 s**.
  - One existing test encoded the old mechanism (`np.interp` once per curve); updated to the new
    invariant (no interpolation at evaluation time) — the plan's §5 gate is behavior, not mechanism.
- 2026-10-16 M3: wired `_curve_value` (treatments), `_criteria_join`/`block_criteria`, and (via
  `_curve_value`) `block_trajectory` to the table, keeping the `curve_value` fallback for non-integer
  ages. Spatial components were already vectorized, so they are unchanged (edge 0.26 s/3 y, patch
  0.17 s/1 y). Green.
  - Insight: with curve evaluation cheap, the **join rebuild (0.13 s)** is now the largest fixed cost
    of a cold simulate. Out of scope here (it is the fragment-to-feature join, not curves); recorded as
    the next cold-path candidate.
- 2026-10-16 M4: docs and guardrails (below). Decision in section 9.
