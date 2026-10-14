# ADR 0011: Adopt the established ForestModelXML format and support legacy datasets

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

The lab already produces and consumes an established model format (ForestModelXML) and a compiled matrix
format, through the FEMIC exporter and a long-lived user base. Inventing a new recipe format would
discard that ecosystem and force every user to convert. ADR 0006 fixed that a recipe compiles into the
matrix contract but left the recipe's concrete format open.

## Decision

Adopt ForestModelXML as the recipe format, with the same structural validation the lab exporter
enforces. Make the compiler a matrix builder that consumes ForestModelXML plus a fragments inventory and
emits the compiled matrix. Support legacy datasets by ingesting an existing matrix directory, a blocks
shapefile, a topology table, and a road model directly. Reuse the lab exporter's format contract rather
than copying it.

## Consequences

- WS4 fits an existing ecosystem instead of asking users to convert.
- Legacy datasets become usable without a recompile.
- The format's semantics (IFM, ORIGIN, RETENTION) become first-class and must be documented and tested.
- WS4 inherits the format's constraints, including its expression language for account labels and its
  curve and attribute conventions.
- The prototype's minimal recipe format is superseded in P2.

## Alternatives considered

- **Invent a new recipe format.** Rejected: it discards the ecosystem and adds a conversion burden.
- **Compile only from the lab exporter's in-memory definitions.** Rejected: it would not read the files
  users already have.
- **Fork the exporter.** Rejected: two implementations of one format drift.
