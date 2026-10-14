# Change Log

Newest entries last. Each milestone gets a dated entry that matches the roadmap status and the GitHub
issue comments.

## 2026-10-14

- Adopted the UBC-FRESH dev workflow in WS4: added `AGENTS.md`, `ROADMAP.md`, `CHANGE_LOG.md`, and the
  `notes/` tree. Phase 0 (Scope and design) is active on `feature/p0-scope-design`.
- P0.2: wrote the problem statement and scope in `notes/design/ws4-scope.md`.
- P0.3: recorded six architecture decisions in `notes/adr/0001` to `notes/adr/0006`.
- P0.4: wrote the architecture design in `notes/design/ws4-architecture.md`.
- P0.6: neutralized third-party naming in the skeleton. Renamed `ws4/io/patchworks_xml.py` to
  `ws4/io/forest_model_xml.py`, and reworded the CLI help, README, and docstrings to describe an
  "XML recipe" and a "launch control file". A repository-wide check for the old vocabulary is clean.
- P0.5: installed the UBC-FRESH dev workflow tooling. Added `scripts/check_workflow.py` and
  `scripts/dashboard.py`, the docs skeleton, the framework tests, the CI workflows, the issue
  templates, `requirements-dev.txt`, `.pre-commit-config.yaml`, and the recommended `LICENSE`,
  `CODE_OF_CONDUCT.md`, and `CITATION.cff`. Merged the tool configuration into `pyproject.toml` and
  fixed the skeleton to pass lint, format, and types.
  Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN` on all six gates (lint,
  format, types, tests, validator, docs).
- Opened the Phase 0 parent issue #1 and child issues #2 to #7.
