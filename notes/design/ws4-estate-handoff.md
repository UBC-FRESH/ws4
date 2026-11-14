# Process optimization estate handoff

Status: implemented (P196)
Phase: P196 (#1155)
Date: 2026-11-14
Related: `notes/design/ws4-process-optimization.md`,
`ws4/ecosystem/management.py`

## 1. Purpose

P195 returns the best process schedule. P196 writes that schedule and its block mapping in the
canonical estate input format, so the existing management loaders and a future estate run can
consume the result without a private translation.

The handoff is an export, not an estate simulation.

## 2. Contract

`ProcessOptimizationResult` now carries the block-to-fragment mapping used by the evaluation.
`write_estate_inputs` writes:

- `schedule.csv` with `block_id,treatment,offset`;
- `block_fragments.csv` with `block_id,fragment_id`;
- the P195 optimization artifact and `best_evaluation/`.

Rows are sorted by block, then offset/treatment or fragment. Headers are stable.

## 3. Validation

Block ids and fragment ids must be positive, and each mapped block needs at least one fragment.
Duplicate fragments are removed and sorted. An invalid mapping fails before any file is written.

## 4. Round-trip evidence

The 3 × 3 test optimization reaches `{1: (CC, 0)}`. Its handoff writes:

```text
block_id,treatment,offset
1,CC,0
```

and

```text
block_id,fragment_id
1,1
1,2
2,3
```

`load_schedule` returns the best candidate schedule, and `load_block_fragments` returns
`{1: (1, 2), 2: (3,)}` exactly.

## 5. Limits

- The export does not run the estate simulator or optimizer.
- The compiled management dataset remains authoritative.
- Treatment windows, roads, adjacency, and patch constraints are unchanged.
- The volume bridge and harvest semantics remain provisional.
