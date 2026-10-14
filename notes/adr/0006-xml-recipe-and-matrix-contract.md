# ADR 0006: An XML recipe compiles a fragment inventory into the matrix contract

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

A management recipe describes tracks, treatments, curves, features, products, and destinations. It is
logical, not spatial: it does not know which fragments exist. The fragment inventory is spatial and
attribute-rich but says nothing about management logic. Compilation must marry the two, and the result
must be a stable contract that execution can rely on.

## Decision

Define the management recipe in XML and compile it against a fragment inventory into the columnar matrix
dataset. Compilation resolves, per fragment, the operable and eligible treatments and expands each track
into strata over offset age. The compiled matrix, with its manifest, is the only runtime contract; the
simulator and optimizer read it and never the raw inventory. The recipe and the inventory are
interchange inputs, not runtime inputs.

## Consequences

- Management logic and spatial data evolve independently; recompiling is cheap relative to re-solving.
- One recipe can be compiled against several inventories, and one inventory against several recipes.
- The recipe grammar and its validation become first-class and must be documented and tested.
- A change to the recipe or inventory requires a recompile before execution.

## Alternatives considered

- **Read the recipe and inventory directly at runtime.** Rejected: slow, repeated work, and it blurs the
  boundary between ingestion and execution.
- **Encode the recipe in code.** Rejected: analysts must be able to change the recipe without changing
  the package.
