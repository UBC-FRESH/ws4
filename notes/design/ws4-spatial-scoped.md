# Adjacency-scoped spatial constraints (performance spike)

Status: **spike**. Branch `spike/incremental-spatial`, off P6 head `e9cba14`. Checkpoint tag
`p6-spatial-checkpoint` for one-command rollback.

Related: `notes/design/ws4-performance.md` (WP3/WP5), `notes/performance.md`.

## 1. Motivation and evidence

The plan item "incremental spatial" was framed as spatial *outputs*, but profiling shows the real cost
is the **optimizer's spatial penalty** — recomputed every objective evaluation:

| Path (C5) | Cost |
| --- | ---: |
| Optimizer `_spatial_penalty`, 300-block schedule | **166 ms / evaluation** |
| `write_patch_metrics` (spatial outputs) | ~0.03 s / year |

166 ms is `O(edges)` per evaluation: `opening_violations`, `core_area_penalty`, and
`green_up_violations` each scan all 68 586 topology edges regardless of how few blocks are scheduled.
For an objective that is otherwise ~7 ms (feature) or ~14 ms (route), this dominates.

## 2. Hypothesis

Only edges **incident to a disturbed block** can contribute to an opening, a perimeter, or a green-up
violation. Precomputing an adjacency index (`block -> incident edges`) once per optimizer lets an
evaluation scan ~`schedule x degree` edges (~2 500 for 300 blocks) instead of all 68 586 (~27x fewer).

## 3. Design

- `Optimizer._edges_by_block()`: build (and cache) `dict[int, list[edge]]` from the topology graph
  (`self._graph()`).
- `Optimizer._incident_edges(blocks)`: union of the incident edges of `blocks`, de-duplicated.
- `_spatial_penalty`: pass the incident edges of the harvested blocks to `spatial_penalty` and
  `core_area_penalty` instead of the full edge list. The constraint functions already ignore edges whose
  endpoints are not selected, so this is exact.
- The simulator's `write_patch_metrics` may reuse the same index later (out of scope if time is short).

## 4. Correctness plan

- The penalty value must be **identical** to the full-edge computation. A test compares
  `_spatial_penalty` with the incident-edge path against a direct full-edge `spatial_penalty` /
  `core_area_penalty` on the fixture for several schedules.
- The existing spatial tests (`test_constraints.py`, `test_optimizer.py`) stay green.

## 5. Targets

| Metric | Before | Target |
| --- | ---: | ---: |
| `_spatial_penalty`, 300-block C5 schedule | 166 ms | < 25 ms |

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| A missed edge changes a violation | Parity test vs the full-edge computation |
| Index build cost | Built once and cached, like `_spatial` / `_graph` |
| Memory | `dict[block, list[edge]]` over 68 586 edges (~few MB) |

## 7. Milestones

- **M1** adjacency index + incident-edge penalty; parity test; full suite green.
- **M2** A/B vs `p6-spatial-checkpoint`; docs and decision.

## 8. Decision and rollback

- **Adopt** if the penalty drops below 25 ms with identical values.
- **Abandon** otherwise: `git checkout feature/p6-performance`.

## 9. Log

- 2026-10-16: plan written; profiling done (section 1). Starting M1.
  - Note: the plan item was framed as spatial *outputs*, but profiling showed the optimizer's
    **spatial penalty** (166 ms/eval) was the real cost, so the scope was the penalty, not the outputs.
- 2026-10-16 M1: added `_edges_by_block` / `_incident_edges` and passed only incident edges (of the
  harvested blocks) to `spatial_penalty` and `core_area_penalty`; the constraint functions already
  ignore edges with no selected endpoint, so this is exact. Parity test vs the full-edge computation
  added; suite green.
- 2026-10-16 M2 A/B vs `p6-spatial-checkpoint` (C5, 300-block schedule; warm):

  | Metric | Checkpoint | Spike | Speedup |
  | --- | ---: | ---: | ---: |
  | `_spatial_penalty`, 300-block | 163.7 ms | **13.1 ms** | 12.5× |

  **Decision: adopt.** Target (< 25 ms) met with identical penalties and the suite green. The spatial
  outputs (`write_patch_metrics`, ~0.03 s/year) were left as-is: they are already cheap and are a
  one-time replay.
