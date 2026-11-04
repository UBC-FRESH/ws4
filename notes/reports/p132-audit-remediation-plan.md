# P132 audit remediation plan

Date: 2026-11-04
Parent: #809
Branch: `feature/p132-audit-remediation`

## Source audit

The adversarial self-audit found no Critical defect, four High-severity
correctness/reporting problems, nine Medium issues, and six Low issues. This
plan closes them in dependency order.

## P132.1 AU metadata integrity and TSA normalization

Findings: H1, M1, M2, H4 (validator side).

1. Add a canonical BEC alias map from `bec_official.csv` (`bgc_no_space` -> `bec`).
2. Normalize phase aliases before AU lookup.
3. Normalize `TSA-24`, `TSA 24`, and `24`.
4. Parse the AU label and compare:
   - BEC to `bec_zone + bec_subzone + bec_variant`
   - TSA to the plot `tsa` column when the label carries one
5. Define TSA-less semantics: aggregate the plot TSA values and require at least
   one supported pair, or document the no-TSA path.
6. Normalize `tsa_bec_counts.csv`; fix `ICHmw5` -> `ICHwm5`.
7. Mark subzone-level support rows and prevent them from masquerading as variant
   coverage.
8. Default `official_bec` and `retired_bec` to the packaged tables.
9. Tests: contradictory BEC, contradictory TSA, TSA-less, phase alias, alias
   support, missing mappings.

## P132.2 BEC crosswalk count and phase corrections

Findings: H2, H3, H4 (crosswalk side), L1, L5, L6.

1. Normalize phase aliases in both label sets.
2. Emit exactly one row per unique `(ws4_bec, cciss_bec)` relationship.
3. Remove parent summary rows.
4. When a parent has finer labels on the other side, use `ws4_finer` or
   `cciss_finer`; never `not_in_*`.
5. Add `covered_by_finer` to the official crosswalk.
6. State 229 rows / 213 unique labels / 16 phase rows everywhere.
7. Make note matching case-insensitive; reconcile `MHun` note/version.
8. Update tests, reports, changelog, and the old crosswalk documentation.

## P132.3 Assistant chip hardening

Findings: M3, M4, M9, L3.

1. `_chat_index`: decimal digits only, length cap, `try/except`.
2. Parse `WS4_ACTIONS:` case-insensitively, multiline/fenced, and repeatedly;
   strip every marker.
3. Cap chips at four after validation.
4. Send context as escaped JSON with an explicit untrusted-data guard.
5. Strip backticks and control characters; cap payload.
6. Add frontend interaction tests for workspace, subview, period, block, and
   `ask`.
7. Tests: 5000 digits, `²`, multiple markers, lowercase, multiline, >4 chips.

## P132.4 Evidence, process, and reproducibility

Findings: M5, M6, M7, M8, L2, L4.

1. Correct P121/P123 closeout contradictions and stale heads/CI runs.
2. Link #770-#773 under #769; update stale issue bodies.
3. Record PR #797 (shared-kernel) as a P123 traceability exception.
4. Add `bec_sources.json` with source URL, version, retrieval date, SHA-256, and
   transforms.
5. Add `scripts/check_bec_authority.py` to verify counts, aliases, and checksums.
6. Fix `docs/reference/sdmd.rst` provenance.
7. Add a workflow check for parent links and merged/not-merged report language.
8. Record `ws4` coverage explicitly; add a second coverage gate if practical.

## Verification

After each task:

```bash
python -m pytest tests/test_sdmd_bec.py tests/test_sdmd_au_integrity.py tests/test_sdmd_api.py -q
python -m pytest tests/test_web.py -q
python scripts/dashboard.py
```

The phase is complete only when every finding has a code, data, test, report, or
process closure and the dashboard is green.
