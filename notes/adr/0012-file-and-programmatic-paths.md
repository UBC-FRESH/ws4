# ADR 0012: Two model-construction paths, file-based and programmatic

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

WS3 has used the Woodstock input file format since 2015, and it remains the go-to format for WS3 models.
In practice, teams also build or patch a `ws3.forest.ForestModel` instance directly, when the file
format is clunky for something unusual or when the model must change programmatically at runtime after
ingestion. WS4 will face the same two needs: a shareable, reproducible file path, and a direct path for
the unusual case and for runtime updates.

## Decision

Provide two construction paths that meet at the same model. The file path compiles ForestModelXML plus a
fragments inventory into the compiled matrix. The programmatic path constructs or patches the model in
memory: add or replace a track, a treatment, a curve, a fragment, or a block; override a parameter; apply
a runtime update after ingestion. A programmatic model can be written to the matrix for a run, and a
matrix can be loaded into the model. Neither path is privileged.

## Consequences

- The common case and interoperability go through the file path; the unusual case and runtime changes go
  through the programmatic path.
- The in-memory model and the compiled matrix must stay isomorphic, so both paths produce the same state.
- The model API becomes a supported surface, with its own tests and documentation.
- A programmatic change made after ingestion must be recorded so a run stays reproducible.

## Alternatives considered

- **File path only.** Rejected: it cannot express an unusual model without a format hack, and it cannot
  change at runtime.
- **Programmatic path only.** Rejected: it loses shareability and reproducibility.
- **Two divergent models.** Rejected: the two paths must meet at one model, or results differ by path.
