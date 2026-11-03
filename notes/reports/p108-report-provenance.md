# P108 Report provenance sidecars

Task: P108.1, issue #738. Parent phase: #734.
Branch: `feature/p108-report-provenance`.

## What changed

`write_report` now writes `report_provenance.json` beside the report tables. The sidecar
uses `ws4.report.provenance.v1` and records:

- the UTC generation time;
- the run identifier;
- the dataset identifier, schema version, source list, and manifest SHA-256 when the
  caller supplies the dataset;
- every report table the writer produced, with its byte count and SHA-256;
- every run-local source metadata file that exists (`dhi_metadata.json`,
  `structure_habitat_metadata.json`, `resilience_metadata.json`), with its byte count,
  SHA-256, and validity status;
- an explicit uncertainty status, `not_stated` unless a source metadata file carries an
  `uncertainty` or `uncertainty_status` field;
- warnings for missing report files and malformed source metadata.

The report CSV contents and model behaviour are unchanged. The report writer passes the
dataset identifier from the optimizer and exact lanes and the run identifier from the CLI.

`GET /api/runs/{run}/reports` keeps its existing `name` and `bytes` fields, adds the
recorded `sha256` where it has one, and exposes the decoded sidecar on the
`report_provenance.json` entry. The Reports tab shows a provenance badge with the
uncertainty status and links to the sidecar and source metadata files. The browser uses
text nodes and does not recompute a digest or a status.

## Verification

- `python -m pytest tests/test_report.py tests/test_web.py -q --no-cov`: 90 passed.
- `python scripts/dashboard.py`: `OVERALL: GREEN` on all seven gates (lint, format,
  types, tests, validator, docs, docstrings).

## Limits

- A digest detects change; it is not a signature, a timestamp authority, or a trust
  anchor.
- The sidecar hashes the report tables and the three run-local metadata files, not the
  whole dataset or the schedule.
- `not_stated` means the inputs carried no uncertainty metadata. It is not a claim that
  the model is free of uncertainty.
- The dataset identifier is available only when the caller supplies the dataset or a run
  record already names it.
