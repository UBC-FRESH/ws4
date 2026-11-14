# P196 close-out: process optimization estate handoff

Date: 2026-11-14
Phase: P196 (#1155)
Branch: `feature/p196-estate-handoff`
Tasks: P196.1 (#1156), P196.2 (#1157), P196.3 (#1158)
Design note: `notes/design/ws4-estate-handoff.md`

## Result

The P195 best schedule can now be exported in the canonical estate input format and loaded
back by the existing management loaders. The export also carries the process optimization and
best-evaluation evidence.

## What changed

- `ProcessOptimizationResult` carries the block-to-fragment mapping.
- `write_estate_inputs` writes:
  - `schedule.csv` with `block_id,treatment,offset`;
  - `block_fragments.csv` with `block_id,fragment_id`;
  - the P195 search and best-evaluation artifacts.
- Mapping validation rejects non-positive blocks or fragments and empty fragment lists.
- Round-trip tests through `load_schedule` and `load_block_fragments`.

## Evidence

- Optimization tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Best schedule `{1: (CC, 0)}` exports as:
  - `1,CC,0`;
  - mapping rows `1,1`, `1,2`, and `2,3`.
- Both exported files round-trip exactly through the existing loaders.

## Boundary

- The export does not run the estate simulator or optimizer.
- The compiled management dataset remains authoritative.
- Treatment windows, roads, adjacency, and patch constraints are unchanged.
- The volume bridge and harvest semantics remain provisional.

## Next

Run the exported schedule through the estate simulator or optimizer as an explicit comparison
mode. The landscape-scale WS4-vs-LBSE comparison remains blocked without an R/SpaDES reference
run or published numeric landscape output.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
