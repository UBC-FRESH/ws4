# Fast fragment-to-feature join rebuild (performance spike)

Status: **spike**. Branch `spike/join-rebuild`, off P6 head `6ff31d3`. Checkpoint tag
`p6-joinrebuild-checkpoint` for one-command rollback.

Related: `notes/design/ws4-curve-grid.md` (the prior spike; it left the join rebuild as the largest
fixed cost of a cold simulate), `notes/performance.md`.

## 1. Motivation and evidence

After the curve-table spike, a **cold** 30-year simulate is 0.261 s and the fragment-to-feature join
rebuild alone is **0.127 s** — ~half of it. cProfile attributes the time entirely to `np.unique`
(0.120 s cumulative, 0.109 s in `argsort`), and there are three `np.unique` calls:

| Call | Input | Cost |
| --- | --- | ---: |
| `np.unique(concatenate([fragment_track, feature_track]))` | ~36 k ints | small |
| `np.unique(pair_label_raw)` | **~210 k strings** | the bulk (~0.1 s) |
| (`feature` side of the expansion) | — | small |

The 210 k-element **string** sort is the target: labels are few (~40 distinct) and fixed, so coding
them with a small dictionary avoids the sort entirely.

## 2. Hypothesis

The feature side of the join is **fixed** (the `features` table never changes) and labels/tracks are
few and known, so almost everything can be precomputed once at construction; a rebuild then only needs
the fragment tracks, a `searchsorted` into a precomputed track table, and a vectorized expansion — no
per-rebuild `np.unique`, no string sort.

## 3. Design

At `Simulator.__init__`, precompute (feature side, once):

- `_track_ids`: sorted unique track ids from the tracks table (any track a fragment can be on).
- `_feature_order`, `_feature_per_code`, `_feature_starts` from `searchsorted(_track_ids, feature_track)`.
- `_sorted_curve`, `_sorted_row`, `_sorted_label_code`: the feature rows sorted by track code, with the
  curve's table row and the label code resolved once.
- `_labels`: the label names (all feature labels; a label whose track has no fragment contributes a
  zero row, which is harmless).

`_rebuild_join` (per rebuild) then:

1. `fragment_codes = np.searchsorted(_track_ids, fragments["track_id"])`
2. expansion (`repeat`/`cumsum`) into `feature_rows` (as today),
3. `_pair_frag`, `_pair_row`, `_pair_label` by gather off the precomputed sorted arrays.

No `np.unique`, no string sort.

## 4. Correctness plan

- The join is a pure function of the features table and the fragment tracks; the expansion is the same
  one as today, only with the feature side precomputed. Parity is asserted by the whole existing suite
  (simulator, prototype, optimizer, performance parity, acceptance) with **no change to results**.
- An added unit test asserts `account_values` matches the pre-spike values on the fixture (already
  covered) and that a rebuild after a track change gives the same result as a from-scratch simulator.

## 5. Targets

| Metric | Before | Target |
| --- | ---: | ---: |
| One join rebuild | 0.127 s | < 0.02 s |
| Cold 30-year simulate | 0.261 s | < 0.15 s |

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| A fragment track absent from `_track_ids` | `_track_ids` is every track in the tracks table, so a real track is present |
| Extra zero-value labels | Labels with no fragment contribute 0; harmless to totals and penalty; tests will catch anything real |
| Behavior drift | The existing suite is the gate; no dataset/schema change |

## 7. Milestones

- **M1** precompute the feature side + rewrite `_rebuild_join`; full suite green.
- **M2** measure + A/B vs `p6-joinrebuild-checkpoint`; docs and decision.

## 8. Decision and rollback

- **Adopt** if a rebuild is < 0.02 s and the cold simulate drops below 0.15 s, with the suite green.
- **Abandon** otherwise: `git checkout feature/p6-performance`; the spike lives only on
  `spike/join-rebuild`, and `git reset --hard p6-joinrebuild-checkpoint` restores the P6 head.

## 9. Log

- 2026-10-16: plan written; profiling done (section 1). Starting M1.
- 2026-10-16 M1: precomputed the feature side (`_track_ids`, sorted feature rows with each curve's
  table row and label code) and rewrote `_rebuild_join` as a `searchsorted` + vectorized expansion
  (no `np.unique`, no string sort). Full suite green.
  - Caution logged: a `git stash` during the first A/B silently reverted the working tree to the old
    code, producing a bogus "no difference" result. Redone after committing.
- 2026-10-16 M2 A/B vs `p6-joinrebuild-checkpoint` (same script and dataset):

  | Metric | Checkpoint | Spike | Speedup |
  | --- | ---: | ---: | ---: |
  | One join rebuild | 0.127 s | **0.0045 s** | **28×** |
  | Cold 30-y simulate (incl. join build) | 0.299 s | 0.129 s | 2.3× |
  | Warm 30-y simulate | 0.102 s | 0.096 s | ~1.1× (no rebuild) |
  | `account_values` / year | 2.55 ms | 2.41 ms | unchanged (not the target) |

  **Decision: adopt.** Both targets met (rebuild < 0.02 s; cold < 0.15 s) with the suite green. The
  gain is small on the warm path (which is the optimizer's case) and material on the cold path.
