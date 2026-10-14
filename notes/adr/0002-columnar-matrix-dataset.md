# ADR 0002: The compiled dataset is a versioned, columnar matrix

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

The compiled dataset is the boundary between ingestion and execution. It must be fast to read, easy to
inspect, stable across runs, and self-describing enough that a run can be reproduced and audited. It
also changes shape as the model evolves, so it needs a version.

## Decision

Represent the compiled dataset as a directory of columnar tables (Parquet/Arrow) plus a manifest. The
manifest records the schema version, the source identities and hashes, the compile options, and the
table list. A `validate` command checks a dataset against its manifest and against schema invariants.

## Consequences

- Reading and writing are fast and memory-friendly, and the tables interoperate with the Python data
  ecosystem.
- The dataset is inspectable without the model code.
- The manifest makes runs reproducible and lets validation fail loudly on a mismatch.
- A schema change requires a version bump and a migration or recompile path.

## Alternatives considered

- **A single serialized object (for example, a pickle).** Rejected: opaque, fragile across versions,
  and unsafe to load from untrusted sources.
- **A relational database.** Rejected for the first release: an extra dependency and operational
  burden for a dataset that is read whole.
- **Plain CSV.** Rejected as the runtime format: too slow and untyped, though CSV export remains a
  reporting feature.
