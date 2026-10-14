# ADR 0001: Fragments are the compilation unit; blocks are a runtime aggregate

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

A landscape inventory can be compiled at the level of the smallest spatial unit (a fragment, for
example a stand polygon) or at the level of the operational unit (a block, an aggregate of fragments).
The operational unit is what analysts schedule and what road access and adjacency usually apply to, but
it is also an aggregation choice that can change between runs. Compiling at the operational level would
bake that choice into the dataset and force a recompile whenever the block layout changes.

## Decision

Compile at the fragment level. A block is a runtime view: its area, product, and feature attributes are
computed by summing its constituent fragments. A block's operability is the intersection of its
fragments' operability, so a block with mixed fragments has a narrowed or empty operation set.

## Consequences

- One compiled dataset serves many block layouts, including alternate block definitions.
- Block-level attributes are always consistent with their fragments, because they are derived.
- The runtime must aggregate fragments to blocks each step, which is a cost to manage (see the open
  questions in the architecture note).
- Operability is naturally conservative: a block is only operable for a treatment if every fragment is.

## Alternatives considered

- **Compile at the block level.** Rejected: it fixes the block layout, duplicates data, and makes
  alternate aggregations expensive.
- **Compile at both levels and keep them in sync.** Rejected: two sources of truth invite drift.
