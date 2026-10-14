# Notes

Working notes for WS4. Notes are living: update them in the same change set as the work they describe.

## Layout

- `adr/` — architecture decision records. One decision per file. Never rewrite an accepted ADR;
  supersede it with a new one.
- `design/` — scope, architecture, and focused design notes.
- `reports/` — phase close-out reports.

## Index

- `design/ws4-scope.md` — problem statement, users, scope, and success criteria.
- `design/ws4-architecture.md` — the architecture design.
- `adr/0001-fragment-compilation.md` — fragments are the compilation unit; blocks are a runtime aggregate.
- `adr/0002-columnar-matrix-dataset.md` — the compiled dataset is versioned and columnar.
- `adr/0003-spatial-structure-first-class.md` — spatial structure is part of the model.
- `adr/0004-goal-programming-metaheuristic.md` — optimization uses weighted goal programming with a parallel metaheuristic search.
- `adr/0005-annual-simulation-step.md` — the simulator steps annually; periods are reporting intervals.
- `adr/0006-xml-recipe-and-matrix-contract.md` — an XML recipe compiles a fragment inventory into the matrix contract.
